"""Create and verify the fixed-26 dnd-character clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b010-dnd-character.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b010-dnd-character"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_dnd_character_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_dnd_character_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b010-dnd-character"
FAMILY_ID = "aider-fixed26-dnd-character-analogs-v1"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
EXPECTED_ROOTS = 20
EXPECTED_PAIRS = 190
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
        "f26dnd-harbor-tide-gauge",
        "f26dnd-caravan-wagon-manifest",
        "f26dnd-cartographer-survey-grid",
        "f26dnd-fencing-bout-board",
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
#include <utility>
#include <vector>
"""


COMMON_SOURCE = r"""
#include <algorithm>
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
            "f26dnd-harbor-tide-gauge",
            "Harbor tide gauge",
            "harbor_tide",
            """
            class TideError : public std::invalid_argument {
            public:
                explicit TideError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TideGauge {
            public:
                explicit TideGauge(int offset);
                int offset() const;
                int surge(int reading) const;
                bool flood_watch(int reading) const;
                std::vector<int> surges(const std::vector<int>& readings) const;
            };
            """,
            """
            class TideError : public std::invalid_argument {
            public:
                explicit TideError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TideGauge {
            public:
                explicit TideGauge(int offset);
                int offset() const;
                int surge(int reading) const;
                bool flood_watch(int reading) const;
                std::vector<int> surges(const std::vector<int>& readings) const;
            private:
                int offset_;
            };
            """,
            """
            TideGauge::TideGauge(int offset) : offset_(offset) {
                if (offset < -5 || offset > 5) throw TideError("offset outside -5..5");
            }
            int TideGauge::offset() const { return offset_; }
            int TideGauge::surge(int reading) const {
                if (reading < 0 || reading > 40) throw TideError("reading outside 0..40");
                const int centered = reading + offset_ - 20;
                return centered / 2;
            }
            bool TideGauge::flood_watch(int reading) const { return surge(reading) >= 5; }
            std::vector<int> TideGauge::surges(const std::vector<int>& readings) const {
                std::vector<int> out;
                out.reserve(readings.size());
                for (int reading : readings) out.push_back(surge(reading));
                return out;
            }
            """,
            """
            TideGauge::TideGauge(int offset) : offset_(offset) {
                if (offset < -5 || offset > 5) throw TideError("offset outside -5..5");
            }
            int TideGauge::offset() const { return offset_; }
            int TideGauge::surge(int reading) const {
                if (reading < 0 || reading > 40) throw TideError("reading outside 0..40");
                const int centered = reading + offset_ - 20;
                if (centered < 0 && centered % 2 != 0) return centered / 2 - 1;
                return centered / 2;
            }
            bool TideGauge::flood_watch(int reading) const { return surge(reading) >= 5; }
            std::vector<int> TideGauge::surges(const std::vector<int>& readings) const {
                std::vector<int> out;
                out.reserve(readings.size());
                for (int reading : readings) out.push_back(surge(reading));
                return out;
            }
            """,
            """
            TideGauge g(0);
            if (g.offset() != 0) return 1;
            if (g.surge(20) != 0) return 2;
            if (g.surge(40) != 10) return 3;
            if (g.surge(0) != -10) return 4;
            if (g.surge(17) != -1) return 5;
            if (!g.flood_watch(30)) return 6;
            if (g.flood_watch(29)) return 7;
            std::vector<int> got = g.surges({20, 40, 0});
            if (got != std::vector<int>{0, 10, -10}) return 8;
            TideGauge low(-3);
            if (low.surge(20) != -1) return 9;
            TideGauge high(5);
            if (high.surge(0) != -7) return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { TideGauge bad(-6); } catch (const TideError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TideGauge bad(6); } catch (const TideError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { TideGauge g(0); g.surge(-1); } catch (const TideError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { TideGauge g(0); g.surge(41); } catch (const TideError&) { threw = true; }
            if (!threw) return 4;
            TideGauge t(1);
            if (t.surge(18) != 0) return 5;
            TideGauge u(-5);
            if (u.surge(12) != -6) return 6;
            if (u.surge(20) != -2) return 7;
            TideGauge w(5);
            if (w.surge(0) != -7) return 8;
            if (w.surge(40) != 12) return 9;
            std::vector<int> many = w.surges({0, 40});
            if (many != std::vector<int>{-7, 12}) return 10;
            TideGauge v(0);
            if (!v.flood_watch(30)) return 11;
            if (v.flood_watch(29)) return 12;
            if (!v.surges({}).empty()) return 13;
            return 0;
            """,
            "signed centering with truncation-toward-zero halving",
            "pseudo-random generators, dice-roll simulators, <random>, floating-point rounding libraries, and floor-adjusted halving",
            "offset bounds at -6 and 6, reading bounds at -1 and 41, negative odd centered values, watch threshold at surge exactly 5, and empty vectors",
            "truncating-versus-floor signed division discipline in a paired .h/.cpp API",
            "truncating signed modifier",
            project_support=True,
        ),
        c(
            "f26dnd-quarry-load-scale",
            "Quarry load scale",
            "quarry_load",
            """
            class ScaleError : public std::domain_error {
            public:
                explicit ScaleError(const std::string& message) : std::domain_error(message) {}
            };
            class LoadScale {
            public:
                explicit LoadScale(int bonus);
                int bonus() const;
                int bracket(int load) const;
                int toll(int load) const;
                std::vector<int> tolls(const std::vector<int>& loads) const;
            };
            """,
            """
            class ScaleError : public std::domain_error {
            public:
                explicit ScaleError(const std::string& message) : std::domain_error(message) {}
            };
            class LoadScale {
            public:
                explicit LoadScale(int bonus);
                int bonus() const;
                int bracket(int load) const;
                int toll(int load) const;
                std::vector<int> tolls(const std::vector<int>& loads) const;
            private:
                int bonus_;
            };
            """,
            """
            LoadScale::LoadScale(int bonus) : bonus_(bonus) {
                if (bonus < 0 || bonus > 3) throw ScaleError("bonus outside 0..3");
            }
            int LoadScale::bonus() const { return bonus_; }
            int LoadScale::bracket(int load) const {
                if (load < 0 || load > 500) throw ScaleError("load outside 0..500");
                if (load < 50) return 0;
                if (load < 100) return 4;
                if (load < 200) return 9;
                if (load < 350) return 15;
                return 22;
            }
            int LoadScale::toll(int load) const { return bracket(load) + bonus_; }
            std::vector<int> LoadScale::tolls(const std::vector<int>& loads) const {
                std::vector<int> out;
                out.reserve(loads.size());
                for (int load : loads) out.push_back(toll(load));
                return out;
            }
            """,
            """
            LoadScale::LoadScale(int bonus) : bonus_(bonus) {
                if (bonus < 0 || bonus > 3) throw ScaleError("bonus outside 0..3");
            }
            int LoadScale::bonus() const { return bonus_; }
            int LoadScale::bracket(int load) const {
                if (load < 0 || load > 500) throw ScaleError("load outside 0..500");
                if (load <= 50) return 0;
                if (load <= 100) return 4;
                if (load <= 200) return 9;
                if (load <= 350) return 15;
                return 22;
            }
            int LoadScale::toll(int load) const { return bracket(load) + bonus_; }
            std::vector<int> LoadScale::tolls(const std::vector<int>& loads) const {
                std::vector<int> out;
                out.reserve(loads.size());
                for (int load : loads) out.push_back(toll(load));
                return out;
            }
            """,
            """
            LoadScale s(0);
            if (s.bonus() != 0) return 1;
            if (s.toll(0) != 0) return 2;
            if (s.toll(49) != 0) return 3;
            if (s.toll(50) != 4) return 4;
            if (s.toll(99) != 4) return 5;
            if (s.toll(100) != 9) return 6;
            if (s.toll(349) != 15) return 7;
            if (s.toll(350) != 22) return 8;
            if (s.bracket(200) != 15) return 9;
            LoadScale b(2);
            if (b.toll(0) != 2) return 10;
            if (b.toll(50) != 6) return 11;
            std::vector<int> got = s.tolls({49, 50, 500});
            if (got != std::vector<int>{0, 4, 22}) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { LoadScale bad(-1); } catch (const ScaleError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LoadScale bad(4); } catch (const ScaleError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { LoadScale s(0); s.toll(-1); } catch (const ScaleError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { LoadScale s(0); s.toll(501); } catch (const ScaleError&) { threw = true; }
            if (!threw) return 4;
            LoadScale s(0);
            if (s.bracket(199) != 9) return 5;
            if (s.bracket(200) != 15) return 6;
            if (s.bracket(99) != 4) return 7;
            if (s.bracket(100) != 9) return 8;
            LoadScale top(3);
            if (top.toll(350) != 25) return 9;
            if (top.toll(500) != 25) return 10;
            if (top.bracket(45) != 0) return 11;
            std::vector<int> got = top.tolls({0, 500});
            if (got != std::vector<int>{3, 25}) return 12;
            if (!s.tolls({}).empty()) return 13;
            return 0;
            """,
            "piecewise threshold walk with lower-inclusive bracket boundaries",
            "pseudo-random generators, dice-roll simulators, <random>, floating-point rounding libraries, and shifted bracket boundaries",
            "bonus and load bounds, every bracket boundary 49/50, 99/100, 199/200, and 349/350, bonus addition at the top bracket, and empty vectors",
            "lower-inclusive bracket boundary discipline as the rejection discriminator",
            "piecewise bracket modifier",
        ),
        c(
            "f26dnd-orchard-crate-rater",
            "Orchard crate rater",
            "orchard_crate",
            """
            class CrateError : public std::invalid_argument {
            public:
                explicit CrateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CrateRater {
            public:
                explicit CrateRater(bool premium);
                bool premium() const;
                int band(int weight) const;
                std::string tag(int weight) const;
                std::vector<int> bands(const std::vector<int>& weights) const;
            };
            """,
            """
            class CrateError : public std::invalid_argument {
            public:
                explicit CrateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CrateRater {
            public:
                explicit CrateRater(bool premium);
                bool premium() const;
                int band(int weight) const;
                std::string tag(int weight) const;
                std::vector<int> bands(const std::vector<int>& weights) const;
            private:
                bool premium_;
            };
            """,
            """
            CrateRater::CrateRater(bool premium) : premium_(premium) {}
            bool CrateRater::premium() const { return premium_; }
            int CrateRater::band(int weight) const {
                if (weight < 5 || weight > 25) throw CrateError("weight outside 5..25");
                const int base = (weight - 5) / 4;
                if (!premium_) return base;
                return base < 5 ? base + 1 : 5;
            }
            std::string CrateRater::tag(int weight) const { return "B" + std::to_string(band(weight)); }
            std::vector<int> CrateRater::bands(const std::vector<int>& weights) const {
                std::vector<int> out;
                out.reserve(weights.size());
                for (int weight : weights) out.push_back(band(weight));
                return out;
            }
            """,
            """
            CrateRater::CrateRater(bool premium) : premium_(premium) {}
            bool CrateRater::premium() const { return premium_; }
            int CrateRater::band(int weight) const {
                if (weight < 5 || weight > 25) throw CrateError("weight outside 5..25");
                const int base = (weight - 5 + 2) / 4;
                if (!premium_) return base;
                return base < 5 ? base + 1 : 5;
            }
            std::string CrateRater::tag(int weight) const { return "B" + std::to_string(band(weight)); }
            std::vector<int> CrateRater::bands(const std::vector<int>& weights) const {
                std::vector<int> out;
                out.reserve(weights.size());
                for (int weight : weights) out.push_back(band(weight));
                return out;
            }
            """,
            """
            CrateRater r(false);
            if (r.premium()) return 1;
            if (r.band(5) != 0) return 2;
            if (r.band(8) != 0) return 3;
            if (r.band(9) != 1) return 4;
            if (r.band(24) != 4) return 5;
            if (r.band(25) != 5) return 6;
            if (r.tag(9) != "B1") return 7;
            CrateRater p(true);
            if (!p.premium()) return 8;
            if (p.band(5) != 1) return 9;
            if (p.band(24) != 5) return 10;
            if (p.tag(25) != "B5") return 11;
            std::vector<int> got = r.bands({5, 9, 25});
            if (got != std::vector<int>{0, 1, 5}) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { CrateRater r(false); r.band(4); } catch (const CrateError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { CrateRater r(false); r.band(26); } catch (const CrateError&) { threw = true; }
            if (!threw) return 2;
            CrateRater p(true);
            if (p.band(21) != 5) return 3;
            if (p.band(22) != 5) return 4;
            if (p.band(20) != 4) return 5;
            CrateRater r(false);
            if (r.band(12) != 1) return 6;
            if (r.band(13) != 2) return 7;
            if (r.tag(5) != "B0") return 8;
            if (p.tag(5) != "B1") return 9;
            std::vector<int> got = p.bands({5, 20, 25});
            if (got != std::vector<int>{1, 4, 5}) return 10;
            if (!r.bands({}).empty()) return 11;
            return 0;
            """,
            "truncating bucket walk of width four with a premium bump capped at the top band",
            "pseudo-random generators, dice-roll simulators, <random>, floating-point rounding libraries, and rounded bucket assignment",
            "weight bounds at 4 and 26, bucket edges at 8/9 and 24/25, premium cap saturation across the top two base bands, tag formatting, and empty vectors",
            "truncating bucket assignment with cap saturation as the rejection discriminator",
            "bucket-walk band with cap",
        ),
        c(
            "f26dnd-furnace-draft-meter",
            "Furnace draft meter",
            "furnace_draft",
            """
            class DraftError : public std::domain_error {
            public:
                explicit DraftError(const std::string& message) : std::domain_error(message) {}
            };
            class DraftMeter {
            public:
                explicit DraftMeter(int target);
                int target() const;
                int draft(int actual) const;
                std::string status(int actual) const;
                std::vector<std::string> statuses(const std::vector<int>& actuals) const;
            };
            """,
            """
            class DraftError : public std::domain_error {
            public:
                explicit DraftError(const std::string& message) : std::domain_error(message) {}
            };
            class DraftMeter {
            public:
                explicit DraftMeter(int target);
                int target() const;
                int draft(int actual) const;
                std::string status(int actual) const;
                std::vector<std::string> statuses(const std::vector<int>& actuals) const;
            private:
                int target_;
            };
            """,
            """
            DraftMeter::DraftMeter(int target) : target_(target) {
                if (target < 150 || target > 250) throw DraftError("target outside 150..250");
            }
            int DraftMeter::target() const { return target_; }
            int DraftMeter::draft(int actual) const {
                if (actual < 0 || actual > 400) throw DraftError("actual outside 0..400");
                const int delta = actual - target_;
                if (delta < -9) return -9;
                if (delta > 9) return 9;
                return delta;
            }
            std::string DraftMeter::status(int actual) const {
                const int value = draft(actual);
                if (value < -2) return "low";
                if (value > 2) return "high";
                return "steady";
            }
            std::vector<std::string> DraftMeter::statuses(const std::vector<int>& actuals) const {
                std::vector<std::string> out;
                out.reserve(actuals.size());
                for (int actual : actuals) out.push_back(status(actual));
                return out;
            }
            """,
            """
            DraftMeter::DraftMeter(int target) : target_(target) {
                if (target < 150 || target > 250) throw DraftError("target outside 150..250");
            }
            int DraftMeter::target() const { return target_; }
            int DraftMeter::draft(int actual) const {
                if (actual < 0 || actual > 400) throw DraftError("actual outside 0..400");
                const int delta = actual - target_;
                if (delta < -8) return -8;
                if (delta > 8) return 8;
                return delta;
            }
            std::string DraftMeter::status(int actual) const {
                const int value = draft(actual);
                if (value < -2) return "low";
                if (value > 2) return "high";
                return "steady";
            }
            std::vector<std::string> DraftMeter::statuses(const std::vector<int>& actuals) const {
                std::vector<std::string> out;
                out.reserve(actuals.size());
                for (int actual : actuals) out.push_back(status(actual));
                return out;
            }
            """,
            """
            DraftMeter m(200);
            if (m.target() != 200) return 1;
            if (m.draft(200) != 0) return 2;
            if (m.draft(195) != -5) return 3;
            if (m.draft(220) != 9) return 4;
            if (m.draft(180) != -9) return 5;
            if (m.status(200) != "steady") return 6;
            if (m.status(197) != "low") return 7;
            if (m.status(203) != "high") return 8;
            std::vector<std::string> got = m.statuses({200, 190, 210});
            if (got != std::vector<std::string>{"steady", "low", "high"}) return 9;
            DraftMeter low_target(150);
            if (low_target.draft(400) != 9) return 10;
            if (low_target.status(0) != "low") return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { DraftMeter bad(149); } catch (const DraftError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { DraftMeter bad(251); } catch (const DraftError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { DraftMeter m(200); m.draft(-1); } catch (const DraftError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { DraftMeter m(200); m.draft(401); } catch (const DraftError&) { threw = true; }
            if (!threw) return 4;
            DraftMeter m(200);
            if (m.draft(191) != -9) return 5;
            if (m.draft(209) != 9) return 6;
            if (m.draft(190) != -9) return 7;
            if (m.status(198) != "steady") return 8;
            if (m.status(202) != "steady") return 9;
            if (m.status(197) != "low") return 10;
            DraftMeter hi(250);
            if (hi.draft(0) != -9) return 11;
            if (hi.status(241) != "low") return 12;
            std::vector<std::string> got = m.statuses({189, 200, 211});
            if (got != std::vector<std::string>{"low", "steady", "high"}) return 13;
            if (!m.statuses({}).empty()) return 14;
            return 0;
            """,
            "symmetric clamp with three-way status thresholds on the clamped value",
            "pseudo-random generators, dice-roll simulators, <random>, floating-point rounding libraries, and narrower clamp bounds",
            "target and actual bounds, clamp saturation at exactly -9 and 9 and beyond, status thresholds at -3/-2/2/3, and empty vectors",
            "exact clamp bounds and the inclusive steady band as the rejection discriminator",
            "two-sided clamp with status thresholds",
        ),
        c(
            "f26dnd-archery-end-scorer",
            "Archery end scorer",
            "archery_end",
            """
            class EndError : public std::invalid_argument {
            public:
                explicit EndError(const std::string& message) : std::invalid_argument(message) {}
            };
            class EndScorer {
            public:
                explicit EndScorer(int arrows);
                int arrows() const;
                int total(const std::vector<int>& scores) const;
                std::vector<int> kept(const std::vector<int>& scores) const;
            };
            """,
            """
            class EndError : public std::invalid_argument {
            public:
                explicit EndError(const std::string& message) : std::invalid_argument(message) {}
            };
            class EndScorer {
            public:
                explicit EndScorer(int arrows);
                int arrows() const;
                int total(const std::vector<int>& scores) const;
                std::vector<int> kept(const std::vector<int>& scores) const;
            private:
                int arrows_;
            };
            """,
            """
            EndScorer::EndScorer(int arrows) : arrows_(arrows) {
                if (arrows < 3 || arrows > 6) throw EndError("arrows outside 3..6");
            }
            int EndScorer::arrows() const { return arrows_; }
            int EndScorer::total(const std::vector<int>& scores) const {
                const std::vector<int> middle = kept(scores);
                int sum = 0;
                for (int value : middle) sum += value;
                return sum;
            }
            std::vector<int> EndScorer::kept(const std::vector<int>& scores) const {
                if (static_cast<int>(scores.size()) != arrows_) throw EndError("scores size must equal arrows");
                std::vector<int> ordered = scores;
                for (int value : ordered) {
                    if (value < 0 || value > 10) throw EndError("score outside 0..10");
                }
                std::sort(ordered.begin(), ordered.end());
                return std::vector<int>(ordered.begin() + 1, ordered.end() - 1);
            }
            """,
            """
            EndScorer::EndScorer(int arrows) : arrows_(arrows) {
                if (arrows < 3 || arrows > 6) throw EndError("arrows outside 3..6");
            }
            int EndScorer::arrows() const { return arrows_; }
            int EndScorer::total(const std::vector<int>& scores) const {
                const std::vector<int> middle = kept(scores);
                int sum = 0;
                for (int value : middle) sum += value;
                return sum;
            }
            std::vector<int> EndScorer::kept(const std::vector<int>& scores) const {
                if (static_cast<int>(scores.size()) != arrows_) throw EndError("scores size must equal arrows");
                std::vector<int> ordered = scores;
                for (int value : ordered) {
                    if (value < 0 || value > 10) throw EndError("score outside 0..10");
                }
                std::sort(ordered.begin(), ordered.end());
                return std::vector<int>(ordered.begin() + 1, ordered.end());
            }
            """,
            """
            EndScorer s(4);
            if (s.arrows() != 4) return 1;
            if (s.total({2, 7, 4, 9}) != 11) return 2;
            if (s.kept({2, 7, 4, 9}) != std::vector<int>{4, 7}) return 3;
            EndScorer three(3);
            if (three.total({10, 0, 5}) != 5) return 4;
            if (three.kept({10, 0, 5}) != std::vector<int>{5}) return 5;
            EndScorer six(6);
            if (six.total({1, 1, 2, 2, 3, 3}) != 8) return 6;
            if (six.kept({1, 1, 2, 2, 3, 3}) != std::vector<int>({1, 2, 2, 3})) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { EndScorer bad(2); } catch (const EndError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { EndScorer bad(7); } catch (const EndError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { EndScorer s(4); s.total({1, 2, 3}); } catch (const EndError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { EndScorer s(4); s.total({1, 2, 3, 11}); } catch (const EndError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { EndScorer s(4); s.kept({1, 2, 3, -1}); } catch (const EndError&) { threw = true; }
            if (!threw) return 5;
            EndScorer five(5);
            if (five.total({8, 8, 8, 8, 8}) != 24) return 6;
            if (five.kept({8, 8, 8, 8, 8}) != std::vector<int>({8, 8, 8})) return 7;
            if (five.total({0, 10, 10, 10, 10}) != 30) return 8;
            EndScorer six(6);
            if (six.total({0, 0, 0, 10, 10, 10}) != 20) return 9;
            if (six.kept({5, 5, 5, 5, 5, 5}) != std::vector<int>({5, 5, 5, 5})) return 10;
            return 0;
            """,
            "sorted two-end trim with exact kept-set publication",
            "pseudo-random generators, dice-roll simulators, <random>, and single-end trimming",
            "arrow bounds at 2 and 7, wrong-size and out-of-range element rejection, duplicate extremes dropped once each, and kept order sorted ascending",
            "two-end trim discipline with an observable kept set as the rejection discriminator",
            "two-end trimmed sum",
        ),
        c(
            "f26dnd-diving-panel-tally",
            "Diving panel tally",
            "diving_panel",
            """
            class PanelError : public std::domain_error {
            public:
                explicit PanelError(const std::string& message) : std::domain_error(message) {}
            };
            class PanelTally {
            public:
                PanelTally(int judges, int difficulty_tenths);
                int judges() const;
                int difficulty_tenths() const;
                int trimmed_sum(const std::vector<int>& marks) const;
                int award(const std::vector<int>& marks) const;
            };
            """,
            """
            class PanelError : public std::domain_error {
            public:
                explicit PanelError(const std::string& message) : std::domain_error(message) {}
            };
            class PanelTally {
            public:
                PanelTally(int judges, int difficulty_tenths);
                int judges() const;
                int difficulty_tenths() const;
                int trimmed_sum(const std::vector<int>& marks) const;
                int award(const std::vector<int>& marks) const;
            private:
                int judges_;
                int difficulty_tenths_;
            };
            """,
            """
            PanelTally::PanelTally(int judges, int difficulty_tenths) : judges_(judges), difficulty_tenths_(difficulty_tenths) {
                if (judges < 5 || judges > 9) throw PanelError("judges outside 5..9");
                if (difficulty_tenths < 10 || difficulty_tenths > 40) throw PanelError("difficulty tenths outside 10..40");
            }
            int PanelTally::judges() const { return judges_; }
            int PanelTally::difficulty_tenths() const { return difficulty_tenths_; }
            int PanelTally::trimmed_sum(const std::vector<int>& marks) const {
                if (static_cast<int>(marks.size()) != judges_) throw PanelError("marks size must equal judges");
                std::vector<int> ordered = marks;
                for (int value : ordered) {
                    if (value < 0 || value > 20) throw PanelError("mark outside 0..20");
                }
                std::sort(ordered.begin(), ordered.end());
                int sum = 0;
                for (std::size_t i = 1; i + 1 < ordered.size(); ++i) sum += ordered[i];
                return sum;
            }
            int PanelTally::award(const std::vector<int>& marks) const {
                return trimmed_sum(marks) * difficulty_tenths_ / 10;
            }
            """,
            """
            PanelTally::PanelTally(int judges, int difficulty_tenths) : judges_(judges), difficulty_tenths_(difficulty_tenths) {
                if (judges < 5 || judges > 9) throw PanelError("judges outside 5..9");
                if (difficulty_tenths < 10 || difficulty_tenths > 40) throw PanelError("difficulty tenths outside 10..40");
            }
            int PanelTally::judges() const { return judges_; }
            int PanelTally::difficulty_tenths() const { return difficulty_tenths_; }
            int PanelTally::trimmed_sum(const std::vector<int>& marks) const {
                if (static_cast<int>(marks.size()) != judges_) throw PanelError("marks size must equal judges");
                std::vector<int> ordered = marks;
                for (int value : ordered) {
                    if (value < 0 || value > 20) throw PanelError("mark outside 0..20");
                }
                std::sort(ordered.begin(), ordered.end());
                int sum = 0;
                for (std::size_t i = 1; i + 1 < ordered.size(); ++i) sum += ordered[i];
                return sum;
            }
            int PanelTally::award(const std::vector<int>& marks) const {
                return (trimmed_sum(marks) * difficulty_tenths_ + 5) / 10;
            }
            """,
            """
            PanelTally t(5, 20);
            if (t.judges() != 5) return 1;
            if (t.difficulty_tenths() != 20) return 2;
            if (t.trimmed_sum({15, 3, 20, 10, 7}) != 32) return 3;
            if (t.award({15, 3, 20, 10, 7}) != 64) return 4;
            PanelTally u(7, 15);
            if (u.trimmed_sum({0, 5, 5, 5, 5, 10, 20}) != 30) return 5;
            if (u.award({0, 5, 5, 5, 5, 10, 20}) != 45) return 6;
            PanelTally v(5, 13);
            if (v.trimmed_sum({1, 2, 3, 4, 5}) != 9) return 7;
            if (v.award({1, 2, 3, 4, 5}) != 11) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { PanelTally bad(4, 20); } catch (const PanelError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PanelTally bad(10, 20); } catch (const PanelError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PanelTally bad(5, 9); } catch (const PanelError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PanelTally bad(5, 41); } catch (const PanelError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { PanelTally t(5, 20); t.trimmed_sum({1, 2, 3, 4}); } catch (const PanelError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { PanelTally t(5, 20); t.trimmed_sum({1, 2, 3, 4, 21}); } catch (const PanelError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { PanelTally t(5, 20); t.award({1, 2, 3, 4, -1}); } catch (const PanelError&) { threw = true; }
            if (!threw) return 7;
            PanelTally nine(9, 10);
            if (nine.trimmed_sum({1, 2, 3, 4, 5, 6, 7, 8, 9}) != 35) return 8;
            if (nine.award({1, 2, 3, 4, 5, 6, 7, 8, 9}) != 35) return 9;
            PanelTally w(6, 25);
            if (w.trimmed_sum({20, 0, 10, 10, 10, 5}) != 35) return 10;
            if (w.award({20, 0, 10, 10, 10, 5}) != 87) return 11;
            PanelTally z(5, 40);
            if (z.award({0, 0, 0, 0, 0}) != 0) return 12;
            return 0;
            """,
            "two-end trim followed by an exact truncating tenths scale",
            "pseudo-random generators, dice-roll simulators, <random>, floating-point rounding libraries, and rounded final division",
            "judge and difficulty bounds, size and element rejection, trim on nine judges keeping seven, and the truncation case 117 / 10 -> 11",
            "truncating scale after a trimmed aggregate as the rejection discriminator",
            "trimmed sum with tenths scaling",
        ),
        c(
            "f26dnd-curling-house-counter",
            "Curling house counter",
            "curling_house",
            """
            class HouseError : public std::invalid_argument {
            public:
                explicit HouseError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HouseCounter {
            public:
                explicit HouseCounter(int radius);
                int radius() const;
                int score(const std::vector<int>& distances) const;
                int closest(const std::vector<int>& distances) const;
                std::vector<int> scoring(const std::vector<int>& distances) const;
            };
            """,
            """
            class HouseError : public std::invalid_argument {
            public:
                explicit HouseError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HouseCounter {
            public:
                explicit HouseCounter(int radius);
                int radius() const;
                int score(const std::vector<int>& distances) const;
                int closest(const std::vector<int>& distances) const;
                std::vector<int> scoring(const std::vector<int>& distances) const;
            private:
                int radius_;
            };
            """,
            """
            HouseCounter::HouseCounter(int radius) : radius_(radius) {
                if (radius < 30 || radius > 60) throw HouseError("radius outside 30..60");
            }
            int HouseCounter::radius() const { return radius_; }
            int HouseCounter::score(const std::vector<int>& distances) const {
                if (distances.size() > 16) throw HouseError("too many distances");
                int count = 0;
                for (int value : distances) {
                    if (value < 0 || value > 600) throw HouseError("distance outside 0..600");
                    if (value <= radius_) ++count;
                }
                return count;
            }
            int HouseCounter::closest(const std::vector<int>& distances) const {
                if (distances.size() > 16) throw HouseError("too many distances");
                int best = -1;
                for (int value : distances) {
                    if (value < 0 || value > 600) throw HouseError("distance outside 0..600");
                    if (best < 0 || value < best) best = value;
                }
                return best;
            }
            std::vector<int> HouseCounter::scoring(const std::vector<int>& distances) const {
                if (distances.size() > 16) throw HouseError("too many distances");
                std::vector<int> out;
                for (int value : distances) {
                    if (value < 0 || value > 600) throw HouseError("distance outside 0..600");
                    if (value <= radius_) out.push_back(value);
                }
                return out;
            }
            """,
            """
            HouseCounter::HouseCounter(int radius) : radius_(radius) {
                if (radius < 30 || radius > 60) throw HouseError("radius outside 30..60");
            }
            int HouseCounter::radius() const { return radius_; }
            int HouseCounter::score(const std::vector<int>& distances) const {
                if (distances.size() > 16) throw HouseError("too many distances");
                int count = 0;
                for (int value : distances) {
                    if (value < 0 || value > 600) throw HouseError("distance outside 0..600");
                    if (value < radius_) ++count;
                }
                return count;
            }
            int HouseCounter::closest(const std::vector<int>& distances) const {
                if (distances.size() > 16) throw HouseError("too many distances");
                int best = -1;
                for (int value : distances) {
                    if (value < 0 || value > 600) throw HouseError("distance outside 0..600");
                    if (best < 0 || value < best) best = value;
                }
                return best;
            }
            std::vector<int> HouseCounter::scoring(const std::vector<int>& distances) const {
                if (distances.size() > 16) throw HouseError("too many distances");
                std::vector<int> out;
                for (int value : distances) {
                    if (value < 0 || value > 600) throw HouseError("distance outside 0..600");
                    if (value < radius_) out.push_back(value);
                }
                return out;
            }
            """,
            """
            HouseCounter c(45);
            if (c.radius() != 45) return 1;
            if (c.score({10, 45, 46, 0}) != 3) return 2;
            if (c.closest({10, 45, 46, 0}) != 0) return 3;
            if (c.closest({}) != -1) return 4;
            if (c.scoring({10, 45, 46, 0}) != std::vector<int>{10, 45, 0}) return 5;
            HouseCounter wide(60);
            if (wide.score({60, 61, 0}) != 2) return 6;
            if (wide.closest({300, 12, 45}) != 12) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { HouseCounter bad(29); } catch (const HouseError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { HouseCounter bad(61); } catch (const HouseError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { HouseCounter c(45); c.score(std::vector<int>(17, 10)); } catch (const HouseError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { HouseCounter c(45); c.score({-1}); } catch (const HouseError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { HouseCounter c(45); c.closest({601}); } catch (const HouseError&) { threw = true; }
            if (!threw) return 5;
            HouseCounter tight(30);
            if (tight.score({30, 31, 29}) != 2) return 6;
            if (tight.scoring({30, 31, 29}) != std::vector<int>{30, 29}) return 7;
            if (tight.closest({}) != -1) return 8;
            HouseCounter c(45);
            if (c.score({}) != 0) return 9;
            if (!c.scoring({}).empty()) return 10;
            if (c.score({600, 600, 600}) != 0) return 11;
            if (c.closest({600}) != 600) return 12;
            return 0;
            """,
            "order-preserving filter with inclusive radius and an empty-input sentinel probe",
            "pseudo-random generators, dice-roll simulators, <random>, and exclusive radius comparison",
            "radius bounds at 29 and 61, size bound at 17, element bounds, distance exactly equal to the radius counted, and empty vectors",
            "inclusive-versus-exclusive comparison on the boundary as the rejection discriminator",
            "filter count with closest probe",
        ),

        c(
            "f26dnd-guild-recruit-roster",
            "Guild recruit roster",
            "guild_recruit",
            """
            class RecruitError : public std::invalid_argument {
            public:
                explicit RecruitError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RecruitProfile {
            public:
                explicit RecruitProfile(const std::vector<int>& aptitudes);
                int aptitude(std::size_t index) const;
                int total() const;
                int strongest() const;
                std::string rank() const;
            };
            """,
            """
            class RecruitError : public std::invalid_argument {
            public:
                explicit RecruitError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RecruitProfile {
            public:
                explicit RecruitProfile(const std::vector<int>& aptitudes);
                int aptitude(std::size_t index) const;
                int total() const;
                int strongest() const;
                std::string rank() const;
            private:
                std::vector<int> aptitudes_;
                int total_;
            };
            """,
            """
            RecruitProfile::RecruitProfile(const std::vector<int>& aptitudes) : aptitudes_(aptitudes), total_(0) {
                if (aptitudes_.size() != 4) throw RecruitError("exactly four aptitudes required");
                for (int value : aptitudes_) {
                    if (value < 1 || value > 20) throw RecruitError("aptitude outside 1..20");
                    total_ += value;
                }
                if (total_ > 60) throw RecruitError("aptitude budget 60 exceeded");
            }
            int RecruitProfile::aptitude(std::size_t index) const {
                if (index >= aptitudes_.size()) throw RecruitError("aptitude index out of range");
                return aptitudes_[index];
            }
            int RecruitProfile::total() const { return total_; }
            int RecruitProfile::strongest() const {
                int best = 0;
                for (std::size_t i = 1; i < aptitudes_.size(); ++i) {
                    if (aptitudes_[i] > aptitudes_[static_cast<std::size_t>(best)]) best = static_cast<int>(i);
                }
                return best;
            }
            std::string RecruitProfile::rank() const {
                if (total_ >= 55) return "elite";
                if (total_ >= 40) return "ready";
                if (total_ >= 25) return "trainee";
                return "recruit";
            }
            """,
            """
            RecruitProfile::RecruitProfile(const std::vector<int>& aptitudes) : aptitudes_(aptitudes), total_(0) {
                if (aptitudes_.size() != 4) throw RecruitError("exactly four aptitudes required");
                for (int value : aptitudes_) {
                    if (value < 1 || value > 20) throw RecruitError("aptitude outside 1..20");
                    total_ += value;
                }
                if (total_ > 60) throw RecruitError("aptitude budget 60 exceeded");
            }
            int RecruitProfile::aptitude(std::size_t index) const {
                if (index >= aptitudes_.size()) throw RecruitError("aptitude index out of range");
                return aptitudes_[index];
            }
            int RecruitProfile::total() const { return total_; }
            int RecruitProfile::strongest() const {
                int best = 0;
                for (std::size_t i = 1; i < aptitudes_.size(); ++i) {
                    if (aptitudes_[i] >= aptitudes_[static_cast<std::size_t>(best)]) best = static_cast<int>(i);
                }
                return best;
            }
            std::string RecruitProfile::rank() const {
                if (total_ >= 55) return "elite";
                if (total_ >= 40) return "ready";
                if (total_ >= 25) return "trainee";
                return "recruit";
            }
            """,
            """
            RecruitProfile r({12, 15, 8, 20});
            if (r.total() != 55) return 1;
            if (r.rank() != "elite") return 2;
            if (r.aptitude(0) != 12) return 3;
            if (r.aptitude(3) != 20) return 4;
            if (r.strongest() != 3) return 5;
            RecruitProfile s({10, 10, 10, 10});
            if (s.total() != 40) return 6;
            if (s.rank() != "ready") return 7;
            if (s.strongest() != 0) return 8;
            RecruitProfile t({5, 6, 7, 4});
            if (t.total() != 22) return 9;
            if (t.rank() != "recruit") return 10;
            if (t.strongest() != 2) return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { RecruitProfile bad({1, 2, 3}); } catch (const RecruitError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RecruitProfile bad({1, 2, 3, 4, 5}); } catch (const RecruitError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { RecruitProfile bad({0, 10, 10, 10}); } catch (const RecruitError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { RecruitProfile bad({21, 10, 10, 10}); } catch (const RecruitError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { RecruitProfile bad({20, 20, 20, 1}); } catch (const RecruitError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { RecruitProfile ok({10, 10, 10, 10}); ok.aptitude(4); } catch (const RecruitError&) { threw = true; }
            if (!threw) return 6;
            RecruitProfile elite({14, 14, 14, 13});
            if (elite.total() != 55) return 7;
            if (elite.rank() != "elite") return 8;
            RecruitProfile ready({14, 14, 14, 12});
            if (ready.total() != 54) return 9;
            if (ready.rank() != "ready") return 10;
            RecruitProfile trainee({7, 6, 6, 6});
            if (trainee.total() != 25) return 11;
            if (trainee.rank() != "trainee") return 12;
            RecruitProfile plain({6, 6, 6, 6});
            if (plain.total() != 24) return 13;
            if (plain.rank() != "recruit") return 14;
            RecruitProfile tie({9, 20, 20, 5});
            if (tie.strongest() != 1) return 15;
            RecruitProfile budget({15, 15, 15, 15});
            if (budget.total() != 60) return 16;
            if (budget.rank() != "elite") return 17;
            return 0;
            """,
            "owned four-cell record with a construction-time budget invariant and first-win tie selection",
            "pseudo-random generators, dice-roll simulators, <random>, and last-win tie selection",
            "size 3 and 5 rejection, value bounds at 0 and 21, sum 61 rejection, index 4 rejection, rank boundaries at 55/54, 40/39, and 25/24, and first-win ties",
            "budget invariant plus deterministic tie policy as the rejection discriminator",
            "budgeted aptitude record",
        ),
        c(
            "f26dnd-caravan-wagon-manifest",
            "Caravan wagon manifest",
            "caravan_wagon",
            """
            class WagonError : public std::domain_error {
            public:
                explicit WagonError(const std::string& message) : std::domain_error(message) {}
            };
            class WagonManifest {
            public:
                WagonManifest(int axles, int crates);
                int axles() const;
                int crates() const;
                int capacity() const;
                bool overloaded() const;
                int fee() const;
                std::vector<int> distribute() const;
            };
            """,
            """
            class WagonError : public std::domain_error {
            public:
                explicit WagonError(const std::string& message) : std::domain_error(message) {}
            };
            class WagonManifest {
            public:
                WagonManifest(int axles, int crates);
                int axles() const;
                int crates() const;
                int capacity() const;
                bool overloaded() const;
                int fee() const;
                std::vector<int> distribute() const;
            private:
                int axles_;
                int crates_;
            };
            """,
            """
            WagonManifest::WagonManifest(int axles, int crates) : axles_(axles), crates_(crates) {
                if (axles < 2 || axles > 8) throw WagonError("axles outside 2..8");
                if (crates < 0 || crates > 200) throw WagonError("crates outside 0..200");
            }
            int WagonManifest::axles() const { return axles_; }
            int WagonManifest::crates() const { return crates_; }
            int WagonManifest::capacity() const { return axles_ * 24; }
            bool WagonManifest::overloaded() const { return crates_ > capacity(); }
            int WagonManifest::fee() const {
                const int base = crates_ * 3;
                if (!overloaded()) return base;
                return base + (crates_ - capacity()) * 5;
            }
            std::vector<int> WagonManifest::distribute() const {
                if (overloaded()) throw WagonError("cannot distribute an overloaded wagon");
                std::vector<int> out(static_cast<std::size_t>(axles_), crates_ / axles_);
                for (int i = 0; i < crates_ % axles_; ++i) out[static_cast<std::size_t>(i)] += 1;
                return out;
            }
            """,
            """
            WagonManifest::WagonManifest(int axles, int crates) : axles_(axles), crates_(crates) {
                if (axles < 2 || axles > 8) throw WagonError("axles outside 2..8");
                if (crates < 0 || crates > 200) throw WagonError("crates outside 0..200");
            }
            int WagonManifest::axles() const { return axles_; }
            int WagonManifest::crates() const { return crates_; }
            int WagonManifest::capacity() const { return axles_ * 24; }
            bool WagonManifest::overloaded() const { return crates_ > capacity(); }
            int WagonManifest::fee() const {
                const int base = crates_ * 3;
                if (!overloaded()) return base;
                return base + (crates_ - capacity()) * 5;
            }
            std::vector<int> WagonManifest::distribute() const {
                if (overloaded()) throw WagonError("cannot distribute an overloaded wagon");
                std::vector<int> out(static_cast<std::size_t>(axles_), crates_ / axles_);
                for (int i = 0; i < crates_ % axles_; ++i) out[static_cast<std::size_t>(axles_ - 1 - i)] += 1;
                return out;
            }
            """,
            """
            WagonManifest w(4, 50);
            if (w.axles() != 4) return 1;
            if (w.crates() != 50) return 2;
            if (w.capacity() != 96) return 3;
            if (w.overloaded()) return 4;
            if (w.fee() != 150) return 5;
            if (w.distribute() != std::vector<int>{13, 13, 12, 12}) return 6;
            WagonManifest x(2, 100);
            if (x.capacity() != 48) return 7;
            if (!x.overloaded()) return 8;
            if (x.fee() != 560) return 9;
            WagonManifest empty(5, 0);
            if (empty.overloaded()) return 10;
            if (empty.fee() != 0) return 11;
            if (empty.distribute() != std::vector<int>({0, 0, 0, 0, 0})) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { WagonManifest bad(1, 0); } catch (const WagonError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { WagonManifest bad(9, 0); } catch (const WagonError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { WagonManifest bad(2, -1); } catch (const WagonError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { WagonManifest bad(2, 201); } catch (const WagonError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { WagonManifest x(2, 100); x.distribute(); } catch (const WagonError&) { threw = true; }
            if (!threw) return 5;
            WagonManifest exact(3, 72);
            if (exact.overloaded()) return 6;
            if (exact.distribute() != std::vector<int>{24, 24, 24}) return 7;
            if (exact.fee() != 216) return 8;
            WagonManifest over(3, 73);
            if (!over.overloaded()) return 9;
            if (over.fee() != 224) return 10;
            WagonManifest rim(4, 96);
            if (rim.overloaded()) return 11;
            if (rim.fee() != 288) return 12;
            WagonManifest rim_over(4, 97);
            if (!rim_over.overloaded()) return 13;
            if (rim_over.fee() != 296) return 14;
            if (rim_over.axles() != 4) return 15;
            WagonManifest spread(6, 20);
            if (spread.distribute() != std::vector<int>({4, 4, 3, 3, 3, 3})) return 16;
            return 0;
            """,
            "quotient/remainder front-heavy distribution gated by an overload rule with a linear surcharge",
            "pseudo-random generators, dice-roll simulators, <random>, and rear-heavy distribution",
            "axle and crate bounds, overload at capacity +1, surcharge arithmetic, distribute rejection when overloaded, and exact-capacity and zero-crate distributions",
            "distribution order as the rejection discriminator",
            "load plan with surcharge",
            project_support=True,
        ),
        c(
            "f26dnd-lighthouse-roster-planner",
            "Lighthouse roster planner",
            "lighthouse_roster",
            """
            class RosterError : public std::invalid_argument {
            public:
                explicit RosterError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RosterPlanner {
            public:
                RosterPlanner(int keepers, int days);
                int keepers() const;
                int days() const;
                int shift_for(int keeper, int day) const;
                std::vector<int> night_counts() const;
                std::vector<int> patrol_counts() const;
            };
            """,
            """
            class RosterError : public std::invalid_argument {
            public:
                explicit RosterError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RosterPlanner {
            public:
                RosterPlanner(int keepers, int days);
                int keepers() const;
                int days() const;
                int shift_for(int keeper, int day) const;
                std::vector<int> night_counts() const;
                std::vector<int> patrol_counts() const;
            private:
                int keepers_;
                int days_;
            };
            """,
            """
            RosterPlanner::RosterPlanner(int keepers, int days) : keepers_(keepers), days_(days) {
                if (keepers < 1 || keepers > 6) throw RosterError("keepers outside 1..6");
                if (days < 1 || days > 28) throw RosterError("days outside 1..28");
            }
            int RosterPlanner::keepers() const { return keepers_; }
            int RosterPlanner::days() const { return days_; }
            int RosterPlanner::shift_for(int keeper, int day) const {
                if (keeper < 0 || keeper >= keepers_) throw RosterError("keeper index out of range");
                if (day < 0 || day >= days_) throw RosterError("day index out of range");
                return (day + keeper) % 3;
            }
            std::vector<int> RosterPlanner::night_counts() const {
                std::vector<int> out(static_cast<std::size_t>(keepers_), 0);
                for (int keeper = 0; keeper < keepers_; ++keeper) {
                    for (int day = 0; day < days_; ++day) {
                        if ((day + keeper) % 3 == 2) out[static_cast<std::size_t>(keeper)] += 1;
                    }
                }
                return out;
            }
            std::vector<int> RosterPlanner::patrol_counts() const {
                std::vector<int> out(static_cast<std::size_t>(keepers_), 0);
                for (int keeper = 0; keeper < keepers_; ++keeper) {
                    for (int day = 0; day < days_; ++day) {
                        if ((day + keeper) % 3 == 1) out[static_cast<std::size_t>(keeper)] += 1;
                    }
                }
                return out;
            }
            """,
            """
            RosterPlanner::RosterPlanner(int keepers, int days) : keepers_(keepers), days_(days) {
                if (keepers < 1 || keepers > 6) throw RosterError("keepers outside 1..6");
                if (days < 1 || days > 28) throw RosterError("days outside 1..28");
            }
            int RosterPlanner::keepers() const { return keepers_; }
            int RosterPlanner::days() const { return days_; }
            int RosterPlanner::shift_for(int keeper, int day) const {
                if (keeper < 0 || keeper >= keepers_) throw RosterError("keeper index out of range");
                if (day < 0 || day >= days_) throw RosterError("day index out of range");
                return (day + keeper + 1) % 3;
            }
            std::vector<int> RosterPlanner::night_counts() const {
                std::vector<int> out(static_cast<std::size_t>(keepers_), 0);
                for (int keeper = 0; keeper < keepers_; ++keeper) {
                    for (int day = 0; day < days_; ++day) {
                        if ((day + keeper + 1) % 3 == 2) out[static_cast<std::size_t>(keeper)] += 1;
                    }
                }
                return out;
            }
            std::vector<int> RosterPlanner::patrol_counts() const {
                std::vector<int> out(static_cast<std::size_t>(keepers_), 0);
                for (int keeper = 0; keeper < keepers_; ++keeper) {
                    for (int day = 0; day < days_; ++day) {
                        if ((day + keeper + 1) % 3 == 1) out[static_cast<std::size_t>(keeper)] += 1;
                    }
                }
                return out;
            }
            """,
            """
            RosterPlanner p(2, 6);
            if (p.keepers() != 2) return 1;
            if (p.days() != 6) return 2;
            if (p.shift_for(0, 0) != 0) return 3;
            if (p.shift_for(1, 0) != 1) return 4;
            if (p.shift_for(0, 1) != 1) return 5;
            if (p.shift_for(1, 1) != 2) return 6;
            if (p.shift_for(0, 2) != 2) return 7;
            if (p.shift_for(1, 2) != 0) return 8;
            if (p.night_counts() != std::vector<int>{2, 2}) return 9;
            if (p.patrol_counts() != std::vector<int>{2, 2}) return 10;
            RosterPlanner solo(1, 7);
            if (solo.night_counts() != std::vector<int>{2}) return 11;
            if (solo.patrol_counts() != std::vector<int>{2}) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { RosterPlanner bad(0, 7); } catch (const RosterError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RosterPlanner bad(7, 7); } catch (const RosterError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { RosterPlanner bad(1, 0); } catch (const RosterError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { RosterPlanner bad(1, 29); } catch (const RosterError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { RosterPlanner p(2, 6); p.shift_for(2, 0); } catch (const RosterError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { RosterPlanner p(2, 6); p.shift_for(0, 6); } catch (const RosterError&) { threw = true; }
            if (!threw) return 6;
            RosterPlanner uneven(3, 4);
            if (uneven.night_counts() != std::vector<int>({1, 1, 2})) return 7;
            if (uneven.patrol_counts() != std::vector<int>({1, 2, 1})) return 8;
            if (uneven.shift_for(2, 0) != 2) return 9;
            if (uneven.shift_for(2, 3) != 2) return 10;
            RosterPlanner wide(4, 1);
            if (wide.shift_for(3, 0) != 0) return 11;
            if (wide.night_counts() != std::vector<int>({0, 0, 1, 0})) return 12;
            RosterPlanner longest(1, 28);
            if (longest.night_counts() != std::vector<int>{9}) return 13;
            if (longest.patrol_counts() != std::vector<int>{9}) return 14;
            return 0;
            """,
            "modular cyclic scheduling with exact per-keeper aggregate counts",
            "pseudo-random generators, dice-roll simulators, <random>, and phase-shifted cycles",
            "keeper and day bounds, index rejection, phase zero at keeper 0 day 0, uneven period counts per keeper, and the full 28-day cycle",
            "cycle phase discipline as the rejection discriminator",
            "cyclic shift roster",
        ),
        c(
            "f26dnd-bakery-oven-schedule",
            "Bakery oven schedule",
            "bakery_oven",
            """
            class OvenError : public std::domain_error {
            public:
                explicit OvenError(const std::string& message) : std::domain_error(message) {}
            };
            class OvenSchedule {
            public:
                OvenSchedule(int racks, int loaves_per_rack, int loaves);
                int racks() const;
                int loaves_per_rack() const;
                int loaves() const;
                int capacity() const;
                int full_batches() const;
                int leftover() const;
                int partial_racks() const;
                int minutes() const;
            };
            """,
            """
            class OvenError : public std::domain_error {
            public:
                explicit OvenError(const std::string& message) : std::domain_error(message) {}
            };
            class OvenSchedule {
            public:
                OvenSchedule(int racks, int loaves_per_rack, int loaves);
                int racks() const;
                int loaves_per_rack() const;
                int loaves() const;
                int capacity() const;
                int full_batches() const;
                int leftover() const;
                int partial_racks() const;
                int minutes() const;
            private:
                int racks_;
                int loaves_per_rack_;
                int loaves_;
            };
            """,
            """
            OvenSchedule::OvenSchedule(int racks, int loaves_per_rack, int loaves) : racks_(racks), loaves_per_rack_(loaves_per_rack), loaves_(loaves) {
                if (racks < 1 || racks > 10) throw OvenError("racks outside 1..10");
                if (loaves_per_rack < 1 || loaves_per_rack > 40) throw OvenError("loaves per rack outside 1..40");
                if (loaves < 0 || loaves > 4000) throw OvenError("loaves outside 0..4000");
            }
            int OvenSchedule::racks() const { return racks_; }
            int OvenSchedule::loaves_per_rack() const { return loaves_per_rack_; }
            int OvenSchedule::loaves() const { return loaves_; }
            int OvenSchedule::capacity() const { return racks_ * loaves_per_rack_; }
            int OvenSchedule::full_batches() const { return loaves_ / capacity(); }
            int OvenSchedule::leftover() const { return loaves_ % capacity(); }
            int OvenSchedule::partial_racks() const {
                const int rest = leftover();
                if (rest == 0) return 0;
                return (rest + loaves_per_rack_ - 1) / loaves_per_rack_;
            }
            int OvenSchedule::minutes() const {
                const int base = full_batches() * 45;
                if (leftover() == 0) return base;
                return base + 30;
            }
            """,
            """
            OvenSchedule::OvenSchedule(int racks, int loaves_per_rack, int loaves) : racks_(racks), loaves_per_rack_(loaves_per_rack), loaves_(loaves) {
                if (racks < 1 || racks > 10) throw OvenError("racks outside 1..10");
                if (loaves_per_rack < 1 || loaves_per_rack > 40) throw OvenError("loaves per rack outside 1..40");
                if (loaves < 0 || loaves > 4000) throw OvenError("loaves outside 0..4000");
            }
            int OvenSchedule::racks() const { return racks_; }
            int OvenSchedule::loaves_per_rack() const { return loaves_per_rack_; }
            int OvenSchedule::loaves() const { return loaves_; }
            int OvenSchedule::capacity() const { return racks_ * loaves_per_rack_; }
            int OvenSchedule::full_batches() const { return loaves_ / capacity(); }
            int OvenSchedule::leftover() const { return loaves_ % capacity(); }
            int OvenSchedule::partial_racks() const {
                return leftover() / loaves_per_rack_;
            }
            int OvenSchedule::minutes() const {
                const int base = full_batches() * 45;
                if (leftover() == 0) return base;
                return base + 30;
            }
            """,
            """
            OvenSchedule s(2, 12, 50);
            if (s.racks() != 2) return 1;
            if (s.capacity() != 24) return 2;
            if (s.full_batches() != 2) return 3;
            if (s.leftover() != 2) return 4;
            if (s.partial_racks() != 1) return 5;
            if (s.minutes() != 120) return 6;
            OvenSchedule t(1, 10, 100);
            if (t.full_batches() != 10) return 7;
            if (t.leftover() != 0) return 8;
            if (t.partial_racks() != 0) return 9;
            if (t.minutes() != 450) return 10;
            OvenSchedule idle(3, 8, 0);
            if (idle.full_batches() != 0) return 11;
            if (idle.minutes() != 0) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { OvenSchedule bad(0, 10, 0); } catch (const OvenError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { OvenSchedule bad(11, 10, 0); } catch (const OvenError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { OvenSchedule bad(1, 0, 0); } catch (const OvenError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { OvenSchedule bad(1, 41, 0); } catch (const OvenError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { OvenSchedule bad(1, 10, -1); } catch (const OvenError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { OvenSchedule bad(1, 10, 4001); } catch (const OvenError&) { threw = true; }
            if (!threw) return 6;
            OvenSchedule a(4, 10, 45);
            if (a.full_batches() != 1) return 7;
            if (a.leftover() != 5) return 8;
            if (a.partial_racks() != 1) return 9;
            if (a.minutes() != 75) return 10;
            OvenSchedule b(2, 10, 30);
            if (b.leftover() != 10) return 11;
            if (b.partial_racks() != 1) return 12;
            OvenSchedule c(2, 10, 31);
            if (c.leftover() != 11) return 13;
            if (c.partial_racks() != 2) return 14;
            if (c.minutes() != 75) return 15;
            OvenSchedule maxed(10, 40, 4000);
            if (maxed.capacity() != 400) return 16;
            if (maxed.full_batches() != 10) return 17;
            if (maxed.minutes() != 450) return 18;
            return 0;
            """,
            "quotient/remainder batching with exact ceiling division and a flat partial surcharge",
            "pseudo-random generators, dice-roll simulators, <random>, and floor division for the partial rack count",
            "rack, per-rack, and loaf bounds, ceiling at leftover 1, exact per-rack multiples, zero-loaf schedule, and minute policy with and without leftover",
            "ceiling-versus-floor division as the rejection discriminator",
            "batch schedule with ceiling division",
        ),
        c(
            "f26dnd-cartographer-survey-grid",
            "Cartographer survey grid",
            "cartographer_survey",
            """
            class SurveyError : public std::invalid_argument {
            public:
                explicit SurveyError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SurveyGrid {
            public:
                explicit SurveyGrid(int budget);
                int budget() const;
                bool valid(const std::vector<int>& quadrants) const;
                int remainder(const std::vector<int>& quadrants) const;
                std::vector<int> excesses(const std::vector<int>& quadrants) const;
            };
            """,
            """
            class SurveyError : public std::invalid_argument {
            public:
                explicit SurveyError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SurveyGrid {
            public:
                explicit SurveyGrid(int budget);
                int budget() const;
                bool valid(const std::vector<int>& quadrants) const;
                int remainder(const std::vector<int>& quadrants) const;
                std::vector<int> excesses(const std::vector<int>& quadrants) const;
            private:
                int budget_;
            };
            """,
            """
            SurveyGrid::SurveyGrid(int budget) : budget_(budget) {
                if (budget < 10 || budget > 100) throw SurveyError("budget outside 10..100");
            }
            int SurveyGrid::budget() const { return budget_; }
            bool SurveyGrid::valid(const std::vector<int>& quadrants) const {
                if (quadrants.size() != 4) throw SurveyError("exactly four quadrants required");
                int sum = 0;
                for (int value : quadrants) {
                    if (value < 1 || value > 30) return false;
                    sum += value;
                }
                return sum == budget_;
            }
            int SurveyGrid::remainder(const std::vector<int>& quadrants) const {
                if (quadrants.size() != 4) throw SurveyError("exactly four quadrants required");
                int sum = 0;
                for (int value : quadrants) {
                    if (value < 0 || value > 100) throw SurveyError("quadrant outside 0..100");
                    sum += value;
                }
                return budget_ - sum;
            }
            std::vector<int> SurveyGrid::excesses(const std::vector<int>& quadrants) const {
                if (!valid(quadrants)) throw SurveyError("excesses require a valid allocation");
                const int share = budget_ / 4;
                std::vector<int> out;
                out.reserve(4);
                for (int value : quadrants) out.push_back(value > share ? value - share : 0);
                return out;
            }
            """,
            """
            SurveyGrid::SurveyGrid(int budget) : budget_(budget) {
                if (budget < 10 || budget > 100) throw SurveyError("budget outside 10..100");
            }
            int SurveyGrid::budget() const { return budget_; }
            bool SurveyGrid::valid(const std::vector<int>& quadrants) const {
                if (quadrants.size() != 4) throw SurveyError("exactly four quadrants required");
                int sum = 0;
                for (int value : quadrants) {
                    if (value < 1 || value > 30) return false;
                    sum += value;
                }
                return sum <= budget_;
            }
            int SurveyGrid::remainder(const std::vector<int>& quadrants) const {
                if (quadrants.size() != 4) throw SurveyError("exactly four quadrants required");
                int sum = 0;
                for (int value : quadrants) {
                    if (value < 0 || value > 100) throw SurveyError("quadrant outside 0..100");
                    sum += value;
                }
                return budget_ - sum;
            }
            std::vector<int> SurveyGrid::excesses(const std::vector<int>& quadrants) const {
                if (!valid(quadrants)) throw SurveyError("excesses require a valid allocation");
                const int share = budget_ / 4;
                std::vector<int> out;
                out.reserve(4);
                for (int value : quadrants) out.push_back(value > share ? value - share : 0);
                return out;
            }
            """,
            """
            SurveyGrid g(50);
            if (g.budget() != 50) return 1;
            if (!g.valid({13, 13, 12, 12})) return 2;
            if (!g.valid({20, 20, 5, 5})) return 3;
            if (g.valid({20, 20, 20, 0})) return 4;
            if (g.valid({25, 25, 25, 25})) return 5;
            if (g.valid({10, 10, 10, 10})) return 6;
            if (g.valid({31, 10, 5, 4})) return 7;
            if (g.remainder({10, 10, 10, 10}) != 10) return 8;
            if (g.remainder({20, 20, 10, 5}) != -5) return 9;
            if (g.excesses({20, 20, 5, 5}) != std::vector<int>{8, 8, 0, 0}) return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { SurveyGrid bad(9); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SurveyGrid bad(101); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { SurveyGrid g(50); g.valid({1, 2, 3}); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { SurveyGrid g(50); g.remainder({1, 2, 3, 4, 5}); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { SurveyGrid g(50); g.remainder({1, 2, 3, -1}); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { SurveyGrid g(50); g.remainder({1, 2, 3, 101}); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { SurveyGrid g(50); g.excesses({10, 10, 10, 10}); } catch (const SurveyError&) { threw = true; }
            if (!threw) return 7;
            SurveyGrid low(10);
            if (!low.valid({3, 3, 2, 2})) return 8;
            if (low.excesses({3, 3, 2, 2}) != std::vector<int>{1, 1, 0, 0}) return 9;
            SurveyGrid high(100);
            if (!high.valid({25, 25, 25, 25})) return 10;
            if (high.excesses({25, 25, 25, 25}) != std::vector<int>({0, 0, 0, 0})) return 11;
            if (!high.valid({30, 30, 30, 10})) return 12;
            SurveyGrid g(50);
            if (g.remainder({50, 0, 0, 0}) != 0) return 13;
            if (g.excesses({13, 13, 12, 12}) != std::vector<int>({1, 1, 0, 0})) return 14;
            if (g.valid({1, 1, 1, 47})) return 15;
            return 0;
            """,
            "exact-sum validation with per-cell caps and derived remainder and excess reports",
            "pseudo-random generators, dice-roll simulators, <random>, and at-most-sum validation",
            "budget bounds at 9 and 101, wrong-size rejection on every query, element bounds on remainder, exact-sum versus under and over sums, and excesses rejection when invalid",
            "exact-sum versus at-most-sum validation as the rejection discriminator",
            "exact-sum quadrant validator",
            project_support=True,
        ),
        c(
            "f26dnd-armory-alloy-mixer",
            "Armory alloy mixer",
            "armory_alloy",
            """
            class AlloyError : public std::domain_error {
            public:
                explicit AlloyError(const std::string& message) : std::domain_error(message) {}
            };
            class AlloyMixer {
            public:
                explicit AlloyMixer(int ingots);
                int ingots() const;
                std::string grade(int copper, int tin, int zinc) const;
                int hardness(int copper, int tin, int zinc) const;
            };
            """,
            """
            class AlloyError : public std::domain_error {
            public:
                explicit AlloyError(const std::string& message) : std::domain_error(message) {}
            };
            class AlloyMixer {
            public:
                explicit AlloyMixer(int ingots);
                int ingots() const;
                std::string grade(int copper, int tin, int zinc) const;
                int hardness(int copper, int tin, int zinc) const;
            private:
                int ingots_;
            };
            """,
            """
            AlloyMixer::AlloyMixer(int ingots) : ingots_(ingots) {
                if (ingots < 1 || ingots > 12) throw AlloyError("ingots outside 1..12");
            }
            int AlloyMixer::ingots() const { return ingots_; }
            std::string AlloyMixer::grade(int copper, int tin, int zinc) const {
                if (copper < 0 || copper > 100) throw AlloyError("copper outside 0..100");
                if (tin < 0 || tin > 100) throw AlloyError("tin outside 0..100");
                if (zinc < 0 || zinc > 100) throw AlloyError("zinc outside 0..100");
                if (copper + tin + zinc != 100) throw AlloyError("metals must sum to 100");
                if (tin >= 5 && tin <= 20 && zinc <= 10) return "standard";
                return "irregular";
            }
            int AlloyMixer::hardness(int copper, int tin, int zinc) const {
                if (copper < 0 || copper > 100) throw AlloyError("copper outside 0..100");
                if (tin < 0 || tin > 100) throw AlloyError("tin outside 0..100");
                if (zinc < 0 || zinc > 100) throw AlloyError("zinc outside 0..100");
                if (copper + tin + zinc != 100) throw AlloyError("metals must sum to 100");
                return (copper * 2 + tin * 7 + zinc * 3) * ingots_;
            }
            """,
            """
            AlloyMixer::AlloyMixer(int ingots) : ingots_(ingots) {
                if (ingots < 1 || ingots > 12) throw AlloyError("ingots outside 1..12");
            }
            int AlloyMixer::ingots() const { return ingots_; }
            std::string AlloyMixer::grade(int copper, int tin, int zinc) const {
                if (copper < 0 || copper > 100) throw AlloyError("copper outside 0..100");
                if (tin < 0 || tin > 100) throw AlloyError("tin outside 0..100");
                if (zinc < 0 || zinc > 100) throw AlloyError("zinc outside 0..100");
                if (copper + tin + zinc != 100) throw AlloyError("metals must sum to 100");
                if (tin >= 5 && tin <= 20 && zinc < 10) return "standard";
                return "irregular";
            }
            int AlloyMixer::hardness(int copper, int tin, int zinc) const {
                if (copper < 0 || copper > 100) throw AlloyError("copper outside 0..100");
                if (tin < 0 || tin > 100) throw AlloyError("tin outside 0..100");
                if (zinc < 0 || zinc > 100) throw AlloyError("zinc outside 0..100");
                if (copper + tin + zinc != 100) throw AlloyError("metals must sum to 100");
                return (copper * 2 + tin * 7 + zinc * 3) * ingots_;
            }
            """,
            """
            AlloyMixer m(1);
            if (m.ingots() != 1) return 1;
            if (m.grade(90, 8, 2) != "standard") return 2;
            if (m.grade(70, 25, 5) != "irregular") return 3;
            if (m.grade(80, 10, 10) != "standard") return 4;
            if (m.grade(87, 3, 10) != "irregular") return 5;
            if (m.hardness(90, 8, 2) != 242) return 6;
            AlloyMixer n(3);
            if (n.hardness(90, 8, 2) != 726) return 7;
            if (n.grade(0, 100, 0) != "irregular") return 8;
            if (n.hardness(0, 100, 0) != 2100) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { AlloyMixer bad(0); } catch (const AlloyError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { AlloyMixer bad(13); } catch (const AlloyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { AlloyMixer m(1); m.grade(-1, 60, 41); } catch (const AlloyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { AlloyMixer m(1); m.grade(101, 0, 0); } catch (const AlloyError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { AlloyMixer m(1); m.grade(50, 30, 19); } catch (const AlloyError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { AlloyMixer m(1); m.hardness(40, 30, 31); } catch (const AlloyError&) { threw = true; }
            if (!threw) return 6;
            AlloyMixer m(1);
            if (m.grade(79, 20, 1) != "standard") return 7;
            if (m.grade(78, 21, 1) != "irregular") return 8;
            if (m.grade(89, 5, 6) != "standard") return 9;
            if (m.grade(88, 4, 8) != "irregular") return 10;
            if (m.grade(80, 10, 10) != "standard") return 11;
            if (m.grade(79, 10, 11) != "irregular") return 12;
            if (m.hardness(33, 33, 34) != 399) return 13;
            AlloyMixer big(12);
            if (big.hardness(100, 0, 0) != 2400) return 14;
            if (big.grade(100, 0, 0) != "irregular") return 15;
            return 0;
            """,
            "sum-validated percentage recipe with a two-condition grade and weighted hardness",
            "pseudo-random generators, dice-roll simulators, <random>, and an exclusive zinc bound",
            "ingot and metal bounds, sum 99 and 101 rejection, tin boundaries at 4/5 and 20/21, zinc boundary at 10/11, and hardness scaling",
            "inclusive grade boundary as the rejection discriminator",
            "percentage recipe with grade conjunction",
        ),
        c(
            "f26dnd-apiary-hive-census",
            "Apiary hive census",
            "apiary_hive",
            """
            class HiveError : public std::invalid_argument {
            public:
                explicit HiveError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HiveCensus {
            public:
                explicit HiveCensus(int capacity);
                int capacity() const;
                int hives_needed(int bees) const;
                std::vector<int> plan(int bees) const;
                int slack(int bees) const;
            };
            """,
            """
            class HiveError : public std::invalid_argument {
            public:
                explicit HiveError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HiveCensus {
            public:
                explicit HiveCensus(int capacity);
                int capacity() const;
                int hives_needed(int bees) const;
                std::vector<int> plan(int bees) const;
                int slack(int bees) const;
            private:
                int capacity_;
            };
            """,
            """
            HiveCensus::HiveCensus(int capacity) : capacity_(capacity) {
                if (capacity < 20 || capacity > 80) throw HiveError("capacity outside 20..80");
            }
            int HiveCensus::capacity() const { return capacity_; }
            int HiveCensus::hives_needed(int bees) const {
                if (bees < 0 || bees > capacity_ * 8) throw HiveError("bees outside 0..capacity*8");
                if (bees == 0) return 0;
                return (bees + capacity_ - 1) / capacity_;
            }
            std::vector<int> HiveCensus::plan(int bees) const {
                const int hives = hives_needed(bees);
                std::vector<int> out;
                out.reserve(static_cast<std::size_t>(hives));
                int remaining = bees;
                for (int i = 0; i < hives; ++i) {
                    const int load = remaining > capacity_ ? capacity_ : remaining;
                    out.push_back(load);
                    remaining -= load;
                }
                return out;
            }
            int HiveCensus::slack(int bees) const {
                return hives_needed(bees) * capacity_ - bees;
            }
            """,
            """
            HiveCensus::HiveCensus(int capacity) : capacity_(capacity) {
                if (capacity < 20 || capacity > 80) throw HiveError("capacity outside 20..80");
            }
            int HiveCensus::capacity() const { return capacity_; }
            int HiveCensus::hives_needed(int bees) const {
                if (bees < 0 || bees > capacity_ * 8) throw HiveError("bees outside 0..capacity*8");
                if (bees == 0) return 0;
                return (bees + capacity_ - 1) / capacity_;
            }
            std::vector<int> HiveCensus::plan(int bees) const {
                const int hives = hives_needed(bees);
                if (hives == 0) return {};
                std::vector<int> out(static_cast<std::size_t>(hives), bees / hives);
                for (int i = 0; i < bees % hives; ++i) out[static_cast<std::size_t>(i)] += 1;
                return out;
            }
            int HiveCensus::slack(int bees) const {
                return hives_needed(bees) * capacity_ - bees;
            }
            """,
            """
            HiveCensus c(20);
            if (c.capacity() != 20) return 1;
            if (c.hives_needed(0) != 0) return 2;
            if (c.hives_needed(1) != 1) return 3;
            if (c.hives_needed(20) != 1) return 4;
            if (c.hives_needed(21) != 2) return 5;
            if (c.plan(45) != std::vector<int>{20, 20, 5}) return 6;
            if (c.slack(45) != 15) return 7;
            if (!c.plan(0).empty()) return 8;
            HiveCensus d(50);
            if (d.plan(50) != std::vector<int>{50}) return 9;
            if (d.plan(51) != std::vector<int>{50, 1}) return 10;
            if (d.slack(51) != 49) return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { HiveCensus bad(19); } catch (const HiveError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { HiveCensus bad(81); } catch (const HiveError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { HiveCensus c(20); c.hives_needed(-1); } catch (const HiveError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { HiveCensus c(20); c.hives_needed(161); } catch (const HiveError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { HiveCensus c(20); c.plan(200); } catch (const HiveError&) { threw = true; }
            if (!threw) return 5;
            HiveCensus c(20);
            if (c.plan(40) != std::vector<int>{20, 20}) return 6;
            if (c.slack(40) != 0) return 7;
            if (c.plan(160) != std::vector<int>(8, 20)) return 8;
            if (c.hives_needed(160) != 8) return 9;
            HiveCensus big(80);
            if (big.plan(640) != std::vector<int>(8, 80)) return 10;
            if (big.slack(640) != 0) return 11;
            HiveCensus mid(30);
            if (mid.plan(95) != std::vector<int>({30, 30, 30, 5})) return 12;
            if (mid.hives_needed(95) != 4) return 13;
            if (mid.slack(95) != 25) return 14;
            return 0;
            """,
            "ceiling count with fill-first distribution and slack accounting",
            "pseudo-random generators, dice-roll simulators, <random>, and even-spread distribution",
            "capacity and bee bounds, ceiling at one bee, exact multiples, the maximum eight-hive plan, the empty plan, and slack at exact and partial fills",
            "fill-first versus even-spread distribution as the rejection discriminator",
            "fill-first plan with slack",
        ),
        c(
            "f26dnd-marathon-pace-band",
            "Marathon pace band",
            "marathon_pace",
            """
            class PaceError : public std::domain_error {
            public:
                explicit PaceError(const std::string& message) : std::domain_error(message) {}
            };
            class PaceBand {
            public:
                explicit PaceBand(int offset);
                int offset() const;
                std::string band(int finish) const;
                int cutoff_delta(int finish) const;
                std::vector<std::string> bands(const std::vector<int>& finishes) const;
            };
            """,
            """
            class PaceError : public std::domain_error {
            public:
                explicit PaceError(const std::string& message) : std::domain_error(message) {}
            };
            class PaceBand {
            public:
                explicit PaceBand(int offset);
                int offset() const;
                std::string band(int finish) const;
                int cutoff_delta(int finish) const;
                std::vector<std::string> bands(const std::vector<int>& finishes) const;
            private:
                int offset_;
            };
            """,
            """
            PaceBand::PaceBand(int offset) : offset_(offset) {
                if (offset < -30 || offset > 30) throw PaceError("offset outside -30..30");
            }
            int PaceBand::offset() const { return offset_; }
            std::string PaceBand::band(int finish) const {
                if (finish < 3600 || finish > 21600) throw PaceError("finish outside 3600..21600");
                const int adjusted = finish + offset_;
                if (adjusted < 7200) return "gold";
                if (adjusted < 9000) return "silver";
                if (adjusted < 12000) return "bronze";
                return "finisher";
            }
            int PaceBand::cutoff_delta(int finish) const {
                if (finish < 3600 || finish > 21600) throw PaceError("finish outside 3600..21600");
                return finish + offset_ - 7200;
            }
            std::vector<std::string> PaceBand::bands(const std::vector<int>& finishes) const {
                std::vector<std::string> out;
                out.reserve(finishes.size());
                for (int finish : finishes) out.push_back(band(finish));
                return out;
            }
            """,
            """
            PaceBand::PaceBand(int offset) : offset_(offset) {
                if (offset < -30 || offset > 30) throw PaceError("offset outside -30..30");
            }
            int PaceBand::offset() const { return offset_; }
            std::string PaceBand::band(int finish) const {
                if (finish < 3600 || finish > 21600) throw PaceError("finish outside 3600..21600");
                const int adjusted = finish + offset_;
                if (adjusted <= 7200) return "gold";
                if (adjusted < 9000) return "silver";
                if (adjusted < 12000) return "bronze";
                return "finisher";
            }
            int PaceBand::cutoff_delta(int finish) const {
                if (finish < 3600 || finish > 21600) throw PaceError("finish outside 3600..21600");
                return finish + offset_ - 7200;
            }
            std::vector<std::string> PaceBand::bands(const std::vector<int>& finishes) const {
                std::vector<std::string> out;
                out.reserve(finishes.size());
                for (int finish : finishes) out.push_back(band(finish));
                return out;
            }
            """,
            """
            PaceBand p(0);
            if (p.offset() != 0) return 1;
            if (p.band(7199) != "gold") return 2;
            if (p.band(7200) != "silver") return 3;
            if (p.band(8999) != "silver") return 4;
            if (p.band(9000) != "bronze") return 5;
            if (p.band(11999) != "bronze") return 6;
            if (p.band(12000) != "finisher") return 7;
            if (p.cutoff_delta(7200) != 0) return 8;
            PaceBand q(15);
            if (q.band(7185) != "silver") return 9;
            if (q.band(7184) != "gold") return 10;
            if (q.cutoff_delta(7185) != 0) return 11;
            std::vector<std::string> got = p.bands({7199, 7200, 12000});
            if (got != std::vector<std::string>{"gold", "silver", "finisher"}) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { PaceBand bad(-31); } catch (const PaceError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PaceBand bad(31); } catch (const PaceError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PaceBand p(0); p.band(3599); } catch (const PaceError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PaceBand p(0); p.band(21601); } catch (const PaceError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { PaceBand p(0); p.cutoff_delta(100); } catch (const PaceError&) { threw = true; }
            if (!threw) return 5;
            PaceBand p(0);
            if (p.cutoff_delta(7000) != -200) return 6;
            if (p.band(21600) != "finisher") return 7;
            if (p.band(3600) != "gold") return 8;
            PaceBand hi(30);
            if (hi.band(7170) != "silver") return 9;
            PaceBand lo(-30);
            if (lo.band(7229) != "gold") return 10;
            if (lo.cutoff_delta(7230) != 0) return 11;
            PaceBand deep(-30);
            if (deep.band(12029) != "bronze") return 12;
            if (!p.bands({}).empty()) return 13;
            return 0;
            """,
            "offset adjustment with exclusive-lower-bound band thresholds",
            "pseudo-random generators, dice-roll simulators, <random>, and an inclusive gold boundary",
            "offset and finish bounds, every band edge 7199/7200, 8999/9000, and 11999/12000, positive and negative deltas, and offset extremes crossing the gold edge",
            "boundary inclusivity after an offset as the rejection discriminator",
            "offset band mapping",
        ),
        c(
            "f26dnd-vineyard-harvest-grade",
            "Vineyard harvest grade",
            "vineyard_harvest",
            """
            class HarvestError : public std::invalid_argument {
            public:
                explicit HarvestError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HarvestGrade {
            public:
                explicit HarvestGrade(bool reserve);
                bool reserve() const;
                std::string grade(int sugar, int acidity) const;
                std::vector<std::string> grades(const std::vector<int>& sugars, const std::vector<int>& acidities) const;
            };
            """,
            """
            class HarvestError : public std::invalid_argument {
            public:
                explicit HarvestError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HarvestGrade {
            public:
                explicit HarvestGrade(bool reserve);
                bool reserve() const;
                std::string grade(int sugar, int acidity) const;
                std::vector<std::string> grades(const std::vector<int>& sugars, const std::vector<int>& acidities) const;
            private:
                bool reserve_;
            };
            """,
            """
            HarvestGrade::HarvestGrade(bool reserve) : reserve_(reserve) {}
            bool HarvestGrade::reserve() const { return reserve_; }
            std::string HarvestGrade::grade(int sugar, int acidity) const {
                if (sugar < 100 || sugar > 300) throw HarvestError("sugar outside 100..300");
                if (acidity < 0 || acidity > 15) throw HarvestError("acidity outside 0..15");
                const int select_sugar = reserve_ ? 260 : 240;
                if (sugar >= select_sugar && acidity >= 6) return "select";
                if (sugar >= 200 && acidity >= 4) return "classic";
                return "table";
            }
            std::vector<std::string> HarvestGrade::grades(const std::vector<int>& sugars, const std::vector<int>& acidities) const {
                if (sugars.size() != acidities.size()) throw HarvestError("sugar and acidity counts differ");
                std::vector<std::string> out;
                out.reserve(sugars.size());
                for (std::size_t i = 0; i < sugars.size(); ++i) out.push_back(grade(sugars[i], acidities[i]));
                return out;
            }
            """,
            """
            HarvestGrade::HarvestGrade(bool reserve) : reserve_(reserve) {}
            bool HarvestGrade::reserve() const { return reserve_; }
            std::string HarvestGrade::grade(int sugar, int acidity) const {
                if (sugar < 100 || sugar > 300) throw HarvestError("sugar outside 100..300");
                if (acidity < 0 || acidity > 15) throw HarvestError("acidity outside 0..15");
                const int select_sugar = reserve_ ? 260 : 240;
                if (sugar >= select_sugar || acidity >= 6) return "select";
                if (sugar >= 200 && acidity >= 4) return "classic";
                return "table";
            }
            std::vector<std::string> HarvestGrade::grades(const std::vector<int>& sugars, const std::vector<int>& acidities) const {
                if (sugars.size() != acidities.size()) throw HarvestError("sugar and acidity counts differ");
                std::vector<std::string> out;
                out.reserve(sugars.size());
                for (std::size_t i = 0; i < sugars.size(); ++i) out.push_back(grade(sugars[i], acidities[i]));
                return out;
            }
            """,
            """
            HarvestGrade h(false);
            if (h.reserve()) return 1;
            if (h.grade(240, 6) != "select") return 2;
            if (h.grade(239, 6) != "classic") return 3;
            if (h.grade(240, 5) != "classic") return 4;
            if (h.grade(199, 7) != "table") return 5;
            if (h.grade(200, 4) != "classic") return 6;
            if (h.grade(150, 3) != "table") return 7;
            HarvestGrade r(true);
            if (!r.reserve()) return 8;
            if (r.grade(250, 7) != "classic") return 9;
            if (r.grade(260, 6) != "select") return 10;
            std::vector<std::string> got = h.grades({240, 150, 220}, {6, 3, 4});
            if (got != std::vector<std::string>{"select", "table", "classic"}) return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { HarvestGrade h(false); h.grade(99, 6); } catch (const HarvestError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { HarvestGrade h(false); h.grade(301, 6); } catch (const HarvestError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { HarvestGrade h(false); h.grade(240, -1); } catch (const HarvestError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { HarvestGrade h(false); h.grade(240, 16); } catch (const HarvestError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { HarvestGrade h(false); h.grades({200, 210}, {4}); } catch (const HarvestError&) { threw = true; }
            if (!threw) return 5;
            HarvestGrade h(false);
            if (h.grade(300, 6) != "select") return 6;
            if (h.grade(300, 5) != "classic") return 7;
            if (h.grade(200, 3) != "table") return 8;
            HarvestGrade r(true);
            if (r.grade(259, 15) != "classic") return 9;
            if (r.grade(260, 5) != "classic") return 10;
            if (r.grade(300, 6) != "select") return 11;
            if (r.grade(100, 15) != "table") return 12;
            if (!h.grades({}, {}).empty()) return 13;
            return 0;
            """,
            "two-input conjunctive grading with a configuration-shifted top threshold",
            "pseudo-random generators, dice-roll simulators, <random>, and a disjunctive select rule",
            "sugar and acidity bounds, mismatched vector rejection, select sugar edges at 239/240 and 259/260, select acidity edge at 5/6, and classic edges",
            "conjunction versus disjunction as the rejection discriminator",
            "two-input grade with reserve shift",
        ),
        c(
            "f26dnd-railway-fare-tier",
            "Railway fare tier",
            "railway_fare",
            """
            class FareError : public std::domain_error {
            public:
                explicit FareError(const std::string& message) : std::domain_error(message) {}
            };
            class FareTier {
            public:
                explicit FareTier(int class_level);
                int class_level() const;
                int base_fare(int km) const;
                int fare(int km) const;
            };
            """,
            """
            class FareError : public std::domain_error {
            public:
                explicit FareError(const std::string& message) : std::domain_error(message) {}
            };
            class FareTier {
            public:
                explicit FareTier(int class_level);
                int class_level() const;
                int base_fare(int km) const;
                int fare(int km) const;
            private:
                int class_level_;
            };
            """,
            """
            FareTier::FareTier(int class_level) : class_level_(class_level) {
                if (class_level < 1 || class_level > 3) throw FareError("class level outside 1..3");
            }
            int FareTier::class_level() const { return class_level_; }
            int FareTier::base_fare(int km) const {
                if (km < 1 || km > 2000) throw FareError("kilometres outside 1..2000");
                int total = 0;
                int remaining = km;
                const int first = remaining > 100 ? 100 : remaining;
                total += first * 12;
                remaining -= first;
                const int second = remaining > 400 ? 400 : remaining;
                total += second * 9;
                remaining -= second;
                total += remaining * 6;
                return total;
            }
            int FareTier::fare(int km) const {
                const int base = base_fare(km);
                const int percent = class_level_ == 1 ? 100 : (class_level_ == 2 ? 140 : 200);
                const int scaled = base * percent / 100;
                return scaled > 25000 ? 25000 : scaled;
            }
            """,
            """
            FareTier::FareTier(int class_level) : class_level_(class_level) {
                if (class_level < 1 || class_level > 3) throw FareError("class level outside 1..3");
            }
            int FareTier::class_level() const { return class_level_; }
            int FareTier::base_fare(int km) const {
                if (km < 1 || km > 2000) throw FareError("kilometres outside 1..2000");
                return km * 12;
            }
            int FareTier::fare(int km) const {
                const int base = base_fare(km);
                const int percent = class_level_ == 1 ? 100 : (class_level_ == 2 ? 140 : 200);
                const int scaled = base * percent / 100;
                return scaled > 25000 ? 25000 : scaled;
            }
            """,
            """
            FareTier f(1);
            if (f.class_level() != 1) return 1;
            if (f.base_fare(100) != 1200) return 2;
            if (f.base_fare(101) != 1209) return 3;
            if (f.base_fare(500) != 4800) return 4;
            if (f.base_fare(501) != 4806) return 5;
            if (f.base_fare(2000) != 13800) return 6;
            if (f.fare(100) != 1200) return 7;
            FareTier g(2);
            if (g.fare(100) != 1680) return 8;
            if (g.fare(3) != 50) return 9;
            FareTier h(3);
            if (h.fare(50) != 1200) return 10;
            if (h.fare(2000) != 25000) return 11;
            return 0;
            """,
            """
            bool threw = false;
            try { FareTier bad(0); } catch (const FareError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { FareTier bad(4); } catch (const FareError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { FareTier f(1); f.base_fare(0); } catch (const FareError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { FareTier f(1); f.base_fare(2001); } catch (const FareError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { FareTier f(1); f.fare(-5); } catch (const FareError&) { threw = true; }
            if (!threw) return 5;
            FareTier f(1);
            if (f.fare(1) != 12) return 6;
            if (f.base_fare(400) != 3900) return 7;
            if (f.base_fare(401) != 3909) return 8;
            FareTier g(2);
            if (g.fare(2000) != 19320) return 9;
            if (g.fare(1) != 16) return 10;
            FareTier h(3);
            if (h.base_fare(1000) != 7800) return 11;
            if (h.fare(1000) != 15600) return 12;
            if (h.fare(1500) != 21600) return 13;
            return 0;
            """,
            "progressive bracket accumulation with a truncating percentage scale and cap",
            "pseudo-random generators, dice-roll simulators, <random>, and a flat per-kilometre rate",
            "class and kilometre bounds, bracket edges at 100/101 and 500/501, the truncation case 36 * 140 / 100 -> 50, and cap engagement at maximum class and distance",
            "progressive brackets as the rejection discriminator",
            "progressive fare with percentage class",
        ),
        c(
            "f26dnd-fencing-bout-board",
            "Fencing bout board",
            "fencing_bout",
            """
            class BoutError : public std::invalid_argument {
            public:
                explicit BoutError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BoutBoard {
            public:
                explicit BoutBoard(int target);
                int target() const;
                int left() const;
                int right() const;
                void score_left();
                void score_right();
                bool over() const;
                std::string leader() const;
                void reset();
            };
            """,
            """
            class BoutError : public std::invalid_argument {
            public:
                explicit BoutError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BoutBoard {
            public:
                explicit BoutBoard(int target);
                int target() const;
                int left() const;
                int right() const;
                void score_left();
                void score_right();
                bool over() const;
                std::string leader() const;
                void reset();
            private:
                int target_;
                int left_ = 0;
                int right_ = 0;
                bool over_ = false;
            };
            """,
            """
            BoutBoard::BoutBoard(int target) : target_(target) {
                if (target < 5 || target > 15) throw BoutError("target outside 5..15");
            }
            int BoutBoard::target() const { return target_; }
            int BoutBoard::left() const { return left_; }
            int BoutBoard::right() const { return right_; }
            void BoutBoard::score_left() {
                if (over_) throw BoutError("bout is over");
                left_ += 1;
                if (left_ >= target_) over_ = true;
            }
            void BoutBoard::score_right() {
                if (over_) throw BoutError("bout is over");
                right_ += 1;
                if (right_ >= target_) over_ = true;
            }
            bool BoutBoard::over() const { return over_; }
            std::string BoutBoard::leader() const {
                if (left_ > right_) return "left";
                if (right_ > left_) return "right";
                return "tied";
            }
            void BoutBoard::reset() {
                left_ = 0;
                right_ = 0;
                over_ = false;
            }
            """,
            """
            BoutBoard::BoutBoard(int target) : target_(target) {
                if (target < 5 || target > 15) throw BoutError("target outside 5..15");
            }
            int BoutBoard::target() const { return target_; }
            int BoutBoard::left() const { return left_; }
            int BoutBoard::right() const { return right_; }
            void BoutBoard::score_left() {
                left_ += 1;
                if (left_ >= target_) over_ = true;
            }
            void BoutBoard::score_right() {
                right_ += 1;
                if (right_ >= target_) over_ = true;
            }
            bool BoutBoard::over() const { return over_; }
            std::string BoutBoard::leader() const {
                if (left_ > right_) return "left";
                if (right_ > left_) return "right";
                return "tied";
            }
            void BoutBoard::reset() {
                left_ = 0;
                right_ = 0;
                over_ = false;
            }
            """,
            """
            BoutBoard b(5);
            if (b.target() != 5) return 1;
            if (b.left() != 0 || b.right() != 0) return 2;
            if (b.over()) return 3;
            if (b.leader() != "tied") return 4;
            for (int i = 0; i < 5; ++i) b.score_left();
            if (b.left() != 5) return 5;
            if (!b.over()) return 6;
            if (b.leader() != "left") return 7;
            bool threw = false;
            try { b.score_right(); } catch (const BoutError&) { threw = true; }
            if (!threw) return 8;
            if (b.right() != 0) return 9;
            b.reset();
            if (b.over()) return 10;
            if (b.left() != 0 || b.right() != 0) return 11;
            b.score_right();
            if (b.right() != 1) return 12;
            if (b.leader() != "right") return 13;
            return 0;
            """,
            """
            bool threw = false;
            try { BoutBoard bad(4); } catch (const BoutError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BoutBoard bad(16); } catch (const BoutError&) { threw = true; }
            if (!threw) return 2;
            BoutBoard c(5);
            c.score_left();
            c.score_left();
            c.score_right();
            c.score_right();
            c.score_left();
            c.score_right();
            c.score_right();
            c.score_left();
            if (c.over()) return 3;
            if (c.left() != 4 || c.right() != 4) return 4;
            if (c.leader() != "tied") return 5;
            c.score_left();
            if (!c.over()) return 6;
            if (c.leader() != "left") return 7;
            if (c.left() != 5) return 8;
            threw = false;
            try { c.score_left(); } catch (const BoutError&) { threw = true; }
            if (!threw) return 9;
            if (c.left() != 5) return 10;
            c.reset();
            for (int i = 0; i < 5; ++i) c.score_right();
            if (!c.over()) return 11;
            if (c.leader() != "right") return 12;
            BoutBoard big(15);
            for (int i = 0; i < 14; ++i) big.score_left();
            if (big.over()) return 13;
            big.score_left();
            if (!big.over()) return 14;
            if (big.left() != 15) return 15;
            return 0;
            """,
            "guarded score mutations with a terminal state and a reopening reset",
            "pseudo-random generators, dice-roll simulators, <random>, and unguarded scoring",
            "target bounds at 4 and 16, terminal rejection on both scoring calls, no mutation on rejected calls, leader across left, right, and tied, and reset reopening",
            "terminal lifecycle guard as the rejection discriminator",
            "terminal-guarded scoreboard",
            project_support=True,
        ),
        c(
            "f26dnd-warehouse-stock-counter",
            "Warehouse stock counter",
            "warehouse_stock",
            """
            class StockError : public std::domain_error {
            public:
                explicit StockError(const std::string& message) : std::domain_error(message) {}
            };
            class StockCounter {
            public:
                StockCounter(int capacity, int initial);
                int capacity() const;
                int stock() const;
                int free_space() const;
                bool reorder() const;
                void receive(int count);
                void ship(int count);
            };
            """,
            """
            class StockError : public std::domain_error {
            public:
                explicit StockError(const std::string& message) : std::domain_error(message) {}
            };
            class StockCounter {
            public:
                StockCounter(int capacity, int initial);
                int capacity() const;
                int stock() const;
                int free_space() const;
                bool reorder() const;
                void receive(int count);
                void ship(int count);
            private:
                int capacity_;
                int stock_;
            };
            """,
            """
            StockCounter::StockCounter(int capacity, int initial) : capacity_(capacity), stock_(initial) {
                if (capacity < 10 || capacity > 1000) throw StockError("capacity outside 10..1000");
                if (initial < 0 || initial > capacity) throw StockError("initial outside 0..capacity");
            }
            int StockCounter::capacity() const { return capacity_; }
            int StockCounter::stock() const { return stock_; }
            int StockCounter::free_space() const { return capacity_ - stock_; }
            bool StockCounter::reorder() const { return stock_ <= capacity_ / 10; }
            void StockCounter::receive(int count) {
                if (count < 1 || count > 500) throw StockError("count outside 1..500");
                if (stock_ + count > capacity_) throw StockError("receive exceeds capacity");
                stock_ += count;
            }
            void StockCounter::ship(int count) {
                if (count < 1 || count > 500) throw StockError("count outside 1..500");
                if (count > stock_) throw StockError("ship exceeds stock");
                stock_ -= count;
            }
            """,
            """
            StockCounter::StockCounter(int capacity, int initial) : capacity_(capacity), stock_(initial) {
                if (capacity < 10 || capacity > 1000) throw StockError("capacity outside 10..1000");
                if (initial < 0 || initial > capacity) throw StockError("initial outside 0..capacity");
            }
            int StockCounter::capacity() const { return capacity_; }
            int StockCounter::stock() const { return stock_; }
            int StockCounter::free_space() const { return capacity_ - stock_; }
            bool StockCounter::reorder() const { return stock_ <= capacity_ / 10; }
            void StockCounter::receive(int count) {
                if (count < 1 || count > 500) throw StockError("count outside 1..500");
                if (stock_ + count >= capacity_) throw StockError("receive exceeds capacity");
                stock_ += count;
            }
            void StockCounter::ship(int count) {
                if (count < 1 || count > 500) throw StockError("count outside 1..500");
                if (count > stock_) throw StockError("ship exceeds stock");
                stock_ -= count;
            }
            """,
            """
            StockCounter c(100, 20);
            if (c.capacity() != 100) return 1;
            if (c.stock() != 20) return 2;
            if (c.free_space() != 80) return 3;
            if (c.reorder()) return 4;
            c.receive(80);
            if (c.stock() != 100) return 5;
            if (c.free_space() != 0) return 6;
            bool threw = false;
            try { c.receive(1); } catch (const StockError&) { threw = true; }
            if (!threw) return 7;
            if (c.stock() != 100) return 8;
            c.ship(100);
            if (c.stock() != 0) return 9;
            if (!c.reorder()) return 10;
            threw = false;
            try { c.ship(1); } catch (const StockError&) { threw = true; }
            if (!threw) return 11;
            StockCounter d(100, 10);
            if (!d.reorder()) return 12;
            StockCounter e(100, 11);
            if (e.reorder()) return 13;
            return 0;
            """,
            """
            bool threw = false;
            try { StockCounter bad(9, 0); } catch (const StockError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { StockCounter bad(1001, 0); } catch (const StockError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { StockCounter bad(100, -1); } catch (const StockError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { StockCounter bad(100, 101); } catch (const StockError&) { threw = true; }
            if (!threw) return 4;
            StockCounter c(50, 40);
            threw = false;
            try { c.receive(0); } catch (const StockError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { c.receive(501); } catch (const StockError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { c.ship(0); } catch (const StockError&) { threw = true; }
            if (!threw) return 7;
            threw = false;
            try { c.ship(41); } catch (const StockError&) { threw = true; }
            if (!threw) return 8;
            if (c.stock() != 40) return 9;
            c.receive(10);
            if (c.stock() != 50) return 10;
            if (c.free_space() != 0) return 11;
            StockCounter d(200, 20);
            if (!d.reorder()) return 12;
            StockCounter e(200, 21);
            if (e.reorder()) return 13;
            d.ship(20);
            if (d.stock() != 0) return 14;
            if (d.free_space() != 200) return 15;
            d.receive(180);
            if (d.stock() != 180) return 16;
            return 0;
            """,
            "capacity and availability guards with an inclusive reorder threshold",
            "pseudo-random generators, dice-roll simulators, <random>, and rejecting the exact-fill receive",
            "capacity and initial bounds, count bounds at 0 and 501, rejected mutations leave stock unchanged, exact fill to capacity succeeds, and the reorder boundary",
            "exact-fill acceptance as the rejection discriminator",
            "capacity-guarded counter",
        ),
        c(
            "f26dnd-park-permit-register",
            "Park permit register",
            "park_permit",
            """
            class PermitError : public std::invalid_argument {
            public:
                explicit PermitError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PermitRegister {
            public:
                explicit PermitRegister(int today);
                int today() const;
                void issue(int permit_id, int days);
                bool active(int permit_id) const;
                int remaining(int permit_id) const;
                void advance(int days);
                int expiring_soon() const;
            };
            """,
            """
            class PermitError : public std::invalid_argument {
            public:
                explicit PermitError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PermitRegister {
            public:
                explicit PermitRegister(int today);
                int today() const;
                void issue(int permit_id, int days);
                bool active(int permit_id) const;
                int remaining(int permit_id) const;
                void advance(int days);
                int expiring_soon() const;
            private:
                int today_;
                std::vector<std::pair<int, int>> issued_;
            };
            """,
            """
            PermitRegister::PermitRegister(int today) : today_(today) {
                if (today < 0 || today > 365) throw PermitError("today outside 0..365");
            }
            int PermitRegister::today() const { return today_; }
            void PermitRegister::issue(int permit_id, int days) {
                if (permit_id < 1 || permit_id > 9999) throw PermitError("permit id outside 1..9999");
                if (days < 1 || days > 30) throw PermitError("days outside 1..30");
                for (const std::pair<int, int>& entry : issued_) {
                    if (entry.first == permit_id) throw PermitError("duplicate permit id");
                }
                issued_.push_back(std::make_pair(permit_id, today_ + days));
            }
            bool PermitRegister::active(int permit_id) const {
                for (const std::pair<int, int>& entry : issued_) {
                    if (entry.first == permit_id) return today_ < entry.second;
                }
                throw PermitError("unknown permit id");
            }
            int PermitRegister::remaining(int permit_id) const {
                for (const std::pair<int, int>& entry : issued_) {
                    if (entry.first == permit_id) return entry.second - today_;
                }
                throw PermitError("unknown permit id");
            }
            void PermitRegister::advance(int days) {
                if (days < 1 || days > 30) throw PermitError("days outside 1..30");
                if (today_ + days > 365) throw PermitError("cannot advance past day 365");
                today_ += days;
            }
            int PermitRegister::expiring_soon() const {
                int count = 0;
                for (const std::pair<int, int>& entry : issued_) {
                    const int left = entry.second - today_;
                    if (left >= 1 && left <= 3) ++count;
                }
                return count;
            }
            """,
            """
            PermitRegister::PermitRegister(int today) : today_(today) {
                if (today < 0 || today > 365) throw PermitError("today outside 0..365");
            }
            int PermitRegister::today() const { return today_; }
            void PermitRegister::issue(int permit_id, int days) {
                if (permit_id < 1 || permit_id > 9999) throw PermitError("permit id outside 1..9999");
                if (days < 1 || days > 30) throw PermitError("days outside 1..30");
                for (const std::pair<int, int>& entry : issued_) {
                    if (entry.first == permit_id) throw PermitError("duplicate permit id");
                }
                issued_.push_back(std::make_pair(permit_id, today_ + days));
            }
            bool PermitRegister::active(int permit_id) const {
                for (const std::pair<int, int>& entry : issued_) {
                    if (entry.first == permit_id) return today_ <= entry.second;
                }
                throw PermitError("unknown permit id");
            }
            int PermitRegister::remaining(int permit_id) const {
                for (const std::pair<int, int>& entry : issued_) {
                    if (entry.first == permit_id) return entry.second - today_;
                }
                throw PermitError("unknown permit id");
            }
            void PermitRegister::advance(int days) {
                if (days < 1 || days > 30) throw PermitError("days outside 1..30");
                if (today_ + days > 365) throw PermitError("cannot advance past day 365");
                today_ += days;
            }
            int PermitRegister::expiring_soon() const {
                int count = 0;
                for (const std::pair<int, int>& entry : issued_) {
                    const int left = entry.second - today_;
                    if (left >= 1 && left <= 3) ++count;
                }
                return count;
            }
            """,
            """
            PermitRegister r(100);
            if (r.today() != 100) return 1;
            r.issue(7, 10);
            if (!r.active(7)) return 2;
            if (r.remaining(7) != 10) return 3;
            r.advance(9);
            if (r.today() != 109) return 4;
            if (!r.active(7)) return 5;
            if (r.remaining(7) != 1) return 6;
            if (r.expiring_soon() != 1) return 7;
            r.advance(1);
            if (r.active(7)) return 8;
            if (r.remaining(7) != 0) return 9;
            if (r.expiring_soon() != 0) return 10;
            bool threw = false;
            try { r.active(999); } catch (const PermitError&) { threw = true; }
            if (!threw) return 11;
            threw = false;
            try { r.issue(7, 5); } catch (const PermitError&) { threw = true; }
            if (!threw) return 12;
            return 0;
            """,
            """
            bool threw = false;
            try { PermitRegister bad(-1); } catch (const PermitError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PermitRegister bad(366); } catch (const PermitError&) { threw = true; }
            if (!threw) return 2;
            PermitRegister r(100);
            threw = false;
            try { r.issue(0, 5); } catch (const PermitError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { r.issue(10000, 5); } catch (const PermitError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { r.issue(5, 0); } catch (const PermitError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { r.issue(5, 31); } catch (const PermitError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { r.remaining(42); } catch (const PermitError&) { threw = true; }
            if (!threw) return 7;
            r.issue(1, 3);
            r.issue(2, 5);
            r.issue(3, 10);
            if (r.expiring_soon() != 1) return 8;
            r.advance(2);
            if (r.expiring_soon() != 2) return 9;
            if (r.remaining(1) != 1) return 10;
            if (r.remaining(2) != 3) return 11;
            if (r.remaining(3) != 8) return 12;
            threw = false;
            try { r.advance(0); } catch (const PermitError&) { threw = true; }
            if (!threw) return 13;
            threw = false;
            try { r.advance(31); } catch (const PermitError&) { threw = true; }
            if (!threw) return 14;
            PermitRegister edge(360);
            threw = false;
            try { edge.advance(6); } catch (const PermitError&) { threw = true; }
            if (!threw) return 15;
            edge.issue(9, 10);
            if (!edge.active(9)) return 16;
            edge.advance(5);
            if (edge.today() != 365) return 17;
            if (!edge.active(9)) return 18;
            if (edge.remaining(9) != 5) return 19;
            PermitRegister window(0);
            window.issue(11, 4);
            if (window.expiring_soon() != 0) return 20;
            window.issue(12, 3);
            if (window.expiring_soon() != 1) return 21;
            PermitRegister exact(50);
            exact.issue(4, 5);
            exact.advance(5);
            if (exact.active(4)) return 22;
            if (exact.remaining(4) != 0) return 23;
            if (exact.expiring_soon() != 0) return 24;
            return 0;
            """,
            "owned id/expiry register with duplicate and absent rules, strict expiry comparison, and a bounded window count",
            "pseudo-random generators, dice-roll simulators, <random>, and inclusive expiry-day activity",
            "today, id, and days bounds, duplicate and unknown id rejection, the advance cap at 365, expiry at the exact expiry day, window edges at remaining 0/1/3/4, and multi-permit counts",
            "strict versus inclusive expiry comparison as the rejection discriminator",
            "identifier register with expiry window",
        ),
    )
    return rows


TASKS = cases()

CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-dnd-seven-dimension-artifacts-v1"


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
#include <utility>
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

Implement a clean-room C++17 deterministic scoring-rules component for a local
dnd-character skill analog. This root is independently authored for SFT
task-family construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep the rules engine exact: every scalar and vector element validated
against the documented inclusive bounds; every derived value computed with the
documented exact integer policy; aggregates, ties, phases, and lifecycle
transitions following the declared rules; typed-error rejection of invalid
inputs with no mutation on rejected calls; and deterministic, pseudo-random-free
behavior for this API shape: {spec.api_shape}.

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
                "source": "w8-biayn clean-room fixed26 dnd-character analog curriculum",
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
description = "{spec.title}: bound validation, boundary values, exact integer policy, invalid inputs, and wrong-substitute rejection"

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
    if spec.task_id != "f26dnd-harbor-tide-gauge":
        _fail("control_mutation_drift", f"controls are bound to f26dnd-harbor-tide-gauge, got {spec.task_id}")
    if name == "domain-identifier-renamed":
        renamed_id = "f26dnd-harbor-tide-meter"
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
                ("try { TideGauge bad(-6); } catch (const TideError&) { threw = true; }", "try { TideGauge bad(-7); } catch (const TideError&) { threw = true; }"),
                ("try { TideGauge bad(6); } catch (const TideError&) { threw = true; }", "try { TideGauge bad(9); } catch (const TideError&) { threw = true; }"),
                ("TideGauge t(1);", "TideGauge t(3);"),
                ("TideGauge u(-5);", "TideGauge u(-4);"),
            ),
            context="constants-or-policy-only:private",
        )
        return mutated, [".meta/private_test.cpp"]
    if name == "opposite-end-selection":
        mutated = dict(files)
        mutated["visible_test.cpp"] = _apply_replacements(
            mutated["visible_test.cpp"],
            (
                ("if (g.surge(40) != 10) return 3;", "if (g.surge(38) != 9) return 3;"),
                ("if (g.surge(0) != -10) return 4;", "if (g.surge(2) != -9) return 4;"),
                ("if (g.surge(17) != -1) return 5;", "if (g.surge(3) != -8) return 5;"),
                ("if (!g.flood_watch(30)) return 6;", "if (!g.flood_watch(31)) return 6;"),
                ("if (g.flood_watch(29)) return 7;", "if (g.flood_watch(28)) return 7;"),
                ("std::vector<int> got = g.surges({20, 40, 0});", "std::vector<int> got = g.surges({39, 21, 3});"),
                ("if (got != std::vector<int>{0, 10, -10}) return 8;", "if (got != std::vector<int>{9, 0, -8}) return 8;"),
                ("TideGauge low(-3);", "TideGauge low(-2);"),
                ("TideGauge high(5);", "TideGauge high(3);"),
                ("if (high.surge(0) != -7) return 10;", "if (high.surge(0) != -8) return 10;"),
            ),
            context="opposite-end-selection:visible",
        )
        mutated[".meta/private_test.cpp"] = _apply_replacements(
            mutated[".meta/private_test.cpp"],
            (
                ("if (t.surge(18) != 0) return 5;", "if (t.surge(38) != 9) return 5;"),
                ("TideGauge u(-5);", "TideGauge u(-4);"),
                ("TideGauge w(5);", "TideGauge w(3);"),
                ("if (w.surge(0) != -7) return 8;", "if (w.surge(0) != -8) return 8;"),
                ("if (w.surge(40) != 12) return 9;", "if (w.surge(40) != 11) return 9;"),
                ("if (many != std::vector<int>{-7, 12}) return 10;", "if (many != std::vector<int>{-8, 11}) return 10;"),
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
            "family": "dnd-character",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "dnd-character",
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
        "project_context_support_note": "The source spec names 4 project-context support roots; this materializer emits private support only for those 4.",
        "scope_reduction": "User-directed scope change (2026-07-24): TARGET_COUNT reduced from the campaign card's 50 to 20; the sub-40 batch is justified by that explicit user directive and recorded in the spec document.",
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
    text = re.sub(r"\bf26dnd[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        control_headers = sorted(path.name for path in control_root.glob("f26dnd-*.h"))
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
        "schema_version": "fixed26-dnd-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-dnd-fresh-") as temporary:
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
        "schema_version": "fixed26-dnd-core-v1",
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
for task_root in sorted(ROOT.glob("f26dnd-*")):
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
            "schema_version": "fixed26-dnd-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-dnd-docker-") as temporary:
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
        "schema_version": "fixed26-dnd-docker-sanity-v1",
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
        "schema_version": "fixed26-dnd-creator-preflight-v1",
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
        "capability": "fixed26-dnd-character-analog",
        "difficulty": "intermediate",
        "interaction": "aider-whole-file",
        "statefulness": "stateful" if "void " in spec.declarations else "stateless",
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
            "task": "implement clean-room fixed26 dnd-character analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned validated integer state with root-specific exact integer derivation; documented truncation, piecewise, clamp, ceiling, or progressive policy; deterministic pseudo-random-free outputs with declared tie, phase, and distribution rules; invalid inputs rejected through typed errors that never mutate observable state; guarded lifecycle transitions for stateful roots",
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
            "target_family": "dnd-character",
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
