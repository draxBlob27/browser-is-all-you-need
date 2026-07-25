"""Create and verify the fixed-26 crypto-square clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b008-crypto-square.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b008-crypto-square"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_csquare_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_csquare_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b008-crypto-square"
FAMILY_ID = "aider-fixed26-csquare-analogs-v1"
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
        "f26csq-harbor-manifest-columns",
        "f26csq-apiary-frame-columns",
        "f26csq-loom-shuttle-weave",
        "f26csq-clocktower-dial-spiral",
        "f26csq-blueprint-strip-bands",
        "f26csq-carousel-ticket-runs",
        "f26csq-theater-seat-chart",
        "f26csq-bulletin-notice-grid",
        "f26csq-tilefloor-grid-estimator",
        "f26csq-turnstile-rotation-grid",
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
            "f26csq-harbor-manifest-columns",
            "Harbor manifest columns",
            "harbor_manifest",
            """
            class ManifestError : public std::invalid_argument {
            public:
                explicit ManifestError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ManifestColumns {
            public:
                explicit ManifestColumns(const std::string& raw);
                std::string normalized() const;
                std::size_t columns() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string column(std::size_t index) const;
                std::string encoded() const;
            };
            """,
            """
            class ManifestError : public std::invalid_argument {
            public:
                explicit ManifestError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ManifestColumns {
            public:
                explicit ManifestColumns(const std::string& raw);
                std::string normalized() const;
                std::size_t columns() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string column(std::size_t index) const;
                std::string encoded() const;
            private:
                std::string normalized_;
            };
            """,
            """
            ManifestColumns::ManifestColumns(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ManifestColumns::normalized() const { return normalized_; }
            std::size_t ManifestColumns::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 4) return 2;
                if (n <= 9) return 3;
                if (n <= 16) return 4;
                if (n <= 25) return 5;
                return 6;
            }
            std::size_t ManifestColumns::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t cols = columns();
                return (n + cols - 1) / cols;
            }
            std::vector<std::string> ManifestColumns::grid() const {
                std::vector<std::string> lines;
                const std::size_t cols = columns();
                if (cols == 0) return lines;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    lines.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return lines;
            }
            std::string ManifestColumns::column(std::size_t index) const {
                if (index >= columns()) throw ManifestError("column index out of range");
                std::string result;
                for (const std::string& line : grid())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string ManifestColumns::encoded() const {
                const std::vector<std::string> lines = grid();
                if (lines.empty()) return "";
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t c = 0; c < cols; ++c) {
                    if (c != 0) result += ' ';
                    for (std::size_t r = 0; r < lines.size(); ++r)
                        result += (c < lines[r].size()) ? lines[r][c] : '.';
                }
                return result;
            }
            """,
            """
            ManifestColumns::ManifestColumns(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ManifestColumns::normalized() const { return normalized_; }
            std::size_t ManifestColumns::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 4) return 2;
                if (n <= 9) return 3;
                if (n <= 16) return 4;
                if (n <= 25) return 5;
                return 6;
            }
            std::size_t ManifestColumns::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t cols = columns();
                return (n + cols - 1) / cols;
            }
            std::vector<std::string> ManifestColumns::grid() const {
                std::vector<std::string> lines;
                const std::size_t cols = columns();
                if (cols == 0) return lines;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    lines.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return lines;
            }
            std::string ManifestColumns::column(std::size_t index) const {
                if (index >= columns()) throw ManifestError("column index out of range");
                std::string result;
                for (const std::string& line : grid())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string ManifestColumns::encoded() const {
                const std::vector<std::string> lines = grid();
                std::string result;
                for (std::size_t r = 0; r < lines.size(); ++r) {
                    if (r != 0) result += ' ';
                    result += lines[r];
                }
                return result;
            }
            """,
            """
            ManifestColumns m("Cranes load cargo at dawn!");
            if (m.normalized() != "cranesloadcargoatdawn") return 1;
            if (m.columns() != 5U) return 2;
            if (m.rows() != 5U) return 3;
            if (m.grid() != std::vector<std::string>{"crane", "sload", "cargo", "atdaw", "n"}) return 4;
            if (m.encoded() != "cscan rlat. aord. naga. edow.") return 5;
            ManifestColumns empty("! ?");
            if (!empty.normalized().empty()) return 6;
            if (!empty.grid().empty()) return 7;
            if (empty.encoded() != "") return 8;
            ManifestColumns one("Q!");
            if (one.columns() != 2U) return 9;
            if (one.encoded() != "q .") return 10;
            return 0;
            """,
            """
            ManifestColumns b4("abcd");
            if (b4.columns() != 2U) return 1;
            ManifestColumns b5("abcde");
            if (b5.columns() != 3U) return 2;
            ManifestColumns b9("abcdefghi");
            if (b9.columns() != 3U) return 3;
            ManifestColumns b10("abcdefghij");
            if (b10.columns() != 4U) return 4;
            ManifestColumns b16("abcdefghijklmnop");
            if (b16.columns() != 4U) return 5;
            ManifestColumns b17("abcdefghijklmnopq");
            if (b17.columns() != 5U) return 6;
            ManifestColumns b25(std::string(25, 'a'));
            if (b25.columns() != 5U) return 7;
            ManifestColumns b26(std::string(26, 'a'));
            if (b26.columns() != 6U) return 8;
            ManifestColumns m("Dock seven barges, mate!");
            if (m.column(0) != "deam") return 9;
            if (m.column(4) != "sbs") return 10;
            bool threw = false;
            try { m.column(5); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 11;
            if (m.encoded() != "deam ovra cegt knee sbs.") return 12;
            ManifestColumns p("A,b!");
            if (p.normalized() != "ab") return 13;
            if (p.encoded() != "a b") return 14;
            return 0;
            """,
            "band-lookup grid dimensions with ragged rows and dot-padded down-column chunk emission",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and row-major emission",
            "band boundaries at lengths 4/5, 9/10, 16/17, and 25/26, ragged-row column padding, empty and single-character inputs, and index rejection",
            "down-column block reading with exact grouped output and a typed error in a paired .h/.cpp API",
            "down-column block reader",
            project_support=True,
        ),
        c(
            "f26csq-orchard-crate-stencil",
            "Orchard crate stencil",
            "orchard_stencil",
            """
            class StencilError : public std::invalid_argument {
            public:
                explicit StencilError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CrateStencil {
            public:
                CrateStencil(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string stencil() const;
            };
            """,
            """
            class StencilError : public std::invalid_argument {
            public:
                explicit StencilError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CrateStencil {
            public:
                CrateStencil(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string stencil() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            CrateStencil::CrateStencil(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 26) throw StencilError("width outside 1..26");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string CrateStencil::normalized() const { return normalized_; }
            std::size_t CrateStencil::width() const { return width_; }
            std::size_t CrateStencil::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> CrateStencil::lines() const {
                std::vector<std::string> rows_out;
                if (normalized_.empty()) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    rows_out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return rows_out;
            }
            std::string CrateStencil::line(std::size_t index) const {
                const std::vector<std::string> rows_out = lines();
                if (index >= rows_out.size()) throw StencilError("line index out of range");
                return rows_out[index];
            }
            std::string CrateStencil::stencil() const {
                const std::vector<std::string> rows_out = lines();
                if (rows_out.empty()) return "";
                std::string result;
                for (std::size_t c = 0; c < width_; ++c) {
                    if (c != 0) result += '/';
                    for (std::size_t r = 0; r < rows_out.size(); ++r)
                        result += (c < rows_out[r].size()) ? rows_out[r][c] : '*';
                }
                return result;
            }
            """,
            """
            CrateStencil::CrateStencil(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 26) throw StencilError("width outside 1..26");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string CrateStencil::normalized() const { return normalized_; }
            std::size_t CrateStencil::width() const { return width_; }
            std::size_t CrateStencil::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> CrateStencil::lines() const {
                std::vector<std::string> rows_out;
                if (normalized_.empty()) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    rows_out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return rows_out;
            }
            std::string CrateStencil::line(std::size_t index) const {
                const std::vector<std::string> rows_out = lines();
                if (index >= rows_out.size()) throw StencilError("line index out of range");
                return rows_out[index];
            }
            std::string CrateStencil::stencil() const {
                const std::vector<std::string> rows_out = lines();
                std::string result;
                for (std::size_t r = 0; r < rows_out.size(); ++r) {
                    if (r != 0) result += '/';
                    result += rows_out[r];
                }
                return result;
            }
            """,
            """
            CrateStencil c("Ripe plums, tart cherries!", 4);
            if (c.normalized() != "RIPEPLUMSTARTCHERRIES") return 1;
            if (c.width() != 4U) return 2;
            if (c.rows() != 6U) return 3;
            if (c.lines() != std::vector<std::string>{"RIPE", "PLUM", "STAR", "TCHE", "RRIE", "S"}) return 4;
            if (c.stencil() != "RPSTRS/ILTCR*/PUAHI*/EMREE*") return 5;
            CrateStencil exact("abcd12ef", 2);
            if (exact.normalized() != "ABCDEF") return 6;
            if (exact.stencil() != "ACE/BDF") return 7;
            CrateStencil empty("!!", 3);
            if (empty.rows() != 0U) return 8;
            if (empty.stencil() != "") return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { CrateStencil bad("abc", 0); } catch (const StencilError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { CrateStencil bad("abc", 27); } catch (const StencilError&) { threw = true; }
            if (!threw) return 2;
            CrateStencil c("Golden delicious 88", 3);
            if (c.normalized() != "GOLDENDELICIOUS") return 3;
            if (c.line(2) != "DEL") return 4;
            threw = false;
            try { c.line(5); } catch (const StencilError&) { threw = true; }
            if (!threw) return 5;
            if (c.stencil() != "GDDIO/OEECU/LNLIS") return 6;
            CrateStencil one("z", 5);
            if (one.rows() != 1U) return 7;
            if (one.stencil() != "Z/*/*/*/*") return 8;
            CrateStencil fold("Mixed Case", 4);
            if (fold.normalized() != "MIXEDCASE") return 9;
            return 0;
            """,
            "caller-validated width with star-padded down-column emission joined by slashes",
            "regex engines or third-party text-grid libraries and row-major emission",
            "width validation at 0 and 27, ragged star padding, letter-only filtering, exact-fit widths, and index rejection",
            "validated constructor arguments plus delimiter-joined chunks in a paired .h/.cpp API",
            "down-column block reader",
        ),
        c(
            "f26csq-kilnyard-tile-columns",
            "Kilnyard tile columns",
            "kiln_tiles",
            """
            class TileError : public std::invalid_argument {
            public:
                explicit TileError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TileColumns {
            public:
                TileColumns(const std::string& raw, std::size_t height);
                std::string normalized() const;
                std::size_t height() const;
                std::size_t columns() const;
                std::vector<std::string> rows() const;
                std::string row(std::size_t index) const;
                std::string fused() const;
            };
            """,
            """
            class TileError : public std::invalid_argument {
            public:
                explicit TileError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TileColumns {
            public:
                TileColumns(const std::string& raw, std::size_t height);
                std::string normalized() const;
                std::size_t height() const;
                std::size_t columns() const;
                std::vector<std::string> rows() const;
                std::string row(std::size_t index) const;
                std::string fused() const;
            private:
                std::string normalized_;
                std::size_t height_;
            };
            """,
            """
            TileColumns::TileColumns(const std::string& raw, std::size_t height) : height_(height) {
                if (height == 0 || height > 13) throw TileError("height outside 1..13");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string TileColumns::normalized() const { return normalized_; }
            std::size_t TileColumns::height() const { return height_; }
            std::size_t TileColumns::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + height_ - 1) / height_;
            }
            std::vector<std::string> TileColumns::rows() const {
                std::vector<std::string> grid_rows;
                const std::size_t cols = columns();
                if (cols == 0) return grid_rows;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    grid_rows.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return grid_rows;
            }
            std::string TileColumns::row(std::size_t index) const {
                const std::vector<std::string> grid_rows = rows();
                if (index >= grid_rows.size()) throw TileError("row index out of range");
                return grid_rows[index];
            }
            std::string TileColumns::fused() const {
                const std::vector<std::string> grid_rows = rows();
                if (grid_rows.empty()) return "";
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t c = 0; c < cols; ++c) {
                    if (c != 0) result += '-';
                    for (std::size_t r = 0; r < grid_rows.size(); ++r)
                        result += (c < grid_rows[r].size()) ? grid_rows[r][c] : '#';
                }
                return result;
            }
            """,
            """
            TileColumns::TileColumns(const std::string& raw, std::size_t height) : height_(height) {
                if (height == 0 || height > 13) throw TileError("height outside 1..13");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string TileColumns::normalized() const { return normalized_; }
            std::size_t TileColumns::height() const { return height_; }
            std::size_t TileColumns::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + height_ - 1) / height_;
            }
            std::vector<std::string> TileColumns::rows() const {
                std::vector<std::string> grid_rows;
                const std::size_t cols = columns();
                if (cols == 0) return grid_rows;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    grid_rows.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return grid_rows;
            }
            std::string TileColumns::row(std::size_t index) const {
                const std::vector<std::string> grid_rows = rows();
                if (index >= grid_rows.size()) throw TileError("row index out of range");
                return grid_rows[index];
            }
            std::string TileColumns::fused() const {
                const std::vector<std::string> grid_rows = rows();
                std::string result;
                for (std::size_t r = 0; r < grid_rows.size(); ++r) {
                    if (r != 0) result += '-';
                    result += grid_rows[r];
                }
                return result;
            }
            """,
            """
            TileColumns t("Glaze fires at cone six", 4);
            if (t.normalized() != "glazefiresatconesix") return 1;
            if (t.height() != 4U) return 2;
            if (t.columns() != 5U) return 3;
            if (t.rows() != std::vector<std::string>{"glaze", "fires", "atcon", "esix"}) return 4;
            if (t.fused() != "gfae-lits-arci-zeox-esn#") return 5;
            TileColumns exact("a1b2c3d4", 2);
            if (exact.fused() != "ac-13-bd-24") return 6;
            TileColumns empty("--", 3);
            if (empty.columns() != 0U) return 7;
            if (empty.fused() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { TileColumns bad("abc", 0); } catch (const TileError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TileColumns bad("abc", 14); } catch (const TileError&) { threw = true; }
            if (!threw) return 2;
            TileColumns t("Kiln shelf 7 stack 2", 3);
            if (t.normalized() != "kilnshelf7stack2") return 3;
            if (t.row(1) != "elf7st") return 4;
            threw = false;
            try { t.row(3); } catch (const TileError&) { threw = true; }
            if (!threw) return 5;
            if (t.fused() != "kea-ilc-lfk-n72-ss#-ht#") return 6;
            TileColumns one("Q", 5);
            if (one.columns() != 1U) return 7;
            if (one.fused() != "q") return 8;
            return 0;
            """,
            "caller-validated height driving the column count with hash-padded down-column emission",
            "regex engines or third-party text-grid libraries and row-major emission",
            "height validation at 0 and 14, ceiling column counts, hash padding, exact-fit heights, and index rejection",
            "height-driven dimensions distinct from width-driven siblings in a paired .h/.cpp API",
            "down-column block reader",
        ),
        c(
            "f26csq-observatory-log-blocks",
            "Observatory log blocks",
            "observatory_log",
            """
            class LogError : public std::domain_error {
            public:
                explicit LogError(const std::string& message) : std::domain_error(message) {}
            };
            class LogBlocks {
            public:
                explicit LogBlocks(const std::string& raw);
                std::string normalized() const;
                std::size_t columns() const;
                std::size_t rows() const;
                std::vector<std::string> blocks() const;
                std::string block(std::size_t index) const;
                std::string transcript() const;
            };
            """,
            """
            class LogError : public std::domain_error {
            public:
                explicit LogError(const std::string& message) : std::domain_error(message) {}
            };
            class LogBlocks {
            public:
                explicit LogBlocks(const std::string& raw);
                std::string normalized() const;
                std::size_t columns() const;
                std::size_t rows() const;
                std::vector<std::string> blocks() const;
                std::string block(std::size_t index) const;
                std::string transcript() const;
            private:
                std::string normalized_;
            };
            """,
            """
            LogBlocks::LogBlocks(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string LogBlocks::normalized() const { return normalized_; }
            std::size_t LogBlocks::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 3;
                while (w * (w + 1) < n) ++w;
                return w;
            }
            std::size_t LogBlocks::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t cols = columns();
                return (n + cols - 1) / cols;
            }
            std::vector<std::string> LogBlocks::blocks() const {
                std::vector<std::string> rows_out;
                const std::size_t cols = columns();
                if (cols == 0) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    rows_out.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return rows_out;
            }
            std::string LogBlocks::block(std::size_t index) const {
                if (index >= columns()) throw LogError("block index out of range");
                std::string result;
                for (const std::string& line : blocks())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string LogBlocks::transcript() const {
                const std::vector<std::string> rows_out = blocks();
                if (rows_out.empty()) return "";
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t c = 0; c < cols; ++c) {
                    if (c != 0) result += " | ";
                    for (std::size_t r = 0; r < rows_out.size(); ++r)
                        result += (c < rows_out[r].size()) ? rows_out[r][c] : '~';
                }
                return result;
            }
            """,
            """
            LogBlocks::LogBlocks(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string LogBlocks::normalized() const { return normalized_; }
            std::size_t LogBlocks::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 3;
                while (w * (w + 1) < n) ++w;
                return w;
            }
            std::size_t LogBlocks::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t cols = columns();
                return (n + cols - 1) / cols;
            }
            std::vector<std::string> LogBlocks::blocks() const {
                std::vector<std::string> rows_out;
                const std::size_t cols = columns();
                if (cols == 0) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    rows_out.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return rows_out;
            }
            std::string LogBlocks::block(std::size_t index) const {
                if (index >= columns()) throw LogError("block index out of range");
                std::string result;
                for (const std::string& line : blocks())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string LogBlocks::transcript() const {
                const std::vector<std::string> rows_out = blocks();
                std::string result;
                for (std::size_t r = 0; r < rows_out.size(); ++r) {
                    if (r != 0) result += " | ";
                    result += rows_out[r];
                }
                return result;
            }
            """,
            """
            LogBlocks b("Comet trails brighten near perihelion");
            if (b.normalized() != "comettrailsbrightennearperihelion") return 1;
            if (b.columns() != 6U) return 2;
            if (b.rows() != 6U) return 3;
            if (b.blocks() != std::vector<std::string>{"comett", "railsb", "righte", "nnearp", "erihel", "ion"}) return 4;
            if (b.transcript() != "crrnei | oainro | migein | elhah~ | tstre~ | tbepl~") return 5;
            LogBlocks small("Star 9 light");
            if (small.columns() != 3U) return 6;
            if (small.rows() != 3U) return 7;
            if (small.transcript() != "srg | tlh | ait") return 8;
            LogBlocks empty("123 !!!");
            if (empty.columns() != 0U) return 9;
            if (empty.transcript() != "") return 10;
            return 0;
            """,
            """
            LogBlocks n12(std::string(12, 'a'));
            if (n12.columns() != 3U) return 1;
            LogBlocks n13(std::string(13, 'a'));
            if (n13.columns() != 4U) return 2;
            LogBlocks n20(std::string(20, 'a'));
            if (n20.columns() != 4U) return 3;
            LogBlocks n21(std::string(21, 'a'));
            if (n21.columns() != 5U) return 4;
            LogBlocks n30(std::string(30, 'a'));
            if (n30.columns() != 5U) return 5;
            LogBlocks n31(std::string(31, 'a'));
            if (n31.columns() != 6U) return 6;
            LogBlocks b("Nebula drifts, faint");
            if (b.normalized() != "nebuladriftsfaint") return 7;
            if (b.block(0) != "nlift") return 8;
            if (b.block(3) != "ursn") return 9;
            bool threw = false;
            try { b.block(4); } catch (const LogError&) { threw = true; }
            if (!threw) return 10;
            if (b.transcript() != "nlift | eafa~ | bdti~ | ursn~") return 11;
            return 0;
            """,
            "growth-rule dimensions with tilde-padded down-column emission and a wide delimiter",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and row-major emission",
            "growth-rule boundaries where w*(w+1) crosses the length, tilde padding on ragged rows, letter-only filtering, and index rejection",
            "growth-rule dimension selection with a multi-character delimiter in a paired .h/.cpp API",
            "down-column block reader",
        ),
        c(
            "f26csq-railcar-seal-grid",
            "Railcar seal grid",
            "railcar_seal",
            """
            class SealError : public std::invalid_argument {
            public:
                explicit SealError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SealGrid {
            public:
                SealGrid(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> grid() const;
                std::string sealed() const;
            };
            """,
            """
            class SealError : public std::invalid_argument {
            public:
                explicit SealError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SealGrid {
            public:
                SealGrid(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> grid() const;
                std::string sealed() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            SealGrid::SealGrid(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 40) throw SealError("width outside 1..40");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string SealGrid::normalized() const { return normalized_; }
            std::size_t SealGrid::width() const { return width_; }
            std::size_t SealGrid::height() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> SealGrid::grid() const {
                std::vector<std::string> rows_out;
                if (normalized_.empty()) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    rows_out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return rows_out;
            }
            std::string SealGrid::sealed() const {
                const std::vector<std::string> rows_out = grid();
                if (rows_out.empty()) return "";
                std::string result;
                for (std::size_t c = 0; c < width_; ++c) {
                    if (c != 0) result += ' ';
                    for (std::size_t step = 0; step < rows_out.size(); ++step) {
                        const std::size_t r = rows_out.size() - 1 - step;
                        result += (c < rows_out[r].size()) ? rows_out[r][c] : '=';
                    }
                }
                return result;
            }
            """,
            """
            SealGrid::SealGrid(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 40) throw SealError("width outside 1..40");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string SealGrid::normalized() const { return normalized_; }
            std::size_t SealGrid::width() const { return width_; }
            std::size_t SealGrid::height() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> SealGrid::grid() const {
                std::vector<std::string> rows_out;
                if (normalized_.empty()) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    rows_out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return rows_out;
            }
            std::string SealGrid::sealed() const {
                const std::vector<std::string> rows_out = grid();
                std::string result;
                for (std::size_t r = 0; r < rows_out.size(); ++r) {
                    if (r != 0) result += ' ';
                    result += rows_out[r];
                }
                return result;
            }
            """,
            """
            SealGrid g("Manifest seven railcars", 4);
            if (g.normalized() != "MANIFESTSEVENRAILCARS") return 1;
            if (g.width() != 4U) return 2;
            if (g.height() != 6U) return 3;
            if (g.grid() != std::vector<std::string>{"MANI", "FEST", "SEVE", "NRAI", "LCAR", "S"}) return 4;
            if (g.sealed() != "SLNSFM =CREEA =AAVSN =RIETI") return 5;
            SealGrid exact("a1b2c3", 3);
            if (exact.sealed() != "2A C1 3B") return 6;
            SealGrid empty("--", 2);
            if (empty.height() != 0U) return 7;
            if (empty.sealed() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { SealGrid bad("abc", 0); } catch (const SealError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SealGrid bad("abc", 41); } catch (const SealError&) { threw = true; }
            if (!threw) return 2;
            SealGrid g("Boxcar 55 loaded", 3);
            if (g.normalized() != "BOXCAR55LOADED") return 3;
            if (g.sealed() != "EO5CB DA5AO =DLRX") return 4;
            SealGrid one("q7", 5);
            if (one.height() != 1U) return 5;
            if (one.sealed() != "Q 7 = = =") return 6;
            return 0;
            """,
            "bottom-up column traversal with equals padding for missing cells",
            "regex engines or third-party text-grid libraries and row-major or top-down emission",
            "bottom-up read order, padding placement on ragged rows, width validation at 0 and 41, and empty inputs",
            "reversed traversal direction as the rejection discriminator in a paired .h/.cpp API",
            "down-column block reader",
        ),
        c(
            "f26csq-apiary-frame-columns",
            "Apiary frame columns",
            "apiary_frames",
            """
            class FrameError : public std::domain_error {
            public:
                explicit FrameError(const std::string& message) : std::domain_error(message) {}
            };
            class FrameColumns {
            public:
                explicit FrameColumns(const std::string& raw);
                std::string normalized() const;
                std::string padded() const;
                std::size_t rows() const;
                std::vector<std::string> cells() const;
                std::string column(std::size_t index) const;
                std::string stamped() const;
            };
            """,
            """
            class FrameError : public std::domain_error {
            public:
                explicit FrameError(const std::string& message) : std::domain_error(message) {}
            };
            class FrameColumns {
            public:
                explicit FrameColumns(const std::string& raw);
                std::string normalized() const;
                std::string padded() const;
                std::size_t rows() const;
                std::vector<std::string> cells() const;
                std::string column(std::size_t index) const;
                std::string stamped() const;
            private:
                std::string normalized_;
            };
            """,
            """
            FrameColumns::FrameColumns(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string FrameColumns::normalized() const { return normalized_; }
            std::string FrameColumns::padded() const {
                if (normalized_.empty()) return "";
                std::string out = normalized_;
                while (out.size() % 5 != 0) out += '_';
                return out;
            }
            std::size_t FrameColumns::rows() const { return padded().size() / 5; }
            std::vector<std::string> FrameColumns::cells() const {
                std::vector<std::string> grid_rows;
                const std::string filled = padded();
                for (std::size_t start = 0; start < filled.size(); start += 5)
                    grid_rows.push_back(filled.substr(start, 5));
                return grid_rows;
            }
            std::string FrameColumns::column(std::size_t index) const {
                if (index >= 5) throw FrameError("column index out of range");
                std::string result;
                for (const std::string& line : cells()) result += line[index];
                return result;
            }
            std::string FrameColumns::stamped() const {
                const std::vector<std::string> grid_rows = cells();
                if (grid_rows.empty()) return "";
                std::string result;
                for (std::size_t c = 0; c < 5; ++c) {
                    if (c != 0) result += '|';
                    for (const std::string& line : grid_rows) result += line[c];
                }
                return result;
            }
            """,
            """
            FrameColumns::FrameColumns(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string FrameColumns::normalized() const { return normalized_; }
            std::string FrameColumns::padded() const {
                if (normalized_.empty()) return "";
                std::string out = normalized_;
                while (out.size() % 5 != 0) out += '_';
                return out;
            }
            std::size_t FrameColumns::rows() const { return padded().size() / 5; }
            std::vector<std::string> FrameColumns::cells() const {
                std::vector<std::string> grid_rows;
                const std::string filled = padded();
                for (std::size_t start = 0; start < filled.size(); start += 5)
                    grid_rows.push_back(filled.substr(start, 5));
                return grid_rows;
            }
            std::string FrameColumns::column(std::size_t index) const {
                if (index >= 5) throw FrameError("column index out of range");
                std::string result;
                for (const std::string& line : cells()) result += line[index];
                return result;
            }
            std::string FrameColumns::stamped() const {
                const std::vector<std::string> grid_rows = cells();
                std::string result;
                for (std::size_t r = 0; r < grid_rows.size(); ++r) {
                    if (r != 0) result += '|';
                    result += grid_rows[r];
                }
                return result;
            }
            """,
            """
            FrameColumns f("Honey frames feed nine hives");
            if (f.normalized() != "honeyframesfeedninehives") return 1;
            if (f.padded() != "honeyframesfeedninehives_") return 2;
            if (f.rows() != 5U) return 3;
            if (f.cells() != std::vector<std::string>{"honey", "frame", "sfeed", "nineh", "ives_"}) return 4;
            if (f.stamped() != "hfsni|orfiv|naene|emees|yedh_") return 5;
            FrameColumns exact("abcde");
            if (exact.padded() != "abcde") return 6;
            if (exact.stamped() != "a|b|c|d|e") return 7;
            FrameColumns empty("--");
            if (empty.rows() != 0U) return 8;
            if (empty.stamped() != "") return 9;
            return 0;
            """,
            """
            FrameColumns one("B7");
            if (one.padded() != "b7___") return 1;
            if (one.rows() != 1U) return 2;
            if (one.stamped() != "b|7|_|_|_") return 3;
            FrameColumns f("Wax comb 24 cells");
            if (f.normalized() != "waxcomb24cells") return 4;
            if (f.column(0) != "wme") return 5;
            if (f.column(4) != "oc_") return 6;
            bool threw = false;
            try { f.column(5); } catch (const FrameError&) { threw = true; }
            if (!threw) return 7;
            if (f.stamped() != "wme|abl|x2l|c4s|oc_") return 8;
            FrameColumns four("hive");
            if (four.padded() != "hive_") return 9;
            return 0;
            """,
            "pad-to-multiple exact-rectangle dimensions with underscore fill and pipe-joined columns",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and row-major emission",
            "exact multiples, one-over-multiple underscore padding, full-height columns, index rejection, and empty inputs",
            "exact-rectangle padding policy distinct from ragged siblings in a paired .h/.cpp API",
            "down-column block reader",
            project_support=True,
        ),
        c(
            "f26csq-granary-bin-blocks",
            "Granary bin blocks",
            "granary_bins",
            """
            class BinError : public std::invalid_argument {
            public:
                explicit BinError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BinBlocks {
            public:
                BinBlocks(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> bins() const;
                std::string bin(std::size_t index) const;
                std::string poured() const;
            };
            """,
            """
            class BinError : public std::invalid_argument {
            public:
                explicit BinError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BinBlocks {
            public:
                BinBlocks(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> bins() const;
                std::string bin(std::size_t index) const;
                std::string poured() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            BinBlocks::BinBlocks(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 32) throw BinError("width outside 1..32");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += '?';
                }
            }
            std::string BinBlocks::normalized() const { return normalized_; }
            std::size_t BinBlocks::width() const { return width_; }
            std::size_t BinBlocks::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> BinBlocks::bins() const {
                std::vector<std::string> rows_out;
                if (normalized_.empty()) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    rows_out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return rows_out;
            }
            std::string BinBlocks::bin(std::size_t index) const {
                if (index >= width_) throw BinError("bin index out of range");
                std::string result;
                for (const std::string& line : bins())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string BinBlocks::poured() const {
                const std::vector<std::string> rows_out = bins();
                if (rows_out.empty()) return "";
                std::string result;
                for (std::size_t c = 0; c < width_; ++c) {
                    if (c != 0) result += ';';
                    for (std::size_t r = 0; r < rows_out.size(); ++r)
                        result += (c < rows_out[r].size()) ? rows_out[r][c] : '.';
                }
                return result;
            }
            """,
            """
            BinBlocks::BinBlocks(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 32) throw BinError("width outside 1..32");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += '?';
                }
            }
            std::string BinBlocks::normalized() const { return normalized_; }
            std::size_t BinBlocks::width() const { return width_; }
            std::size_t BinBlocks::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> BinBlocks::bins() const {
                std::vector<std::string> rows_out;
                if (normalized_.empty()) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    rows_out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return rows_out;
            }
            std::string BinBlocks::bin(std::size_t index) const {
                if (index >= width_) throw BinError("bin index out of range");
                std::string result;
                for (const std::string& line : bins())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string BinBlocks::poured() const {
                const std::vector<std::string> rows_out = bins();
                std::string result;
                for (std::size_t r = 0; r < rows_out.size(); ++r) {
                    if (r != 0) result += ';';
                    result += rows_out[r];
                }
                return result;
            }
            """,
            """
            BinBlocks b("Wheat 100 tons, rye 25", 4);
            if (b.normalized() != "wheat???tonsrye??") return 1;
            if (b.width() != 4U) return 2;
            if (b.rows() != 5U) return 3;
            if (b.bins() != std::vector<std::string>{"whea", "t???", "tons", "rye?", "?"}) return 4;
            if (b.poured() != "wttr?;h?oy.;e?ne.;a?s?.") return 5;
            BinBlocks exact("oats66", 3);
            if (exact.poured() != "os;a?;t?") return 6;
            BinBlocks empty("---", 2);
            if (empty.rows() != 0U) return 7;
            if (empty.poured() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { BinBlocks bad("abc", 0); } catch (const BinError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BinBlocks bad("abc", 33); } catch (const BinError&) { threw = true; }
            if (!threw) return 2;
            BinBlocks b("Corn 9 barley 8", 3);
            if (b.normalized() != "corn?barley?") return 3;
            if (b.bin(0) != "cnae") return 4;
            if (b.bin(2) != "rbl?") return 5;
            threw = false;
            try { b.bin(3); } catch (const BinError&) { threw = true; }
            if (!threw) return 6;
            if (b.poured() != "cnae;o?ry;rbl?") return 7;
            BinBlocks one("5a", 4);
            if (one.poured() != "?;a;.;.") return 8;
            return 0;
            """,
            "digit-mapping normalization with semicolon-joined down-column chunks",
            "regex engines or third-party text-grid libraries and row-major emission",
            "digit-to-question-mark mapping, width validation at 0 and 33, dot padding, index rejection, and empty inputs",
            "character-mapping normalization beyond case folding in a paired .h/.cpp API",
            "down-column block reader",
        ),
        c(
            "f26csq-boathouse-oar-grid",
            "Boathouse oar grid",
            "boathouse_oars",
            """
            class OarError : public std::domain_error {
            public:
                explicit OarError(const std::string& message) : std::domain_error(message) {}
            };
            class OarGrid {
            public:
                explicit OarGrid(const std::string& raw);
                std::string normalized() const;
                std::size_t columns() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string oar(std::size_t index) const;
                std::string rigged() const;
            };
            """,
            """
            class OarError : public std::domain_error {
            public:
                explicit OarError(const std::string& message) : std::domain_error(message) {}
            };
            class OarGrid {
            public:
                explicit OarGrid(const std::string& raw);
                std::string normalized() const;
                std::size_t columns() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string oar(std::size_t index) const;
                std::string rigged() const;
            private:
                std::string normalized_;
            };
            """,
            """
            OarGrid::OarGrid(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string OarGrid::normalized() const { return normalized_; }
            std::size_t OarGrid::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 2;
                while (w * w < 2 * n) ++w;
                return w;
            }
            std::size_t OarGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t cols = columns();
                return (n + cols - 1) / cols;
            }
            std::vector<std::string> OarGrid::grid() const {
                std::vector<std::string> rows_out;
                const std::size_t cols = columns();
                if (cols == 0) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    rows_out.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return rows_out;
            }
            std::string OarGrid::oar(std::size_t index) const {
                if (index >= columns()) throw OarError("oar index out of range");
                std::string result;
                for (const std::string& line : grid())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string OarGrid::rigged() const {
                const std::vector<std::string> rows_out = grid();
                if (rows_out.empty()) return "";
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t c = 0; c < cols; ++c) {
                    if (c != 0) result += ' ';
                    for (std::size_t r = 0; r < rows_out.size(); ++r)
                        result += (c < rows_out[r].size()) ? rows_out[r][c] : '+';
                }
                return result;
            }
            """,
            """
            OarGrid::OarGrid(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string OarGrid::normalized() const { return normalized_; }
            std::size_t OarGrid::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 2;
                while (w * w < 2 * n) ++w;
                return w;
            }
            std::size_t OarGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t cols = columns();
                return (n + cols - 1) / cols;
            }
            std::vector<std::string> OarGrid::grid() const {
                std::vector<std::string> rows_out;
                const std::size_t cols = columns();
                if (cols == 0) return rows_out;
                for (std::size_t start = 0; start < normalized_.size(); start += cols)
                    rows_out.push_back(normalized_.substr(start, std::min(cols, normalized_.size() - start)));
                return rows_out;
            }
            std::string OarGrid::oar(std::size_t index) const {
                if (index >= columns()) throw OarError("oar index out of range");
                std::string result;
                for (const std::string& line : grid())
                    if (index < line.size()) result += line[index];
                return result;
            }
            std::string OarGrid::rigged() const {
                const std::vector<std::string> rows_out = grid();
                std::string result;
                for (std::size_t r = 0; r < rows_out.size(); ++r) {
                    if (r != 0) result += ' ';
                    result += rows_out[r];
                }
                return result;
            }
            """,
            """
            OarGrid g("Rowers slice through calm water");
            if (g.normalized() != "rowersslicethroughcalmwater") return 1;
            if (g.columns() != 8U) return 2;
            if (g.rows() != 4U) return 3;
            if (g.grid() != std::vector<std::string>{"rowerssl", "icethrou", "ghcalmwa", "ter"}) return 4;
            if (g.rigged() != "rigt oche wecr eta+ rhl+ srm+ sow+ lua+") return 5;
            OarGrid small("Kayak");
            if (small.columns() != 4U) return 6;
            if (small.rows() != 2U) return 7;
            if (small.rigged() != "kk a+ y+ a+") return 8;
            OarGrid empty("!!");
            if (empty.columns() != 0U) return 9;
            if (empty.rigged() != "") return 10;
            return 0;
            """,
            """
            OarGrid n2(std::string(2, 'a'));
            if (n2.columns() != 2U) return 1;
            OarGrid n3(std::string(3, 'a'));
            if (n3.columns() != 3U) return 2;
            OarGrid n4(std::string(4, 'a'));
            if (n4.columns() != 3U) return 3;
            OarGrid n8(std::string(8, 'a'));
            if (n8.columns() != 4U) return 4;
            OarGrid n9(std::string(9, 'a'));
            if (n9.columns() != 5U) return 5;
            OarGrid g("Dock lines hold fast");
            if (g.normalized() != "docklinesholdfast") return 6;
            if (g.oar(0) != "dnd") return 7;
            if (g.oar(5) != "il") return 8;
            bool threw = false;
            try { g.oar(6); } catch (const OarError&) { threw = true; }
            if (!threw) return 9;
            if (g.rigged() != "dnd oef csa khs lot il+") return 10;
            return 0;
            """,
            "doubled-length growth rule with plus-padded down-column emission",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and row-major emission",
            "growth boundaries where w*w crosses twice the length, plus padding on ragged rows, index rejection, and empty inputs",
            "a second distinct growth rule with its own fill character in a paired .h/.cpp API",
            "down-column block reader",
        ),
        c(
            "f26csq-vineyard-row-serpentine",
            "Vineyard row serpentine",
            "vineyard_rows",
            """
            class SerpentineError : public std::invalid_argument {
            public:
                explicit SerpentineError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RowSerpentine {
            public:
                RowSerpentine(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class SerpentineError : public std::invalid_argument {
            public:
                explicit SerpentineError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RowSerpentine {
            public:
                RowSerpentine(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            RowSerpentine::RowSerpentine(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 24) throw SerpentineError("width outside 1..24");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string RowSerpentine::normalized() const { return normalized_; }
            std::size_t RowSerpentine::width() const { return width_; }
            std::size_t RowSerpentine::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> RowSerpentine::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    for (std::size_t step = 0; step < width_ && pos < n; ++step) {
                        const std::size_t c = (r % 2 == 0) ? step : (width_ - 1 - step);
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string RowSerpentine::row(std::size_t index) const {
                const std::vector<std::string> out = grid();
                if (index >= out.size()) throw SerpentineError("row index out of range");
                return out[index];
            }
            std::string RowSerpentine::render() const {
                const std::vector<std::string> out = grid();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            RowSerpentine::RowSerpentine(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 24) throw SerpentineError("width outside 1..24");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string RowSerpentine::normalized() const { return normalized_; }
            std::size_t RowSerpentine::width() const { return width_; }
            std::size_t RowSerpentine::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> RowSerpentine::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    for (std::size_t c = 0; c < width_ && pos < n; ++c) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string RowSerpentine::row(std::size_t index) const {
                const std::vector<std::string> out = grid();
                if (index >= out.size()) throw SerpentineError("row index out of range");
                return out[index];
            }
            std::string RowSerpentine::render() const {
                const std::vector<std::string> out = grid();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            RowSerpentine v("Grapes ripen on the vine", 5);
            if (v.normalized() != "grapesripenonthevine") return 1;
            if (v.width() != 5U) return 2;
            if (v.rows() != 4U) return 3;
            if (v.grid() != std::vector<std::string>{"grape", "epirs", "nonth", "enive"}) return 4;
            if (v.render() != "grape\\nepirs\\nnonth\\nenive") return 5;
            RowSerpentine pad("Fig tree", 3);
            if (pad.grid() != std::vector<std::string>{"fig", "ert", "e.."}) return 6;
            if (pad.render() != "fig\\nert\\ne..") return 7;
            RowSerpentine empty("!!", 4);
            if (empty.rows() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { RowSerpentine bad("abc", 0); } catch (const SerpentineError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RowSerpentine bad("abc", 25); } catch (const SerpentineError&) { threw = true; }
            if (!threw) return 2;
            RowSerpentine v("Plum and pear", 4);
            if (v.row(1) != "pdna") return 3;
            threw = false;
            try { v.row(3); } catch (const SerpentineError&) { threw = true; }
            if (!threw) return 4;
            if (v.render() != "plum\\npdna\\near.") return 5;
            RowSerpentine one("x", 3);
            if (one.render() != "x..") return 6;
            RowSerpentine exact("abc", 3);
            if (exact.render() != "abc") return 7;
            return 0;
            """,
            "row boustrophedon fill from the left with dot tail padding and newline render",
            "regex engines or third-party text-grid libraries and same-direction fills",
            "alternation on three or more rows, dot tail padding, width validation at 0 and 25, single-row inputs, and index rejection",
            "direction-alternating fill as the rejection discriminator in a paired .h/.cpp API",
            "serpentine grid filler",
        ),
        c(
            "f26csq-loom-shuttle-weave",
            "Loom shuttle weave",
            "loom_shuttle",
            """
            class WeaveError : public std::domain_error {
            public:
                explicit WeaveError(const std::string& message) : std::domain_error(message) {}
            };
            class ShuttleWeave {
            public:
                explicit ShuttleWeave(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> weave() const;
                std::string pick(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class WeaveError : public std::domain_error {
            public:
                explicit WeaveError(const std::string& message) : std::domain_error(message) {}
            };
            class ShuttleWeave {
            public:
                explicit ShuttleWeave(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> weave() const;
                std::string pick(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
            };
            """,
            """
            ShuttleWeave::ShuttleWeave(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string ShuttleWeave::normalized() const { return normalized_; }
            std::size_t ShuttleWeave::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 3;
                while (w * w < n) ++w;
                return w;
            }
            std::size_t ShuttleWeave::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> ShuttleWeave::weave() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(w, '*'));
                std::size_t pos = 0;
                for (std::size_t c = 0; c < w; ++c) {
                    for (std::size_t step = 0; step < total_rows && pos < n; ++step) {
                        const std::size_t r = (c % 2 == 0) ? step : (total_rows - 1 - step);
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string ShuttleWeave::pick(std::size_t index) const {
                const std::vector<std::string> out = weave();
                if (index >= out.size()) throw WeaveError("pick index out of range");
                return out[index];
            }
            std::string ShuttleWeave::render() const {
                const std::vector<std::string> out = weave();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            ShuttleWeave::ShuttleWeave(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string ShuttleWeave::normalized() const { return normalized_; }
            std::size_t ShuttleWeave::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 3;
                while (w * w < n) ++w;
                return w;
            }
            std::size_t ShuttleWeave::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> ShuttleWeave::weave() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(w, '*'));
                std::size_t pos = 0;
                for (std::size_t c = 0; c < w; ++c) {
                    for (std::size_t r = 0; r < total_rows && pos < n; ++r) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string ShuttleWeave::pick(std::size_t index) const {
                const std::vector<std::string> out = weave();
                if (index >= out.size()) throw WeaveError("pick index out of range");
                return out[index];
            }
            std::string ShuttleWeave::render() const {
                const std::vector<std::string> out = weave();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            ShuttleWeave w("Warp threads cross weft");
            if (w.normalized() != "WARPTHREADSCROSSWEFT") return 1;
            if (w.width() != 5U) return 2;
            if (w.rows() != 4U) return 3;
            if (w.weave() != std::vector<std::string>{"WEASW", "ARDSE", "RHSOF", "PTCRT"}) return 4;
            if (w.render() != "WEASW\\nARDSE\\nRHSOF\\nPTCRT") return 5;
            ShuttleWeave small("Linen");
            if (small.weave() != std::vector<std::string>{"LEN", "IN*"}) return 6;
            if (small.render() != "LEN\\nIN*") return 7;
            ShuttleWeave empty("!!");
            if (empty.width() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            ShuttleWeave n9(std::string(9, 'a'));
            if (n9.width() != 3U) return 1;
            ShuttleWeave n10(std::string(10, 'a'));
            if (n10.width() != 4U) return 2;
            ShuttleWeave n16(std::string(16, 'a'));
            if (n16.width() != 4U) return 3;
            ShuttleWeave n17(std::string(17, 'a'));
            if (n17.width() != 5U) return 4;
            ShuttleWeave n25(std::string(25, 'a'));
            if (n25.width() != 5U) return 5;
            ShuttleWeave n26(std::string(26, 'a'));
            if (n26.width() != 6U) return 6;
            ShuttleWeave w("Silk 7 cotton");
            if (w.pick(1) != "I7TN") return 7;
            bool threw = false;
            try { w.pick(3); } catch (const WeaveError&) { threw = true; }
            if (!threw) return 8;
            if (w.render() != "SCO*\\nI7TN\\nLKTO") return 9;
            return 0;
            """,
            "column boustrophedon fill with a square-ish growth rule and star padding",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and same-direction fills",
            "column alternation, growth boundaries where w*w crosses the length, star padding, index rejection, and empty inputs",
            "column-axis serpentine distinct from row-axis siblings in a paired .h/.cpp API",
            "serpentine grid filler",
            project_support=True,
        ),
        c(
            "f26csq-greenhouse-bed-snake",
            "Greenhouse bed snake",
            "greenhouse_beds",
            """
            class BedError : public std::invalid_argument {
            public:
                explicit BedError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BedSnake {
            public:
                BedSnake(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> beds() const;
                std::string bed(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class BedError : public std::invalid_argument {
            public:
                explicit BedError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BedSnake {
            public:
                BedSnake(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> beds() const;
                std::string bed(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t rows_;
            };
            """,
            """
            BedSnake::BedSnake(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 12) throw BedError("row count outside 1..12");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string BedSnake::normalized() const { return normalized_; }
            std::size_t BedSnake::rows() const { return rows_; }
            std::size_t BedSnake::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> BedSnake::beds() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(rows_, std::string(cols, '#'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < rows_; ++r) {
                    for (std::size_t step = 0; step < cols && pos < n; ++step) {
                        const std::size_t c = (r % 2 == 0) ? (cols - 1 - step) : step;
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string BedSnake::bed(std::size_t index) const {
                if (index >= rows_) throw BedError("bed index out of range");
                return beds()[index];
            }
            std::string BedSnake::render() const {
                const std::vector<std::string> out = beds();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            BedSnake::BedSnake(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 12) throw BedError("row count outside 1..12");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string BedSnake::normalized() const { return normalized_; }
            std::size_t BedSnake::rows() const { return rows_; }
            std::size_t BedSnake::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> BedSnake::beds() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(rows_, std::string(cols, '#'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < rows_; ++r) {
                    for (std::size_t c = 0; c < cols && pos < n; ++c) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string BedSnake::bed(std::size_t index) const {
                if (index >= rows_) throw BedError("bed index out of range");
                return beds()[index];
            }
            std::string BedSnake::render() const {
                const std::vector<std::string> out = beds();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            BedSnake b("Seedlings sprout in rows", 3);
            if (b.normalized() != "seedlingssproutinrows") return 1;
            if (b.rows() != 3U) return 2;
            if (b.columns() != 7U) return 3;
            if (b.beds() != std::vector<std::string>{"nildees", "gssprou", "swornit"}) return 4;
            if (b.render() != "nildees\\ngssprou\\nswornit") return 5;
            BedSnake pad("Kale bed 9", 2);
            if (pad.render() != "elak\\nbed9") return 6;
            BedSnake empty("!!", 2);
            if (empty.columns() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { BedSnake bad("abc", 0); } catch (const BedError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BedSnake bad("abc", 13); } catch (const BedError&) { threw = true; }
            if (!threw) return 2;
            BedSnake b("Herb garden", 4);
            if (b.bed(2) != "edr") return 3;
            threw = false;
            try { b.bed(4); } catch (const BedError&) { threw = true; }
            if (!threw) return 4;
            if (b.render() != "reh\\nbga\\nedr\\nn##") return 5;
            BedSnake one("z9", 5);
            if (one.render() != "z\\n9\\n#\\n#\\n#") return 6;
            return 0;
            """,
            "row boustrophedon fill from the right with hash padding and caller row counts",
            "regex engines or third-party text-grid libraries and same-direction or left-start fills",
            "right-start first row, alternation, hash padding, row-count validation at 0 and 13, and index rejection",
            "opposite starting direction as a materially different contract in a paired .h/.cpp API",
            "serpentine grid filler",
        ),
        c(
            "f26csq-library-shelf-zigzag",
            "Library shelf zigzag",
            "library_zigzag",
            """
            class ZigzagError : public std::invalid_argument {
            public:
                explicit ZigzagError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ShelfZigzag {
            public:
                ShelfZigzag(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> shelves() const;
                std::string shelf(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class ZigzagError : public std::invalid_argument {
            public:
                explicit ZigzagError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ShelfZigzag {
            public:
                ShelfZigzag(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> shelves() const;
                std::string shelf(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            ShelfZigzag::ShelfZigzag(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 30) throw ZigzagError("width outside 1..30");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string ShelfZigzag::normalized() const { return normalized_; }
            std::size_t ShelfZigzag::width() const { return width_; }
            std::size_t ShelfZigzag::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ShelfZigzag::shelves() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '0'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    for (std::size_t step = 0; step < width_ && pos < n; ++step) {
                        const std::size_t c = (r % 2 == 0) ? step : (width_ - 1 - step);
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string ShelfZigzag::shelf(std::size_t index) const {
                const std::vector<std::string> out = shelves();
                if (index >= out.size()) throw ZigzagError("shelf index out of range");
                return out[index];
            }
            std::string ShelfZigzag::render() const {
                const std::vector<std::string> out = shelves();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += '[';
                    result += out[r];
                    result += ']';
                }
                return result;
            }
            """,
            """
            ShelfZigzag::ShelfZigzag(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 30) throw ZigzagError("width outside 1..30");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string ShelfZigzag::normalized() const { return normalized_; }
            std::size_t ShelfZigzag::width() const { return width_; }
            std::size_t ShelfZigzag::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ShelfZigzag::shelves() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '0'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    for (std::size_t c = 0; c < width_ && pos < n; ++c) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string ShelfZigzag::shelf(std::size_t index) const {
                const std::vector<std::string> out = shelves();
                if (index >= out.size()) throw ZigzagError("shelf index out of range");
                return out[index];
            }
            std::string ShelfZigzag::render() const {
                const std::vector<std::string> out = shelves();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += '[';
                    result += out[r];
                    result += ']';
                }
                return result;
            }
            """,
            """
            ShelfZigzag z("Stacks hold rare tomes", 4);
            if (z.normalized() != "STACKSHOLDRARETOMES") return 1;
            if (z.width() != 4U) return 2;
            if (z.rows() != 5U) return 3;
            if (z.shelves() != std::vector<std::string>{"STAC", "OHSK", "LDRA", "OTER", "MES0"}) return 4;
            if (z.render() != "[STAC]\\n[OHSK]\\n[LDRA]\\n[OTER]\\n[MES0]") return 5;
            ShelfZigzag exact("a1b2c3d4", 2);
            if (exact.render() != "[A1]\\n[2B]\\n[C3]\\n[4D]") return 6;
            ShelfZigzag empty("!!", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { ShelfZigzag bad("abc", 0); } catch (const ZigzagError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ShelfZigzag bad("abc", 31); } catch (const ZigzagError&) { threw = true; }
            if (!threw) return 2;
            ShelfZigzag z("Atlas 42 maps", 3);
            if (z.shelf(3) != "0SP") return 3;
            threw = false;
            try { z.shelf(4); } catch (const ZigzagError&) { threw = true; }
            if (!threw) return 4;
            if (z.render() != "[ATL]\\n[4SA]\\n[2MA]\\n[0SP]") return 5;
            ShelfZigzag one("q", 2);
            if (one.render() != "[Q0]") return 6;
            return 0;
            """,
            "bracket-wrapped row serpentine render with zero padding",
            "regex engines or third-party text-grid libraries, same-direction fills, and unwrapped renders",
            "exact bracket bytes, zero padding, alternation, width validation at 0 and 31, and index rejection",
            "exact wrapped output shapes beyond bare newline joining in a paired .h/.cpp API",
            "serpentine grid filler",
        ),
        c(
            "f26csq-quarry-cart-switchback",
            "Quarry cart switchback",
            "quarry_switch",
            """
            class SwitchbackError : public std::domain_error {
            public:
                explicit SwitchbackError(const std::string& message) : std::domain_error(message) {}
            };
            class SwitchbackGrid {
            public:
                explicit SwitchbackGrid(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string track(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class SwitchbackError : public std::domain_error {
            public:
                explicit SwitchbackError(const std::string& message) : std::domain_error(message) {}
            };
            class SwitchbackGrid {
            public:
                explicit SwitchbackGrid(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string track(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
            };
            """,
            """
            SwitchbackGrid::SwitchbackGrid(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string SwitchbackGrid::normalized() const { return normalized_; }
            std::size_t SwitchbackGrid::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 6) return 3;
                if (n <= 12) return 4;
                if (n <= 20) return 5;
                return 7;
            }
            std::size_t SwitchbackGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> SwitchbackGrid::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(w, '.'));
                std::size_t pos = 0;
                for (std::size_t c = 0; c < w; ++c) {
                    for (std::size_t step = 0; step < total_rows && pos < n; ++step) {
                        const std::size_t r = (c % 2 == 0) ? (total_rows - 1 - step) : step;
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string SwitchbackGrid::track(std::size_t index) const {
                const std::vector<std::string> out = grid();
                if (index >= out.size()) throw SwitchbackError("track index out of range");
                return out[index];
            }
            std::string SwitchbackGrid::render() const {
                const std::vector<std::string> out = grid();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            SwitchbackGrid::SwitchbackGrid(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string SwitchbackGrid::normalized() const { return normalized_; }
            std::size_t SwitchbackGrid::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 6) return 3;
                if (n <= 12) return 4;
                if (n <= 20) return 5;
                return 7;
            }
            std::size_t SwitchbackGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> SwitchbackGrid::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(w, '.'));
                std::size_t pos = 0;
                for (std::size_t c = 0; c < w; ++c) {
                    for (std::size_t r = 0; r < total_rows && pos < n; ++r) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string SwitchbackGrid::track(std::size_t index) const {
                const std::vector<std::string> out = grid();
                if (index >= out.size()) throw SwitchbackError("track index out of range");
                return out[index];
            }
            std::string SwitchbackGrid::render() const {
                const std::vector<std::string> out = grid();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            SwitchbackGrid g("Granite blocks slide down");
            if (g.normalized() != "graniteblocksslidedown") return 1;
            if (g.width() != 7U) return 2;
            if (g.rows() != 4U) return 3;
            if (g.grid() != std::vector<std::string>{"niksow.", "atcsdn.", "reole..", "gblid.."}) return 4;
            if (g.render() != "niksow.\\natcsdn.\\nreole..\\ngblid..") return 5;
            SwitchbackGrid small("Ore cart");
            if (small.grid() != std::vector<std::string>{"rert", "oca."}) return 6;
            if (small.render() != "rert\\noca.") return 7;
            SwitchbackGrid empty("123");
            if (empty.width() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            SwitchbackGrid n6(std::string(6, 'a'));
            if (n6.width() != 3U) return 1;
            SwitchbackGrid n7(std::string(7, 'a'));
            if (n7.width() != 4U) return 2;
            SwitchbackGrid n12(std::string(12, 'a'));
            if (n12.width() != 4U) return 3;
            SwitchbackGrid n13(std::string(13, 'a'));
            if (n13.width() != 5U) return 4;
            SwitchbackGrid n20(std::string(20, 'a'));
            if (n20.width() != 5U) return 5;
            SwitchbackGrid n21(std::string(21, 'a'));
            if (n21.width() != 7U) return 6;
            SwitchbackGrid g("Slate chips");
            if (g.track(1) != "lei.") return 7;
            bool threw = false;
            try { g.track(3); } catch (const SwitchbackError&) { threw = true; }
            if (!threw) return 8;
            if (g.render() != "atps\\nlei.\\nsch.") return 9;
            return 0;
            """,
            "column boustrophedon fill from the bottom with band-lookup dimensions",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and same-direction fills",
            "bottom-start first column, alternation, band boundaries at 6/7, 12/13, and 20/21, dot padding, and index rejection",
            "a third distinct serpentine axis-direction combination in a paired .h/.cpp API",
            "serpentine grid filler",
        ),
        c(
            "f26csq-net-mending-panels",
            "Net mending panels",
            "net_mending",
            """
            class NetError : public std::invalid_argument {
            public:
                explicit NetError(const std::string& message) : std::invalid_argument(message) {}
            };
            class NetPanels {
            public:
                NetPanels(const std::string& raw, std::size_t height);
                std::string normalized() const;
                std::size_t height() const;
                std::size_t columns() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class NetError : public std::invalid_argument {
            public:
                explicit NetError(const std::string& message) : std::invalid_argument(message) {}
            };
            class NetPanels {
            public:
                NetPanels(const std::string& raw, std::size_t height);
                std::string normalized() const;
                std::size_t height() const;
                std::size_t columns() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t height_;
            };
            """,
            """
            NetPanels::NetPanels(const std::string& raw, std::size_t height) : height_(height) {
                if (height == 0 || height > 10) throw NetError("height outside 1..10");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string NetPanels::normalized() const { return normalized_; }
            std::size_t NetPanels::height() const { return height_; }
            std::size_t NetPanels::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + height_ - 1) / height_;
            }
            std::vector<std::string> NetPanels::panels() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(height_, std::string(cols, '='));
                std::size_t pos = 0;
                for (std::size_t c = 0; c < cols; ++c) {
                    for (std::size_t step = 0; step < height_ && pos < n; ++step) {
                        const std::size_t r = (c % 2 == 0) ? step : (height_ - 1 - step);
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string NetPanels::panel(std::size_t index) const {
                if (index >= height_) throw NetError("panel index out of range");
                return panels()[index];
            }
            std::string NetPanels::render() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            NetPanels::NetPanels(const std::string& raw, std::size_t height) : height_(height) {
                if (height == 0 || height > 10) throw NetError("height outside 1..10");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string NetPanels::normalized() const { return normalized_; }
            std::size_t NetPanels::height() const { return height_; }
            std::size_t NetPanels::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + height_ - 1) / height_;
            }
            std::vector<std::string> NetPanels::panels() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(height_, std::string(cols, '='));
                std::size_t pos = 0;
                for (std::size_t c = 0; c < cols; ++c) {
                    for (std::size_t r = 0; r < height_ && pos < n; ++r) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string NetPanels::panel(std::size_t index) const {
                if (index >= height_) throw NetError("panel index out of range");
                return panels()[index];
            }
            std::string NetPanels::render() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            NetPanels n("Mended nets dry on racks", 3);
            if (n.normalized() != "mendednetsdryonracks") return 1;
            if (n.height() != 3U) return 2;
            if (n.columns() != 7U) return 3;
            if (n.panels() != std::vector<std::string>{"mdnryck", "eeedoas", "ndtsnr="}) return 4;
            if (n.render() != "mdnryck\\neeedoas\\nndtsnr=") return 5;
            NetPanels exact("a1b2c3d4", 2);
            if (exact.render() != "a2c4\\n1b3d") return 6;
            NetPanels empty("!!", 2);
            if (empty.columns() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { NetPanels bad("abc", 0); } catch (const NetError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { NetPanels bad("abc", 11); } catch (const NetError&) { threw = true; }
            if (!threw) return 2;
            NetPanels n("Rope twine knots", 4);
            if (n.panel(2) != "pwns") return 3;
            threw = false;
            try { n.panel(4); } catch (const NetError&) { threw = true; }
            if (!threw) return 4;
            if (n.render() != "rne=\\noik=\\npwns\\netot") return 5;
            NetPanels one("q", 3);
            if (one.render() != "q\\n=\\n=") return 6;
            return 0;
            """,
            "caller-height column boustrophedon with equals padding",
            "regex engines or third-party text-grid libraries and same-direction fills",
            "alternation across columns, ceiling column counts, height validation at 0 and 11, equals padding, and index rejection",
            "height-driven column serpentine distinct from growth-rule siblings in a paired .h/.cpp API",
            "serpentine grid filler",
        ),
        c(
            "f26csq-terrarium-layer-wind",
            "Terrarium layer wind",
            "terrarium_layers",
            """
            class LayerError : public std::invalid_argument {
            public:
                explicit LayerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LayerWind {
            public:
                LayerWind(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> layers() const;
                std::string layer(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class LayerError : public std::invalid_argument {
            public:
                explicit LayerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LayerWind {
            public:
                LayerWind(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> layers() const;
                std::string layer(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            LayerWind::LayerWind(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 16) throw LayerError("width outside 1..16");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string LayerWind::normalized() const { return normalized_; }
            std::size_t LayerWind::width() const { return width_; }
            std::size_t LayerWind::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> LayerWind::layers() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '~'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    for (std::size_t step = 0; step < width_ && pos < n; ++step) {
                        const std::size_t c = (r % 2 == 0) ? step : (width_ - 1 - step);
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string LayerWind::layer(std::size_t index) const {
                const std::vector<std::string> out = layers();
                if (index >= out.size()) throw LayerError("layer index out of range");
                return out[index];
            }
            std::string LayerWind::render() const {
                const std::vector<std::string> out = layers();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            LayerWind::LayerWind(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 16) throw LayerError("width outside 1..16");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string LayerWind::normalized() const { return normalized_; }
            std::size_t LayerWind::width() const { return width_; }
            std::size_t LayerWind::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> LayerWind::layers() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '~'));
                std::size_t pos = 0;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    for (std::size_t c = 0; c < width_ && pos < n; ++c) {
                        out[r][c] = normalized_[pos++];
                    }
                }
                return out;
            }
            std::string LayerWind::layer(std::size_t index) const {
                const std::vector<std::string> out = layers();
                if (index >= out.size()) throw LayerError("layer index out of range");
                return out[index];
            }
            std::string LayerWind::render() const {
                const std::vector<std::string> out = layers();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            LayerWind w("Ferns and moss 2 grow", 4);
            if (w.normalized() != "FERNSANDMOSSGROW") return 1;
            if (w.width() != 4U) return 2;
            if (w.rows() != 4U) return 3;
            if (w.layers() != std::vector<std::string>{"FERN", "DNAS", "MOSS", "WORG"}) return 4;
            if (w.render() != "FERN\\nDNAS\\nMOSS\\nWORG") return 5;
            LayerWind pad("Ivy 9", 3);
            if (pad.render() != "IVY") return 6;
            LayerWind empty("42", 2);
            if (empty.rows() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { LayerWind bad("abc", 0); } catch (const LayerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LayerWind bad("abc", 17); } catch (const LayerError&) { threw = true; }
            if (!threw) return 2;
            LayerWind w("Moss 7 peat 3", 5);
            if (w.layer(1) != "~~TAE") return 3;
            threw = false;
            try { w.layer(2); } catch (const LayerError&) { threw = true; }
            if (!threw) return 4;
            if (w.render() != "MOSSP\\n~~TAE") return 5;
            LayerWind digits("123", 4);
            if (digits.rows() != 0U) return 6;
            return 0;
            """,
            "letter-only row serpentine fill with tilde padding and digit dropping",
            "regex engines or third-party text-grid libraries, same-direction fills, and digit retention",
            "digit dropping, alternation, tilde padding, width validation at 0 and 17, and index rejection",
            "normalization filtering combined with direction alternation in a paired .h/.cpp API",
            "serpentine grid filler",
        ),
        c(
            "f26csq-maze-wall-spiral",
            "Maze wall spiral",
            "maze_walls",
            """
            class SpiralError : public std::invalid_argument {
            public:
                explicit SpiralError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WallSpiral {
            public:
                WallSpiral(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string spiral() const;
                std::string render() const;
            };
            """,
            """
            class SpiralError : public std::invalid_argument {
            public:
                explicit SpiralError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WallSpiral {
            public:
                WallSpiral(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string spiral() const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            WallSpiral::WallSpiral(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 20) throw SpiralError("width outside 1..20");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string WallSpiral::normalized() const { return normalized_; }
            std::size_t WallSpiral::width() const { return width_; }
            std::size_t WallSpiral::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> WallSpiral::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string WallSpiral::spiral() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                std::vector<std::vector<bool>> seen(total_rows, std::vector<bool>(cols, false));
                const int dr[4] = {0, 1, 0, -1};
                const int dc[4] = {1, 0, -1, 0};
                std::size_t r = 0;
                std::size_t c = 0;
                std::size_t dir = 0;
                std::string out;
                for (std::size_t step = 0; step < total_rows * cols; ++step) {
                    out += g[r][c];
                    seen[r][c] = true;
                    const std::size_t nr = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    const std::size_t nc = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                    if (nr >= total_rows || nc >= cols || seen[nr][nc]) dir = (dir + 1) % 4;
                    r = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    c = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                }
                return out;
            }
            std::string WallSpiral::render() const {
                const std::string walked = spiral();
                if (walked.empty()) return "";
                const std::size_t chunk = rows();
                std::string result;
                for (std::size_t start = 0; start < walked.size(); start += chunk) {
                    if (start != 0) result += ' ';
                    result += walked.substr(start, chunk);
                }
                return result;
            }
            """,
            """
            WallSpiral::WallSpiral(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 20) throw SpiralError("width outside 1..20");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string WallSpiral::normalized() const { return normalized_; }
            std::size_t WallSpiral::width() const { return width_; }
            std::size_t WallSpiral::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> WallSpiral::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string WallSpiral::spiral() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (const std::string& line : g) out += line;
                return out;
            }
            std::string WallSpiral::render() const {
                const std::string walked = spiral();
                if (walked.empty()) return "";
                const std::size_t chunk = rows();
                std::string result;
                for (std::size_t start = 0; start < walked.size(); start += chunk) {
                    if (start != 0) result += ' ';
                    result += walked.substr(start, chunk);
                }
                return result;
            }
            """,
            """
            WallSpiral s("Winding paths cross the garden", 4);
            if (s.normalized() != "windingpathscrossthegarden") return 1;
            if (s.width() != 4U) return 2;
            if (s.rows() != 7U) return 3;
            if (s.grid() != std::vector<std::string>{"wind", "ingp", "aths", "cros", "sthe", "gard", "en.."}) return 4;
            if (s.spiral() != "windpssed..negscainghohratrt") return 5;
            if (s.render() != "windpss ed..neg scaingh ohratrt") return 6;
            WallSpiral exact("ab cd", 2);
            if (exact.spiral() != "abdc") return 7;
            if (exact.render() != "ab dc") return 8;
            WallSpiral empty("!!", 3);
            if (empty.rows() != 0U) return 9;
            if (empty.render() != "") return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { WallSpiral bad("abc", 0); } catch (const SpiralError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { WallSpiral bad("abc", 21); } catch (const SpiralError&) { threw = true; }
            if (!threw) return 2;
            WallSpiral s("Maze runner", 3);
            if (s.spiral() != "mazue..rnern") return 3;
            if (s.render() != "mazu e..r nern") return 4;
            WallSpiral one("q", 5);
            if (one.spiral() != "q....") return 5;
            if (one.render() != "q . . . .") return 6;
            return 0;
            """,
            "clockwise spiral from the top-left over a dot-padded rectangle with row-count chunking",
            "regex engines or third-party text-grid libraries and row-major or column-major reads",
            "ring-by-ring order on a non-square grid, dot padding, width validation at 0 and 21, and empty inputs",
            "spiral traversal as a materially different read order in a paired .h/.cpp API",
            "spiral ring reader",
        ),
        c(
            "f26csq-beehive-ring-readout",
            "Beehive ring readout",
            "beehive_rings",
            """
            class RingError : public std::domain_error {
            public:
                explicit RingError(const std::string& message) : std::domain_error(message) {}
            };
            class RingReadout {
            public:
                explicit RingReadout(const std::string& raw);
                std::string normalized() const;
                std::size_t side() const;
                std::vector<std::string> grid() const;
                std::string rings() const;
                std::string readout() const;
            };
            """,
            """
            class RingError : public std::domain_error {
            public:
                explicit RingError(const std::string& message) : std::domain_error(message) {}
            };
            class RingReadout {
            public:
                explicit RingReadout(const std::string& raw);
                std::string normalized() const;
                std::size_t side() const;
                std::vector<std::string> grid() const;
                std::string rings() const;
                std::string readout() const;
            private:
                std::string normalized_;
            };
            """,
            """
            RingReadout::RingReadout(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string RingReadout::normalized() const { return normalized_; }
            std::size_t RingReadout::side() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t s = 1;
                while (s * s < n) ++s;
                return s;
            }
            std::vector<std::string> RingReadout::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t s = side();
                out.assign(s, std::string(s, '*'));
                for (std::size_t i = 0; i < n; ++i) out[i / s][i % s] = normalized_[i];
                return out;
            }
            std::string RingReadout::rings() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                std::vector<std::vector<bool>> seen(total_rows, std::vector<bool>(cols, false));
                const int dr[4] = {1, 0, -1, 0};
                const int dc[4] = {0, 1, 0, -1};
                std::size_t r = 0;
                std::size_t c = 0;
                std::size_t dir = 0;
                std::string out;
                for (std::size_t step = 0; step < total_rows * cols; ++step) {
                    out += g[r][c];
                    seen[r][c] = true;
                    const std::size_t nr = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    const std::size_t nc = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                    if (nr >= total_rows || nc >= cols || seen[nr][nc]) dir = (dir + 1) % 4;
                    r = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    c = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                }
                return out;
            }
            std::string RingReadout::readout() const {
                const std::string walked = rings();
                if (walked.empty()) return "";
                const std::size_t chunk = side();
                std::string result;
                for (std::size_t start = 0; start < walked.size(); start += chunk) {
                    if (start != 0) result += '-';
                    result += walked.substr(start, chunk);
                }
                return result;
            }
            """,
            """
            RingReadout::RingReadout(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string RingReadout::normalized() const { return normalized_; }
            std::size_t RingReadout::side() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t s = 1;
                while (s * s < n) ++s;
                return s;
            }
            std::vector<std::string> RingReadout::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t s = side();
                out.assign(s, std::string(s, '*'));
                for (std::size_t i = 0; i < n; ++i) out[i / s][i % s] = normalized_[i];
                return out;
            }
            std::string RingReadout::rings() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (const std::string& line : g) out += line;
                return out;
            }
            std::string RingReadout::readout() const {
                const std::string walked = rings();
                if (walked.empty()) return "";
                const std::size_t chunk = side();
                std::string result;
                for (std::size_t start = 0; start < walked.size(); start += chunk) {
                    if (start != 0) result += '-';
                    result += walked.substr(start, chunk);
                }
                return result;
            }
            """,
            """
            RingReadout r("Honeycomb cells hum");
            if (r.normalized() != "honeycombcellshum") return 1;
            if (r.side() != 5U) return 2;
            if (r.grid() != std::vector<std::string>{"honey", "combc", "ellsh", "um***", "*****"}) return 3;
            if (r.rings() != "hceu******hcyenoolm**sbml") return 4;
            if (r.readout() != "hceu*-*****-hcyen-oolm*-*sbml") return 5;
            RingReadout small("bee");
            if (small.rings() != "be*e") return 6;
            if (small.readout() != "be-*e") return 7;
            RingReadout empty("!!");
            if (empty.side() != 0U) return 8;
            if (empty.readout() != "") return 9;
            return 0;
            """,
            """
            RingReadout one("q");
            if (one.side() != 1U) return 1;
            if (one.rings() != "q") return 2;
            RingReadout four("abcd");
            if (four.rings() != "acdb") return 3;
            RingReadout nine("abcdefghi");
            if (nine.rings() != "adghifcbe") return 4;
            if (nine.readout() != "adg-hif-cbe") return 5;
            RingReadout ten("abcdefghij");
            if (ten.side() != 4U) return 6;
            if (ten.grid()[3] != "****") return 7;
            return 0;
            """,
            "counterclockwise perfect-square spiral with star padding and dash chunking",
            "regex engines or third-party text-grid libraries and row-major reads",
            "square padding counts, downward first move, chunk grouping by side, and empty inputs",
            "square-padding dimensions with the opposite rotation in a paired .h/.cpp API",
            "spiral ring reader",
        ),
        c(
            "f26csq-clocktower-dial-spiral",
            "Clocktower dial spiral",
            "clocktower_dial",
            """
            class DialError : public std::invalid_argument {
            public:
                explicit DialError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DialSpiral {
            public:
                DialSpiral(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> dial() const;
                std::string traced() const;
            };
            """,
            """
            class DialError : public std::invalid_argument {
            public:
                explicit DialError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DialSpiral {
            public:
                DialSpiral(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> dial() const;
                std::string traced() const;
            private:
                std::string normalized_;
                std::size_t rows_;
            };
            """,
            """
            DialSpiral::DialSpiral(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 9) throw DialError("row count outside 1..9");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string DialSpiral::normalized() const { return normalized_; }
            std::size_t DialSpiral::rows() const { return rows_; }
            std::size_t DialSpiral::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> DialSpiral::dial() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(rows_, std::string(cols, '#'));
                for (std::size_t i = 0; i < n; ++i) out[i / cols][i % cols] = normalized_[i];
                return out;
            }
            std::string DialSpiral::traced() const {
                const std::vector<std::string> g = dial();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                std::vector<std::vector<bool>> seen(total_rows, std::vector<bool>(cols, false));
                const int dr[4] = {1, 0, -1, 0};
                const int dc[4] = {0, -1, 0, 1};
                std::size_t r = 0;
                std::size_t c = cols - 1;
                std::size_t dir = 0;
                std::string out;
                for (std::size_t step = 0; step < total_rows * cols; ++step) {
                    out += g[r][c];
                    seen[r][c] = true;
                    const std::size_t nr = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    const std::size_t nc = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                    if (nr >= total_rows || nc >= cols || seen[nr][nc]) dir = (dir + 1) % 4;
                    r = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    c = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                }
                return out;
            }
            """,
            """
            DialSpiral::DialSpiral(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 9) throw DialError("row count outside 1..9");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string DialSpiral::normalized() const { return normalized_; }
            std::size_t DialSpiral::rows() const { return rows_; }
            std::size_t DialSpiral::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> DialSpiral::dial() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(rows_, std::string(cols, '#'));
                for (std::size_t i = 0; i < n; ++i) out[i / cols][i % cols] = normalized_[i];
                return out;
            }
            std::string DialSpiral::traced() const {
                const std::vector<std::string> g = dial();
                std::string out;
                for (const std::string& line : g) out += line;
                return out;
            }
            """,
            """
            DialSpiral d("Clock hands sweep past noon", 4);
            if (d.normalized() != "CLOCKHANDSSWEEPPASTNOON") return 1;
            if (d.rows() != 4U) return 2;
            if (d.columns() != 6U) return 3;
            if (d.dial() != std::vector<std::string>{"CLOCKH", "ANDSSW", "EEPPAS", "TNOON#"}) return 4;
            if (d.traced() != "HWS#NOONTEACLOCKSAPPENDS") return 5;
            DialSpiral exact("ab cd", 2);
            if (exact.traced() != "BDCA") return 6;
            DialSpiral empty("!!", 2);
            if (empty.columns() != 0U) return 7;
            if (empty.traced() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { DialSpiral bad("abc", 0); } catch (const DialError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { DialSpiral bad("abc", 10); } catch (const DialError&) { threw = true; }
            if (!threw) return 2;
            DialSpiral d("Bell tower", 3);
            if (d.traced() != "LOREWLBET") return 3;
            DialSpiral one("q", 3);
            if (one.traced() != "Q##") return 4;
            DialSpiral two("ab", 1);
            if (two.traced() != "BA") return 5;
            return 0;
            """,
            "top-right clockwise spiral over a hash-padded caller-row grid",
            "regex engines or third-party text-grid libraries and row-major reads",
            "first-move direction, hash padding, row-count validation at 0 and 10, and non-square grids",
            "named-corner spiral distinct from top-left siblings in a paired .h/.cpp API",
            "spiral ring reader",
            project_support=True,
        ),
        c(
            "f26csq-garden-maze-inside-out",
            "Garden maze inside out",
            "garden_maze",
            """
            class MazeError : public std::invalid_argument {
            public:
                explicit MazeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class InsideOutSpiral {
            public:
                InsideOutSpiral(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> paths() const;
                std::string inside_out() const;
            };
            """,
            """
            class MazeError : public std::invalid_argument {
            public:
                explicit MazeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class InsideOutSpiral {
            public:
                InsideOutSpiral(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> paths() const;
                std::string inside_out() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            InsideOutSpiral::InsideOutSpiral(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 15) throw MazeError("width outside 1..15");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string InsideOutSpiral::normalized() const { return normalized_; }
            std::size_t InsideOutSpiral::width() const { return width_; }
            std::size_t InsideOutSpiral::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> InsideOutSpiral::paths() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string InsideOutSpiral::inside_out() const {
                const std::vector<std::string> g = paths();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                std::vector<std::vector<bool>> seen(total_rows, std::vector<bool>(cols, false));
                const int dr[4] = {0, 1, 0, -1};
                const int dc[4] = {1, 0, -1, 0};
                std::size_t r = 0;
                std::size_t c = 0;
                std::size_t dir = 0;
                std::string walked;
                for (std::size_t step = 0; step < total_rows * cols; ++step) {
                    walked += g[r][c];
                    seen[r][c] = true;
                    const std::size_t nr = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    const std::size_t nc = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                    if (nr >= total_rows || nc >= cols || seen[nr][nc]) dir = (dir + 1) % 4;
                    r = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    c = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                }
                return std::string(walked.rbegin(), walked.rend());
            }
            """,
            """
            InsideOutSpiral::InsideOutSpiral(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 15) throw MazeError("width outside 1..15");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string InsideOutSpiral::normalized() const { return normalized_; }
            std::size_t InsideOutSpiral::width() const { return width_; }
            std::size_t InsideOutSpiral::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> InsideOutSpiral::paths() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string InsideOutSpiral::inside_out() const {
                const std::vector<std::string> g = paths();
                std::string out;
                for (const std::string& line : g) out += line;
                return out;
            }
            """,
            """
            InsideOutSpiral m("Hedges hide the quiet path", 4);
            if (m.normalized() != "hedgeshidethequietpath") return 1;
            if (m.width() != 4U) return 2;
            if (m.rows() != 6U) return 3;
            if (m.paths() != std::vector<std::string>{"hedg", "eshi", "deth", "equi", "etpa", "th.."}) return 4;
            if (m.inside_out() != "eqtputhsedeeth..aihigdeh") return 5;
            InsideOutSpiral exact("ab cd", 2);
            if (exact.inside_out() != "cdba") return 6;
            InsideOutSpiral empty("!!", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.inside_out() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { InsideOutSpiral bad("abc", 0); } catch (const MazeError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { InsideOutSpiral bad("abc", 16); } catch (const MazeError&) { threw = true; }
            if (!threw) return 2;
            InsideOutSpiral m("Maze 7 turns", 3);
            if (m.inside_out() != "r7eus..ntzam") return 3;
            InsideOutSpiral one("q", 4);
            if (one.inside_out() != "...q") return 4;
            InsideOutSpiral two("ab", 2);
            if (two.inside_out() != "ba") return 5;
            return 0;
            """,
            "reversed clockwise spiral emission, center first, over a dot-padded grid",
            "regex engines or third-party text-grid libraries, row-major reads, and unreversed spiral order",
            "center-first ordering, exact reversal of a known spiral, dot padding, and width validation at 0 and 16",
            "inside-out emission as a distinct output contract in a paired .h/.cpp API",
            "spiral ring reader",
        ),
        c(
            "f26csq-silo-ladder-spiral",
            "Silo ladder spiral",
            "silo_ladder",
            """
            class LadderError : public std::domain_error {
            public:
                explicit LadderError(const std::string& message) : std::domain_error(message) {}
            };
            class LadderSpiral {
            public:
                explicit LadderSpiral(const std::string& raw);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> grid() const;
                std::string climb() const;
            };
            """,
            """
            class LadderError : public std::domain_error {
            public:
                explicit LadderError(const std::string& message) : std::domain_error(message) {}
            };
            class LadderSpiral {
            public:
                explicit LadderSpiral(const std::string& raw);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> grid() const;
                std::string climb() const;
            private:
                std::string normalized_;
            };
            """,
            """
            LadderSpiral::LadderSpiral(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string LadderSpiral::normalized() const { return normalized_; }
            std::size_t LadderSpiral::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t r = 2;
                while (r * (r + 1) < n) ++r;
                return r;
            }
            std::size_t LadderSpiral::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t total_rows = rows();
                return (n + total_rows - 1) / total_rows;
            }
            std::vector<std::string> LadderSpiral::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                const std::size_t cols = columns();
                out.assign(total_rows, std::string(cols, '0'));
                for (std::size_t i = 0; i < n; ++i) out[i / cols][i % cols] = normalized_[i];
                return out;
            }
            std::string LadderSpiral::climb() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                std::vector<std::vector<bool>> seen(total_rows, std::vector<bool>(cols, false));
                const int dr[4] = {0, -1, 0, 1};
                const int dc[4] = {1, 0, -1, 0};
                std::size_t r = total_rows - 1;
                std::size_t c = 0;
                std::size_t dir = 0;
                std::string out;
                for (std::size_t step = 0; step < total_rows * cols; ++step) {
                    out += g[r][c];
                    seen[r][c] = true;
                    const std::size_t nr = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    const std::size_t nc = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                    if (nr >= total_rows || nc >= cols || seen[nr][nc]) dir = (dir + 1) % 4;
                    r = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    c = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                }
                return out;
            }
            """,
            """
            LadderSpiral::LadderSpiral(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string LadderSpiral::normalized() const { return normalized_; }
            std::size_t LadderSpiral::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t r = 2;
                while (r * (r + 1) < n) ++r;
                return r;
            }
            std::size_t LadderSpiral::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t total_rows = rows();
                return (n + total_rows - 1) / total_rows;
            }
            std::vector<std::string> LadderSpiral::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                const std::size_t cols = columns();
                out.assign(total_rows, std::string(cols, '0'));
                for (std::size_t i = 0; i < n; ++i) out[i / cols][i % cols] = normalized_[i];
                return out;
            }
            std::string LadderSpiral::climb() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (const std::string& line : g) out += line;
                return out;
            }
            """,
            """
            LadderSpiral l("Grain rises through the chute");
            if (l.normalized() != "grainrisesthroughthechute") return 1;
            if (l.rows() != 5U) return 2;
            if (l.columns() != 5U) return 3;
            if (l.grid() != std::vector<std::string>{"grain", "rises", "throu", "ghthe", "chute"}) return 4;
            if (l.climb() != "chuteeusniargrtghthoesihr") return 5;
            LadderSpiral small("Silo 9");
            if (small.climb() != "lois") return 6;
            LadderSpiral empty("!!");
            if (empty.rows() != 0U) return 7;
            if (empty.climb() != "") return 8;
            return 0;
            """,
            """
            LadderSpiral n2(std::string(2, 'a'));
            if (n2.rows() != 2U) return 1;
            LadderSpiral n6(std::string(6, 'a'));
            if (n6.rows() != 2U) return 2;
            LadderSpiral n7(std::string(7, 'a'));
            if (n7.rows() != 3U) return 3;
            LadderSpiral n12(std::string(12, 'a'));
            if (n12.rows() != 3U) return 4;
            LadderSpiral n13(std::string(13, 'a'));
            if (n13.rows() != 4U) return 5;
            LadderSpiral n20(std::string(20, 'a'));
            if (n20.rows() != 4U) return 6;
            LadderSpiral n21(std::string(21, 'a'));
            if (n21.rows() != 5U) return 7;
            LadderSpiral l("Ladder rungs");
            if (l.climb() != "ngs0uddalerr") return 8;
            LadderSpiral one("q");
            if (one.climb() != "0q") return 9;
            return 0;
            """,
            "counterclockwise spiral from the bottom-left moving right, with zero padding",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and row-major reads",
            "rightward first move from the bottom-left, growth boundaries where r*(r+1) crosses the length, and zero padding",
            "a fourth distinct corner-rotation spiral combination in a paired .h/.cpp API",
            "spiral ring reader",
        ),
        c(
            "f26csq-fountain-ring-trace",
            "Fountain ring trace",
            "fountain_rings",
            """
            class TraceError : public std::invalid_argument {
            public:
                explicit TraceError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RingTrace {
            public:
                RingTrace(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string trace() const;
                std::string render() const;
            };
            """,
            """
            class TraceError : public std::invalid_argument {
            public:
                explicit TraceError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RingTrace {
            public:
                RingTrace(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string trace() const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            RingTrace::RingTrace(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 18) throw TraceError("width outside 1..18");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string RingTrace::normalized() const { return normalized_; }
            std::size_t RingTrace::width() const { return width_; }
            std::size_t RingTrace::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> RingTrace::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '~'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string RingTrace::trace() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                std::vector<std::vector<bool>> seen(total_rows, std::vector<bool>(cols, false));
                const int dr[4] = {0, -1, 0, 1};
                const int dc[4] = {-1, 0, 1, 0};
                std::size_t r = total_rows - 1;
                std::size_t c = cols - 1;
                std::size_t dir = 0;
                std::string out;
                for (std::size_t step = 0; step < total_rows * cols; ++step) {
                    out += g[r][c];
                    seen[r][c] = true;
                    const std::size_t nr = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    const std::size_t nc = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                    if (nr >= total_rows || nc >= cols || seen[nr][nc]) dir = (dir + 1) % 4;
                    r = static_cast<std::size_t>(static_cast<long>(r) + dr[dir]);
                    c = static_cast<std::size_t>(static_cast<long>(c) + dc[dir]);
                }
                return out;
            }
            std::string RingTrace::render() const {
                const std::string walked = trace();
                if (walked.empty()) return "";
                const std::size_t chunk = rows();
                std::string result;
                for (std::size_t start = 0; start < walked.size(); start += chunk) {
                    if (start != 0) result += '|';
                    result += walked.substr(start, chunk);
                }
                return result;
            }
            """,
            """
            RingTrace::RingTrace(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 18) throw TraceError("width outside 1..18");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string RingTrace::normalized() const { return normalized_; }
            std::size_t RingTrace::width() const { return width_; }
            std::size_t RingTrace::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> RingTrace::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '~'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string RingTrace::trace() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t cols = g[0].size();
                std::string out;
                for (std::size_t c = 0; c < cols; ++c)
                    for (const std::string& line : g) out += line[c];
                return out;
            }
            std::string RingTrace::render() const {
                const std::string walked = trace();
                if (walked.empty()) return "";
                const std::size_t chunk = rows();
                std::string result;
                for (std::size_t start = 0; start < walked.size(); start += chunk) {
                    if (start != 0) result += '|';
                    result += walked.substr(start, chunk);
                }
                return result;
            }
            """,
            """
            RingTrace t("Water arcs over the basin", 5);
            if (t.normalized() != "WATERARCSOVERTHEBASIN") return 1;
            if (t.width() != 5U) return 2;
            if (t.rows() != 5U) return 3;
            if (t.grid() != std::vector<std::string>{"WATER", "ARCSO", "VERTH", "EBASI", "N~~~~"}) return 4;
            if (t.trace() != "~~~~NEVAWATEROHISABERCSTR") return 5;
            if (t.render() != "~~~~N|EVAWA|TEROH|ISABE|RCSTR") return 6;
            RingTrace exact("ab cd", 2);
            if (exact.trace() != "DCAB") return 7;
            if (exact.render() != "DC|AB") return 8;
            RingTrace empty("!!", 3);
            if (empty.rows() != 0U) return 9;
            if (empty.render() != "") return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { RingTrace bad("abc", 0); } catch (const TraceError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RingTrace bad("abc", 19); } catch (const TraceError&) { threw = true; }
            if (!threw) return 2;
            RingTrace t("Fountain 8 jets", 4);
            if (t.trace() != "~~~S8TFOUNNTEJAI") return 3;
            if (t.render() != "~~~S|8TFO|UNNT|EJAI") return 4;
            RingTrace one("q", 3);
            if (one.trace() != "~~Q") return 5;
            if (one.render() != "~|~|Q") return 6;
            return 0;
            """,
            "clockwise spiral from the bottom-right moving left, with tilde padding and pipe chunking",
            "regex engines or third-party text-grid libraries, row-major reads, and column-major reads",
            "leftward first move, tilde padding, pipe grouping, and width validation at 0 and 19",
            "corner variety plus a column-major wrong substitute in a paired .h/.cpp API",
            "spiral ring reader",
        ),
        c(
            "f26csq-dovecote-perch-spiral",
            "Dovecote perch spiral",
            "dovecote_perches",
            """
            class PerchError : public std::invalid_argument {
            public:
                explicit PerchError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PerchSpiral {
            public:
                PerchSpiral(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> perches() const;
                std::vector<std::string> rings() const;
                std::string render() const;
            };
            """,
            """
            class PerchError : public std::invalid_argument {
            public:
                explicit PerchError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PerchSpiral {
            public:
                PerchSpiral(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> perches() const;
                std::vector<std::string> rings() const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t rows_;
            };
            """,
            """
            PerchSpiral::PerchSpiral(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 8) throw PerchError("row count outside 1..8");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string PerchSpiral::normalized() const { return normalized_; }
            std::size_t PerchSpiral::rows() const { return rows_; }
            std::size_t PerchSpiral::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> PerchSpiral::perches() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(rows_, std::string(cols, '='));
                for (std::size_t i = 0; i < n; ++i) out[i / cols][i % cols] = normalized_[i];
                return out;
            }
            std::vector<std::string> PerchSpiral::rings() const {
                const std::vector<std::string> g = perches();
                std::vector<std::string> out;
                if (g.empty()) return out;
                const std::size_t total_rows = g.size();
                const std::size_t cols = g[0].size();
                const std::size_t ring_count = (std::min(total_rows, cols) + 1) / 2;
                for (std::size_t k = 0; k < ring_count; ++k) {
                    const std::size_t top = k;
                    const std::size_t left = k;
                    const std::size_t bottom = total_rows - 1 - k;
                    const std::size_t right = cols - 1 - k;
                    std::string ring;
                    for (std::size_t c = left; c <= right; ++c) ring += g[top][c];
                    for (std::size_t r = top + 1; r <= bottom; ++r) ring += g[r][right];
                    if (bottom > top)
                        for (std::size_t step = 1; step <= right - left; ++step) ring += g[bottom][right - step];
                    if (right > left)
                        for (std::size_t step = 1; step < bottom - top; ++step) ring += g[bottom - step][left];
                    out.push_back(ring);
                }
                return out;
            }
            std::string PerchSpiral::render() const {
                const std::vector<std::string> out = rings();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += ';';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            PerchSpiral::PerchSpiral(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 8) throw PerchError("row count outside 1..8");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string PerchSpiral::normalized() const { return normalized_; }
            std::size_t PerchSpiral::rows() const { return rows_; }
            std::size_t PerchSpiral::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> PerchSpiral::perches() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                out.assign(rows_, std::string(cols, '='));
                for (std::size_t i = 0; i < n; ++i) out[i / cols][i % cols] = normalized_[i];
                return out;
            }
            std::vector<std::string> PerchSpiral::rings() const {
                const std::vector<std::string> g = perches();
                std::vector<std::string> out;
                for (const std::string& line : g) out.push_back(line);
                return out;
            }
            std::string PerchSpiral::render() const {
                const std::vector<std::string> out = rings();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += ';';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            PerchSpiral p("Doves circle the cote at dusk", 3);
            if (p.normalized() != "dovescirclethecoteatdusk") return 1;
            if (p.rows() != 3U) return 2;
            if (p.columns() != 8U) return 3;
            if (p.perches() != std::vector<std::string>{"dovescir", "cletheco", "teatdusk"}) return 4;
            if (p.rings() != std::vector<std::string>{"dovesciroksudtaetc", "lethec"}) return 5;
            if (p.render() != "dovesciroksudtaetc;lethec") return 6;
            PerchSpiral exact("ab cd", 2);
            if (exact.rings() != std::vector<std::string>{"abdc"}) return 7;
            if (exact.render() != "abdc") return 8;
            PerchSpiral empty("!!", 2);
            if (empty.columns() != 0U) return 9;
            if (empty.render() != "") return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { PerchSpiral bad("abc", 0); } catch (const PerchError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PerchSpiral bad("abc", 9); } catch (const PerchError&) { threw = true; }
            if (!threw) return 2;
            PerchSpiral p("Dove nest", 2);
            if (p.rings() != std::vector<std::string>{"dovetsen"}) return 3;
            if (p.render() != "dovetsen") return 4;
            PerchSpiral pad("Coo 7", 3);
            if (pad.rings() != std::vector<std::string>{"coo"}) return 5;
            if (pad.render() != "coo") return 6;
            PerchSpiral one("q", 4);
            if (one.render() != "q===") return 7;
            return 0;
            """,
            "per-ring clockwise spiral decomposition with equals padding and semicolon joining",
            "regex engines or third-party text-grid libraries, row-major reads, and flattened single-string output",
            "ring counts on odd and even grids, equals padding, row-count validation at 0 and 9, and empty inputs",
            "structured per-ring output beyond a flat traversal in a paired .h/.cpp API",
            "spiral ring reader",
        ),
        c(
            "f26csq-telegraph-tape-bands",
            "Telegraph tape bands",
            "telegraph_tape",
            """
            class TapeError : public std::invalid_argument {
            public:
                explicit TapeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TapeBands {
            public:
                TapeBands(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t band_count() const;
                std::vector<std::string> bands() const;
                std::string band(std::size_t index) const;
                std::string spliced() const;
            };
            """,
            """
            class TapeError : public std::invalid_argument {
            public:
                explicit TapeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TapeBands {
            public:
                TapeBands(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t band_count() const;
                std::vector<std::string> bands() const;
                std::string band(std::size_t index) const;
                std::string spliced() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            TapeBands::TapeBands(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 40) throw TapeError("width outside 1..40");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string TapeBands::normalized() const { return normalized_; }
            std::size_t TapeBands::width() const { return width_; }
            std::size_t TapeBands::band_count() const { return bands().size(); }
            std::vector<std::string> TapeBands::bands() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string TapeBands::band(std::size_t index) const {
                const std::vector<std::string> out = bands();
                if (index >= out.size()) throw TapeError("band index out of range");
                return out[index];
            }
            std::string TapeBands::spliced() const {
                const std::vector<std::string> out = bands();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += ' ';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            TapeBands::TapeBands(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 40) throw TapeError("width outside 1..40");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string TapeBands::normalized() const { return normalized_; }
            std::size_t TapeBands::width() const { return width_; }
            std::size_t TapeBands::band_count() const { return bands().size(); }
            std::vector<std::string> TapeBands::bands() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string TapeBands::band(std::size_t index) const {
                const std::vector<std::string> out = bands();
                if (index >= out.size()) throw TapeError("band index out of range");
                return out[index];
            }
            std::string TapeBands::spliced() const {
                std::vector<std::string> out = bands();
                if (!out.empty() && out.back().size() < width_)
                    out.back() += std::string(width_ - out.back().size(), '.');
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += ' ';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            TapeBands t("Stop the presses now", 4);
            if (t.normalized() != "STOPTHEPRESSESNOW") return 1;
            if (t.width() != 4U) return 2;
            if (t.band_count() != 5U) return 3;
            if (t.bands() != std::vector<std::string>{"STOP", "THEP", "RESS", "ESNO", "W"}) return 4;
            if (t.spliced() != "STOP THEP RESS ESNO W") return 5;
            TapeBands exact("a1b2c3d4", 2);
            if (exact.spliced() != "AB CD") return 6;
            TapeBands empty("123", 3);
            if (empty.band_count() != 0U) return 7;
            if (empty.spliced() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { TapeBands bad("abc", 0); } catch (const TapeError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TapeBands bad("abc", 41); } catch (const TapeError&) { threw = true; }
            if (!threw) return 2;
            TapeBands t("Morse code dots", 3);
            if (t.band(3) != "DOT") return 3;
            threw = false;
            try { t.band(5); } catch (const TapeError&) { threw = true; }
            if (!threw) return 4;
            if (t.spliced() != "MOR SEC ODE DOT S") return 5;
            TapeBands one("q", 6);
            if (one.spliced() != "Q") return 6;
            return 0;
            """,
            "caller-width ragged banding with space joining and no final-band padding",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "ragged final bands, exact-fit multiples, width validation at 0 and 41, index rejection, and empty inputs",
            "ragged grouping as the rejection discriminator in a paired .h/.cpp API",
            "ragged band grouper",
        ),
        c(
            "f26csq-newsprint-column-bands",
            "Newsprint column bands",
            "newsprint_columns",
            """
            class ColumnError : public std::domain_error {
            public:
                explicit ColumnError(const std::string& message) : std::domain_error(message) {}
            };
            class ColumnBands {
            public:
                explicit ColumnBands(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t band_count() const;
                std::vector<std::string> columns() const;
                std::string column(std::size_t index) const;
                std::string folded() const;
            };
            """,
            """
            class ColumnError : public std::domain_error {
            public:
                explicit ColumnError(const std::string& message) : std::domain_error(message) {}
            };
            class ColumnBands {
            public:
                explicit ColumnBands(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t band_count() const;
                std::vector<std::string> columns() const;
                std::string column(std::size_t index) const;
                std::string folded() const;
            private:
                std::string normalized_;
            };
            """,
            """
            ColumnBands::ColumnBands(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ColumnBands::normalized() const { return normalized_; }
            std::size_t ColumnBands::width() const { return 4; }
            std::size_t ColumnBands::band_count() const { return columns().size(); }
            std::vector<std::string> ColumnBands::columns() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += 4)
                    out.push_back(normalized_.substr(start, std::min(std::size_t{4}, normalized_.size() - start)));
                return out;
            }
            std::string ColumnBands::column(std::size_t index) const {
                const std::vector<std::string> out = columns();
                if (index >= out.size()) throw ColumnError("column index out of range");
                return out[index];
            }
            std::string ColumnBands::folded() const {
                const std::vector<std::string> out = columns();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '/';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            ColumnBands::ColumnBands(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ColumnBands::normalized() const { return normalized_; }
            std::size_t ColumnBands::width() const { return 4; }
            std::size_t ColumnBands::band_count() const { return columns().size(); }
            std::vector<std::string> ColumnBands::columns() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += 4)
                    out.push_back(normalized_.substr(start, std::min(std::size_t{4}, normalized_.size() - start)));
                return out;
            }
            std::string ColumnBands::column(std::size_t index) const {
                const std::vector<std::string> out = columns();
                if (index >= out.size()) throw ColumnError("column index out of range");
                return out[index];
            }
            std::string ColumnBands::folded() const {
                const std::vector<std::string> out = columns();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '/';
                    result += out[i];
                    if (out[i].size() < 4) result += std::string(4 - out[i].size(), '*');
                }
                return result;
            }
            """,
            """
            ColumnBands c("Evening edition ships late");
            if (c.normalized() != "eveningeditionshipslate") return 1;
            if (c.width() != 4U) return 2;
            if (c.band_count() != 6U) return 3;
            if (c.columns() != std::vector<std::string>{"even", "inge", "diti", "onsh", "ipsl", "ate"}) return 4;
            if (c.folded() != "even/inge/diti/onsh/ipsl/ate") return 5;
            ColumnBands exact("abcdefgh");
            if (exact.folded() != "abcd/efgh") return 6;
            ColumnBands empty("123");
            if (empty.band_count() != 0U) return 7;
            if (empty.folded() != "") return 8;
            return 0;
            """,
            """
            ColumnBands c("Headline news daily");
            if (c.column(2) != "news") return 1;
            bool threw = false;
            try { c.column(5); } catch (const ColumnError&) { threw = true; }
            if (!threw) return 2;
            if (c.folded() != "head/line/news/dail/y") return 3;
            ColumnBands three("abc");
            if (three.band_count() != 1U) return 4;
            if (three.folded() != "abc") return 5;
            ColumnBands five("abcde");
            if (five.folded() != "abcd/e") return 6;
            return 0;
            """,
            "fixed-width ragged banding with slash joining and no final-band padding",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "exact multiples of four, one-over-multiple raggedness, letter filtering, and index rejection",
            "fixed-width policy contrast with caller-width siblings in a paired .h/.cpp API",
            "ragged band grouper",
        ),
        c(
            "f26csq-seedpacket-label-runs",
            "Seedpacket label runs",
            "seed_labels",
            """
            class LabelError : public std::invalid_argument {
            public:
                explicit LabelError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LabelRuns {
            public:
                LabelRuns(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t run_count() const;
                std::vector<std::string> runs() const;
                std::string run(std::size_t index) const;
                std::string stamped() const;
            };
            """,
            """
            class LabelError : public std::invalid_argument {
            public:
                explicit LabelError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LabelRuns {
            public:
                LabelRuns(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t run_count() const;
                std::vector<std::string> runs() const;
                std::string run(std::size_t index) const;
                std::string stamped() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            LabelRuns::LabelRuns(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 12) throw LabelError("width outside 1..12");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string LabelRuns::normalized() const { return normalized_; }
            std::size_t LabelRuns::width() const { return width_; }
            std::size_t LabelRuns::run_count() const { return runs().size(); }
            std::vector<std::string> LabelRuns::runs() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string LabelRuns::run(std::size_t index) const {
                const std::vector<std::string> out = runs();
                if (index >= out.size()) throw LabelError("run index out of range");
                return out[index];
            }
            std::string LabelRuns::stamped() const {
                const std::vector<std::string> out = runs();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '-';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            LabelRuns::LabelRuns(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 12) throw LabelError("width outside 1..12");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string LabelRuns::normalized() const { return normalized_; }
            std::size_t LabelRuns::width() const { return width_; }
            std::size_t LabelRuns::run_count() const { return runs().size(); }
            std::vector<std::string> LabelRuns::runs() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string LabelRuns::run(std::size_t index) const {
                const std::vector<std::string> out = runs();
                if (index >= out.size()) throw LabelError("run index out of range");
                return out[index];
            }
            std::string LabelRuns::stamped() const {
                const std::vector<std::string> out = runs();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '-';
                    result += out[i];
                    if (out[i].size() < width_) result += std::string(width_ - out[i].size(), '#');
                }
                return result;
            }
            """,
            """
            LabelRuns l("Tomato seeds sow deep", 3);
            if (l.normalized() != "tomatoseedssowdeep") return 1;
            if (l.width() != 3U) return 2;
            if (l.run_count() != 6U) return 3;
            if (l.runs() != std::vector<std::string>{"tom", "ato", "see", "dss", "owd", "eep"}) return 4;
            if (l.stamped() != "tom-ato-see-dss-owd-eep") return 5;
            LabelRuns pad("Bean 7", 4);
            if (pad.stamped() != "bean-7") return 6;
            LabelRuns empty("!!", 2);
            if (empty.run_count() != 0U) return 7;
            if (empty.stamped() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { LabelRuns bad("abc", 0); } catch (const LabelError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LabelRuns bad("abc", 13); } catch (const LabelError&) { threw = true; }
            if (!threw) return 2;
            LabelRuns l("Carrot 22 row", 5);
            if (l.run(1) != "t22ro") return 3;
            threw = false;
            try { l.run(3); } catch (const LabelError&) { threw = true; }
            if (!threw) return 4;
            if (l.stamped() != "carro-t22ro-w") return 5;
            LabelRuns one("q", 1);
            if (one.stamped() != "q") return 6;
            return 0;
            """,
            "small-bound caller width with dash joining and no final-run padding",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "width validation at 0 and 13, ragged tails, dash joining, and index rejection",
            "tight validation bounds as boundary-input discipline in a paired .h/.cpp API",
            "ragged band grouper",
        ),
        c(
            "f26csq-ticket-stub-tears",
            "Ticket stub tears",
            "ticket_stubs",
            """
            class StubError : public std::domain_error {
            public:
                explicit StubError(const std::string& message) : std::domain_error(message) {}
            };
            class StubTears {
            public:
                explicit StubTears(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t tear_count() const;
                std::vector<std::string> stubs() const;
                std::string stub(std::size_t index) const;
                std::string torn() const;
            };
            """,
            """
            class StubError : public std::domain_error {
            public:
                explicit StubError(const std::string& message) : std::domain_error(message) {}
            };
            class StubTears {
            public:
                explicit StubTears(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t tear_count() const;
                std::vector<std::string> stubs() const;
                std::string stub(std::size_t index) const;
                std::string torn() const;
            private:
                std::string normalized_;
            };
            """,
            """
            StubTears::StubTears(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string StubTears::normalized() const { return normalized_; }
            std::size_t StubTears::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 6) return 2;
                if (n <= 15) return 3;
                if (n <= 28) return 4;
                return 5;
            }
            std::size_t StubTears::tear_count() const { return stubs().size(); }
            std::vector<std::string> StubTears::stubs() const {
                std::vector<std::string> out;
                const std::size_t w = width();
                if (w == 0) return out;
                for (std::size_t start = 0; start < normalized_.size(); start += w)
                    out.push_back(normalized_.substr(start, std::min(w, normalized_.size() - start)));
                return out;
            }
            std::string StubTears::stub(std::size_t index) const {
                const std::vector<std::string> out = stubs();
                if (index >= out.size()) throw StubError("stub index out of range");
                return out[index];
            }
            std::string StubTears::torn() const {
                const std::vector<std::string> out = stubs();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '|';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            StubTears::StubTears(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string StubTears::normalized() const { return normalized_; }
            std::size_t StubTears::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 6) return 2;
                if (n <= 15) return 3;
                if (n <= 28) return 4;
                return 5;
            }
            std::size_t StubTears::tear_count() const { return stubs().size(); }
            std::vector<std::string> StubTears::stubs() const {
                std::vector<std::string> out;
                const std::size_t w = width();
                if (w == 0) return out;
                for (std::size_t start = 0; start < normalized_.size(); start += w)
                    out.push_back(normalized_.substr(start, std::min(w, normalized_.size() - start)));
                return out;
            }
            std::string StubTears::stub(std::size_t index) const {
                const std::vector<std::string> out = stubs();
                if (index >= out.size()) throw StubError("stub index out of range");
                return out[index];
            }
            std::string StubTears::torn() const {
                const std::vector<std::string> out = stubs();
                const std::size_t w = width();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '|';
                    result += out[i];
                    if (out[i].size() < w) result += std::string(w - out[i].size(), '0');
                }
                return result;
            }
            """,
            """
            StubTears t("Matinee shows sell fast");
            if (t.normalized() != "MATINEESHOWSSELLFAST") return 1;
            if (t.width() != 4U) return 2;
            if (t.tear_count() != 5U) return 3;
            if (t.stubs() != std::vector<std::string>{"MATI", "NEES", "HOWS", "SELL", "FAST"}) return 4;
            if (t.torn() != "MATI|NEES|HOWS|SELL|FAST") return 5;
            StubTears small("Gate 7");
            if (small.width() != 2U) return 6;
            if (small.torn() != "GA|TE|7") return 7;
            StubTears empty("!!");
            if (empty.tear_count() != 0U) return 8;
            if (empty.torn() != "") return 9;
            return 0;
            """,
            """
            StubTears n6(std::string(6, 'a'));
            if (n6.width() != 2U) return 1;
            StubTears n7(std::string(7, 'a'));
            if (n7.width() != 3U) return 2;
            StubTears n15(std::string(15, 'a'));
            if (n15.width() != 3U) return 3;
            StubTears n16(std::string(16, 'a'));
            if (n16.width() != 4U) return 4;
            StubTears n28(std::string(28, 'a'));
            if (n28.width() != 4U) return 5;
            StubTears n29(std::string(29, 'a'));
            if (n29.width() != 5U) return 6;
            StubTears t("Balcony 3 row 9");
            if (t.stub(2) != "Y3R") return 7;
            bool threw = false;
            try { t.stub(4); } catch (const StubError&) { threw = true; }
            if (!threw) return 8;
            if (t.torn() != "BAL|CON|Y3R|OW9") return 9;
            return 0;
            """,
            "band-lookup width with pipe joining and no final-stub padding",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "band boundaries at 6/7, 15/16, and 28/29, ragged tails, and index rejection",
            "dimension-rule variety inside the ragged group in a paired .h/.cpp API",
            "ragged band grouper",
        ),
        c(
            "f26csq-blueprint-strip-bands",
            "Blueprint strip bands",
            "blueprint_strips",
            """
            class StripError : public std::invalid_argument {
            public:
                explicit StripError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StripBands {
            public:
                StripBands(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t strip_count() const;
                std::vector<std::string> strips() const;
                std::string strip(std::size_t index) const;
                std::string rolled() const;
            };
            """,
            """
            class StripError : public std::invalid_argument {
            public:
                explicit StripError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StripBands {
            public:
                StripBands(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t strip_count() const;
                std::vector<std::string> strips() const;
                std::string strip(std::size_t index) const;
                std::string rolled() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            StripBands::StripBands(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 36) throw StripError("width outside 1..36");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += '#';
                }
            }
            std::string StripBands::normalized() const { return normalized_; }
            std::size_t StripBands::width() const { return width_; }
            std::size_t StripBands::strip_count() const { return strips().size(); }
            std::vector<std::string> StripBands::strips() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string StripBands::strip(std::size_t index) const {
                const std::vector<std::string> out = strips();
                if (index >= out.size()) throw StripError("strip index out of range");
                return out[index];
            }
            std::string StripBands::rolled() const {
                const std::vector<std::string> out = strips();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += ' ';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            StripBands::StripBands(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 36) throw StripError("width outside 1..36");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                    else if (std::isdigit(byte)) normalized_ += '#';
                }
            }
            std::string StripBands::normalized() const { return normalized_; }
            std::size_t StripBands::width() const { return width_; }
            std::size_t StripBands::strip_count() const { return strips().size(); }
            std::vector<std::string> StripBands::strips() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string StripBands::strip(std::size_t index) const {
                const std::vector<std::string> out = strips();
                if (index >= out.size()) throw StripError("strip index out of range");
                return out[index];
            }
            std::string StripBands::rolled() const {
                std::vector<std::string> out = strips();
                if (!out.empty() && out.back().size() < width_)
                    out.back() += std::string(width_ - out.back().size(), '.');
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += ' ';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            StripBands s("North wall 22 meters", 4);
            if (s.normalized() != "northwall##meters") return 1;
            if (s.width() != 4U) return 2;
            if (s.strip_count() != 5U) return 3;
            if (s.strips() != std::vector<std::string>{"nort", "hwal", "l##m", "eter", "s"}) return 4;
            if (s.rolled() != "nort hwal l##m eter s") return 5;
            StripBands exact("gate77", 3);
            if (exact.rolled() != "gat e##") return 6;
            StripBands empty("!!", 2);
            if (empty.strip_count() != 0U) return 7;
            if (empty.rolled() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { StripBands bad("abc", 0); } catch (const StripError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { StripBands bad("abc", 37); } catch (const StripError&) { threw = true; }
            if (!threw) return 2;
            StripBands s("Beam 4 joist 8", 3);
            if (s.strip(1) != "m#j") return 3;
            threw = false;
            try { s.strip(4); } catch (const StripError&) { threw = true; }
            if (!threw) return 4;
            if (s.rolled() != "bea m#j ois t#") return 5;
            StripBands one("5", 2);
            if (one.rolled() != "#") return 6;
            return 0;
            """,
            "digit-mapping normalization with ragged strips and space joining",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "digit-to-hash mapping, width validation at 0 and 37, ragged tails, and index rejection",
            "character-mapping normalization inside ragged grouping in a paired .h/.cpp API",
            "ragged band grouper",
            project_support=True,
        ),
        c(
            "f26csq-carousel-ticket-runs",
            "Carousel ticket runs",
            "carousel_tickets",
            """
            class TicketError : public std::invalid_argument {
            public:
                explicit TicketError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TicketRuns {
            public:
                TicketRuns(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t run_count() const;
                std::vector<std::string> runs() const;
                std::string run(std::size_t index) const;
                std::string punched() const;
            };
            """,
            """
            class TicketError : public std::invalid_argument {
            public:
                explicit TicketError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TicketRuns {
            public:
                TicketRuns(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t run_count() const;
                std::vector<std::string> runs() const;
                std::string run(std::size_t index) const;
                std::string punched() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            TicketRuns::TicketRuns(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 20) throw TicketError("width outside 1..20");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string TicketRuns::normalized() const { return normalized_; }
            std::size_t TicketRuns::width() const { return width_; }
            std::size_t TicketRuns::run_count() const { return runs().size(); }
            std::vector<std::string> TicketRuns::runs() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string TicketRuns::run(std::size_t index) const {
                const std::vector<std::string> out = runs();
                if (index >= out.size()) throw TicketError("run index out of range");
                return out[index];
            }
            std::string TicketRuns::punched() const {
                const std::vector<std::string> out = runs();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += "..";
                    result += out[i];
                }
                return result;
            }
            """,
            """
            TicketRuns::TicketRuns(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 20) throw TicketError("width outside 1..20");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string TicketRuns::normalized() const { return normalized_; }
            std::size_t TicketRuns::width() const { return width_; }
            std::size_t TicketRuns::run_count() const { return runs().size(); }
            std::vector<std::string> TicketRuns::runs() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string TicketRuns::run(std::size_t index) const {
                const std::vector<std::string> out = runs();
                if (index >= out.size()) throw TicketError("run index out of range");
                return out[index];
            }
            std::string TicketRuns::punched() const {
                std::vector<std::string> out = runs();
                if (!out.empty() && out.back().size() < width_)
                    out.back() += std::string(width_ - out.back().size(), '*');
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += "..";
                    result += out[i];
                }
                return result;
            }
            """,
            """
            TicketRuns t("Brass rings spin twice", 5);
            if (t.normalized() != "brassringsspintwice") return 1;
            if (t.width() != 5U) return 2;
            if (t.run_count() != 4U) return 3;
            if (t.runs() != std::vector<std::string>{"brass", "rings", "spint", "wice"}) return 4;
            if (t.punched() != "brass..rings..spint..wice") return 5;
            TicketRuns exact("abcdef", 2);
            if (exact.punched() != "ab..cd..ef") return 6;
            TicketRuns empty("123", 2);
            if (empty.run_count() != 0U) return 7;
            if (empty.punched() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { TicketRuns bad("abc", 0); } catch (const TicketError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TicketRuns bad("abc", 21); } catch (const TicketError&) { threw = true; }
            if (!threw) return 2;
            TicketRuns t("Painted ponies gallop", 4);
            if (t.run(2) != "onie") return 3;
            threw = false;
            try { t.run(6); } catch (const TicketError&) { threw = true; }
            if (!threw) return 4;
            if (t.punched() != "pain..tedp..onie..sgal..lop") return 5;
            TicketRuns one("q", 3);
            if (one.punched() != "q") return 6;
            return 0;
            """,
            "double-dot joiner with ragged runs and caller width",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "exact joiner bytes, width validation at 0 and 21, ragged tails, and index rejection",
            "multi-character delimiters in exact output shapes in a paired .h/.cpp API",
            "ragged band grouper",
            project_support=True,
        ),
        c(
            "f26csq-stencil-strip-bands",
            "Stencil strip bands",
            "stencil_paint",
            """
            class PaintError : public std::invalid_argument {
            public:
                explicit PaintError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PaintBands {
            public:
                PaintBands(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t band_count() const;
                std::vector<std::string> bands() const;
                std::string band(std::size_t index) const;
                std::string sprayed() const;
            };
            """,
            """
            class PaintError : public std::invalid_argument {
            public:
                explicit PaintError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PaintBands {
            public:
                PaintBands(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t band_count() const;
                std::vector<std::string> bands() const;
                std::string band(std::size_t index) const;
                std::string sprayed() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            PaintBands::PaintBands(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 28) throw PaintError("width outside 1..28");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string PaintBands::normalized() const { return normalized_; }
            std::size_t PaintBands::width() const { return width_; }
            std::size_t PaintBands::band_count() const { return bands().size(); }
            std::vector<std::string> PaintBands::bands() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string PaintBands::band(std::size_t index) const {
                const std::vector<std::string> out = bands();
                if (index >= out.size()) throw PaintError("band index out of range");
                return out[index];
            }
            std::string PaintBands::sprayed() const {
                const std::vector<std::string> out = bands();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '=';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            PaintBands::PaintBands(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 28) throw PaintError("width outside 1..28");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string PaintBands::normalized() const { return normalized_; }
            std::size_t PaintBands::width() const { return width_; }
            std::size_t PaintBands::band_count() const { return bands().size(); }
            std::vector<std::string> PaintBands::bands() const {
                std::vector<std::string> out;
                for (std::size_t start = 0; start < normalized_.size(); start += width_)
                    out.push_back(normalized_.substr(start, std::min(width_, normalized_.size() - start)));
                return out;
            }
            std::string PaintBands::band(std::size_t index) const {
                const std::vector<std::string> out = bands();
                if (index >= out.size()) throw PaintError("band index out of range");
                return out[index];
            }
            std::string PaintBands::sprayed() const {
                std::vector<std::string> out = bands();
                if (!out.empty() && out.back().size() < width_)
                    out.back() += std::string(width_ - out.back().size(), '~');
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '=';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            PaintBands p("Wet paint keeps off", 3);
            if (p.normalized() != "WETPAINTKEEPSOFF") return 1;
            if (p.width() != 3U) return 2;
            if (p.band_count() != 6U) return 3;
            if (p.bands() != std::vector<std::string>{"WET", "PAI", "NTK", "EEP", "SOF", "F"}) return 4;
            if (p.sprayed() != "WET=PAI=NTK=EEP=SOF=F") return 5;
            PaintBands exact("abcd", 2);
            if (exact.sprayed() != "AB=CD") return 6;
            PaintBands empty("123", 4);
            if (empty.band_count() != 0U) return 7;
            if (empty.sprayed() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { PaintBands bad("abc", 0); } catch (const PaintError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PaintBands bad("abc", 29); } catch (const PaintError&) { threw = true; }
            if (!threw) return 2;
            PaintBands p("Fresh coats dry", 5);
            if (p.band(2) != "DRY") return 3;
            threw = false;
            try { p.band(3); } catch (const PaintError&) { threw = true; }
            if (!threw) return 4;
            if (p.sprayed() != "FRESH=COATS=DRY") return 5;
            PaintBands one("q", 7);
            if (one.sprayed() != "Q") return 6;
            return 0;
            """,
            "equals-joined ragged banding with caller width",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "joiner bytes, width validation at 0 and 29, ragged tails, and index rejection",
            "delimiter variety with the same ragged discipline in a paired .h/.cpp API",
            "ragged band grouper",
        ),
        c(
            "f26csq-postcard-panel-runs",
            "Postcard panel runs",
            "postcard_panels",
            """
            class PanelError : public std::domain_error {
            public:
                explicit PanelError(const std::string& message) : std::domain_error(message) {}
            };
            class PanelRuns {
            public:
                explicit PanelRuns(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t panel_count() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string posted() const;
            };
            """,
            """
            class PanelError : public std::domain_error {
            public:
                explicit PanelError(const std::string& message) : std::domain_error(message) {}
            };
            class PanelRuns {
            public:
                explicit PanelRuns(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t panel_count() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string posted() const;
            private:
                std::string normalized_;
            };
            """,
            """
            PanelRuns::PanelRuns(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string PanelRuns::normalized() const { return normalized_; }
            std::size_t PanelRuns::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n <= 24 ? 3 : 7;
            }
            std::size_t PanelRuns::panel_count() const { return panels().size(); }
            std::vector<std::string> PanelRuns::panels() const {
                std::vector<std::string> out;
                const std::size_t w = width();
                if (w == 0) return out;
                for (std::size_t start = 0; start < normalized_.size(); start += w)
                    out.push_back(normalized_.substr(start, std::min(w, normalized_.size() - start)));
                return out;
            }
            std::string PanelRuns::panel(std::size_t index) const {
                const std::vector<std::string> out = panels();
                if (index >= out.size()) throw PanelError("panel index out of range");
                return out[index];
            }
            std::string PanelRuns::posted() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '+';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            PanelRuns::PanelRuns(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string PanelRuns::normalized() const { return normalized_; }
            std::size_t PanelRuns::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n <= 24 ? 3 : 7;
            }
            std::size_t PanelRuns::panel_count() const { return panels().size(); }
            std::vector<std::string> PanelRuns::panels() const {
                std::vector<std::string> out;
                const std::size_t w = width();
                if (w == 0) return out;
                for (std::size_t start = 0; start < normalized_.size(); start += w)
                    out.push_back(normalized_.substr(start, std::min(w, normalized_.size() - start)));
                return out;
            }
            std::string PanelRuns::panel(std::size_t index) const {
                const std::vector<std::string> out = panels();
                if (index >= out.size()) throw PanelError("panel index out of range");
                return out[index];
            }
            std::string PanelRuns::posted() const {
                std::vector<std::string> out = panels();
                const std::size_t w = width();
                if (!out.empty() && out.back().size() < w)
                    out.back() += std::string(w - out.back().size(), '#');
                std::string result;
                for (std::size_t i = 0; i < out.size(); ++i) {
                    if (i != 0) result += '+';
                    result += out[i];
                }
                return result;
            }
            """,
            """
            PanelRuns p("Greetings from the seaside pier");
            if (p.normalized() != "greetingsfromtheseasidepier") return 1;
            if (p.width() != 7U) return 2;
            if (p.panel_count() != 4U) return 3;
            if (p.panels() != std::vector<std::string>{"greetin", "gsfromt", "heseasi", "depier"}) return 4;
            if (p.posted() != "greetin+gsfromt+heseasi+depier") return 5;
            PanelRuns small("Wish you 2");
            if (small.width() != 3U) return 6;
            if (small.posted() != "wis+hyo+u2") return 7;
            PanelRuns empty("!!");
            if (empty.panel_count() != 0U) return 8;
            if (empty.posted() != "") return 9;
            return 0;
            """,
            """
            PanelRuns b24(std::string(24, 'a'));
            if (b24.width() != 3U) return 1;
            PanelRuns b25(std::string(25, 'a'));
            if (b25.width() != 7U) return 2;
            PanelRuns p("Sunny beach 5 day");
            if (p.panel(3) != "h5d") return 3;
            bool threw = false;
            try { p.panel(5); } catch (const PanelError&) { threw = true; }
            if (!threw) return 4;
            if (p.posted() != "sun+nyb+eac+h5d+ay") return 5;
            PanelRuns one("q");
            if (one.posted() != "q") return 6;
            return 0;
            """,
            "two-step width rule with plus joining and no final-panel padding",
            "regex engines or third-party text-grid libraries and any final-band padding",
            "the 24/25 width boundary, ragged tails, index rejection, and empty inputs",
            "step-function dimensions inside ragged grouping in a paired .h/.cpp API",
            "ragged band grouper",
        ),
        c(
            "f26csq-marquee-letter-board",
            "Marquee letter board",
            "marquee_board",
            """
            class BoardError : public std::invalid_argument {
            public:
                explicit BoardError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LetterBoard {
            public:
                LetterBoard(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> board() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class BoardError : public std::invalid_argument {
            public:
                explicit BoardError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LetterBoard {
            public:
                LetterBoard(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> board() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            LetterBoard::LetterBoard(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 30) throw BoardError("width outside 1..30");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string LetterBoard::normalized() const { return normalized_; }
            std::size_t LetterBoard::width() const { return width_; }
            std::size_t LetterBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> LetterBoard::board() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string LetterBoard::row(std::size_t index) const {
                const std::vector<std::string> out = board();
                if (index >= out.size()) throw BoardError("row index out of range");
                return out[index];
            }
            std::string LetterBoard::render() const {
                const std::vector<std::string> out = board();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            LetterBoard::LetterBoard(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 30) throw BoardError("width outside 1..30");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string LetterBoard::normalized() const { return normalized_; }
            std::size_t LetterBoard::width() const { return width_; }
            std::size_t LetterBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> LetterBoard::board() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(std::string(width_ - used, '.') + body);
                }
                return out;
            }
            std::string LetterBoard::row(std::size_t index) const {
                const std::vector<std::string> out = board();
                if (index >= out.size()) throw BoardError("row index out of range");
                return out[index];
            }
            std::string LetterBoard::render() const {
                const std::vector<std::string> out = board();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            LetterBoard b("Now showing tonight", 5);
            if (b.normalized() != "NOWSHOWINGTONIGHT") return 1;
            if (b.width() != 5U) return 2;
            if (b.rows() != 4U) return 3;
            if (b.board() != std::vector<std::string>{"NOWSH", "OWING", "TONIG", "HT..."}) return 4;
            if (b.render() != "NOWSH\\nOWING\\nTONIG\\nHT...") return 5;
            LetterBoard exact("abcd", 2);
            if (exact.render() != "AB\\nCD") return 6;
            LetterBoard empty("123", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { LetterBoard bad("abc", 0); } catch (const BoardError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LetterBoard bad("abc", 31); } catch (const BoardError&) { threw = true; }
            if (!threw) return 2;
            LetterBoard b("Matinee at noon", 4);
            if (b.row(3) != "N...") return 3;
            threw = false;
            try { b.row(4); } catch (const BoardError&) { threw = true; }
            if (!threw) return 4;
            if (b.render() != "MATI\\nNEEA\\nTNOO\\nN...") return 5;
            LetterBoard one("q", 3);
            if (one.render() != "Q..") return 6;
            return 0;
            """,
            "right-side dot padding with exact newline grid render",
            "regex engines or third-party text-grid libraries, left or center padding, and trailing spaces",
            "exact-fit rows, partial-row right padding, width validation at 0 and 31, index rejection, and empty inputs",
            "named-side padding as the rejection discriminator in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-depot-sign-panels",
            "Depot sign panels",
            "depot_signs",
            """
            class SignError : public std::invalid_argument {
            public:
                explicit SignError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SignPanels {
            public:
                SignPanels(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class SignError : public std::invalid_argument {
            public:
                explicit SignError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SignPanels {
            public:
                SignPanels(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            SignPanels::SignPanels(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 24) throw SignError("width outside 1..24");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string SignPanels::normalized() const { return normalized_; }
            std::size_t SignPanels::width() const { return width_; }
            std::size_t SignPanels::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> SignPanels::panels() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(std::string(width_ - used, '*') + body);
                }
                return out;
            }
            std::string SignPanels::panel(std::size_t index) const {
                const std::vector<std::string> out = panels();
                if (index >= out.size()) throw SignError("panel index out of range");
                return out[index];
            }
            std::string SignPanels::render() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            SignPanels::SignPanels(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 24) throw SignError("width outside 1..24");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string SignPanels::normalized() const { return normalized_; }
            std::size_t SignPanels::width() const { return width_; }
            std::size_t SignPanels::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> SignPanels::panels() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(body + std::string(width_ - used, '*'));
                }
                return out;
            }
            std::string SignPanels::panel(std::size_t index) const {
                const std::vector<std::string> out = panels();
                if (index >= out.size()) throw SignError("panel index out of range");
                return out[index];
            }
            std::string SignPanels::render() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            SignPanels p("Track 9 north bound", 4);
            if (p.normalized() != "TRACK9NORTHBOUND") return 1;
            if (p.width() != 4U) return 2;
            if (p.rows() != 4U) return 3;
            if (p.panels() != std::vector<std::string>{"TRAC", "K9NO", "RTHB", "OUND"}) return 4;
            if (p.render() != "TRAC\\nK9NO\\nRTHB\\nOUND") return 5;
            SignPanels pad("Bus 7", 3);
            if (pad.panels() != std::vector<std::string>{"BUS", "**7"}) return 6;
            if (pad.render() != "BUS\\n**7") return 7;
            SignPanels empty("!!", 2);
            if (empty.rows() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { SignPanels bad("abc", 0); } catch (const SignError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SignPanels bad("abc", 25); } catch (const SignError&) { threw = true; }
            if (!threw) return 2;
            SignPanels p("Depot 42 east", 5);
            if (p.panel(2) != "****T") return 3;
            threw = false;
            try { p.panel(3); } catch (const SignError&) { threw = true; }
            if (!threw) return 4;
            if (p.render() != "DEPOT\\n42EAS\\n****T") return 5;
            SignPanels one("q", 2);
            if (one.render() != "*Q") return 6;
            return 0;
            """,
            "left-side star padding with exact newline grid render",
            "regex engines or third-party text-grid libraries, right or center padding",
            "left-side fill on partial rows, exact-fit rows, width validation at 0 and 25, and index rejection",
            "opposite padding side from the sibling board root in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-museum-plaque-grid",
            "Museum plaque grid",
            "museum_plaques",
            """
            class PlaqueError : public std::invalid_argument {
            public:
                explicit PlaqueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PlaqueGrid {
            public:
                PlaqueGrid(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> plaques() const;
                std::string plaque(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class PlaqueError : public std::invalid_argument {
            public:
                explicit PlaqueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PlaqueGrid {
            public:
                PlaqueGrid(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> plaques() const;
                std::string plaque(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t rows_;
            };
            """,
            """
            PlaqueGrid::PlaqueGrid(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 8) throw PlaqueError("row count outside 1..8");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string PlaqueGrid::normalized() const { return normalized_; }
            std::size_t PlaqueGrid::rows() const { return rows_; }
            std::size_t PlaqueGrid::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> PlaqueGrid::plaques() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t start = r * cols;
                    const std::string body = start < n ? normalized_.substr(start, std::min(cols, n - start)) : "";
                    out.push_back(body + std::string(cols - body.size(), '#'));
                }
                return out;
            }
            std::string PlaqueGrid::plaque(std::size_t index) const {
                if (index >= rows_) throw PlaqueError("plaque index out of range");
                return plaques()[index];
            }
            std::string PlaqueGrid::render() const {
                const std::vector<std::string> out = plaques();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += '[';
                    result += out[r];
                    result += ']';
                }
                return result;
            }
            """,
            """
            PlaqueGrid::PlaqueGrid(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 8) throw PlaqueError("row count outside 1..8");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string PlaqueGrid::normalized() const { return normalized_; }
            std::size_t PlaqueGrid::rows() const { return rows_; }
            std::size_t PlaqueGrid::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> PlaqueGrid::plaques() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t start = r * cols;
                    const std::string body = start < n ? normalized_.substr(start, std::min(cols, n - start)) : "";
                    out.push_back(std::string(cols - body.size(), '#') + body);
                }
                return out;
            }
            std::string PlaqueGrid::plaque(std::size_t index) const {
                if (index >= rows_) throw PlaqueError("plaque index out of range");
                return plaques()[index];
            }
            std::string PlaqueGrid::render() const {
                const std::vector<std::string> out = plaques();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += '[';
                    result += out[r];
                    result += ']';
                }
                return result;
            }
            """,
            """
            PlaqueGrid p("Bronze plaques mark the hall", 4);
            if (p.normalized() != "bronzeplaquesmarkthehall") return 1;
            if (p.rows() != 4U) return 2;
            if (p.columns() != 6U) return 3;
            if (p.plaques() != std::vector<std::string>{"bronze", "plaque", "smarkt", "hehall"}) return 4;
            if (p.render() != "[bronze]\\n[plaque]\\n[smarkt]\\n[hehall]") return 5;
            PlaqueGrid pad("Gallery", 2);
            if (pad.render() != "[gall]\\n[ery#]") return 6;
            PlaqueGrid empty("123", 3);
            if (empty.columns() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { PlaqueGrid bad("abc", 0); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PlaqueGrid bad("abc", 9); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 2;
            PlaqueGrid p("Stone carved names", 3);
            if (p.plaque(2) != "ames##") return 3;
            threw = false;
            try { p.plaque(3); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 4;
            if (p.render() != "[stonec]\\n[arvedn]\\n[ames##]") return 5;
            PlaqueGrid one("q", 3);
            if (one.render() != "[q]\\n[#]\\n[#]") return 6;
            return 0;
            """,
            "bracket-wrapped right hash padding with caller row counts",
            "regex engines or third-party text-grid libraries, left padding, and unwrapped renders",
            "bracket bytes, hash fill, row-count validation at 0 and 9, and index rejection",
            "wrapped exact shapes in a row-count-driven layout in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-theater-seat-chart",
            "Theater seat chart",
            "theater_seats",
            """
            class SeatError : public std::invalid_argument {
            public:
                explicit SeatError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SeatChart {
            public:
                SeatChart(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> chart() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class SeatError : public std::invalid_argument {
            public:
                explicit SeatError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SeatChart {
            public:
                SeatChart(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> chart() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            SeatChart::SeatChart(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 26) throw SeatError("width outside 1..26");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string SeatChart::normalized() const { return normalized_; }
            std::size_t SeatChart::width() const { return width_; }
            std::size_t SeatChart::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> SeatChart::chart() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '0'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string SeatChart::row(std::size_t index) const {
                const std::vector<std::string> out = chart();
                if (index >= out.size()) throw SeatError("row index out of range");
                return out[index];
            }
            std::string SeatChart::render() const {
                const std::vector<std::string> out = chart();
                std::string result;
                for (const std::string& line : out) {
                    result += line;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            SeatChart::SeatChart(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 26) throw SeatError("width outside 1..26");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                    else if (std::isdigit(byte)) normalized_ += ch;
                }
            }
            std::string SeatChart::normalized() const { return normalized_; }
            std::size_t SeatChart::width() const { return width_; }
            std::size_t SeatChart::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> SeatChart::chart() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(std::string(width_ - used, '0') + body);
                }
                return out;
            }
            std::string SeatChart::row(std::size_t index) const {
                const std::vector<std::string> out = chart();
                if (index >= out.size()) throw SeatError("row index out of range");
                return out[index];
            }
            std::string SeatChart::render() const {
                const std::vector<std::string> out = chart();
                std::string result;
                for (const std::string& line : out) {
                    result += line;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            SeatChart c("Row a aisle three", 4);
            if (c.normalized() != "ROWAAISLETHREE") return 1;
            if (c.width() != 4U) return 2;
            if (c.rows() != 4U) return 3;
            if (c.chart() != std::vector<std::string>{"ROWA", "AISL", "ETHR", "EE00"}) return 4;
            if (c.render() != "ROWA\\nAISL\\nETHR\\nEE00\\n") return 5;
            SeatChart exact("ab12", 2);
            if (exact.render() != "AB\\n12\\n") return 6;
            SeatChart empty("!!", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { SeatChart bad("abc", 0); } catch (const SeatError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SeatChart bad("abc", 27); } catch (const SeatError&) { threw = true; }
            if (!threw) return 2;
            SeatChart c("Balcony b seat 8", 3);
            if (c.row(4) != "800") return 3;
            threw = false;
            try { c.row(5); } catch (const SeatError&) { threw = true; }
            if (!threw) return 4;
            if (c.render() != "BAL\\nCON\\nYBS\\nEAT\\n800\\n") return 5;
            SeatChart one("q", 2);
            if (one.render() != "Q0\\n") return 6;
            return 0;
            """,
            "trailing-newline render policy with right zero padding",
            "regex engines or third-party text-grid libraries, left padding, and a missing trailing newline",
            "the exact trailing byte, zero fill, width validation at 0 and 27, and index rejection",
            "byte-exact trailing policy as part of the contract in a paired .h/.cpp API",
            "rectangle padding formatter",
            project_support=True,
        ),
        c(
            "f26csq-ferry-manifest-board",
            "Ferry manifest board",
            "ferry_board",
            """
            class FerryError : public std::domain_error {
            public:
                explicit FerryError(const std::string& message) : std::domain_error(message) {}
            };
            class ManifestBoard {
            public:
                explicit ManifestBoard(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> board() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class FerryError : public std::domain_error {
            public:
                explicit FerryError(const std::string& message) : std::domain_error(message) {}
            };
            class ManifestBoard {
            public:
                explicit ManifestBoard(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> board() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
            };
            """,
            """
            ManifestBoard::ManifestBoard(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ManifestBoard::normalized() const { return normalized_; }
            std::size_t ManifestBoard::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 9) return 3;
                if (n <= 16) return 4;
                if (n <= 25) return 5;
                return 8;
            }
            std::size_t ManifestBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> ManifestBoard::board() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % w != 0) ? n % w : w;
                    const std::string body = normalized_.substr(r * w, used);
                    out.push_back(std::string(w - used, '.') + body);
                }
                return out;
            }
            std::string ManifestBoard::row(std::size_t index) const {
                const std::vector<std::string> out = board();
                if (index >= out.size()) throw FerryError("row index out of range");
                return out[index];
            }
            std::string ManifestBoard::render() const {
                const std::vector<std::string> out = board();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            ManifestBoard::ManifestBoard(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ManifestBoard::normalized() const { return normalized_; }
            std::size_t ManifestBoard::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                if (n <= 9) return 3;
                if (n <= 16) return 4;
                if (n <= 25) return 5;
                return 8;
            }
            std::size_t ManifestBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> ManifestBoard::board() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % w != 0) ? n % w : w;
                    const std::string body = normalized_.substr(r * w, used);
                    out.push_back(body + std::string(w - used, '.'));
                }
                return out;
            }
            std::string ManifestBoard::row(std::size_t index) const {
                const std::vector<std::string> out = board();
                if (index >= out.size()) throw FerryError("row index out of range");
                return out[index];
            }
            std::string ManifestBoard::render() const {
                const std::vector<std::string> out = board();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            ManifestBoard b("Morning ferry leaves dock");
            if (b.normalized() != "morningferryleavesdock") return 1;
            if (b.width() != 5U) return 2;
            if (b.rows() != 5U) return 3;
            if (b.board() != std::vector<std::string>{"morni", "ngfer", "rylea", "vesdo", "...ck"}) return 4;
            if (b.render() != "morni\\nngfer\\nrylea\\nvesdo\\n...ck") return 5;
            ManifestBoard small("Tide 8am");
            if (small.width() != 3U) return 6;
            if (small.render() != "tid\\neam") return 7;
            ManifestBoard empty("123");
            if (empty.width() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            ManifestBoard n9(std::string(9, 'a'));
            if (n9.width() != 3U) return 1;
            ManifestBoard n10(std::string(10, 'a'));
            if (n10.width() != 4U) return 2;
            ManifestBoard n16(std::string(16, 'a'));
            if (n16.width() != 4U) return 3;
            ManifestBoard n17(std::string(17, 'a'));
            if (n17.width() != 5U) return 4;
            ManifestBoard n25(std::string(25, 'a'));
            if (n25.width() != 5U) return 5;
            ManifestBoard n26(std::string(26, 'a'));
            if (n26.width() != 8U) return 6;
            ManifestBoard b("Harbor lights dim");
            if (b.row(3) != ".dim") return 7;
            if (b.render() != "harb\\norli\\nghts\\n.dim") return 8;
            ManifestBoard one("q");
            if (one.render() != "..q") return 9;
            return 0;
            """,
            "band-lookup width with left dot padding",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and right padding",
            "band boundaries at 9/10, 16/17, and 25/26, left fill, index rejection, and empty inputs",
            "dimension-rule variety inside the padding group in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-scoreboard-line-panels",
            "Scoreboard line panels",
            "scoreboard_lines",
            """
            class ScoreError : public std::invalid_argument {
            public:
                explicit ScoreError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LinePanels {
            public:
                LinePanels(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class ScoreError : public std::invalid_argument {
            public:
                explicit ScoreError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LinePanels {
            public:
                LinePanels(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> panels() const;
                std::string panel(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            LinePanels::LinePanels(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 22) throw ScoreError("width outside 1..22");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string LinePanels::normalized() const { return normalized_; }
            std::size_t LinePanels::width() const { return width_; }
            std::size_t LinePanels::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> LinePanels::panels() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    const std::size_t pad = width_ - used;
                    out.push_back(std::string(pad / 2, '~') + body + std::string(pad - pad / 2, '~'));
                }
                return out;
            }
            std::string LinePanels::panel(std::size_t index) const {
                const std::vector<std::string> out = panels();
                if (index >= out.size()) throw ScoreError("panel index out of range");
                return out[index];
            }
            std::string LinePanels::render() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            LinePanels::LinePanels(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 22) throw ScoreError("width outside 1..22");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string LinePanels::normalized() const { return normalized_; }
            std::size_t LinePanels::width() const { return width_; }
            std::size_t LinePanels::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> LinePanels::panels() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(body + std::string(width_ - used, '~'));
                }
                return out;
            }
            std::string LinePanels::panel(std::size_t index) const {
                const std::vector<std::string> out = panels();
                if (index >= out.size()) throw ScoreError("panel index out of range");
                return out[index];
            }
            std::string LinePanels::render() const {
                const std::vector<std::string> out = panels();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            LinePanels l("Final score tied up", 6);
            if (l.normalized() != "FINALSCORETIEDUP") return 1;
            if (l.width() != 6U) return 2;
            if (l.rows() != 3U) return 3;
            if (l.panels() != std::vector<std::string>{"FINALS", "CORETI", "~EDUP~"}) return 4;
            if (l.render() != "FINALS\\nCORETI\\n~EDUP~") return 5;
            LinePanels odd("Win 7", 4);
            if (odd.render() != "WIN7") return 6;
            LinePanels edge("Tie 2", 5);
            if (edge.render() != "TIE2~") return 7;
            LinePanels empty("!!", 3);
            if (empty.rows() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { LinePanels bad("abc", 0); } catch (const ScoreError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LinePanels bad("abc", 23); } catch (const ScoreError&) { threw = true; }
            if (!threw) return 2;
            LinePanels l("Team a leads 3", 4);
            if (l.panel(2) != "DS3~") return 3;
            threw = false;
            try { l.panel(3); } catch (const ScoreError&) { threw = true; }
            if (!threw) return 4;
            if (l.render() != "TEAM\\nALEA\\nDS3~") return 5;
            LinePanels half("ab", 5);
            if (half.render() != "~AB~~") return 6;
            return 0;
            """,
            "right-leaning center padding with tilde fill",
            "regex engines or third-party text-grid libraries, one-sided padding, and left-leaning splits",
            "odd and even padding splits, exact-fit rows, width validation at 0 and 23, and index rejection",
            "split-padding policy distinct from one-sided siblings in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-bunkhouse-name-board",
            "Bunkhouse name board",
            "bunkhouse_names",
            """
            class BunkError : public std::invalid_argument {
            public:
                explicit BunkError(const std::string& message) : std::invalid_argument(message) {}
            };
            class NameBoard {
            public:
                NameBoard(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> board() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class BunkError : public std::invalid_argument {
            public:
                explicit BunkError(const std::string& message) : std::invalid_argument(message) {}
            };
            class NameBoard {
            public:
                NameBoard(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> board() const;
                std::string row(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            NameBoard::NameBoard(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 14) throw BunkError("width outside 1..14");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string NameBoard::normalized() const { return normalized_; }
            std::size_t NameBoard::width() const { return width_; }
            std::size_t NameBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> NameBoard::board() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(std::string(width_ - used, '#') + body);
                }
                return out;
            }
            std::string NameBoard::row(std::size_t index) const {
                const std::vector<std::string> out = board();
                if (index >= out.size()) throw BunkError("row index out of range");
                return out[index];
            }
            std::string NameBoard::render() const {
                const std::vector<std::string> out = board();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            NameBoard::NameBoard(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 14) throw BunkError("width outside 1..14");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string NameBoard::normalized() const { return normalized_; }
            std::size_t NameBoard::width() const { return width_; }
            std::size_t NameBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> NameBoard::board() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % width_ != 0) ? n % width_ : width_;
                    const std::string body = normalized_.substr(r * width_, used);
                    out.push_back(body + std::string(width_ - used, '#'));
                }
                return out;
            }
            std::string NameBoard::row(std::size_t index) const {
                const std::vector<std::string> out = board();
                if (index >= out.size()) throw BunkError("row index out of range");
                return out[index];
            }
            std::string NameBoard::render() const {
                const std::vector<std::string> out = board();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            NameBoard b("Bunk 7 upper 3 lower", 4);
            if (b.normalized() != "bunkupperlower") return 1;
            if (b.width() != 4U) return 2;
            if (b.rows() != 4U) return 3;
            if (b.board() != std::vector<std::string>{"bunk", "uppe", "rlow", "##er"}) return 4;
            if (b.render() != "bunk\\nuppe\\nrlow\\n##er") return 5;
            NameBoard exact("abcd", 2);
            if (exact.render() != "ab\\ncd") return 6;
            NameBoard empty("42", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.render() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { NameBoard bad("abc", 0); } catch (const BunkError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { NameBoard bad("abc", 15); } catch (const BunkError&) { threw = true; }
            if (!threw) return 2;
            NameBoard b("Cabin 9 west", 3);
            if (b.row(1) != "inw") return 3;
            threw = false;
            try { b.row(3); } catch (const BunkError&) { threw = true; }
            if (!threw) return 4;
            if (b.render() != "cab\\ninw\\nest") return 5;
            NameBoard pad("Loft 2", 5);
            if (pad.render() != "#loft") return 6;
            return 0;
            """,
            "letter-only filtering with left hash padding",
            "regex engines or third-party text-grid libraries, right padding, and digit retention",
            "digit dropping, left fill, width validation at 0 and 15, and index rejection",
            "normalization filtering combined with padding-side discipline in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-workshop-tag-board",
            "Workshop tag board",
            "workshop_tags",
            """
            class TagError : public std::domain_error {
            public:
                explicit TagError(const std::string& message) : std::domain_error(message) {}
            };
            class TagBoard {
            public:
                explicit TagBoard(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> tags() const;
                std::string tag(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class TagError : public std::domain_error {
            public:
                explicit TagError(const std::string& message) : std::domain_error(message) {}
            };
            class TagBoard {
            public:
                explicit TagBoard(const std::string& raw);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> tags() const;
                std::string tag(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
            };
            """,
            """
            TagBoard::TagBoard(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string TagBoard::normalized() const { return normalized_; }
            std::size_t TagBoard::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 2;
                while (w * (w + 1) < n) ++w;
                return w;
            }
            std::size_t TagBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> TagBoard::tags() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % w != 0) ? n % w : w;
                    out.push_back(normalized_.substr(r * w, used) + std::string(w - used, '*'));
                }
                return out;
            }
            std::string TagBoard::tag(std::size_t index) const {
                const std::vector<std::string> out = tags();
                if (index >= out.size()) throw TagError("tag index out of range");
                return out[index];
            }
            std::string TagBoard::render() const {
                const std::vector<std::string> out = tags();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            TagBoard::TagBoard(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string TagBoard::normalized() const { return normalized_; }
            std::size_t TagBoard::width() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                std::size_t w = 2;
                while (w * (w + 1) < n) ++w;
                return w;
            }
            std::size_t TagBoard::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                const std::size_t w = width();
                return (n + w - 1) / w;
            }
            std::vector<std::string> TagBoard::tags() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t w = width();
                const std::size_t total_rows = rows();
                for (std::size_t r = 0; r < total_rows; ++r) {
                    const std::size_t used = (r == total_rows - 1 && n % w != 0) ? n % w : w;
                    out.push_back(std::string(w - used, '*') + normalized_.substr(r * w, used));
                }
                return out;
            }
            std::string TagBoard::tag(std::size_t index) const {
                const std::vector<std::string> out = tags();
                if (index >= out.size()) throw TagError("tag index out of range");
                return out[index];
            }
            std::string TagBoard::render() const {
                const std::vector<std::string> out = tags();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            TagBoard t("Hammers hang by the bench");
            if (t.normalized() != "hammershangbythebench") return 1;
            if (t.width() != 5U) return 2;
            if (t.rows() != 5U) return 3;
            if (t.tags() != std::vector<std::string>{"hamme", "rshan", "gbyth", "ebenc", "h****"}) return 4;
            if (t.render() != "hamme\\nrshan\\ngbyth\\nebenc\\nh****") return 5;
            TagBoard small("Awl 3");
            if (small.width() != 2U) return 6;
            if (small.render() != "aw\\nl3") return 7;
            TagBoard empty("!!");
            if (empty.width() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            TagBoard n6(std::string(6, 'a'));
            if (n6.width() != 2U) return 1;
            TagBoard n7(std::string(7, 'a'));
            if (n7.width() != 3U) return 2;
            TagBoard n12(std::string(12, 'a'));
            if (n12.width() != 3U) return 3;
            TagBoard n13(std::string(13, 'a'));
            if (n13.width() != 4U) return 4;
            TagBoard n20(std::string(20, 'a'));
            if (n20.width() != 4U) return 5;
            TagBoard n31(std::string(31, 'a'));
            if (n31.width() != 6U) return 6;
            TagBoard t("Drill 8 bits");
            if (t.tag(3) != "s**") return 7;
            if (t.render() != "dri\\nll8\\nbit\\ns**") return 8;
            TagBoard one("q");
            if (one.render() != "q*") return 9;
            return 0;
            """,
            "growth-rule width with right star padding",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and left padding",
            "growth boundaries where w*(w+1) crosses the length, right fill, index rejection, and empty inputs",
            "caller-free dimensions inside the padding group in a paired .h/.cpp API",
            "rectangle padding formatter",
        ),
        c(
            "f26csq-bulletin-notice-grid",
            "Bulletin notice grid",
            "bulletin_notices",
            """
            class NoticeError : public std::invalid_argument {
            public:
                explicit NoticeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class NoticeGrid {
            public:
                NoticeGrid(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> notices() const;
                std::string notice(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class NoticeError : public std::invalid_argument {
            public:
                explicit NoticeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class NoticeGrid {
            public:
                NoticeGrid(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::vector<std::string> notices() const;
                std::string notice(std::size_t index) const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t rows_;
            };
            """,
            """
            NoticeGrid::NoticeGrid(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 7) throw NoticeError("row count outside 1..7");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string NoticeGrid::normalized() const { return normalized_; }
            std::size_t NoticeGrid::rows() const { return rows_; }
            std::size_t NoticeGrid::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> NoticeGrid::notices() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t start = r * cols;
                    const std::string body = start < n ? normalized_.substr(start, std::min(cols, n - start)) : "";
                    const std::size_t pad = cols - body.size();
                    out.push_back(std::string(pad - pad / 2, '.') + body + std::string(pad / 2, '.'));
                }
                return out;
            }
            std::string NoticeGrid::notice(std::size_t index) const {
                if (index >= rows_) throw NoticeError("notice index out of range");
                return notices()[index];
            }
            std::string NoticeGrid::render() const {
                const std::vector<std::string> out = notices();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            NoticeGrid::NoticeGrid(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 7) throw NoticeError("row count outside 1..7");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string NoticeGrid::normalized() const { return normalized_; }
            std::size_t NoticeGrid::rows() const { return rows_; }
            std::size_t NoticeGrid::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::vector<std::string> NoticeGrid::notices() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t cols = columns();
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t start = r * cols;
                    const std::string body = start < n ? normalized_.substr(start, std::min(cols, n - start)) : "";
                    out.push_back(std::string(cols - body.size(), '.') + body);
                }
                return out;
            }
            std::string NoticeGrid::notice(std::size_t index) const {
                if (index >= rows_) throw NoticeError("notice index out of range");
                return notices()[index];
            }
            std::string NoticeGrid::render() const {
                const std::vector<std::string> out = notices();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += out[r];
                }
                return result;
            }
            """,
            """
            NoticeGrid n("Lost cat seen near elm", 3);
            if (n.normalized() != "LOSTCATSEENNEARELM") return 1;
            if (n.rows() != 3U) return 2;
            if (n.columns() != 6U) return 3;
            if (n.notices() != std::vector<std::string>{"LOSTCA", "TSEENN", "EARELM"}) return 4;
            if (n.render() != "LOSTCA\\nTSEENN\\nEARELM") return 5;
            NoticeGrid pad("Found keys", 2);
            if (pad.render() != "FOUND\\n.KEYS") return 6;
            NoticeGrid odd("Garage sale", 4);
            if (odd.render() != "GAR\\nAGE\\nSAL\\n.E.") return 7;
            NoticeGrid empty("123", 2);
            if (empty.columns() != 0U) return 8;
            if (empty.render() != "") return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { NoticeGrid bad("abc", 0); } catch (const NoticeError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { NoticeGrid bad("abc", 8); } catch (const NoticeError&) { threw = true; }
            if (!threw) return 2;
            NoticeGrid n("Yard sale sat", 5);
            if (n.notice(3) != ".AT") return 3;
            threw = false;
            try { n.notice(5); } catch (const NoticeError&) { threw = true; }
            if (!threw) return 4;
            if (n.render() != "YAR\\nDSA\\nLES\\n.AT\\n...") return 5;
            NoticeGrid half("ab", 3);
            if (half.render() != "A\\nB\\n.") return 6;
            NoticeGrid lean("abc", 2);
            if (lean.render() != "AB\\n.C") return 7;
            return 0;
            """,
            "left-leaning center padding with dot fill and caller row counts",
            "regex engines or third-party text-grid libraries, one-sided padding, and right-leaning splits",
            "odd and even padding splits, row-count validation at 0 and 8, and index rejection",
            "opposite lean from the scoreboard sibling as a distinct contract in a paired .h/.cpp API",
            "rectangle padding formatter",
            project_support=True,
        ),
        c(
            "f26csq-parcel-grid-measure",
            "Parcel grid measure",
            "parcel_measure",
            """
            class MeasureError : public std::invalid_argument {
            public:
                explicit MeasureError(const std::string& message) : std::invalid_argument(message) {}
            };
            class GridMeasure {
            public:
                GridMeasure(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            };
            """,
            """
            class MeasureError : public std::invalid_argument {
            public:
                explicit MeasureError(const std::string& message) : std::invalid_argument(message) {}
            };
            class GridMeasure {
            public:
                GridMeasure(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            GridMeasure::GridMeasure(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 50) throw MeasureError("width outside 1..50");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string GridMeasure::normalized() const { return normalized_; }
            std::size_t GridMeasure::width() const { return width_; }
            std::size_t GridMeasure::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::size_t GridMeasure::padding() const { return rows() * width_ - normalized_.size(); }
            std::string GridMeasure::plan() const {
                return "rows=" + std::to_string(rows()) + ";cols=" + std::to_string(width_)
                    + ";pad=" + std::to_string(padding());
            }
            std::string GridMeasure::template_grid() const {
                const std::size_t total_rows = rows();
                std::string result;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(width_, '.');
                }
                return result;
            }
            """,
            """
            GridMeasure::GridMeasure(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 50) throw MeasureError("width outside 1..50");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string GridMeasure::normalized() const { return normalized_; }
            std::size_t GridMeasure::width() const { return width_; }
            std::size_t GridMeasure::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n / width_;
            }
            std::size_t GridMeasure::padding() const { return rows() * width_ - normalized_.size(); }
            std::string GridMeasure::plan() const {
                return "rows=" + std::to_string(rows()) + ";cols=" + std::to_string(width_)
                    + ";pad=" + std::to_string(padding());
            }
            std::string GridMeasure::template_grid() const {
                const std::size_t total_rows = rows();
                std::string result;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(width_, '.');
                }
                return result;
            }
            """,
            """
            GridMeasure m("Parcels stack in the bay", 5);
            if (m.normalized() != "parcelsstackinthebay") return 1;
            if (m.width() != 5U) return 2;
            if (m.rows() != 4U) return 3;
            if (m.padding() != 0U) return 4;
            if (m.plan() != "rows=4;cols=5;pad=0") return 5;
            if (m.template_grid() != ".....\\n.....\\n.....\\n.....") return 6;
            GridMeasure pad("Crates 9", 4);
            if (pad.rows() != 2U) return 7;
            if (pad.padding() != 1U) return 8;
            if (pad.plan() != "rows=2;cols=4;pad=1") return 9;
            GridMeasure empty("!!", 3);
            if (empty.plan() != "rows=0;cols=3;pad=0") return 10;
            if (empty.template_grid() != "") return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { GridMeasure bad("abc", 0); } catch (const MeasureError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { GridMeasure bad("abc", 51); } catch (const MeasureError&) { threw = true; }
            if (!threw) return 2;
            GridMeasure m("Box 12 crate 34", 3);
            if (m.plan() != "rows=4;cols=3;pad=0") return 3;
            GridMeasure one("q", 6);
            if (one.plan() != "rows=1;cols=6;pad=5") return 4;
            if (one.template_grid() != "......") return 5;
            GridMeasure t("ab", 2);
            if (t.template_grid() != "..") return 6;
            return 0;
            """,
            "ceiling row division with an exact labeled plan string and dot template",
            "regex engines or third-party text-grid libraries and truncating division",
            "partial final rows, exact multiples, empty input plans, template shapes, and width validation at 0 and 51",
            "exact labeled plan output plus a fill template in a paired .h/.cpp API",
            "grid plan calculator",
        ),
        c(
            "f26csq-banner-width-planner",
            "Banner width planner",
            "banner_planner",
            """
            class PlannerError : public std::invalid_argument {
            public:
                explicit PlannerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WidthPlanner {
            public:
                WidthPlanner(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::size_t short_count() const;
                std::string plan() const;
                std::string template_grid() const;
            };
            """,
            """
            class PlannerError : public std::invalid_argument {
            public:
                explicit PlannerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WidthPlanner {
            public:
                WidthPlanner(const std::string& raw, std::size_t rows);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::size_t short_count() const;
                std::string plan() const;
                std::string template_grid() const;
            private:
                std::string normalized_;
                std::size_t rows_;
            };
            """,
            """
            WidthPlanner::WidthPlanner(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 11) throw PlannerError("row count outside 1..11");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string WidthPlanner::normalized() const { return normalized_; }
            std::size_t WidthPlanner::rows() const { return rows_; }
            std::size_t WidthPlanner::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + rows_ - 1) / rows_;
            }
            std::size_t WidthPlanner::short_count() const { return rows_ * columns() - normalized_.size(); }
            std::string WidthPlanner::plan() const {
                return "cols=" + std::to_string(columns()) + ";rows=" + std::to_string(rows_)
                    + ";short=" + std::to_string(short_count());
            }
            std::string WidthPlanner::template_grid() const {
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t r = 0; r < rows_ && cols != 0; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(cols, '#');
                }
                return result;
            }
            """,
            """
            WidthPlanner::WidthPlanner(const std::string& raw, std::size_t rows) : rows_(rows) {
                if (rows == 0 || rows > 11) throw PlannerError("row count outside 1..11");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string WidthPlanner::normalized() const { return normalized_; }
            std::size_t WidthPlanner::rows() const { return rows_; }
            std::size_t WidthPlanner::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n / rows_;
            }
            std::size_t WidthPlanner::short_count() const { return rows_ * columns() - normalized_.size(); }
            std::string WidthPlanner::plan() const {
                return "cols=" + std::to_string(columns()) + ";rows=" + std::to_string(rows_)
                    + ";short=" + std::to_string(short_count());
            }
            std::string WidthPlanner::template_grid() const {
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t r = 0; r < rows_ && cols != 0; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(cols, '#');
                }
                return result;
            }
            """,
            """
            WidthPlanner w("Sale ends soon", 3);
            if (w.normalized() != "SALEENDSSOON") return 1;
            if (w.rows() != 3U) return 2;
            if (w.columns() != 4U) return 3;
            if (w.short_count() != 0U) return 4;
            if (w.plan() != "cols=4;rows=3;short=0") return 5;
            if (w.template_grid() != "####\\n####\\n####") return 6;
            WidthPlanner pad("Fest 5", 3);
            if (pad.columns() != 2U) return 7;
            if (pad.short_count() != 2U) return 8;
            if (pad.plan() != "cols=2;rows=3;short=2") return 9;
            WidthPlanner empty("!!", 2);
            if (empty.plan() != "cols=0;rows=2;short=0") return 10;
            if (empty.template_grid() != "") return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { WidthPlanner bad("abc", 0); } catch (const PlannerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { WidthPlanner bad("abc", 12); } catch (const PlannerError&) { threw = true; }
            if (!threw) return 2;
            WidthPlanner w("Gala 8 night", 2);
            if (w.plan() != "cols=5;rows=2;short=1") return 3;
            WidthPlanner one("q", 4);
            if (one.plan() != "cols=1;rows=4;short=3") return 4;
            if (one.template_grid() != "#\\n#\\n#\\n#") return 5;
            return 0;
            """,
            "row-count-driven ceiling columns with an exact plan string and hash template",
            "regex engines or third-party text-grid libraries and truncating division",
            "ceiling columns, hash templates, empty inputs, and row-count validation at 0 and 12",
            "the inverse dimension direction from the parcel sibling in a paired .h/.cpp API",
            "grid plan calculator",
        ),
        c(
            "f26csq-tilefloor-grid-estimator",
            "Tilefloor grid estimator",
            "tilefloor_estimator",
            """
            class EstimatorError : public std::domain_error {
            public:
                explicit EstimatorError(const std::string& message) : std::domain_error(message) {}
            };
            class GridEstimator {
            public:
                explicit GridEstimator(const std::string& raw);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            };
            """,
            """
            class EstimatorError : public std::domain_error {
            public:
                explicit EstimatorError(const std::string& message) : std::domain_error(message) {}
            };
            class GridEstimator {
            public:
                explicit GridEstimator(const std::string& raw);
                std::string normalized() const;
                std::size_t rows() const;
                std::size_t columns() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            private:
                std::string normalized_;
            };
            """,
            """
            GridEstimator::GridEstimator(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string GridEstimator::normalized() const { return normalized_; }
            std::size_t GridEstimator::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + 2) / 3;
            }
            std::size_t GridEstimator::columns() const { return 3; }
            std::size_t GridEstimator::padding() const { return rows() * 3 - normalized_.size(); }
            std::string GridEstimator::plan() const {
                return "rows=" + std::to_string(rows()) + ";cols=3;pad=" + std::to_string(padding());
            }
            std::string GridEstimator::template_grid() const {
                const std::size_t total_rows = rows();
                std::string result;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    if (r != 0) result += '\\n';
                    result += "000";
                }
                return result;
            }
            """,
            """
            GridEstimator::GridEstimator(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string GridEstimator::normalized() const { return normalized_; }
            std::size_t GridEstimator::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n / 3;
            }
            std::size_t GridEstimator::columns() const { return 3; }
            std::size_t GridEstimator::padding() const { return rows() * 3 - normalized_.size(); }
            std::string GridEstimator::plan() const {
                return "rows=" + std::to_string(rows()) + ";cols=3;pad=" + std::to_string(padding());
            }
            std::string GridEstimator::template_grid() const {
                const std::size_t total_rows = rows();
                std::string result;
                for (std::size_t r = 0; r < total_rows; ++r) {
                    if (r != 0) result += '\\n';
                    result += "000";
                }
                return result;
            }
            """,
            """
            GridEstimator e("Tiles cover the mudroom");
            if (e.normalized() != "tilescoverthemudroom") return 1;
            if (e.rows() != 7U) return 2;
            if (e.columns() != 3U) return 3;
            if (e.padding() != 1U) return 4;
            if (e.plan() != "rows=7;cols=3;pad=1") return 5;
            if (e.template_grid() != "000\\n000\\n000\\n000\\n000\\n000\\n000") return 6;
            GridEstimator exact("abc123");
            if (exact.plan() != "rows=2;cols=3;pad=0") return 7;
            GridEstimator empty("!!");
            if (empty.plan() != "rows=0;cols=3;pad=0") return 8;
            if (empty.template_grid() != "") return 9;
            return 0;
            """,
            """
            GridEstimator one("q");
            if (one.plan() != "rows=1;cols=3;pad=2") return 1;
            if (one.template_grid() != "000") return 2;
            GridEstimator two("ab");
            if (two.plan() != "rows=1;cols=3;pad=1") return 3;
            GridEstimator nine("abcdefghi");
            if (nine.plan() != "rows=3;cols=3;pad=0") return 4;
            GridEstimator ten("abcdefghij");
            if (ten.plan() != "rows=4;cols=3;pad=2") return 5;
            return 0;
            """,
            "fixed-column ceiling plan with zero template",
            "regex engines or third-party text-grid libraries, the official benchmark rectangle rule, and truncating division",
            "multiples of three, one-over-multiple padding, zero templates, and empty inputs",
            "fixed-width plan policy contrast with caller-driven siblings in a paired .h/.cpp API",
            "grid plan calculator",
            project_support=True,
        ),
        c(
            "f26csq-shelf-run-planner",
            "Shelf run planner",
            "shelf_runs",
            """
            class RunError : public std::invalid_argument {
            public:
                explicit RunError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RunPlanner {
            public:
                RunPlanner(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t runs() const;
                std::size_t leftover() const;
                std::string plan() const;
                std::string template_grid() const;
            };
            """,
            """
            class RunError : public std::invalid_argument {
            public:
                explicit RunError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RunPlanner {
            public:
                RunPlanner(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t runs() const;
                std::size_t leftover() const;
                std::string plan() const;
                std::string template_grid() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            RunPlanner::RunPlanner(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 16) throw RunError("width outside 1..16");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string RunPlanner::normalized() const { return normalized_; }
            std::size_t RunPlanner::width() const { return width_; }
            std::size_t RunPlanner::runs() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::size_t RunPlanner::leftover() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n - (runs() - 1) * width_;
            }
            std::string RunPlanner::plan() const {
                return "runs=" + std::to_string(runs()) + ";span=" + std::to_string(width_)
                    + ";leftover=" + std::to_string(leftover());
            }
            std::string RunPlanner::template_grid() const {
                const std::size_t total = runs();
                std::string result;
                for (std::size_t r = 0; r < total; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(width_, '.');
                }
                return result;
            }
            """,
            """
            RunPlanner::RunPlanner(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 16) throw RunError("width outside 1..16");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string RunPlanner::normalized() const { return normalized_; }
            std::size_t RunPlanner::width() const { return width_; }
            std::size_t RunPlanner::runs() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::size_t RunPlanner::leftover() const { return runs() * width_ - normalized_.size(); }
            std::string RunPlanner::plan() const {
                return "runs=" + std::to_string(runs()) + ";span=" + std::to_string(width_)
                    + ";leftover=" + std::to_string(leftover());
            }
            std::string RunPlanner::template_grid() const {
                const std::size_t total = runs();
                std::string result;
                for (std::size_t r = 0; r < total; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(width_, '.');
                }
                return result;
            }
            """,
            """
            RunPlanner s("Novels stack the shelf", 5);
            if (s.normalized() != "NOVELSSTACKTHESHELF") return 1;
            if (s.width() != 5U) return 2;
            if (s.runs() != 4U) return 3;
            if (s.leftover() != 4U) return 4;
            if (s.plan() != "runs=4;span=5;leftover=4") return 5;
            if (s.template_grid() != ".....\\n.....\\n.....\\n.....") return 6;
            RunPlanner exact("abcdef", 3);
            if (exact.leftover() != 3U) return 7;
            if (exact.plan() != "runs=2;span=3;leftover=3") return 8;
            RunPlanner empty("!!", 2);
            if (empty.leftover() != 0U) return 9;
            if (empty.plan() != "runs=0;span=2;leftover=0") return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { RunPlanner bad("abc", 0); } catch (const RunError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RunPlanner bad("abc", 17); } catch (const RunError&) { threw = true; }
            if (!threw) return 2;
            RunPlanner s("Atlas 42 maps", 4);
            if (s.plan() != "runs=3;span=4;leftover=1") return 3;
            RunPlanner one("q", 6);
            if (one.plan() != "runs=1;span=6;leftover=1") return 4;
            if (one.template_grid() != "......") return 5;
            return 0;
            """,
            "final-run length accounting with an exact plan string and dot template",
            "regex engines or third-party text-grid libraries, reporting pad count as leftover, and truncating division",
            "leftover on exact fits and partial runs, empty inputs, and width validation at 0 and 17",
            "complementary remainder accounting as a distinct contract in a paired .h/.cpp API",
            "grid plan calculator",
        ),
        c(
            "f26csq-poster-block-measure",
            "Poster block measure",
            "poster_blocks",
            """
            class BlockError : public std::invalid_argument {
            public:
                explicit BlockError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BlockMeasure {
            public:
                BlockMeasure(const std::string& raw, std::size_t height);
                std::string normalized() const;
                std::size_t height() const;
                std::size_t columns() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            };
            """,
            """
            class BlockError : public std::invalid_argument {
            public:
                explicit BlockError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BlockMeasure {
            public:
                BlockMeasure(const std::string& raw, std::size_t height);
                std::string normalized() const;
                std::size_t height() const;
                std::size_t columns() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            private:
                std::string normalized_;
                std::size_t height_;
            };
            """,
            """
            BlockMeasure::BlockMeasure(const std::string& raw, std::size_t height) : height_(height) {
                if (height == 0 || height > 9) throw BlockError("height outside 1..9");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string BlockMeasure::normalized() const { return normalized_; }
            std::size_t BlockMeasure::height() const { return height_; }
            std::size_t BlockMeasure::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + height_ - 1) / height_;
            }
            std::size_t BlockMeasure::padding() const { return height_ * columns() - normalized_.size(); }
            std::string BlockMeasure::plan() const {
                return "blocks=" + std::to_string(columns()) + ";stack=" + std::to_string(height_)
                    + ";pad=" + std::to_string(padding());
            }
            std::string BlockMeasure::template_grid() const {
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t r = 0; r < height_ && cols != 0; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(cols, '=');
                }
                return result;
            }
            """,
            """
            BlockMeasure::BlockMeasure(const std::string& raw, std::size_t height) : height_(height) {
                if (height == 0 || height > 9) throw BlockError("height outside 1..9");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string BlockMeasure::normalized() const { return normalized_; }
            std::size_t BlockMeasure::height() const { return height_; }
            std::size_t BlockMeasure::columns() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n / height_;
            }
            std::size_t BlockMeasure::padding() const { return height_ * columns() - normalized_.size(); }
            std::string BlockMeasure::plan() const {
                return "blocks=" + std::to_string(columns()) + ";stack=" + std::to_string(height_)
                    + ";pad=" + std::to_string(padding());
            }
            std::string BlockMeasure::template_grid() const {
                const std::size_t cols = columns();
                std::string result;
                for (std::size_t r = 0; r < height_ && cols != 0; ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(cols, '=');
                }
                return result;
            }
            """,
            """
            BlockMeasure b("Posters dry on the line", 3);
            if (b.normalized() != "postersdryontheline") return 1;
            if (b.height() != 3U) return 2;
            if (b.columns() != 7U) return 3;
            if (b.padding() != 2U) return 4;
            if (b.plan() != "blocks=7;stack=3;pad=2") return 5;
            if (b.template_grid() != "=======\\n=======\\n=======") return 6;
            BlockMeasure exact("abcdef", 2);
            if (exact.plan() != "blocks=3;stack=2;pad=0") return 7;
            BlockMeasure empty("!!", 4);
            if (empty.plan() != "blocks=0;stack=4;pad=0") return 8;
            if (empty.template_grid() != "") return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { BlockMeasure bad("abc", 0); } catch (const BlockError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BlockMeasure bad("abc", 10); } catch (const BlockError&) { threw = true; }
            if (!threw) return 2;
            BlockMeasure b("Glue 7 sticks", 2);
            if (b.plan() != "blocks=6;stack=2;pad=1") return 3;
            BlockMeasure one("q", 5);
            if (one.plan() != "blocks=1;stack=5;pad=4") return 4;
            if (one.template_grid() != "=\\n=\\n=\\n=\\n=") return 5;
            return 0;
            """,
            "height-driven plan with equals template and exact labels",
            "regex engines or third-party text-grid libraries and truncating division",
            "ceiling columns, equals templates, height validation at 0 and 10, and empty inputs",
            "label vocabulary variety inside the plan group in a paired .h/.cpp API",
            "grid plan calculator",
        ),
        c(
            "f26csq-tablecloth-fold-grid",
            "Tablecloth fold grid",
            "tablecloth_folds",
            """
            class FoldError : public std::domain_error {
            public:
                explicit FoldError(const std::string& message) : std::domain_error(message) {}
            };
            class FoldGrid {
            public:
                explicit FoldGrid(const std::string& raw);
                std::string normalized() const;
                std::size_t folds() const;
                std::size_t panels() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            };
            """,
            """
            class FoldError : public std::domain_error {
            public:
                explicit FoldError(const std::string& message) : std::domain_error(message) {}
            };
            class FoldGrid {
            public:
                explicit FoldGrid(const std::string& raw);
                std::string normalized() const;
                std::size_t folds() const;
                std::size_t panels() const;
                std::size_t padding() const;
                std::string plan() const;
                std::string template_grid() const;
            private:
                std::string normalized_;
            };
            """,
            """
            FoldGrid::FoldGrid(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string FoldGrid::normalized() const { return normalized_; }
            std::size_t FoldGrid::folds() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + 3) / 4;
            }
            std::size_t FoldGrid::panels() const { return 4; }
            std::size_t FoldGrid::padding() const { return folds() * 4 - normalized_.size(); }
            std::string FoldGrid::plan() const {
                return "folds=" + std::to_string(folds()) + ";panels=4;pad=" + std::to_string(padding());
            }
            std::string FoldGrid::template_grid() const {
                const std::size_t total = folds();
                std::string result;
                for (std::size_t r = 0; r < total; ++r) {
                    if (r != 0) result += '\\n';
                    result += "++++";
                }
                return result;
            }
            """,
            """
            FoldGrid::FoldGrid(const std::string& raw) {
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string FoldGrid::normalized() const { return normalized_; }
            std::size_t FoldGrid::folds() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return n / 4;
            }
            std::size_t FoldGrid::panels() const { return 4; }
            std::size_t FoldGrid::padding() const { return folds() * 4 - normalized_.size(); }
            std::string FoldGrid::plan() const {
                return "folds=" + std::to_string(folds()) + ";panels=4;pad=" + std::to_string(padding());
            }
            std::string FoldGrid::template_grid() const {
                const std::size_t total = folds();
                std::string result;
                for (std::size_t r = 0; r < total; ++r) {
                    if (r != 0) result += '\\n';
                    result += "++++";
                }
                return result;
            }
            """,
            """
            FoldGrid f("Napkins fold into quarters");
            if (f.normalized() != "napkinsfoldintoquarters") return 1;
            if (f.folds() != 6U) return 2;
            if (f.panels() != 4U) return 3;
            if (f.padding() != 1U) return 4;
            if (f.plan() != "folds=6;panels=4;pad=1") return 5;
            if (f.template_grid() != "++++\\n++++\\n++++\\n++++\\n++++\\n++++") return 6;
            FoldGrid exact("abcdefgh");
            if (exact.plan() != "folds=2;panels=4;pad=0") return 7;
            FoldGrid empty("123");
            if (empty.plan() != "folds=0;panels=4;pad=0") return 8;
            if (empty.template_grid() != "") return 9;
            return 0;
            """,
            """
            FoldGrid one("q");
            if (one.plan() != "folds=1;panels=4;pad=3") return 1;
            if (one.template_grid() != "++++") return 2;
            FoldGrid three("abc");
            if (three.plan() != "folds=1;panels=4;pad=1") return 3;
            FoldGrid five("abcde");
            if (five.plan() != "folds=2;panels=4;pad=3") return 4;
            FoldGrid twelve(std::string(12, 'a'));
            if (twelve.plan() != "folds=3;panels=4;pad=0") return 5;
            return 0;
            """,
            "fixed-panel ceiling plan with plus template and exact labels",
            "regex engines or third-party text-grid libraries and truncating division",
            "multiples of four, partial folds, plus templates, and empty inputs",
            "a second fixed-panel policy with its own labels in a paired .h/.cpp API",
            "grid plan calculator",
        ),
        c(
            "f26csq-mirrorlake-reflection-grid",
            "Mirrorlake reflection grid",
            "mirrorlake_grids",
            """
            class ReflectionError : public std::invalid_argument {
            public:
                explicit ReflectionError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ReflectionGrid {
            public:
                ReflectionGrid(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string row(std::size_t index) const;
                std::string reflected() const;
            };
            """,
            """
            class ReflectionError : public std::invalid_argument {
            public:
                explicit ReflectionError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ReflectionGrid {
            public:
                ReflectionGrid(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string row(std::size_t index) const;
                std::string reflected() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            ReflectionGrid::ReflectionGrid(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 20) throw ReflectionError("width outside 1..20");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ReflectionGrid::normalized() const { return normalized_; }
            std::size_t ReflectionGrid::width() const { return width_; }
            std::size_t ReflectionGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ReflectionGrid::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string ReflectionGrid::row(std::size_t index) const {
                const std::vector<std::string> out = grid();
                if (index >= out.size()) throw ReflectionError("row index out of range");
                return out[index];
            }
            std::string ReflectionGrid::reflected() const {
                const std::vector<std::string> out = grid();
                std::string result;
                for (std::size_t r = 0; r < out.size(); ++r) {
                    if (r != 0) result += '\\n';
                    result += std::string(out[r].rbegin(), out[r].rend());
                }
                return result;
            }
            """,
            """
            ReflectionGrid::ReflectionGrid(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 20) throw ReflectionError("width outside 1..20");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ReflectionGrid::normalized() const { return normalized_; }
            std::size_t ReflectionGrid::width() const { return width_; }
            std::size_t ReflectionGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ReflectionGrid::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string ReflectionGrid::row(std::size_t index) const {
                const std::vector<std::string> out = grid();
                if (index >= out.size()) throw ReflectionError("row index out of range");
                return out[index];
            }
            std::string ReflectionGrid::reflected() const {
                const std::vector<std::string> out = grid();
                std::string flat;
                for (const std::string& line : out) flat += line;
                const std::string flipped(flat.rbegin(), flat.rend());
                std::string result;
                for (std::size_t start = 0; start < flipped.size(); start += width_) {
                    if (start != 0) result += '\\n';
                    result += flipped.substr(start, width_);
                }
                return result;
            }
            """,
            """
            ReflectionGrid m("Still ponds reflect pines", 4);
            if (m.normalized() != "stillpondsreflectpines") return 1;
            if (m.width() != 4U) return 2;
            if (m.rows() != 6U) return 3;
            if (m.grid() != std::vector<std::string>{"stil", "lpon", "dsre", "flec", "tpin", "es.."}) return 4;
            if (m.reflected() != "lits\\nnopl\\nersd\\ncelf\\nnipt\\n..se") return 5;
            ReflectionGrid exact("ab cd", 2);
            if (exact.reflected() != "ba\\ndc") return 6;
            ReflectionGrid empty("!!", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.reflected() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { ReflectionGrid bad("abc", 0); } catch (const ReflectionError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ReflectionGrid bad("abc", 21); } catch (const ReflectionError&) { threw = true; }
            if (!threw) return 2;
            ReflectionGrid m("Lake 7 shore", 3);
            if (m.row(1) != "esh") return 3;
            threw = false;
            try { m.row(3); } catch (const ReflectionError&) { threw = true; }
            if (!threw) return 4;
            if (m.reflected() != "kal\\nhse\\nero") return 5;
            ReflectionGrid one("q", 2);
            if (one.reflected() != ".q") return 6;
            return 0;
            """,
            "per-row horizontal mirror with dot padding and exact newline render",
            "regex engines or third-party text-grid libraries and whole-string reversal",
            "per-row reversal on multi-row grids, dot padding, width validation at 0 and 21, and index rejection",
            "row-local transform as the rejection discriminator in a paired .h/.cpp API",
            "grid transform reader",
        ),
        c(
            "f26csq-turnstile-rotation-grid",
            "Turnstile rotation grid",
            "turnstile_grids",
            """
            class RotationError : public std::invalid_argument {
            public:
                explicit RotationError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RotationGrid {
            public:
                RotationGrid(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string rotated() const;
            };
            """,
            """
            class RotationError : public std::invalid_argument {
            public:
                explicit RotationError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RotationGrid {
            public:
                RotationGrid(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string rotated() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            RotationGrid::RotationGrid(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 18) throw RotationError("width outside 1..18");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string RotationGrid::normalized() const { return normalized_; }
            std::size_t RotationGrid::width() const { return width_; }
            std::size_t RotationGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> RotationGrid::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '*'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string RotationGrid::rotated() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string result;
                for (std::size_t c = 0; c < width_; ++c) {
                    if (c != 0) result += '\\n';
                    for (std::size_t step = 0; step < total_rows; ++step) result += g[total_rows - 1 - step][c];
                }
                return result;
            }
            """,
            """
            RotationGrid::RotationGrid(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 18) throw RotationError("width outside 1..18");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string RotationGrid::normalized() const { return normalized_; }
            std::size_t RotationGrid::width() const { return width_; }
            std::size_t RotationGrid::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> RotationGrid::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '*'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string RotationGrid::rotated() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string result;
                for (std::size_t c = 0; c < width_; ++c) {
                    if (c != 0) result += '\\n';
                    for (std::size_t r = 0; r < total_rows; ++r) result += g[r][width_ - 1 - c];
                }
                return result;
            }
            """,
            """
            RotationGrid g("Turnstiles click at noon", 3);
            if (g.normalized() != "TURNSTILESCLICKATNOON") return 1;
            if (g.width() != 3U) return 2;
            if (g.rows() != 7U) return 3;
            if (g.grid() != std::vector<std::string>{"TUR", "NST", "ILE", "SCL", "ICK", "ATN", "OON"}) return 4;
            if (g.rotated() != "OAISINT\\nOTCCLSU\\nNNKLETR") return 5;
            RotationGrid exact("ab cd", 2);
            if (exact.rotated() != "CA\\nDB") return 6;
            RotationGrid empty("!!", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.rotated() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { RotationGrid bad("abc", 0); } catch (const RotationError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RotationGrid bad("abc", 19); } catch (const RotationError&) { threw = true; }
            if (!threw) return 2;
            RotationGrid g("Metro 4 line", 4);
            if (g.rotated() != "NOM\\nE4E\\n*LT\\n*IR") return 3;
            RotationGrid one("q", 3);
            if (one.rotated() != "Q\\n*\\n*") return 4;
            return 0;
            """,
            "clockwise quarter-turn rotation with star padding and dimension swap",
            "regex engines or third-party text-grid libraries and counterclockwise rotation",
            "dimension swaps on non-square grids, star padding, clockwise cell mapping, and width validation at 0 and 19",
            "rotation direction as the rejection discriminator in a paired .h/.cpp API",
            "grid transform reader",
            project_support=True,
        ),
        c(
            "f26csq-cascade-diagonal-read",
            "Cascade diagonal read",
            "cascade_diagonals",
            """
            class DiagonalError : public std::invalid_argument {
            public:
                explicit DiagonalError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DiagonalRead {
            public:
                DiagonalRead(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string diagonals() const;
                std::string render() const;
            };
            """,
            """
            class DiagonalError : public std::invalid_argument {
            public:
                explicit DiagonalError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DiagonalRead {
            public:
                DiagonalRead(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string diagonals() const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            DiagonalRead::DiagonalRead(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 14) throw DiagonalError("width outside 1..14");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string DiagonalRead::normalized() const { return normalized_; }
            std::size_t DiagonalRead::width() const { return width_; }
            std::size_t DiagonalRead::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> DiagonalRead::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '#'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string DiagonalRead::diagonals() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string out;
                for (std::size_t s = 0; s < total_rows + width_ - 1; ++s)
                    for (std::size_t r = 0; r < total_rows; ++r)
                        if (s >= r && s - r < width_) out += g[r][s - r];
                return out;
            }
            std::string DiagonalRead::render() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string result;
                for (std::size_t s = 0; s < total_rows + width_ - 1; ++s) {
                    if (s != 0) result += '/';
                    for (std::size_t r = 0; r < total_rows; ++r)
                        if (s >= r && s - r < width_) result += g[r][s - r];
                }
                return result;
            }
            """,
            """
            DiagonalRead::DiagonalRead(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 14) throw DiagonalError("width outside 1..14");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string DiagonalRead::normalized() const { return normalized_; }
            std::size_t DiagonalRead::width() const { return width_; }
            std::size_t DiagonalRead::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> DiagonalRead::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '#'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string DiagonalRead::diagonals() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string out;
                for (std::size_t kk = 0; kk < total_rows + width_ - 1; ++kk)
                    for (std::size_t r = 0; r < total_rows; ++r) {
                        const long c = static_cast<long>(r) - (static_cast<long>(kk) - static_cast<long>(width_ - 1));
                        if (c >= 0 && c < static_cast<long>(width_)) out += g[r][static_cast<std::size_t>(c)];
                    }
                return out;
            }
            std::string DiagonalRead::render() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string result;
                for (std::size_t kk = 0; kk < total_rows + width_ - 1; ++kk) {
                    if (kk != 0) result += '/';
                    for (std::size_t r = 0; r < total_rows; ++r) {
                        const long c = static_cast<long>(r) - (static_cast<long>(kk) - static_cast<long>(width_ - 1));
                        if (c >= 0 && c < static_cast<long>(width_)) result += g[r][static_cast<std::size_t>(c)];
                    }
                }
                return result;
            }
            """,
            """
            DiagonalRead d("Waterfalls pour over rock", 4);
            if (d.normalized() != "waterfallspouroverrock") return 1;
            if (d.width() != 4U) return 2;
            if (d.rows() != 6U) return 3;
            if (d.grid() != std::vector<std::string>{"wate", "rfal", "lspo", "urov", "erro", "ck##"}) return 4;
            if (d.diagonals() != "wartfleasulpreoorcvrko##") return 5;
            if (d.render() != "w/ar/tfl/easu/lpre/oorc/vrk/o#/#") return 6;
            DiagonalRead exact("ab cd", 2);
            if (exact.diagonals() != "abcd") return 7;
            if (exact.render() != "a/bc/d") return 8;
            DiagonalRead empty("!!", 3);
            if (empty.rows() != 0U) return 9;
            if (empty.render() != "") return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { DiagonalRead bad("abc", 0); } catch (const DiagonalError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { DiagonalRead bad("abc", 15); } catch (const DiagonalError&) { threw = true; }
            if (!threw) return 2;
            DiagonalRead d("Creek 9 bend", 3);
            if (d.diagonals() != "creekebnd") return 3;
            if (d.render() != "c/re/eke/bn/d") return 4;
            DiagonalRead one("q", 4);
            if (one.diagonals() != "q###") return 5;
            if (one.render() != "q/#/#/#") return 6;
            return 0;
            """,
            "anti-diagonal traversal with hash padding and per-diagonal slash chunking",
            "regex engines or third-party text-grid libraries, row-major reads, and main-diagonal order",
            "diagonal chunk boundaries, hash padding, and width validation at 0 and 15",
            "diagonal-axis discipline as a distinct traversal in a paired .h/.cpp API",
            "grid transform reader",
        ),
        c(
            "f26csq-checkerboard-parity-filter",
            "Checkerboard parity filter",
            "checkerboard_filters",
            """
            class ParityError : public std::invalid_argument {
            public:
                explicit ParityError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ParityFilter {
            public:
                ParityFilter(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string even_cells() const;
                std::string odd_cells() const;
                std::string render() const;
            };
            """,
            """
            class ParityError : public std::invalid_argument {
            public:
                explicit ParityError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ParityFilter {
            public:
                ParityFilter(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string even_cells() const;
                std::string odd_cells() const;
                std::string render() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            ParityFilter::ParityFilter(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 24) throw ParityError("width outside 1..24");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ParityFilter::normalized() const { return normalized_; }
            std::size_t ParityFilter::width() const { return width_; }
            std::size_t ParityFilter::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ParityFilter::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string ParityFilter::even_cells() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (std::size_t r = 0; r < g.size(); ++r)
                    for (std::size_t c = 0; c < width_ && !g.empty(); ++c)
                        if ((r + c) % 2 == 0) out += g[r][c];
                return out;
            }
            std::string ParityFilter::odd_cells() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (std::size_t r = 0; r < g.size(); ++r)
                    for (std::size_t c = 0; c < width_ && !g.empty(); ++c)
                        if ((r + c) % 2 != 0) out += g[r][c];
                return out;
            }
            std::string ParityFilter::render() const {
                if (grid().empty()) return "";
                return even_cells() + "|" + odd_cells();
            }
            """,
            """
            ParityFilter::ParityFilter(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 24) throw ParityError("width outside 1..24");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalnum(byte)) normalized_ += static_cast<char>(std::tolower(byte));
                }
            }
            std::string ParityFilter::normalized() const { return normalized_; }
            std::size_t ParityFilter::width() const { return width_; }
            std::size_t ParityFilter::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ParityFilter::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '.'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string ParityFilter::even_cells() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (std::size_t r = 0; r < g.size(); ++r)
                    for (std::size_t c = 0; c < width_ && !g.empty(); ++c)
                        if ((r + c) % 2 != 0) out += g[r][c];
                return out;
            }
            std::string ParityFilter::odd_cells() const {
                const std::vector<std::string> g = grid();
                std::string out;
                for (std::size_t r = 0; r < g.size(); ++r)
                    for (std::size_t c = 0; c < width_ && !g.empty(); ++c)
                        if ((r + c) % 2 == 0) out += g[r][c];
                return out;
            }
            std::string ParityFilter::render() const {
                if (grid().empty()) return "";
                return even_cells() + "|" + odd_cells();
            }
            """,
            """
            ParityFilter f("Squares alternate in play", 3);
            if (f.normalized() != "squaresalternateinplay") return 1;
            if (f.width() != 3U) return 2;
            if (f.rows() != 8U) return 3;
            if (f.grid() != std::vector<std::string>{"squ", "are", "sal", "ter", "nat", "ein", "pla", "y.."}) return 4;
            if (f.even_cells() != "surslentipa.") return 5;
            if (f.odd_cells() != "qaeatraenly.") return 6;
            if (f.render() != "surslentipa.|qaeatraenly.") return 7;
            ParityFilter exact("ab cd", 2);
            if (exact.render() != "ad|bc") return 8;
            ParityFilter empty("!!", 3);
            if (empty.rows() != 0U) return 9;
            if (empty.render() != "") return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { ParityFilter bad("abc", 0); } catch (const ParityError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ParityFilter bad("abc", 25); } catch (const ParityError&) { threw = true; }
            if (!threw) return 2;
            ParityFilter f("Board 8 tile", 4);
            if (f.even_cells() != "ba8il.") return 3;
            if (f.odd_cells() != "ordte.") return 4;
            if (f.render() != "ba8il.|ordte.") return 5;
            ParityFilter one("q", 2);
            if (one.render() != "q|.") return 6;
            return 0;
            """,
            "parity cell selection with dot padding and pipe-joined split render",
            "regex engines or third-party text-grid libraries and swapped parity assignment",
            "parity split counts on even and odd grids, dot padding, and width validation at 0 and 25",
            "selection-rule discipline as the rejection discriminator in a paired .h/.cpp API",
            "grid transform reader",
        ),
        c(
            "f26csq-ledger-column-swap",
            "Ledger column swap",
            "ledger_swaps",
            """
            class SwapError : public std::invalid_argument {
            public:
                explicit SwapError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ColumnSwap {
            public:
                ColumnSwap(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string swapped() const;
            };
            """,
            """
            class SwapError : public std::invalid_argument {
            public:
                explicit SwapError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ColumnSwap {
            public:
                ColumnSwap(const std::string& raw, std::size_t width);
                std::string normalized() const;
                std::size_t width() const;
                std::size_t rows() const;
                std::vector<std::string> grid() const;
                std::string swapped() const;
            private:
                std::string normalized_;
                std::size_t width_;
            };
            """,
            """
            ColumnSwap::ColumnSwap(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 32) throw SwapError("width outside 1..32");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string ColumnSwap::normalized() const { return normalized_; }
            std::size_t ColumnSwap::width() const { return width_; }
            std::size_t ColumnSwap::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ColumnSwap::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '0'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string ColumnSwap::swapped() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string result;
                bool first = true;
                for (std::size_t pass = 0; pass < 2; ++pass)
                    for (std::size_t c = pass; c < width_; c += 2) {
                        if (!first) result += ' ';
                        first = false;
                        for (std::size_t r = 0; r < total_rows; ++r) result += g[r][c];
                    }
                return result;
            }
            """,
            """
            ColumnSwap::ColumnSwap(const std::string& raw, std::size_t width) : width_(width) {
                if (width == 0 || width > 32) throw SwapError("width outside 1..32");
                for (char ch : raw) {
                    const unsigned char byte = static_cast<unsigned char>(ch);
                    if (std::isalpha(byte)) normalized_ += static_cast<char>(std::toupper(byte));
                }
            }
            std::string ColumnSwap::normalized() const { return normalized_; }
            std::size_t ColumnSwap::width() const { return width_; }
            std::size_t ColumnSwap::rows() const {
                const std::size_t n = normalized_.size();
                if (n == 0) return 0;
                return (n + width_ - 1) / width_;
            }
            std::vector<std::string> ColumnSwap::grid() const {
                std::vector<std::string> out;
                const std::size_t n = normalized_.size();
                if (n == 0) return out;
                const std::size_t total_rows = rows();
                out.assign(total_rows, std::string(width_, '0'));
                for (std::size_t i = 0; i < n; ++i) out[i / width_][i % width_] = normalized_[i];
                return out;
            }
            std::string ColumnSwap::swapped() const {
                const std::vector<std::string> g = grid();
                if (g.empty()) return "";
                const std::size_t total_rows = g.size();
                std::string result;
                bool first = true;
                for (std::size_t pass = 0; pass < 2; ++pass)
                    for (std::size_t c = 1 - pass; c < width_; c += 2) {
                        if (pass == 0 && width_ == 1) continue;
                        if (!first) result += ' ';
                        first = false;
                        for (std::size_t r = 0; r < total_rows; ++r) result += g[r][c];
                    }
                return result;
            }
            """,
            """
            ColumnSwap s("Ledger pages balance out", 4);
            if (s.normalized() != "LEDGERPAGESBALANCEOUT") return 1;
            if (s.width() != 4U) return 2;
            if (s.rows() != 6U) return 3;
            if (s.grid() != std::vector<std::string>{"LEDG", "ERPA", "GESB", "ALAN", "CEOU", "T000"}) return 4;
            if (s.swapped() != "LEGACT DPSAO0 ERELE0 GABNU0") return 5;
            ColumnSwap exact("ab cd", 2);
            if (exact.swapped() != "AC BD") return 6;
            ColumnSwap empty("!!", 3);
            if (empty.rows() != 0U) return 7;
            if (empty.swapped() != "") return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { ColumnSwap bad("abc", 0); } catch (const SwapError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ColumnSwap bad("abc", 33); } catch (const SwapError&) { threw = true; }
            if (!threw) return 2;
            ColumnSwap s("Entry 9 debit", 3);
            if (s.swapped() != "ERET TDI0 NYB0") return 3;
            ColumnSwap one("q", 4);
            if (one.swapped() != "Q 0 0 0") return 4;
            ColumnSwap five("abcde", 5);
            if (five.swapped() != "A C E B D") return 5;
            return 0;
            """,
            "even-then-odd column permutation with zero padding and space-joined chunks",
            "regex engines or third-party text-grid libraries and odd-first or sequential column order",
            "permutation order on odd and even column counts, zero padding, and width validation at 0 and 33",
            "permutation discipline as the rejection discriminator in a paired .h/.cpp API",
            "grid transform reader",
        ),
    )
    return rows


TASKS = cases()

CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-csq-seven-dimension-artifacts-v1"


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

Implement a clean-room C++17 string-grid formatting component for a local
crypto-square skill analog. This root is independently authored for SFT
task-family construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep ASCII-only normalization through unsigned-char classification, exact
grid dimension and ceiling-division rules, named traversal orders, named padding
characters and sides, delimiter-joined or newline-joined exact output shapes,
typed-error rejection, and empty-input behavior deterministic and explicit for
this API shape: {spec.api_shape}.

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
                "source": "w8-biayn clean-room fixed26 crypto-square analog curriculum",
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
description = "{spec.title}: normalization, grid dimensions, padding, grouping, exact output shapes, boundary inputs, and wrong-substitute rejection"

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
    if spec.task_id != "f26csq-harbor-manifest-columns":
        _fail("control_mutation_drift", f"controls are bound to f26csq-harbor-manifest-columns, got {spec.task_id}")
    if name == "domain-identifier-renamed":
        renamed_id = "f26csq-quay-manifest-columns"
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
                ("ManifestColumns b25(std::string(25, 'a'));", "ManifestColumns b25(std::string(24, 'a'));"),
                ("ManifestColumns b26(std::string(26, 'a'));", "ManifestColumns b26(std::string(30, 'a'));"),
                (
                    "try { m.column(5); } catch (const ManifestError&) { threw = true; }",
                    "try { m.column(7); } catch (const ManifestError&) { threw = true; }",
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
                ('ManifestColumns m("Cranes load cargo at dawn!");', 'ManifestColumns m("Dawn cargo loads cranes!");'),
                (
                    'if (m.normalized() != "cranesloadcargoatdawn") return 1;',
                    'if (m.normalized() != "dawncargoloadscranes") return 1;',
                ),
                ("if (m.rows() != 5U) return 3;", "if (m.rows() != 4U) return 3;"),
                (
                    'if (m.grid() != std::vector<std::string>{"crane", "sload", "cargo", "atdaw", "n"}) return 4;',
                    'if (m.grid() != std::vector<std::string>{"dawnc", "argol", "oadsc", "ranes"}) return 4;',
                ),
                (
                    'if (m.encoded() != "cscan rlat. aord. naga. edow.") return 5;',
                    'if (m.encoded() != "daor araa wgdn nose clcs") return 5;',
                ),
                ('ManifestColumns one("Q!");', 'ManifestColumns one("Z9");'),
                ('if (one.encoded() != "q .") return 10;', 'if (one.encoded() != "z 9") return 10;'),
            ),
            context="opposite-end-selection:visible",
        )
        mutated[".meta/private_test.cpp"] = _apply_replacements(
            mutated[".meta/private_test.cpp"],
            (
                ('ManifestColumns m("Dock seven barges, mate!");', 'ManifestColumns m("Mate docks seven barges!");'),
                ('if (m.column(0) != "deam") return 9;', 'if (m.column(0) != "moea") return 9;'),
                ('if (m.column(4) != "sbs") return 10;', 'if (m.column(4) != "dsbs") return 10;'),
                (
                    'if (m.encoded() != "deam ovra cegt knee sbs.") return 12;',
                    'if (m.encoded() != "moea acvr tkeg esne dsbs") return 12;',
                ),
                ('ManifestColumns p("A,b!");', 'ManifestColumns p("Z,9!");'),
                ('if (p.normalized() != "ab") return 13;', 'if (p.normalized() != "z9") return 13;'),
                ('if (p.encoded() != "a b") return 14;', 'if (p.encoded() != "z 9") return 14;'),
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
            "family": "crypto-square",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "crypto-square",
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
    text = re.sub(r"\bf26csq[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        control_headers = sorted(path.name for path in control_root.glob("f26csq-*.h"))
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
        "schema_version": "fixed26-csq-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-csq-fresh-") as temporary:
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
        "schema_version": "fixed26-csq-core-v1",
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
for task_root in sorted(ROOT.glob("f26csq-*")):
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
            "schema_version": "fixed26-csq-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-csq-docker-") as temporary:
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
        "schema_version": "fixed26-csq-docker-sanity-v1",
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
        "schema_version": "fixed26-csq-creator-preflight-v1",
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
        "capability": "fixed26-csquare-analog",
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
            "task": "implement clean-room fixed26 crypto-square analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned normalized string and grid state with task-owned dimension, traversal, padding, and grouping rules; ASCII-only unsigned-char classification; exact ceiling division; named fill characters, sides, and delimiters; byte-identical deterministic output; rejected operations never mutate",
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
            "target_family": "crypto-square",
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
