"""Create and verify the fixed-26 complex-numbers clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b007-complex-numbers.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b007-complex-numbers"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_complex_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_complex_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b007-complex-numbers"
FAMILY_ID = "aider-fixed26-complex-analogs-v1"
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
        "f26cpx-reservoir-level-flow",
        "f26cpx-bobsled-track-boost",
        "f26cpx-brew-mixture-share",
        "f26cpx-vaccine-dose-window",
        "f26cpx-rover-steering-offset",
        "f26cpx-affine-grid-transform",
        "f26cpx-freight-tonnage-ledger",
        "f26cpx-gyro-orientation-frame",
        "f26cpx-rigging-load-path",
        "f26cpx-hatchery-batch-stats",
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
#include <cmath>
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
#include <cmath>
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
            "f26cpx-forge-heating-curve",
            "Forge heating curve",
            "forge_heat",
            """
            class HeatError : public std::domain_error {
            public:
                explicit HeatError(const std::string& message) : std::domain_error(message) {}
            };
            class HeatCurve {
            public:
                HeatCurve(double temp, double rate);
                double temp() const;
                double rate() const;
                HeatCurve operator+(const HeatCurve& other) const;
                HeatCurve operator-(const HeatCurve& other) const;
                HeatCurve operator*(const HeatCurve& other) const;
                HeatCurve operator/(const HeatCurve& other) const;
                HeatCurve scale(double factor) const;
                HeatCurve raise_e() const;
            };
            bool nearly_equal(const HeatCurve& left, const HeatCurve& right, double eps);
            """,
            """
            class HeatError : public std::domain_error {
            public:
                explicit HeatError(const std::string& message) : std::domain_error(message) {}
            };
            class HeatCurve {
            public:
                HeatCurve(double temp, double rate);
                double temp() const;
                double rate() const;
                HeatCurve operator+(const HeatCurve& other) const;
                HeatCurve operator-(const HeatCurve& other) const;
                HeatCurve operator*(const HeatCurve& other) const;
                HeatCurve operator/(const HeatCurve& other) const;
                HeatCurve scale(double factor) const;
                HeatCurve raise_e() const;
            private:
                double temp_;
                double rate_;
            };
            bool nearly_equal(const HeatCurve& left, const HeatCurve& right, double eps);
            """,
            """
            HeatCurve::HeatCurve(double temp, double rate) : temp_(temp), rate_(rate) {}
            double HeatCurve::temp() const { return temp_; }
            double HeatCurve::rate() const { return rate_; }
            HeatCurve HeatCurve::operator+(const HeatCurve& other) const {
                return HeatCurve(temp_ + other.temp_, rate_ + other.rate_);
            }
            HeatCurve HeatCurve::operator-(const HeatCurve& other) const {
                return HeatCurve(temp_ - other.temp_, rate_ - other.rate_);
            }
            HeatCurve HeatCurve::operator*(const HeatCurve& other) const {
                return HeatCurve(temp_ * other.temp_, temp_ * other.rate_ + other.temp_ * rate_);
            }
            HeatCurve HeatCurve::operator/(const HeatCurve& other) const {
                if (other.temp_ == 0.0) throw HeatError("divisor has zero value");
                return HeatCurve(temp_ / other.temp_,
                                 (other.temp_ * rate_ - temp_ * other.rate_) / (other.temp_ * other.temp_));
            }
            HeatCurve HeatCurve::scale(double factor) const {
                return HeatCurve(factor * temp_, factor * rate_);
            }
            HeatCurve HeatCurve::raise_e() const {
                double lifted = std::exp(temp_);
                return HeatCurve(lifted, lifted * rate_);
            }
            bool nearly_equal(const HeatCurve& left, const HeatCurve& right, double eps) {
                return std::fabs(left.temp() - right.temp()) <= eps
                    && std::fabs(left.rate() - right.rate()) <= eps;
            }
            """,
            """
            HeatCurve::HeatCurve(double temp, double rate) : temp_(temp), rate_(rate) {}
            double HeatCurve::temp() const { return temp_; }
            double HeatCurve::rate() const { return rate_; }
            HeatCurve HeatCurve::operator+(const HeatCurve& other) const {
                return HeatCurve(temp_ + other.temp_, rate_ + other.rate_);
            }
            HeatCurve HeatCurve::operator-(const HeatCurve& other) const {
                return HeatCurve(temp_ - other.temp_, rate_ - other.rate_);
            }
            HeatCurve HeatCurve::operator*(const HeatCurve& other) const {
                return HeatCurve(temp_ * other.temp_, temp_ * other.rate_);
            }
            HeatCurve HeatCurve::operator/(const HeatCurve& other) const {
                if (other.temp_ == 0.0) throw HeatError("divisor has zero value");
                return HeatCurve(temp_ / other.temp_,
                                 (other.temp_ * rate_ - temp_ * other.rate_) / (other.temp_ * other.temp_));
            }
            HeatCurve HeatCurve::scale(double factor) const {
                return HeatCurve(factor * temp_, factor * rate_);
            }
            HeatCurve HeatCurve::raise_e() const {
                double lifted = std::exp(temp_);
                return HeatCurve(lifted, lifted * rate_);
            }
            bool nearly_equal(const HeatCurve& left, const HeatCurve& right, double eps) {
                return std::fabs(left.temp() - right.temp()) <= eps
                    && std::fabs(left.rate() - right.rate()) <= eps;
            }
            """,
            """
            HeatCurve a(2.0, 0.5);
            HeatCurve b(3.0, -1.0);
            HeatCurve s = a + b;
            if (std::fabs(s.temp() - 5.0) > 1e-9 || std::fabs(s.rate() + 0.5) > 1e-9) return 1;
            HeatCurve p = a * b;
            if (std::fabs(p.temp() - 6.0) > 1e-9) return 2;
            if (std::fabs(p.rate() - (-0.5)) > 1e-9) return 3;
            HeatCurve q = a / b;
            if (std::fabs(q.temp() - 2.0 / 3.0) > 1e-9) return 4;
            if (std::fabs(q.rate() - 3.5 / 9.0) > 1e-9) return 5;
            HeatCurve e = a.raise_e();
            if (std::fabs(e.temp() - std::exp(2.0)) > 1e-9) return 6;
            if (std::fabs(e.rate() - 0.5 * std::exp(2.0)) > 1e-9) return 7;
            if (!nearly_equal(a, HeatCurve(2.0 + 1e-12, 0.5), 1e-9)) return 8;
            HeatCurve sc = a.scale(-2.0);
            if (std::fabs(sc.temp() + 4.0) > 1e-9 || std::fabs(sc.rate() + 1.0) > 1e-9) return 9;
            return 0;
            """,
            """
            HeatCurve a(1.5, 2.0);
            HeatCurve b(0.5, 0.25);
            HeatCurve q = a / b;
            if (std::fabs(q.temp() - 3.0) > 1e-9) return 1;
            if (std::fabs(q.rate() - 2.5) > 1e-9) return 2;
            bool threw = false;
            try { HeatCurve z(0.0, 1.0); a / z; } catch (const HeatError&) { threw = true; }
            if (!threw) return 3;
            HeatCurve p = a * a;
            if (std::fabs(p.temp() - 2.25) > 1e-9 || std::fabs(p.rate() - 6.0) > 1e-9) return 4;
            HeatCurve e = HeatCurve(0.0, 3.0).raise_e();
            if (std::fabs(e.temp() - 1.0) > 1e-9 || std::fabs(e.rate() - 3.0) > 1e-9) return 5;
            if (nearly_equal(a, HeatCurve(1.5 + 1e-6, 2.0), 1e-9)) return 6;
            if (!nearly_equal(a, a, 0.0)) return 7;
            HeatCurve d = a - b;
            if (std::fabs(d.temp() - 1.0) > 1e-9 || std::fabs(d.rate() - 1.75) > 1e-9) return 8;
            threw = false;
            try { HeatCurve z(0.0, 1.0); z.raise_e(); } catch (const HeatError&) { threw = true; }
            if (threw) return 9;
            return 0;
            """,
            "dual rate-pair propagation with the exact product and quotient rules over owned temp/rate fields, dropping the epsilon-squared term",
            "std::complex, <complex>, or any automatic-differentiation library; do not drop a cross term of the product rule",
            "quotient-rule sign and divisor-zero rejection, negative scaling, the exponential rate chain, and tolerance boundaries just inside and outside eps",
            "member operator overloads with a transcendental helper and tolerance equality in a paired .h/.cpp API",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-ferment-gravity-track",
            "Ferment gravity track",
            "ferment_gravity",
            """
            class GravityError : public std::domain_error {
            public:
                explicit GravityError(const std::string& message) : std::domain_error(message) {}
            };
            class GravityTrack {
            public:
                GravityTrack(double gravity, double drift);
                double gravity() const;
                double drift() const;
                GravityTrack pow(unsigned exponent) const;
                GravityTrack log() const;
                bool within(const GravityTrack& other, double eps) const;
            };
            GravityTrack operator+(const GravityTrack& left, const GravityTrack& right);
            GravityTrack operator-(const GravityTrack& left, const GravityTrack& right);
            GravityTrack operator*(const GravityTrack& left, const GravityTrack& right);
            GravityTrack operator/(const GravityTrack& left, const GravityTrack& right);
            """,
            """
            class GravityError : public std::domain_error {
            public:
                explicit GravityError(const std::string& message) : std::domain_error(message) {}
            };
            class GravityTrack {
            public:
                GravityTrack(double gravity, double drift);
                double gravity() const;
                double drift() const;
                GravityTrack pow(unsigned exponent) const;
                GravityTrack log() const;
                bool within(const GravityTrack& other, double eps) const;
            private:
                double gravity_;
                double drift_;
            };
            GravityTrack operator+(const GravityTrack& left, const GravityTrack& right);
            GravityTrack operator-(const GravityTrack& left, const GravityTrack& right);
            GravityTrack operator*(const GravityTrack& left, const GravityTrack& right);
            GravityTrack operator/(const GravityTrack& left, const GravityTrack& right);
            """,
            """
            GravityTrack::GravityTrack(double gravity, double drift) : gravity_(gravity), drift_(drift) {}
            double GravityTrack::gravity() const { return gravity_; }
            double GravityTrack::drift() const { return drift_; }
            GravityTrack GravityTrack::pow(unsigned exponent) const {
                GravityTrack result(1.0, 0.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            GravityTrack GravityTrack::log() const {
                if (gravity_ <= 0.0) throw GravityError("log of non-positive value");
                return GravityTrack(std::log(gravity_), drift_ / gravity_);
            }
            bool GravityTrack::within(const GravityTrack& other, double eps) const {
                return std::fabs(gravity_ - other.gravity_) <= eps
                    && std::fabs(drift_ - other.drift_) <= eps;
            }
            GravityTrack operator+(const GravityTrack& left, const GravityTrack& right) {
                return GravityTrack(left.gravity() + right.gravity(), left.drift() + right.drift());
            }
            GravityTrack operator-(const GravityTrack& left, const GravityTrack& right) {
                return GravityTrack(left.gravity() - right.gravity(), left.drift() - right.drift());
            }
            GravityTrack operator*(const GravityTrack& left, const GravityTrack& right) {
                return GravityTrack(left.gravity() * right.gravity(),
                                    left.gravity() * right.drift() + right.gravity() * left.drift());
            }
            GravityTrack operator/(const GravityTrack& left, const GravityTrack& right) {
                if (right.gravity() == 0.0) throw GravityError("divisor has zero value");
                return GravityTrack(left.gravity() / right.gravity(),
                                    (right.gravity() * left.drift() - left.gravity() * right.drift())
                                        / (right.gravity() * right.gravity()));
            }
            """,
            """
            GravityTrack::GravityTrack(double gravity, double drift) : gravity_(gravity), drift_(drift) {}
            double GravityTrack::gravity() const { return gravity_; }
            double GravityTrack::drift() const { return drift_; }
            GravityTrack GravityTrack::pow(unsigned exponent) const {
                GravityTrack result(1.0, 0.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            GravityTrack GravityTrack::log() const {
                if (gravity_ <= 0.0) throw GravityError("log of non-positive value");
                return GravityTrack(std::log(gravity_), drift_ / gravity_);
            }
            bool GravityTrack::within(const GravityTrack& other, double eps) const {
                return std::fabs(gravity_ - other.gravity_) <= eps
                    && std::fabs(drift_ - other.drift_) <= eps;
            }
            GravityTrack operator+(const GravityTrack& left, const GravityTrack& right) {
                return GravityTrack(left.gravity() + right.gravity(), left.drift() + right.drift());
            }
            GravityTrack operator-(const GravityTrack& left, const GravityTrack& right) {
                return GravityTrack(left.gravity() - right.gravity(), left.drift() - right.drift());
            }
            GravityTrack operator*(const GravityTrack& left, const GravityTrack& right) {
                return GravityTrack(left.gravity() * right.gravity(),
                                    left.gravity() * right.drift());
            }
            GravityTrack operator/(const GravityTrack& left, const GravityTrack& right) {
                if (right.gravity() == 0.0) throw GravityError("divisor has zero value");
                return GravityTrack(left.gravity() / right.gravity(),
                                    (right.gravity() * left.drift() - left.gravity() * right.drift())
                                        / (right.gravity() * right.gravity()));
            }
            """,
            """
            GravityTrack a(1.1, 0.2);
            GravityTrack b(0.9, -0.1);
            GravityTrack s = a + b;
            if (std::fabs(s.gravity() - 2.0) > 1e-9 || std::fabs(s.drift() - 0.1) > 1e-9) return 1;
            GravityTrack p = a * b;
            if (std::fabs(p.gravity() - 0.99) > 1e-9) return 2;
            if (std::fabs(p.drift() - 0.07) > 1e-9) return 3;
            GravityTrack q = a / b;
            if (std::fabs(q.gravity() - 1.1 / 0.9) > 1e-9) return 4;
            if (std::fabs(q.drift() - 0.29 / 0.81) > 1e-9) return 5;
            GravityTrack sq = a.pow(2);
            if (std::fabs(sq.gravity() - 1.21) > 1e-9 || std::fabs(sq.drift() - 0.44) > 1e-9) return 6;
            if (!a.within(GravityTrack(1.1 + 1e-12, 0.2), 1e-9)) return 7;
            return 0;
            """,
            """
            GravityTrack a(2.0, 0.5);
            GravityTrack one = a.pow(0);
            if (std::fabs(one.gravity() - 1.0) > 1e-9 || std::fabs(one.drift()) > 1e-9) return 1;
            GravityTrack cube = a.pow(3);
            if (std::fabs(cube.gravity() - 8.0) > 1e-9 || std::fabs(cube.drift() - 6.0) > 1e-9) return 2;
            GravityTrack lg = a.log();
            if (std::fabs(lg.gravity() - std::log(2.0)) > 1e-9 || std::fabs(lg.drift() - 0.25) > 1e-9) return 3;
            bool threw = false;
            try { GravityTrack(0.0, 1.0).log(); } catch (const GravityError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { GravityTrack(-1.0, 1.0).log(); } catch (const GravityError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { GravityTrack z(0.0, 2.0); a / z; } catch (const GravityError&) { threw = true; }
            if (!threw) return 6;
            if (a.within(GravityTrack(2.0, 0.5 + 1e-6), 1e-9)) return 7;
            GravityTrack d = a - GravityTrack(0.5, 0.5);
            if (std::fabs(d.gravity() - 1.5) > 1e-9 || std::fabs(d.drift()) > 1e-9) return 8;
            return 0;
            """,
            "dual rate-pair propagation through free operators with integer-power and natural-log chain rules",
            "std::complex, <complex>, or any automatic-differentiation library; do not log the drift component directly and do not drop a product-rule cross term",
            "pow(0) identity, the power rate chain, log domain edges at zero and negative values, free-operator argument order, and divisor-zero rejection",
            "free operators plus a domain-restricted transcendental helper in a paired .h/.cpp API",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-geartrain-ratio-step",
            "Geartrain ratio step",
            "geartrain_ratio",
            """
            class RatioError : public std::domain_error {
            public:
                explicit RatioError(const std::string& message) : std::domain_error(message) {}
            };
            class RatioStep {
            public:
                RatioStep(double ratio, double slip);
                double ratio() const;
                double slip() const;
                RatioStep operator+(const RatioStep& other) const;
                RatioStep operator-(const RatioStep& other) const;
                RatioStep operator*(const RatioStep& other) const;
                RatioStep operator/(const RatioStep& other) const;
                RatioStep reciprocal() const;
                RatioStep root2() const;
                std::string render() const;
            };
            """,
            """
            class RatioError : public std::domain_error {
            public:
                explicit RatioError(const std::string& message) : std::domain_error(message) {}
            };
            class RatioStep {
            public:
                RatioStep(double ratio, double slip);
                double ratio() const;
                double slip() const;
                RatioStep operator+(const RatioStep& other) const;
                RatioStep operator-(const RatioStep& other) const;
                RatioStep operator*(const RatioStep& other) const;
                RatioStep operator/(const RatioStep& other) const;
                RatioStep reciprocal() const;
                RatioStep root2() const;
                std::string render() const;
            private:
                double ratio_;
                double slip_;
            };
            """,
            """
            RatioStep::RatioStep(double ratio, double slip) : ratio_(ratio), slip_(slip) {}
            double RatioStep::ratio() const { return ratio_; }
            double RatioStep::slip() const { return slip_; }
            RatioStep RatioStep::operator+(const RatioStep& other) const {
                return RatioStep(ratio_ + other.ratio_, slip_ + other.slip_);
            }
            RatioStep RatioStep::operator-(const RatioStep& other) const {
                return RatioStep(ratio_ - other.ratio_, slip_ - other.slip_);
            }
            RatioStep RatioStep::operator*(const RatioStep& other) const {
                return RatioStep(ratio_ * other.ratio_, ratio_ * other.slip_ + other.ratio_ * slip_);
            }
            RatioStep RatioStep::operator/(const RatioStep& other) const {
                if (other.ratio_ == 0.0) throw RatioError("divisor has zero value");
                return RatioStep(ratio_ / other.ratio_,
                                 (other.ratio_ * slip_ - ratio_ * other.slip_) / (other.ratio_ * other.ratio_));
            }
            RatioStep RatioStep::reciprocal() const {
                if (ratio_ == 0.0) throw RatioError("reciprocal of zero value");
                return RatioStep(1.0 / ratio_, -slip_ / (ratio_ * ratio_));
            }
            RatioStep RatioStep::root2() const {
                if (ratio_ <= 0.0) throw RatioError("square root of non-positive value");
                double root = std::sqrt(ratio_);
                return RatioStep(root, slip_ / (2.0 * root));
            }
            std::string RatioStep::render() const {
                std::ostringstream out;
                out << "ratio=" << std::fixed << std::setprecision(6) << ratio_ << ";slip=" << slip_;
                return out.str();
            }
            """,
            """
            RatioStep::RatioStep(double ratio, double slip) : ratio_(ratio), slip_(slip) {}
            double RatioStep::ratio() const { return ratio_; }
            double RatioStep::slip() const { return slip_; }
            RatioStep RatioStep::operator+(const RatioStep& other) const {
                return RatioStep(ratio_ + other.ratio_, slip_ + other.slip_);
            }
            RatioStep RatioStep::operator-(const RatioStep& other) const {
                return RatioStep(ratio_ - other.ratio_, slip_ - other.slip_);
            }
            RatioStep RatioStep::operator*(const RatioStep& other) const {
                return RatioStep(ratio_ * other.ratio_, ratio_ * other.slip_);
            }
            RatioStep RatioStep::operator/(const RatioStep& other) const {
                if (other.ratio_ == 0.0) throw RatioError("divisor has zero value");
                return RatioStep(ratio_ / other.ratio_,
                                 (other.ratio_ * slip_ - ratio_ * other.slip_) / (other.ratio_ * other.ratio_));
            }
            RatioStep RatioStep::reciprocal() const {
                if (ratio_ == 0.0) throw RatioError("reciprocal of zero value");
                return RatioStep(1.0 / ratio_, -slip_ / (ratio_ * ratio_));
            }
            RatioStep RatioStep::root2() const {
                if (ratio_ <= 0.0) throw RatioError("square root of non-positive value");
                double root = std::sqrt(ratio_);
                return RatioStep(root, slip_ / (2.0 * root));
            }
            std::string RatioStep::render() const {
                std::ostringstream out;
                out << "ratio=" << std::fixed << std::setprecision(6) << ratio_ << ";slip=" << slip_;
                return out.str();
            }
            """,
            """
            RatioStep a(4.0, 0.8);
            RatioStep b(2.0, -0.4);
            RatioStep p = a * b;
            if (std::fabs(p.ratio() - 8.0) > 1e-9 || std::fabs(p.slip()) > 1e-9) return 1;
            RatioStep q = a / b;
            if (std::fabs(q.ratio() - 2.0) > 1e-9 || std::fabs(q.slip() - 0.8) > 1e-9) return 2;
            RatioStep r = a.root2();
            if (std::fabs(r.ratio() - 2.0) > 1e-9 || std::fabs(r.slip() - 0.2) > 1e-9) return 3;
            RatioStep v = b.reciprocal();
            if (std::fabs(v.ratio() - 0.5) > 1e-9 || std::fabs(v.slip() - 0.1) > 1e-9) return 4;
            if (RatioStep(1.5, 0.25).render() != "ratio=1.500000;slip=0.250000") return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { RatioStep(0.0, 1.0).root2(); } catch (const RatioError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RatioStep(-4.0, 1.0).root2(); } catch (const RatioError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { RatioStep(0.0, 0.5).reciprocal(); } catch (const RatioError&) { threw = true; }
            if (!threw) return 3;
            RatioStep a(9.0, 3.0);
            RatioStep r = a.root2();
            if (std::fabs(r.ratio() - 3.0) > 1e-9 || std::fabs(r.slip() - 0.5) > 1e-9) return 4;
            RatioStep s = a + RatioStep(1.0, -1.0);
            if (std::fabs(s.ratio() - 10.0) > 1e-9 || std::fabs(s.slip() - 2.0) > 1e-9) return 5;
            if (s.render() != "ratio=10.000000;slip=2.000000") return 6;
            RatioStep d = a - RatioStep(4.0, 1.0);
            if (std::fabs(d.ratio() - 5.0) > 1e-9 || std::fabs(d.slip() - 2.0) > 1e-9) return 7;
            threw = false;
            try { RatioStep z(0.0, 1.0); a / z; } catch (const RatioError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "dual rate-pair propagation through reciprocal and square-root helpers with an exact fixed-precision readout",
            "std::complex, <complex>, or any automatic-differentiation library; do not truncate the readout precision and do not drop a product-rule cross term",
            "root2 domain edge at zero and negative values, reciprocal of zero, quotient rule, and byte-exact render after arithmetic",
            "deterministic formatting plus a domain-restricted root helper in a paired .h/.cpp API",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-kiln-heat-soak",
            "Kiln heat soak",
            "kiln_soak",
            """
            class SoakError : public std::domain_error {
            public:
                explicit SoakError(const std::string& message) : std::domain_error(message) {}
            };
            class SoakCurve {
            public:
                SoakCurve(double heat, double creep);
                double heat() const;
                double creep() const;
                SoakCurve operator+(const SoakCurve& other) const;
                SoakCurve operator-(const SoakCurve& other) const;
                SoakCurve operator*(const SoakCurve& other) const;
                SoakCurve operator/(const SoakCurve& other) const;
                SoakCurve scale(double factor) const;
                SoakCurve wave_sin() const;
                SoakCurve wave_cos() const;
            };
            bool nearly_equal(const SoakCurve& left, const SoakCurve& right, double eps);
            """,
            """
            class SoakError : public std::domain_error {
            public:
                explicit SoakError(const std::string& message) : std::domain_error(message) {}
            };
            class SoakCurve {
            public:
                SoakCurve(double heat, double creep);
                double heat() const;
                double creep() const;
                SoakCurve operator+(const SoakCurve& other) const;
                SoakCurve operator-(const SoakCurve& other) const;
                SoakCurve operator*(const SoakCurve& other) const;
                SoakCurve operator/(const SoakCurve& other) const;
                SoakCurve scale(double factor) const;
                SoakCurve wave_sin() const;
                SoakCurve wave_cos() const;
            private:
                double heat_;
                double creep_;
            };
            bool nearly_equal(const SoakCurve& left, const SoakCurve& right, double eps);
            """,
            """
            SoakCurve::SoakCurve(double heat, double creep) : heat_(heat), creep_(creep) {}
            double SoakCurve::heat() const { return heat_; }
            double SoakCurve::creep() const { return creep_; }
            SoakCurve SoakCurve::operator+(const SoakCurve& other) const {
                return SoakCurve(heat_ + other.heat_, creep_ + other.creep_);
            }
            SoakCurve SoakCurve::operator-(const SoakCurve& other) const {
                return SoakCurve(heat_ - other.heat_, creep_ - other.creep_);
            }
            SoakCurve SoakCurve::operator*(const SoakCurve& other) const {
                return SoakCurve(heat_ * other.heat_, heat_ * other.creep_ + other.heat_ * creep_);
            }
            SoakCurve SoakCurve::operator/(const SoakCurve& other) const {
                if (other.heat_ == 0.0) throw SoakError("divisor has zero value");
                return SoakCurve(heat_ / other.heat_,
                                 (other.heat_ * creep_ - heat_ * other.creep_) / (other.heat_ * other.heat_));
            }
            SoakCurve SoakCurve::scale(double factor) const {
                return SoakCurve(factor * heat_, factor * creep_);
            }
            SoakCurve SoakCurve::wave_sin() const {
                return SoakCurve(std::sin(heat_), creep_ * std::cos(heat_));
            }
            SoakCurve SoakCurve::wave_cos() const {
                return SoakCurve(std::cos(heat_), -creep_ * std::sin(heat_));
            }
            bool nearly_equal(const SoakCurve& left, const SoakCurve& right, double eps) {
                return std::fabs(left.heat() - right.heat()) <= eps
                    && std::fabs(left.creep() - right.creep()) <= eps;
            }
            """,
            """
            SoakCurve::SoakCurve(double heat, double creep) : heat_(heat), creep_(creep) {}
            double SoakCurve::heat() const { return heat_; }
            double SoakCurve::creep() const { return creep_; }
            SoakCurve SoakCurve::operator+(const SoakCurve& other) const {
                return SoakCurve(heat_ + other.heat_, creep_ + other.creep_);
            }
            SoakCurve SoakCurve::operator-(const SoakCurve& other) const {
                return SoakCurve(heat_ - other.heat_, creep_ - other.creep_);
            }
            SoakCurve SoakCurve::operator*(const SoakCurve& other) const {
                return SoakCurve(heat_ * other.heat_, heat_ * other.creep_);
            }
            SoakCurve SoakCurve::operator/(const SoakCurve& other) const {
                if (other.heat_ == 0.0) throw SoakError("divisor has zero value");
                return SoakCurve(heat_ / other.heat_,
                                 (other.heat_ * creep_ - heat_ * other.creep_) / (other.heat_ * other.heat_));
            }
            SoakCurve SoakCurve::scale(double factor) const {
                return SoakCurve(factor * heat_, factor * creep_);
            }
            SoakCurve SoakCurve::wave_sin() const {
                return SoakCurve(std::sin(heat_), creep_ * std::cos(heat_));
            }
            SoakCurve SoakCurve::wave_cos() const {
                return SoakCurve(std::cos(heat_), -creep_ * std::sin(heat_));
            }
            bool nearly_equal(const SoakCurve& left, const SoakCurve& right, double eps) {
                return std::fabs(left.heat() - right.heat()) <= eps
                    && std::fabs(left.creep() - right.creep()) <= eps;
            }
            """,
            """
            SoakCurve a(0.0, 2.0);
            SoakCurve ws = a.wave_sin();
            if (std::fabs(ws.heat()) > 1e-9 || std::fabs(ws.creep() - 2.0) > 1e-9) return 1;
            SoakCurve wc = a.wave_cos();
            if (std::fabs(wc.heat() - 1.0) > 1e-9 || std::fabs(wc.creep()) > 1e-9) return 2;
            SoakCurve b(1.0, 0.5);
            SoakCurve c(2.0, -0.25);
            SoakCurve p = b * c;
            if (std::fabs(p.heat() - 2.0) > 1e-9 || std::fabs(p.creep() - 0.75) > 1e-9) return 3;
            SoakCurve q = b / c;
            if (std::fabs(q.heat() - 0.5) > 1e-9 || std::fabs(q.creep() - 0.3125) > 1e-9) return 4;
            if (!nearly_equal(b, SoakCurve(1.0, 0.5 + 1e-12), 1e-9)) return 5;
            SoakCurve s = b.scale(3.0);
            if (std::fabs(s.heat() - 3.0) > 1e-9 || std::fabs(s.creep() - 1.5) > 1e-9) return 6;
            return 0;
            """,
            """
            const double kPi = 3.14159265358979323846;
            SoakCurve half_turn(kPi, 1.0);
            SoakCurve ws = half_turn.wave_sin();
            if (std::fabs(ws.heat()) > 1e-9 || std::fabs(ws.creep() + 1.0) > 1e-9) return 1;
            SoakCurve wc = half_turn.wave_cos();
            if (std::fabs(wc.heat() + 1.0) > 1e-9 || std::fabs(wc.creep()) > 1e-9) return 2;
            SoakCurve quarter(kPi / 2.0, 2.0);
            SoakCurve qs = quarter.wave_sin();
            if (std::fabs(qs.heat() - 1.0) > 1e-9 || std::fabs(qs.creep()) > 1e-9) return 3;
            bool threw = false;
            try { SoakCurve z(0.0, 1.0); quarter / z; } catch (const SoakError&) { threw = true; }
            if (!threw) return 4;
            SoakCurve a(1.5, 0.75);
            SoakCurve n = a.scale(-2.0);
            if (std::fabs(n.heat() + 3.0) > 1e-9 || std::fabs(n.creep() + 1.5) > 1e-9) return 5;
            if (nearly_equal(a, SoakCurve(1.5, 0.75 + 1e-6), 1e-9)) return 6;
            SoakCurve d = a - SoakCurve(0.5, 0.25);
            if (std::fabs(d.heat() - 1.0) > 1e-9 || std::fabs(d.creep() - 0.5) > 1e-9) return 7;
            return 0;
            """,
            "dual rate-pair propagation through sine and cosine chain rules with signed rate transport",
            "std::complex, <complex>, or any automatic-differentiation library; do not flip the sign of the cosine rate and do not drop a product-rule cross term",
            "wave helper rate signs at multiples of pi, negative scaling, quotient rule, and divisor-zero rejection",
            "trigonometric transcendental helpers with signed rate propagation in a paired .h/.cpp API",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-reservoir-level-flow",
            "Reservoir level flow",
            "reservoir_flow",
            """
            class FlowError : public std::domain_error {
            public:
                explicit FlowError(const std::string& message) : std::domain_error(message) {}
            };
            class LevelFlow {
            public:
                LevelFlow(double level, double inflow);
                double level() const;
                double inflow() const;
                std::string render() const;
            };
            LevelFlow operator+(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator-(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator*(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator/(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator*(double factor, const LevelFlow& value);
            LevelFlow operator*(const LevelFlow& value, double factor);
            bool nearly_equal(const LevelFlow& left, const LevelFlow& right, double eps);
            """,
            """
            class FlowError : public std::domain_error {
            public:
                explicit FlowError(const std::string& message) : std::domain_error(message) {}
            };
            class LevelFlow {
            public:
                LevelFlow(double level, double inflow);
                double level() const;
                double inflow() const;
                std::string render() const;
            private:
                double level_;
                double inflow_;
            };
            LevelFlow operator+(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator-(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator*(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator/(const LevelFlow& left, const LevelFlow& right);
            LevelFlow operator*(double factor, const LevelFlow& value);
            LevelFlow operator*(const LevelFlow& value, double factor);
            bool nearly_equal(const LevelFlow& left, const LevelFlow& right, double eps);
            """,
            """
            LevelFlow::LevelFlow(double level, double inflow) : level_(level), inflow_(inflow) {}
            double LevelFlow::level() const { return level_; }
            double LevelFlow::inflow() const { return inflow_; }
            std::string LevelFlow::render() const {
                std::ostringstream out;
                out << "level=" << std::fixed << std::setprecision(6) << level_ << ";inflow=" << inflow_;
                return out.str();
            }
            LevelFlow operator+(const LevelFlow& left, const LevelFlow& right) {
                return LevelFlow(left.level() + right.level(), left.inflow() + right.inflow());
            }
            LevelFlow operator-(const LevelFlow& left, const LevelFlow& right) {
                return LevelFlow(left.level() - right.level(), left.inflow() - right.inflow());
            }
            LevelFlow operator*(const LevelFlow& left, const LevelFlow& right) {
                return LevelFlow(left.level() * right.level(),
                                 left.level() * right.inflow() + right.level() * left.inflow());
            }
            LevelFlow operator/(const LevelFlow& left, const LevelFlow& right) {
                if (right.level() == 0.0) throw FlowError("divisor has zero value");
                return LevelFlow(left.level() / right.level(),
                                 (right.level() * left.inflow() - left.level() * right.inflow())
                                     / (right.level() * right.level()));
            }
            LevelFlow operator*(double factor, const LevelFlow& value) {
                return LevelFlow(factor * value.level(), factor * value.inflow());
            }
            LevelFlow operator*(const LevelFlow& value, double factor) {
                return factor * value;
            }
            bool nearly_equal(const LevelFlow& left, const LevelFlow& right, double eps) {
                return std::fabs(left.level() - right.level()) <= eps
                    && std::fabs(left.inflow() - right.inflow()) <= eps;
            }
            """,
            """
            LevelFlow::LevelFlow(double level, double inflow) : level_(level), inflow_(inflow) {}
            double LevelFlow::level() const { return level_; }
            double LevelFlow::inflow() const { return inflow_; }
            std::string LevelFlow::render() const {
                std::ostringstream out;
                out << "level=" << std::fixed << std::setprecision(6) << level_ << ";inflow=" << inflow_;
                return out.str();
            }
            LevelFlow operator+(const LevelFlow& left, const LevelFlow& right) {
                return LevelFlow(left.level() + right.level(), left.inflow() + right.inflow());
            }
            LevelFlow operator-(const LevelFlow& left, const LevelFlow& right) {
                return LevelFlow(left.level() - right.level(), left.inflow() - right.inflow());
            }
            LevelFlow operator*(const LevelFlow& left, const LevelFlow& right) {
                return LevelFlow(left.level() * right.level(),
                                 left.level() * right.inflow());
            }
            LevelFlow operator/(const LevelFlow& left, const LevelFlow& right) {
                if (right.level() == 0.0) throw FlowError("divisor has zero value");
                return LevelFlow(left.level() / right.level(),
                                 (right.level() * left.inflow() - left.level() * right.inflow())
                                     / (right.level() * right.level()));
            }
            LevelFlow operator*(double factor, const LevelFlow& value) {
                return LevelFlow(factor * value.level(), factor * value.inflow());
            }
            LevelFlow operator*(const LevelFlow& value, double factor) {
                return factor * value;
            }
            bool nearly_equal(const LevelFlow& left, const LevelFlow& right, double eps) {
                return std::fabs(left.level() - right.level()) <= eps
                    && std::fabs(left.inflow() - right.inflow()) <= eps;
            }
            """,
            """
            LevelFlow a(10.0, 1.5);
            LevelFlow b(4.0, -0.5);
            LevelFlow s = a + b;
            if (std::fabs(s.level() - 14.0) > 1e-9 || std::fabs(s.inflow() - 1.0) > 1e-9) return 1;
            LevelFlow p = a * b;
            if (std::fabs(p.level() - 40.0) > 1e-9 || std::fabs(p.inflow() - 1.0) > 1e-9) return 2;
            LevelFlow l = 2.0 * a;
            if (std::fabs(l.level() - 20.0) > 1e-9 || std::fabs(l.inflow() - 3.0) > 1e-9) return 3;
            LevelFlow r = a * 0.5;
            if (std::fabs(r.level() - 5.0) > 1e-9 || std::fabs(r.inflow() - 0.75) > 1e-9) return 4;
            if (a.render() != "level=10.000000;inflow=1.500000") return 5;
            if (!nearly_equal(a, LevelFlow(10.0, 1.5 + 1e-12), 1e-9)) return 6;
            return 0;
            """,
            """
            LevelFlow a(8.0, 2.0);
            LevelFlow b(2.0, 0.5);
            LevelFlow q = a / b;
            if (std::fabs(q.level() - 4.0) > 1e-9 || std::fabs(q.inflow()) > 1e-9) return 1;
            bool threw = false;
            try { LevelFlow z(0.0, 1.0); a / z; } catch (const FlowError&) { threw = true; }
            if (!threw) return 2;
            LevelFlow d = a - b;
            if (std::fabs(d.level() - 6.0) > 1e-9 || std::fabs(d.inflow() - 1.5) > 1e-9) return 3;
            LevelFlow l = -1.0 * a;
            if (std::fabs(l.level() + 8.0) > 1e-9 || std::fabs(l.inflow() + 2.0) > 1e-9) return 4;
            if (l.render() != "level=-8.000000;inflow=-2.000000") return 5;
            if (nearly_equal(a, LevelFlow(8.0 + 1e-6, 2.0), 1e-9)) return 6;
            LevelFlow p = 3.0 * b * 2.0;
            if (std::fabs(p.level() - 12.0) > 1e-9 || std::fabs(p.inflow() - 3.0) > 1e-9) return 7;
            return 0;
            """,
            "dual rate-pair propagation through scalar-left and scalar-right free operators with an exact labeled readout",
            "std::complex, <complex>, or any automatic-differentiation library; do not treat scalar multiplication asymmetrically and do not drop a product-rule cross term",
            "scalar-left multiplication order, quotient rule with exact zero rate, negative scalar rendering, and divisor-zero rejection",
            "mixed-operand free functions and exact readout in a project-context paired .h/.cpp layout",
            "first-order rate-pair value type",
            project_support=True,
        ),
        c(
            "f26cpx-orchard-yield-trend",
            "Orchard yield trend",
            "orchard_yield",
            """
            class YieldError : public std::domain_error {
            public:
                explicit YieldError(const std::string& message) : std::domain_error(message) {}
            };
            class YieldTrend {
            public:
                YieldTrend(double harvest, double trend);
                double harvest() const;
                double trend() const;
                YieldTrend operator+(const YieldTrend& other) const;
                YieldTrend operator-(const YieldTrend& other) const;
                YieldTrend operator*(const YieldTrend& other) const;
                YieldTrend operator/(const YieldTrend& other) const;
                YieldTrend pow(unsigned exponent) const;
            };
            bool close(const YieldTrend& left, const YieldTrend& right, double tol);
            """,
            """
            class YieldError : public std::domain_error {
            public:
                explicit YieldError(const std::string& message) : std::domain_error(message) {}
            };
            class YieldTrend {
            public:
                YieldTrend(double harvest, double trend);
                double harvest() const;
                double trend() const;
                YieldTrend operator+(const YieldTrend& other) const;
                YieldTrend operator-(const YieldTrend& other) const;
                YieldTrend operator*(const YieldTrend& other) const;
                YieldTrend operator/(const YieldTrend& other) const;
                YieldTrend pow(unsigned exponent) const;
            private:
                double harvest_;
                double trend_;
            };
            bool close(const YieldTrend& left, const YieldTrend& right, double tol);
            """,
            """
            YieldTrend::YieldTrend(double harvest, double trend) : harvest_(harvest), trend_(trend) {}
            double YieldTrend::harvest() const { return harvest_; }
            double YieldTrend::trend() const { return trend_; }
            YieldTrend YieldTrend::operator+(const YieldTrend& other) const {
                return YieldTrend(harvest_ + other.harvest_, trend_ + other.trend_);
            }
            YieldTrend YieldTrend::operator-(const YieldTrend& other) const {
                return YieldTrend(harvest_ - other.harvest_, trend_ - other.trend_);
            }
            YieldTrend YieldTrend::operator*(const YieldTrend& other) const {
                return YieldTrend(harvest_ * other.harvest_, harvest_ * other.trend_ + other.harvest_ * trend_);
            }
            YieldTrend YieldTrend::operator/(const YieldTrend& other) const {
                if (other.harvest_ == 0.0) throw YieldError("divisor has zero value");
                return YieldTrend(harvest_ / other.harvest_,
                                  (other.harvest_ * trend_ - harvest_ * other.trend_) / (other.harvest_ * other.harvest_));
            }
            YieldTrend YieldTrend::pow(unsigned exponent) const {
                YieldTrend result(1.0, 0.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            bool close(const YieldTrend& left, const YieldTrend& right, double tol) {
                return std::fabs(left.harvest() - right.harvest()) <= tol
                    && std::fabs(left.trend() - right.trend()) <= tol;
            }
            """,
            """
            YieldTrend::YieldTrend(double harvest, double trend) : harvest_(harvest), trend_(trend) {}
            double YieldTrend::harvest() const { return harvest_; }
            double YieldTrend::trend() const { return trend_; }
            YieldTrend YieldTrend::operator+(const YieldTrend& other) const {
                return YieldTrend(harvest_ + other.harvest_, trend_ + other.trend_);
            }
            YieldTrend YieldTrend::operator-(const YieldTrend& other) const {
                return YieldTrend(harvest_ - other.harvest_, trend_ - other.trend_);
            }
            YieldTrend YieldTrend::operator*(const YieldTrend& other) const {
                return YieldTrend(harvest_ * other.harvest_, harvest_ * other.trend_);
            }
            YieldTrend YieldTrend::operator/(const YieldTrend& other) const {
                if (other.harvest_ == 0.0) throw YieldError("divisor has zero value");
                return YieldTrend(harvest_ / other.harvest_,
                                  (other.harvest_ * trend_ - harvest_ * other.trend_) / (other.harvest_ * other.harvest_));
            }
            YieldTrend YieldTrend::pow(unsigned exponent) const {
                YieldTrend result(1.0, 0.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            bool close(const YieldTrend& left, const YieldTrend& right, double tol) {
                return std::fabs(left.harvest() - right.harvest()) <= tol
                    && std::fabs(left.trend() - right.trend()) <= tol;
            }
            """,
            """
            YieldTrend a(3.0, 0.6);
            YieldTrend b(1.5, -0.3);
            YieldTrend p = a * b;
            if (std::fabs(p.harvest() - 4.5) > 1e-9 || std::fabs(p.trend()) > 1e-9) return 1;
            YieldTrend sq = a.pow(2);
            if (std::fabs(sq.harvest() - 9.0) > 1e-9 || std::fabs(sq.trend() - 3.6) > 1e-9) return 2;
            YieldTrend q = a / b;
            if (std::fabs(q.harvest() - 2.0) > 1e-9 || std::fabs(q.trend() - 0.8) > 1e-9) return 3;
            if (!close(a, YieldTrend(3.0 + 1e-12, 0.6), 1e-9)) return 4;
            YieldTrend s = a + b;
            if (std::fabs(s.harvest() - 4.5) > 1e-9 || std::fabs(s.trend() - 0.3) > 1e-9) return 5;
            return 0;
            """,
            """
            YieldTrend a(2.0, 0.4);
            YieldTrend one = a.pow(0);
            if (std::fabs(one.harvest() - 1.0) > 1e-9 || std::fabs(one.trend()) > 1e-9) return 1;
            YieldTrend same = a.pow(1);
            if (std::fabs(same.harvest() - 2.0) > 1e-9 || std::fabs(same.trend() - 0.4) > 1e-9) return 2;
            YieldTrend cube = a.pow(3);
            if (std::fabs(cube.harvest() - 8.0) > 1e-9 || std::fabs(cube.trend() - 4.8) > 1e-9) return 3;
            bool threw = false;
            try { YieldTrend z(0.0, 1.0); a / z; } catch (const YieldError&) { threw = true; }
            if (!threw) return 4;
            if (close(a, YieldTrend(2.0, 0.4 + 1e-6), 1e-9)) return 5;
            YieldTrend d = a - YieldTrend(0.5, 0.1);
            if (std::fabs(d.harvest() - 1.5) > 1e-9 || std::fabs(d.trend() - 0.3) > 1e-9) return 6;
            YieldTrend chain = a * a * a;
            if (!close(chain, cube, 1e-9)) return 7;
            return 0;
            """,
            "dual rate-pair propagation with an integer-power chain rule and a named tolerance function",
            "std::complex, <complex>, or any automatic-differentiation library; do not accumulate additively for pow and do not drop a product-rule cross term",
            "pow(0) and pow(1) identities, chained products matching pow(3), quotient rule, divisor-zero rejection, and tolerance rejection just outside tol",
            "member operators plus a named tolerance function distinct from sibling rate-pair roots",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-probe-pressure-rate",
            "Probe pressure rate",
            "probe_pressure",
            """
            class PressureError : public std::domain_error {
            public:
                explicit PressureError(const std::string& message) : std::domain_error(message) {}
            };
            class PressureRate {
            public:
                PressureRate(double kpa, double rise);
                double kpa() const;
                double rise() const;
                PressureRate operator+(const PressureRate& other) const;
                PressureRate operator-(const PressureRate& other) const;
                PressureRate operator*(const PressureRate& other) const;
                PressureRate operator/(const PressureRate& other) const;
                PressureRate raise_e() const;
                PressureRate log() const;
                bool within(const PressureRate& other, double eps) const;
            };
            """,
            """
            class PressureError : public std::domain_error {
            public:
                explicit PressureError(const std::string& message) : std::domain_error(message) {}
            };
            class PressureRate {
            public:
                PressureRate(double kpa, double rise);
                double kpa() const;
                double rise() const;
                PressureRate operator+(const PressureRate& other) const;
                PressureRate operator-(const PressureRate& other) const;
                PressureRate operator*(const PressureRate& other) const;
                PressureRate operator/(const PressureRate& other) const;
                PressureRate raise_e() const;
                PressureRate log() const;
                bool within(const PressureRate& other, double eps) const;
            private:
                double kpa_;
                double rise_;
            };
            """,
            """
            PressureRate::PressureRate(double kpa, double rise) : kpa_(kpa), rise_(rise) {}
            double PressureRate::kpa() const { return kpa_; }
            double PressureRate::rise() const { return rise_; }
            PressureRate PressureRate::operator+(const PressureRate& other) const {
                return PressureRate(kpa_ + other.kpa_, rise_ + other.rise_);
            }
            PressureRate PressureRate::operator-(const PressureRate& other) const {
                return PressureRate(kpa_ - other.kpa_, rise_ - other.rise_);
            }
            PressureRate PressureRate::operator*(const PressureRate& other) const {
                return PressureRate(kpa_ * other.kpa_, kpa_ * other.rise_ + other.kpa_ * rise_);
            }
            PressureRate PressureRate::operator/(const PressureRate& other) const {
                if (other.kpa_ == 0.0) throw PressureError("divisor has zero value");
                return PressureRate(kpa_ / other.kpa_,
                                    (other.kpa_ * rise_ - kpa_ * other.rise_) / (other.kpa_ * other.kpa_));
            }
            PressureRate PressureRate::raise_e() const {
                double lifted = std::exp(kpa_);
                return PressureRate(lifted, lifted * rise_);
            }
            PressureRate PressureRate::log() const {
                if (kpa_ <= 0.0) throw PressureError("log of non-positive value");
                return PressureRate(std::log(kpa_), rise_ / kpa_);
            }
            bool PressureRate::within(const PressureRate& other, double eps) const {
                return std::fabs(kpa_ - other.kpa_) <= eps
                    && std::fabs(rise_ - other.rise_) <= eps;
            }
            """,
            """
            PressureRate::PressureRate(double kpa, double rise) : kpa_(kpa), rise_(rise) {}
            double PressureRate::kpa() const { return kpa_; }
            double PressureRate::rise() const { return rise_; }
            PressureRate PressureRate::operator+(const PressureRate& other) const {
                return PressureRate(kpa_ + other.kpa_, rise_ + other.rise_);
            }
            PressureRate PressureRate::operator-(const PressureRate& other) const {
                return PressureRate(kpa_ - other.kpa_, rise_ - other.rise_);
            }
            PressureRate PressureRate::operator*(const PressureRate& other) const {
                return PressureRate(kpa_ * other.kpa_, kpa_ * other.rise_);
            }
            PressureRate PressureRate::operator/(const PressureRate& other) const {
                if (other.kpa_ == 0.0) throw PressureError("divisor has zero value");
                return PressureRate(kpa_ / other.kpa_,
                                    (other.kpa_ * rise_ - kpa_ * other.rise_) / (other.kpa_ * other.kpa_));
            }
            PressureRate PressureRate::raise_e() const {
                double lifted = std::exp(kpa_);
                return PressureRate(lifted, lifted * rise_);
            }
            PressureRate PressureRate::log() const {
                if (kpa_ <= 0.0) throw PressureError("log of non-positive value");
                return PressureRate(std::log(kpa_), rise_ / kpa_);
            }
            bool PressureRate::within(const PressureRate& other, double eps) const {
                return std::fabs(kpa_ - other.kpa_) <= eps
                    && std::fabs(rise_ - other.rise_) <= eps;
            }
            """,
            """
            PressureRate a(2.0, 0.4);
            PressureRate b(4.0, -0.8);
            PressureRate p = a * b;
            if (std::fabs(p.kpa() - 8.0) > 1e-9 || std::fabs(p.rise()) > 1e-9) return 1;
            PressureRate e = a.raise_e();
            if (std::fabs(e.kpa() - std::exp(2.0)) > 1e-9) return 2;
            if (std::fabs(e.rise() - 0.4 * std::exp(2.0)) > 1e-9) return 3;
            PressureRate lg = a.log();
            if (std::fabs(lg.kpa() - std::log(2.0)) > 1e-9 || std::fabs(lg.rise() - 0.2) > 1e-9) return 4;
            if (!a.within(PressureRate(2.0, 0.4 + 1e-12), 1e-9)) return 5;
            return 0;
            """,
            """
            PressureRate a(1.0, 1.0);
            PressureRate rt = a.log().raise_e();
            if (std::fabs(rt.kpa() - 1.0) > 1e-9 || std::fabs(rt.rise() - 1.0) > 1e-9) return 1;
            bool threw = false;
            try { PressureRate(0.0, 1.0).log(); } catch (const PressureError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PressureRate(-2.0, 1.0).log(); } catch (const PressureError&) { threw = true; }
            if (!threw) return 3;
            PressureRate b(3.0, 0.9);
            PressureRate c(1.5, 0.3);
            PressureRate q = b / c;
            if (std::fabs(q.kpa() - 2.0) > 1e-9 || std::fabs(q.rise() - 0.2) > 1e-9) return 4;
            threw = false;
            try { PressureRate z(0.0, 1.0); b / z; } catch (const PressureError&) { threw = true; }
            if (!threw) return 5;
            if (b.within(PressureRate(3.0 + 1e-6, 0.9), 1e-9)) return 6;
            PressureRate d = b - c;
            if (std::fabs(d.kpa() - 1.5) > 1e-9 || std::fabs(d.rise() - 0.6) > 1e-9) return 7;
            return 0;
            """,
            "dual rate-pair propagation through inverse exponential and logarithm helpers on one owned pair",
            "std::complex, <complex>, or any automatic-differentiation library; do not apply the helpers to the rise component independently and do not drop a product-rule cross term",
            "log-of-raise_e round trip, log domain edges at zero and negative values, quotient rule, and divisor-zero rejection",
            "two inverse transcendental helpers on one owned pair in a paired .h/.cpp API",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-balloon-lift-budget",
            "Balloon lift budget",
            "balloon_lift",
            """
            class LiftError : public std::domain_error {
            public:
                explicit LiftError(const std::string& message) : std::domain_error(message) {}
            };
            class LiftBudget {
            public:
                LiftBudget(double lift, double gust);
                double lift() const;
                double gust() const;
                LiftBudget operator+(const LiftBudget& other) const;
                LiftBudget operator-(const LiftBudget& other) const;
                LiftBudget operator*(const LiftBudget& other) const;
                LiftBudget operator/(const LiftBudget& other) const;
                LiftBudget root2() const;
                LiftBudget pow(unsigned exponent) const;
                std::string render() const;
            };
            """,
            """
            class LiftError : public std::domain_error {
            public:
                explicit LiftError(const std::string& message) : std::domain_error(message) {}
            };
            class LiftBudget {
            public:
                LiftBudget(double lift, double gust);
                double lift() const;
                double gust() const;
                LiftBudget operator+(const LiftBudget& other) const;
                LiftBudget operator-(const LiftBudget& other) const;
                LiftBudget operator*(const LiftBudget& other) const;
                LiftBudget operator/(const LiftBudget& other) const;
                LiftBudget root2() const;
                LiftBudget pow(unsigned exponent) const;
                std::string render() const;
            private:
                double lift_;
                double gust_;
            };
            """,
            """
            LiftBudget::LiftBudget(double lift, double gust) : lift_(lift), gust_(gust) {}
            double LiftBudget::lift() const { return lift_; }
            double LiftBudget::gust() const { return gust_; }
            LiftBudget LiftBudget::operator+(const LiftBudget& other) const {
                return LiftBudget(lift_ + other.lift_, gust_ + other.gust_);
            }
            LiftBudget LiftBudget::operator-(const LiftBudget& other) const {
                return LiftBudget(lift_ - other.lift_, gust_ - other.gust_);
            }
            LiftBudget LiftBudget::operator*(const LiftBudget& other) const {
                return LiftBudget(lift_ * other.lift_, lift_ * other.gust_ + other.lift_ * gust_);
            }
            LiftBudget LiftBudget::operator/(const LiftBudget& other) const {
                if (other.lift_ == 0.0) throw LiftError("divisor has zero value");
                return LiftBudget(lift_ / other.lift_,
                                  (other.lift_ * gust_ - lift_ * other.gust_) / (other.lift_ * other.lift_));
            }
            LiftBudget LiftBudget::root2() const {
                if (lift_ <= 0.0) throw LiftError("square root of non-positive value");
                double root = std::sqrt(lift_);
                return LiftBudget(root, gust_ / (2.0 * root));
            }
            LiftBudget LiftBudget::pow(unsigned exponent) const {
                LiftBudget result(1.0, 0.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            std::string LiftBudget::render() const {
                std::ostringstream out;
                out << "lift=" << std::fixed << std::setprecision(6) << lift_ << ";gust=" << gust_;
                return out.str();
            }
            """,
            """
            LiftBudget::LiftBudget(double lift, double gust) : lift_(lift), gust_(gust) {}
            double LiftBudget::lift() const { return lift_; }
            double LiftBudget::gust() const { return gust_; }
            LiftBudget LiftBudget::operator+(const LiftBudget& other) const {
                return LiftBudget(lift_ + other.lift_, gust_ + other.gust_);
            }
            LiftBudget LiftBudget::operator-(const LiftBudget& other) const {
                return LiftBudget(lift_ - other.lift_, gust_ - other.gust_);
            }
            LiftBudget LiftBudget::operator*(const LiftBudget& other) const {
                return LiftBudget(lift_ * other.lift_, lift_ * other.gust_);
            }
            LiftBudget LiftBudget::operator/(const LiftBudget& other) const {
                if (other.lift_ == 0.0) throw LiftError("divisor has zero value");
                return LiftBudget(lift_ / other.lift_,
                                  (other.lift_ * gust_ - lift_ * other.gust_) / (other.lift_ * other.lift_));
            }
            LiftBudget LiftBudget::root2() const {
                if (lift_ <= 0.0) throw LiftError("square root of non-positive value");
                double root = std::sqrt(lift_);
                return LiftBudget(root, gust_ / (2.0 * root));
            }
            LiftBudget LiftBudget::pow(unsigned exponent) const {
                LiftBudget result(1.0, 0.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            std::string LiftBudget::render() const {
                std::ostringstream out;
                out << "lift=" << std::fixed << std::setprecision(6) << lift_ << ";gust=" << gust_;
                return out.str();
            }
            """,
            """
            LiftBudget a(4.0, 0.4);
            LiftBudget b(2.0, 0.2);
            LiftBudget p = a * b;
            if (std::fabs(p.lift() - 8.0) > 1e-9 || std::fabs(p.gust() - 1.6) > 1e-9) return 1;
            LiftBudget r = a.root2();
            if (std::fabs(r.lift() - 2.0) > 1e-9 || std::fabs(r.gust() - 0.1) > 1e-9) return 2;
            LiftBudget sq = a.pow(2);
            if (std::fabs(sq.lift() - 16.0) > 1e-9 || std::fabs(sq.gust() - 3.2) > 1e-9) return 3;
            if (a.render() != "lift=4.000000;gust=0.400000") return 4;
            LiftBudget q = a / b;
            if (std::fabs(q.lift() - 2.0) > 1e-9 || std::fabs(q.gust()) > 1e-9) return 5;
            return 0;
            """,
            """
            LiftBudget a(9.0, 0.9);
            LiftBudget sq = a.root2().pow(2);
            if (std::fabs(sq.lift() - 9.0) > 1e-9 || std::fabs(sq.gust() - 0.9) > 1e-9) return 1;
            bool threw = false;
            try { LiftBudget(0.0, 1.0).root2(); } catch (const LiftError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { LiftBudget(-1.0, 1.0).root2(); } catch (const LiftError&) { threw = true; }
            if (!threw) return 3;
            LiftBudget one = a.pow(0);
            if (std::fabs(one.lift() - 1.0) > 1e-9 || std::fabs(one.gust()) > 1e-9) return 4;
            threw = false;
            try { LiftBudget z(0.0, 1.0); a / z; } catch (const LiftError&) { threw = true; }
            if (!threw) return 5;
            LiftBudget s = a + LiftBudget(1.0, 0.1);
            if (s.render() != "lift=10.000000;gust=1.000000") return 6;
            LiftBudget d = a - LiftBudget(4.0, 0.4);
            if (std::fabs(d.lift() - 5.0) > 1e-9 || std::fabs(d.gust() - 0.5) > 1e-9) return 7;
            return 0;
            """,
            "dual rate-pair propagation through a composed root-then-power pipeline with an exact labeled readout",
            "std::complex, <complex>, or any automatic-differentiation library; do not truncate the readout precision and do not drop a product-rule cross term",
            "root2-then-pow(2) recovery for positive values, root domain edges, pow(0) identity, byte-exact render, and divisor-zero rejection",
            "composed helper pipeline with deterministic formatting in a paired .h/.cpp API",
            "first-order rate-pair value type",
        ),
        c(
            "f26cpx-regatta-tide-offset",
            "Regatta tide offset",
            "tide_offset",
            """
            class OffsetError : public std::domain_error {
            public:
                explicit OffsetError(const std::string& message) : std::domain_error(message) {}
            };
            class TideOffset {
            public:
                TideOffset(double surge, double drift);
                double surge() const;
                double drift() const;
                TideOffset operator+(const TideOffset& other) const;
                TideOffset operator-(const TideOffset& other) const;
                TideOffset operator*(const TideOffset& other) const;
                TideOffset operator/(const TideOffset& other) const;
                TideOffset mirror() const;
                double gauge() const;
                TideOffset boost(double rapidity) const;
            };
            bool nearly_equal(const TideOffset& left, const TideOffset& right, double eps);
            """,
            """
            class OffsetError : public std::domain_error {
            public:
                explicit OffsetError(const std::string& message) : std::domain_error(message) {}
            };
            class TideOffset {
            public:
                TideOffset(double surge, double drift);
                double surge() const;
                double drift() const;
                TideOffset operator+(const TideOffset& other) const;
                TideOffset operator-(const TideOffset& other) const;
                TideOffset operator*(const TideOffset& other) const;
                TideOffset operator/(const TideOffset& other) const;
                TideOffset mirror() const;
                double gauge() const;
                TideOffset boost(double rapidity) const;
            private:
                double surge_;
                double drift_;
            };
            bool nearly_equal(const TideOffset& left, const TideOffset& right, double eps);
            """,
            """
            TideOffset::TideOffset(double surge, double drift) : surge_(surge), drift_(drift) {}
            double TideOffset::surge() const { return surge_; }
            double TideOffset::drift() const { return drift_; }
            TideOffset TideOffset::operator+(const TideOffset& other) const {
                return TideOffset(surge_ + other.surge_, drift_ + other.drift_);
            }
            TideOffset TideOffset::operator-(const TideOffset& other) const {
                return TideOffset(surge_ - other.surge_, drift_ - other.drift_);
            }
            TideOffset TideOffset::operator*(const TideOffset& other) const {
                return TideOffset(surge_ * other.surge_ + drift_ * other.drift_,
                                  surge_ * other.drift_ + other.surge_ * drift_);
            }
            TideOffset TideOffset::operator/(const TideOffset& other) const {
                double g = other.surge_ * other.surge_ - other.drift_ * other.drift_;
                if (g == 0.0) throw OffsetError("divisor has zero gauge");
                return TideOffset((surge_ * other.surge_ - drift_ * other.drift_) / g,
                                  (other.surge_ * drift_ - surge_ * other.drift_) / g);
            }
            TideOffset TideOffset::mirror() const {
                return TideOffset(surge_, -drift_);
            }
            double TideOffset::gauge() const {
                return surge_ * surge_ - drift_ * drift_;
            }
            TideOffset TideOffset::boost(double rapidity) const {
                return (*this) * TideOffset(std::cosh(rapidity), std::sinh(rapidity));
            }
            bool nearly_equal(const TideOffset& left, const TideOffset& right, double eps) {
                return std::fabs(left.surge() - right.surge()) <= eps
                    && std::fabs(left.drift() - right.drift()) <= eps;
            }
            """,
            """
            TideOffset::TideOffset(double surge, double drift) : surge_(surge), drift_(drift) {}
            double TideOffset::surge() const { return surge_; }
            double TideOffset::drift() const { return drift_; }
            TideOffset TideOffset::operator+(const TideOffset& other) const {
                return TideOffset(surge_ + other.surge_, drift_ + other.drift_);
            }
            TideOffset TideOffset::operator-(const TideOffset& other) const {
                return TideOffset(surge_ - other.surge_, drift_ - other.drift_);
            }
            TideOffset TideOffset::operator*(const TideOffset& other) const {
                return TideOffset(surge_ * other.surge_ - drift_ * other.drift_,
                                  surge_ * other.drift_ + other.surge_ * drift_);
            }
            TideOffset TideOffset::operator/(const TideOffset& other) const {
                double g = other.surge_ * other.surge_ - other.drift_ * other.drift_;
                if (g == 0.0) throw OffsetError("divisor has zero gauge");
                return TideOffset((surge_ * other.surge_ - drift_ * other.drift_) / g,
                                  (other.surge_ * drift_ - surge_ * other.drift_) / g);
            }
            TideOffset TideOffset::mirror() const {
                return TideOffset(surge_, -drift_);
            }
            double TideOffset::gauge() const {
                return surge_ * surge_ - drift_ * drift_;
            }
            TideOffset TideOffset::boost(double rapidity) const {
                return (*this) * TideOffset(std::cosh(rapidity), std::sinh(rapidity));
            }
            bool nearly_equal(const TideOffset& left, const TideOffset& right, double eps) {
                return std::fabs(left.surge() - right.surge()) <= eps
                    && std::fabs(left.drift() - right.drift()) <= eps;
            }
            """,
            """
            TideOffset a(3.0, 1.0);
            TideOffset b(2.0, 0.5);
            TideOffset s = a + b;
            if (std::fabs(s.surge() - 5.0) > 1e-9 || std::fabs(s.drift() - 1.5) > 1e-9) return 1;
            TideOffset p = a * b;
            if (std::fabs(p.surge() - 6.5) > 1e-9 || std::fabs(p.drift() - 3.5) > 1e-9) return 2;
            TideOffset m = a.mirror();
            if (std::fabs(m.surge() - 3.0) > 1e-9 || std::fabs(m.drift() + 1.0) > 1e-9) return 3;
            if (std::fabs(a.gauge() - 8.0) > 1e-9) return 4;
            TideOffset q = a / b;
            if (std::fabs(q.surge() - 5.5 / 3.75) > 1e-9 || std::fabs(q.drift() - 0.5 / 3.75) > 1e-9) return 5;
            if (!nearly_equal(a, TideOffset(3.0 + 1e-12, 1.0), 1e-9)) return 6;
            return 0;
            """,
            """
            TideOffset a(2.0, 1.0);
            TideOffset z = a * a.mirror();
            if (std::fabs(z.surge() - 3.0) > 1e-9 || std::fabs(z.drift()) > 1e-9) return 1;
            TideOffset boosted = a.boost(0.5);
            if (std::fabs(boosted.gauge() - a.gauge()) > 1e-9) return 2;
            TideOffset two_step = a.boost(0.3).boost(0.4);
            TideOffset one_step = a.boost(0.7);
            if (!nearly_equal(two_step, one_step, 1e-9)) return 3;
            bool threw = false;
            try { TideOffset edge(1.0, 1.0); a / edge; } catch (const OffsetError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { TideOffset edge(2.0, -2.0); a / edge; } catch (const OffsetError&) { threw = true; }
            if (!threw) return 5;
            if (nearly_equal(a, TideOffset(2.0, 1.0 + 1e-6), 1e-9)) return 6;
            TideOffset d = a - TideOffset(0.5, 0.25);
            if (std::fabs(d.surge() - 1.5) > 1e-9 || std::fabs(d.drift() - 0.75) > 1e-9) return 7;
            TideOffset zero = a.boost(0.0);
            if (!nearly_equal(zero, a, 1e-12)) return 8;
            return 0;
            """,
            "hyperbolic gauge-pair algebra with the plus-sign product table, mirror involution, and gauge-based division",
            "std::complex, <complex>, or the minus-sign product table; do not use trigonometric helpers for the boost",
            "the z-times-mirror gauge identity, boost composition and gauge preservation, division by a nonzero zero-gauge pair, and tolerance boundaries",
            "norm-based inversion with a genuine zero-divisor edge in a paired .h/.cpp API",
            "hyperbolic gauge-pair value type",
        ),
        c(
            "f26cpx-laser-cavity-detune",
            "Laser cavity detune",
            "cavity_detune",
            """
            class DetuneError : public std::domain_error {
            public:
                explicit DetuneError(const std::string& message) : std::domain_error(message) {}
            };
            class DetunePair {
            public:
                DetunePair(double gain, double chirp);
                double gain() const;
                double chirp() const;
                DetunePair operator+(const DetunePair& other) const;
                DetunePair operator-(const DetunePair& other) const;
                DetunePair operator*(const DetunePair& other) const;
                DetunePair operator/(const DetunePair& other) const;
                double gauge() const;
                DetunePair spread() const;
            };
            DetunePair operator*(double factor, const DetunePair& value);
            bool nearly_equal(const DetunePair& left, const DetunePair& right, double eps);
            """,
            """
            class DetuneError : public std::domain_error {
            public:
                explicit DetuneError(const std::string& message) : std::domain_error(message) {}
            };
            class DetunePair {
            public:
                DetunePair(double gain, double chirp);
                double gain() const;
                double chirp() const;
                DetunePair operator+(const DetunePair& other) const;
                DetunePair operator-(const DetunePair& other) const;
                DetunePair operator*(const DetunePair& other) const;
                DetunePair operator/(const DetunePair& other) const;
                double gauge() const;
                DetunePair spread() const;
            private:
                double gain_;
                double chirp_;
            };
            DetunePair operator*(double factor, const DetunePair& value);
            bool nearly_equal(const DetunePair& left, const DetunePair& right, double eps);
            """,
            """
            DetunePair::DetunePair(double gain, double chirp) : gain_(gain), chirp_(chirp) {}
            double DetunePair::gain() const { return gain_; }
            double DetunePair::chirp() const { return chirp_; }
            DetunePair DetunePair::operator+(const DetunePair& other) const {
                return DetunePair(gain_ + other.gain_, chirp_ + other.chirp_);
            }
            DetunePair DetunePair::operator-(const DetunePair& other) const {
                return DetunePair(gain_ - other.gain_, chirp_ - other.chirp_);
            }
            DetunePair DetunePair::operator*(const DetunePair& other) const {
                return DetunePair(gain_ * other.gain_ + chirp_ * other.chirp_,
                                  gain_ * other.chirp_ + other.gain_ * chirp_);
            }
            DetunePair DetunePair::operator/(const DetunePair& other) const {
                double g = other.gain_ * other.gain_ - other.chirp_ * other.chirp_;
                if (g == 0.0) throw DetuneError("divisor has zero gauge");
                return DetunePair((gain_ * other.gain_ - chirp_ * other.chirp_) / g,
                                  (other.gain_ * chirp_ - gain_ * other.chirp_) / g);
            }
            double DetunePair::gauge() const {
                return gain_ * gain_ - chirp_ * chirp_;
            }
            DetunePair DetunePair::spread() const {
                double lifted = std::exp(gain_);
                return DetunePair(lifted * std::cosh(chirp_), lifted * std::sinh(chirp_));
            }
            DetunePair operator*(double factor, const DetunePair& value) {
                return DetunePair(factor * value.gain(), factor * value.chirp());
            }
            bool nearly_equal(const DetunePair& left, const DetunePair& right, double eps) {
                return std::fabs(left.gain() - right.gain()) <= eps
                    && std::fabs(left.chirp() - right.chirp()) <= eps;
            }
            """,
            """
            DetunePair::DetunePair(double gain, double chirp) : gain_(gain), chirp_(chirp) {}
            double DetunePair::gain() const { return gain_; }
            double DetunePair::chirp() const { return chirp_; }
            DetunePair DetunePair::operator+(const DetunePair& other) const {
                return DetunePair(gain_ + other.gain_, chirp_ + other.chirp_);
            }
            DetunePair DetunePair::operator-(const DetunePair& other) const {
                return DetunePair(gain_ - other.gain_, chirp_ - other.chirp_);
            }
            DetunePair DetunePair::operator*(const DetunePair& other) const {
                return DetunePair(gain_ * other.gain_ - chirp_ * other.chirp_,
                                  gain_ * other.chirp_ + other.gain_ * chirp_);
            }
            DetunePair DetunePair::operator/(const DetunePair& other) const {
                double g = other.gain_ * other.gain_ - other.chirp_ * other.chirp_;
                if (g == 0.0) throw DetuneError("divisor has zero gauge");
                return DetunePair((gain_ * other.gain_ - chirp_ * other.chirp_) / g,
                                  (other.gain_ * chirp_ - gain_ * other.chirp_) / g);
            }
            double DetunePair::gauge() const {
                return gain_ * gain_ - chirp_ * chirp_;
            }
            DetunePair DetunePair::spread() const {
                double lifted = std::exp(gain_);
                return DetunePair(lifted * std::cosh(chirp_), lifted * std::sinh(chirp_));
            }
            DetunePair operator*(double factor, const DetunePair& value) {
                return DetunePair(factor * value.gain(), factor * value.chirp());
            }
            bool nearly_equal(const DetunePair& left, const DetunePair& right, double eps) {
                return std::fabs(left.gain() - right.gain()) <= eps
                    && std::fabs(left.chirp() - right.chirp()) <= eps;
            }
            """,
            """
            DetunePair a(1.0, 0.5);
            DetunePair b(0.5, 0.25);
            DetunePair p = a * b;
            if (std::fabs(p.gain() - 0.625) > 1e-9 || std::fabs(p.chirp() - 0.5) > 1e-9) return 1;
            DetunePair e = DetunePair(0.0, 0.0).spread();
            if (std::fabs(e.gain() - 1.0) > 1e-9 || std::fabs(e.chirp()) > 1e-9) return 2;
            DetunePair l = 2.0 * a;
            if (std::fabs(l.gain() - 2.0) > 1e-9 || std::fabs(l.chirp() - 1.0) > 1e-9) return 3;
            DetunePair q = a / b;
            if (std::fabs(q.gain() - 2.0) > 1e-9 || std::fabs(q.chirp()) > 1e-9) return 4;
            if (!nearly_equal(a, DetunePair(1.0 + 1e-12, 0.5), 1e-9)) return 5;
            return 0;
            """,
            """
            DetunePair a(1.5, 0.5);
            DetunePair sp = a.spread();
            if (std::fabs(sp.gauge() - std::exp(3.0)) > 1e-7) return 1;
            DetunePair hom = DetunePair(0.5, 0.25).spread() * DetunePair(1.0, 0.25).spread();
            DetunePair direct = DetunePair(1.5, 0.5).spread();
            if (!nearly_equal(hom, direct, 1e-9)) return 2;
            bool threw = false;
            try { DetunePair edge(1.0, -1.0); a / edge; } catch (const DetuneError&) { threw = true; }
            if (!threw) return 3;
            DetunePair s = a + DetunePair(0.5, -0.5);
            if (std::fabs(s.gain() - 2.0) > 1e-9 || std::fabs(s.chirp()) > 1e-9) return 4;
            DetunePair m = 3.0 * a;
            if (std::fabs(m.gain() - 4.5) > 1e-9 || std::fabs(m.chirp() - 1.5) > 1e-9) return 5;
            if (nearly_equal(a, DetunePair(1.5, 0.5 + 1e-6), 1e-9)) return 6;
            DetunePair d = a - DetunePair(0.5, 0.25);
            if (std::fabs(d.gain() - 1.0) > 1e-9 || std::fabs(d.chirp() - 0.25) > 1e-9) return 7;
            return 0;
            """,
            "hyperbolic gauge-pair algebra with an exponential spread helper and scalar-left free operator",
            "std::complex, <complex>, or the minus-sign product table; do not use trigonometric sin/cos inside spread",
            "spread gauge law, the spread homomorphism over addition, scalar-left multiplication, and zero-gauge division rejection",
            "hyperbolic transcendental helper distinct from trigonometric roots in a paired .h/.cpp API",
            "hyperbolic gauge-pair value type",
        ),
        c(
            "f26cpx-bobsled-track-boost",
            "Bobsled track boost",
            "track_boost",
            """
            class BoostError : public std::domain_error {
            public:
                explicit BoostError(const std::string& message) : std::domain_error(message) {}
            };
            class BoostPair {
            public:
                BoostPair(double pace, double lean);
                double pace() const;
                double lean() const;
                BoostPair operator+(const BoostPair& other) const;
                BoostPair operator-(const BoostPair& other) const;
                BoostPair operator*(const BoostPair& other) const;
                BoostPair operator/(const BoostPair& other) const;
                BoostPair mirror() const;
                double gauge() const;
                std::string render() const;
            };
            """,
            """
            class BoostError : public std::domain_error {
            public:
                explicit BoostError(const std::string& message) : std::domain_error(message) {}
            };
            class BoostPair {
            public:
                BoostPair(double pace, double lean);
                double pace() const;
                double lean() const;
                BoostPair operator+(const BoostPair& other) const;
                BoostPair operator-(const BoostPair& other) const;
                BoostPair operator*(const BoostPair& other) const;
                BoostPair operator/(const BoostPair& other) const;
                BoostPair mirror() const;
                double gauge() const;
                std::string render() const;
            private:
                double pace_;
                double lean_;
            };
            """,
            """
            BoostPair::BoostPair(double pace, double lean) : pace_(pace), lean_(lean) {}
            double BoostPair::pace() const { return pace_; }
            double BoostPair::lean() const { return lean_; }
            BoostPair BoostPair::operator+(const BoostPair& other) const {
                return BoostPair(pace_ + other.pace_, lean_ + other.lean_);
            }
            BoostPair BoostPair::operator-(const BoostPair& other) const {
                return BoostPair(pace_ - other.pace_, lean_ - other.lean_);
            }
            BoostPair BoostPair::operator*(const BoostPair& other) const {
                return BoostPair(pace_ * other.pace_ + lean_ * other.lean_,
                                 pace_ * other.lean_ + other.pace_ * lean_);
            }
            BoostPair BoostPair::operator/(const BoostPair& other) const {
                double g = other.pace_ * other.pace_ - other.lean_ * other.lean_;
                if (g == 0.0) throw BoostError("divisor has zero gauge");
                return BoostPair((pace_ * other.pace_ - lean_ * other.lean_) / g,
                                 (other.pace_ * lean_ - pace_ * other.lean_) / g);
            }
            BoostPair BoostPair::mirror() const {
                return BoostPair(pace_, -lean_);
            }
            double BoostPair::gauge() const {
                return pace_ * pace_ - lean_ * lean_;
            }
            std::string BoostPair::render() const {
                std::ostringstream out;
                out << "pace=" << std::fixed << std::setprecision(6) << pace_ << ";lean=" << lean_;
                return out.str();
            }
            """,
            """
            BoostPair::BoostPair(double pace, double lean) : pace_(pace), lean_(lean) {}
            double BoostPair::pace() const { return pace_; }
            double BoostPair::lean() const { return lean_; }
            BoostPair BoostPair::operator+(const BoostPair& other) const {
                return BoostPair(pace_ + other.pace_, lean_ + other.lean_);
            }
            BoostPair BoostPair::operator-(const BoostPair& other) const {
                return BoostPair(pace_ - other.pace_, lean_ - other.lean_);
            }
            BoostPair BoostPair::operator*(const BoostPair& other) const {
                return BoostPair(pace_ * other.pace_ - lean_ * other.lean_,
                                 pace_ * other.lean_ + other.pace_ * lean_);
            }
            BoostPair BoostPair::operator/(const BoostPair& other) const {
                double g = other.pace_ * other.pace_ - other.lean_ * other.lean_;
                if (g == 0.0) throw BoostError("divisor has zero gauge");
                return BoostPair((pace_ * other.pace_ - lean_ * other.lean_) / g,
                                 (other.pace_ * lean_ - pace_ * other.lean_) / g);
            }
            BoostPair BoostPair::mirror() const {
                return BoostPair(pace_, -lean_);
            }
            double BoostPair::gauge() const {
                return pace_ * pace_ - lean_ * lean_;
            }
            std::string BoostPair::render() const {
                std::ostringstream out;
                out << "pace=" << std::fixed << std::setprecision(6) << pace_ << ";lean=" << lean_;
                return out.str();
            }
            """,
            """
            BoostPair a(2.5, 1.5);
            BoostPair b(1.5, 0.5);
            BoostPair p = a * b;
            if (std::fabs(p.pace() - 4.5) > 1e-9 || std::fabs(p.lean() - 3.5) > 1e-9) return 1;
            if (std::fabs(a.gauge() - 4.0) > 1e-9) return 2;
            BoostPair m = a.mirror();
            if (std::fabs(m.pace() - 2.5) > 1e-9 || std::fabs(m.lean() + 1.5) > 1e-9) return 3;
            BoostPair q = a / b;
            if (std::fabs(q.pace() - 1.5) > 1e-9 || std::fabs(q.lean() - 0.5) > 1e-9) return 4;
            if (a.render() != "pace=2.500000;lean=1.500000") return 5;
            return 0;
            """,
            """
            BoostPair a(3.0, 1.0);
            BoostPair z = a * a.mirror();
            if (std::fabs(z.pace() - 8.0) > 1e-9 || std::fabs(z.lean()) > 1e-9) return 1;
            bool threw = false;
            try { BoostPair edge(1.0, 1.0); a / edge; } catch (const BoostError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { BoostPair edge(-2.0, 2.0); a / edge; } catch (const BoostError&) { threw = true; }
            if (!threw) return 3;
            BoostPair s = a + BoostPair(1.0, 1.0);
            if (std::fabs(s.pace() - 4.0) > 1e-9 || std::fabs(s.lean() - 2.0) > 1e-9) return 4;
            if (s.render() != "pace=4.000000;lean=2.000000") return 5;
            BoostPair d = a - BoostPair(1.5, 0.5);
            if (std::fabs(d.pace() - 1.5) > 1e-9 || std::fabs(d.lean() - 0.5) > 1e-9) return 6;
            BoostPair p = a * a;
            if (std::fabs(p.pace() - 10.0) > 1e-9 || std::fabs(p.lean() - 6.0) > 1e-9) return 7;
            if (p.render() != "pace=10.000000;lean=6.000000") return 8;
            return 0;
            """,
            "hyperbolic gauge-pair algebra with mirror involution and an exact fixed-precision readout",
            "std::complex, <complex>, or the minus-sign product table; do not truncate the readout precision",
            "the z-times-mirror gauge identity, division by a nonzero zero-gauge pair, and byte-exact render after products",
            "deterministic formatting over a gauge algebra in a project-context paired .h/.cpp layout",
            "hyperbolic gauge-pair value type",
            project_support=True,
        ),
        c(
            "f26cpx-seismic-wave-rapidity",
            "Seismic wave rapidity",
            "wave_rapidity",
            """
            class RapidityError : public std::domain_error {
            public:
                explicit RapidityError(const std::string& message) : std::domain_error(message) {}
            };
            class RapidityPair {
            public:
                RapidityPair(double shift, double skew);
                double shift() const;
                double skew() const;
                RapidityPair square() const;
                double gauge() const;
                RapidityPair boost(double rapidity) const;
                bool within(const RapidityPair& other, double eps) const;
            };
            RapidityPair operator+(const RapidityPair& left, const RapidityPair& right);
            RapidityPair operator-(const RapidityPair& left, const RapidityPair& right);
            RapidityPair operator*(const RapidityPair& left, const RapidityPair& right);
            RapidityPair operator/(const RapidityPair& left, const RapidityPair& right);
            """,
            """
            class RapidityError : public std::domain_error {
            public:
                explicit RapidityError(const std::string& message) : std::domain_error(message) {}
            };
            class RapidityPair {
            public:
                RapidityPair(double shift, double skew);
                double shift() const;
                double skew() const;
                RapidityPair square() const;
                double gauge() const;
                RapidityPair boost(double rapidity) const;
                bool within(const RapidityPair& other, double eps) const;
            private:
                double shift_;
                double skew_;
            };
            RapidityPair operator+(const RapidityPair& left, const RapidityPair& right);
            RapidityPair operator-(const RapidityPair& left, const RapidityPair& right);
            RapidityPair operator*(const RapidityPair& left, const RapidityPair& right);
            RapidityPair operator/(const RapidityPair& left, const RapidityPair& right);
            """,
            """
            RapidityPair::RapidityPair(double shift, double skew) : shift_(shift), skew_(skew) {}
            double RapidityPair::shift() const { return shift_; }
            double RapidityPair::skew() const { return skew_; }
            RapidityPair RapidityPair::square() const {
                return (*this) * (*this);
            }
            double RapidityPair::gauge() const {
                return shift_ * shift_ - skew_ * skew_;
            }
            RapidityPair RapidityPair::boost(double rapidity) const {
                return (*this) * RapidityPair(std::cosh(rapidity), std::sinh(rapidity));
            }
            bool RapidityPair::within(const RapidityPair& other, double eps) const {
                return std::fabs(shift_ - other.shift_) <= eps
                    && std::fabs(skew_ - other.skew_) <= eps;
            }
            RapidityPair operator+(const RapidityPair& left, const RapidityPair& right) {
                return RapidityPair(left.shift() + right.shift(), left.skew() + right.skew());
            }
            RapidityPair operator-(const RapidityPair& left, const RapidityPair& right) {
                return RapidityPair(left.shift() - right.shift(), left.skew() - right.skew());
            }
            RapidityPair operator*(const RapidityPair& left, const RapidityPair& right) {
                return RapidityPair(left.shift() * right.shift() + left.skew() * right.skew(),
                                    left.shift() * right.skew() + right.shift() * left.skew());
            }
            RapidityPair operator/(const RapidityPair& left, const RapidityPair& right) {
                double g = right.shift() * right.shift() - right.skew() * right.skew();
                if (g == 0.0) throw RapidityError("divisor has zero gauge");
                return RapidityPair((left.shift() * right.shift() - left.skew() * right.skew()) / g,
                                    (right.shift() * left.skew() - left.shift() * right.skew()) / g);
            }
            """,
            """
            RapidityPair::RapidityPair(double shift, double skew) : shift_(shift), skew_(skew) {}
            double RapidityPair::shift() const { return shift_; }
            double RapidityPair::skew() const { return skew_; }
            RapidityPair RapidityPair::square() const {
                return (*this) * (*this);
            }
            double RapidityPair::gauge() const {
                return shift_ * shift_ - skew_ * skew_;
            }
            RapidityPair RapidityPair::boost(double rapidity) const {
                return (*this) * RapidityPair(std::cosh(rapidity), std::sinh(rapidity));
            }
            bool RapidityPair::within(const RapidityPair& other, double eps) const {
                return std::fabs(shift_ - other.shift_) <= eps
                    && std::fabs(skew_ - other.skew_) <= eps;
            }
            RapidityPair operator+(const RapidityPair& left, const RapidityPair& right) {
                return RapidityPair(left.shift() + right.shift(), left.skew() + right.skew());
            }
            RapidityPair operator-(const RapidityPair& left, const RapidityPair& right) {
                return RapidityPair(left.shift() - right.shift(), left.skew() - right.skew());
            }
            RapidityPair operator*(const RapidityPair& left, const RapidityPair& right) {
                return RapidityPair(left.shift() * right.shift() - left.skew() * right.skew(),
                                    left.shift() * right.skew() + right.shift() * left.skew());
            }
            RapidityPair operator/(const RapidityPair& left, const RapidityPair& right) {
                double g = right.shift() * right.shift() - right.skew() * right.skew();
                if (g == 0.0) throw RapidityError("divisor has zero gauge");
                return RapidityPair((left.shift() * right.shift() - left.skew() * right.skew()) / g,
                                    (right.shift() * left.skew() - left.shift() * right.skew()) / g);
            }
            """,
            """
            RapidityPair a(2.0, 1.0);
            RapidityPair b(1.0, 0.5);
            RapidityPair p = a * b;
            if (std::fabs(p.shift() - 2.5) > 1e-9 || std::fabs(p.skew() - 2.0) > 1e-9) return 1;
            RapidityPair sq = a.square();
            if (std::fabs(sq.shift() - 5.0) > 1e-9 || std::fabs(sq.skew() - 4.0) > 1e-9) return 2;
            RapidityPair q = a / b;
            if (std::fabs(q.shift() - 2.0) > 1e-9 || std::fabs(q.skew()) > 1e-9) return 3;
            if (!a.within(RapidityPair(2.0, 1.0 + 1e-12), 1e-9)) return 4;
            RapidityPair s = a + b;
            if (std::fabs(s.shift() - 3.0) > 1e-9 || std::fabs(s.skew() - 1.5) > 1e-9) return 5;
            return 0;
            """,
            """
            RapidityPair a(3.0, 2.0);
            RapidityPair sq = a.square();
            RapidityPair manual = a * a;
            if (!sq.within(manual, 1e-12)) return 1;
            RapidityPair boosted = a.boost(1.0);
            if (std::fabs(boosted.gauge() - a.gauge()) > 1e-9) return 2;
            bool threw = false;
            try { RapidityPair edge(1.0, 1.0); a / edge; } catch (const RapidityError&) { threw = true; }
            if (!threw) return 3;
            RapidityPair two = a.boost(0.5).boost(0.5);
            RapidityPair one = a.boost(1.0);
            if (!two.within(one, 1e-9)) return 4;
            if (a.within(RapidityPair(3.0 + 1e-6, 2.0), 1e-9)) return 5;
            RapidityPair d = a - RapidityPair(1.0, 1.0);
            if (std::fabs(d.shift() - 2.0) > 1e-9 || std::fabs(d.skew() - 1.0) > 1e-9) return 6;
            threw = false;
            try { RapidityPair edge(0.0, 0.0); a / edge; } catch (const RapidityError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            "free-operator gauge algebra with member square, boost composition, and member tolerance",
            "std::complex, <complex>, or the minus-sign product table; do not use trigonometric helpers for the boost",
            "square equals self-product, boost preserves gauge and composes, division by zero-gauge pairs including the zero pair",
            "free functions over gauge pairs with composition invariants in a paired .h/.cpp API",
            "hyperbolic gauge-pair value type",
        ),
        c(
            "f26cpx-antenna-feed-null",
            "Antenna feed null",
            "feed_null",
            """
            class NullError : public std::domain_error {
            public:
                explicit NullError(const std::string& message) : std::domain_error(message) {}
            };
            class NullPair {
            public:
                NullPair(double lobe, double null);
                double lobe() const;
                double null() const;
                NullPair operator+(const NullPair& other) const;
                NullPair operator-(const NullPair& other) const;
                NullPair operator*(const NullPair& other) const;
                NullPair operator/(const NullPair& other) const;
                NullPair mirror() const;
                double gauge() const;
                NullPair spread() const;
            };
            """,
            """
            class NullError : public std::domain_error {
            public:
                explicit NullError(const std::string& message) : std::domain_error(message) {}
            };
            class NullPair {
            public:
                NullPair(double lobe, double null);
                double lobe() const;
                double null() const;
                NullPair operator+(const NullPair& other) const;
                NullPair operator-(const NullPair& other) const;
                NullPair operator*(const NullPair& other) const;
                NullPair operator/(const NullPair& other) const;
                NullPair mirror() const;
                double gauge() const;
                NullPair spread() const;
            private:
                double lobe_;
                double null_;
            };
            """,
            """
            NullPair::NullPair(double lobe, double null) : lobe_(lobe), null_(null) {}
            double NullPair::lobe() const { return lobe_; }
            double NullPair::null() const { return null_; }
            NullPair NullPair::operator+(const NullPair& other) const {
                return NullPair(lobe_ + other.lobe_, null_ + other.null_);
            }
            NullPair NullPair::operator-(const NullPair& other) const {
                return NullPair(lobe_ - other.lobe_, null_ - other.null_);
            }
            NullPair NullPair::operator*(const NullPair& other) const {
                return NullPair(lobe_ * other.lobe_ + null_ * other.null_,
                                lobe_ * other.null_ + other.lobe_ * null_);
            }
            NullPair NullPair::operator/(const NullPair& other) const {
                double g = other.lobe_ * other.lobe_ - other.null_ * other.null_;
                if (g == 0.0) throw NullError("divisor has zero gauge");
                return NullPair((lobe_ * other.lobe_ - null_ * other.null_) / g,
                                (other.lobe_ * null_ - lobe_ * other.null_) / g);
            }
            NullPair NullPair::mirror() const {
                return NullPair(lobe_, -null_);
            }
            double NullPair::gauge() const {
                return lobe_ * lobe_ - null_ * null_;
            }
            NullPair NullPair::spread() const {
                double lifted = std::exp(lobe_);
                return NullPair(lifted * std::cosh(null_), lifted * std::sinh(null_));
            }
            """,
            """
            NullPair::NullPair(double lobe, double null) : lobe_(lobe), null_(null) {}
            double NullPair::lobe() const { return lobe_; }
            double NullPair::null() const { return null_; }
            NullPair NullPair::operator+(const NullPair& other) const {
                return NullPair(lobe_ + other.lobe_, null_ + other.null_);
            }
            NullPair NullPair::operator-(const NullPair& other) const {
                return NullPair(lobe_ - other.lobe_, null_ - other.null_);
            }
            NullPair NullPair::operator*(const NullPair& other) const {
                return NullPair(lobe_ * other.lobe_ - null_ * other.null_,
                                lobe_ * other.null_ + other.lobe_ * null_);
            }
            NullPair NullPair::operator/(const NullPair& other) const {
                double g = other.lobe_ * other.lobe_ - other.null_ * other.null_;
                if (g == 0.0) throw NullError("divisor has zero gauge");
                return NullPair((lobe_ * other.lobe_ - null_ * other.null_) / g,
                                (other.lobe_ * null_ - lobe_ * other.null_) / g);
            }
            NullPair NullPair::mirror() const {
                return NullPair(lobe_, -null_);
            }
            double NullPair::gauge() const {
                return lobe_ * lobe_ - null_ * null_;
            }
            NullPair NullPair::spread() const {
                double lifted = std::exp(lobe_);
                return NullPair(lifted * std::cosh(null_), lifted * std::sinh(null_));
            }
            """,
            """
            NullPair a(2.0, 0.5);
            NullPair b(1.0, 0.25);
            NullPair p = a * b;
            if (std::fabs(p.lobe() - 2.125) > 1e-9 || std::fabs(p.null() - 1.0) > 1e-9) return 1;
            NullPair e = a.spread();
            if (std::fabs(e.gauge() - std::exp(4.0)) > 1e-6) return 2;
            NullPair m = a.mirror();
            if (std::fabs(m.lobe() - 2.0) > 1e-9 || std::fabs(m.null() + 0.5) > 1e-9) return 3;
            NullPair q = a / b;
            if (std::fabs(q.lobe() - 2.0) > 1e-9 || std::fabs(q.null()) > 1e-9) return 4;
            if (std::fabs(a.gauge() - 3.75) > 1e-9) return 5;
            return 0;
            """,
            """
            NullPair a(1.0, 0.5);
            NullPair hom = NullPair(0.5, 0.25).spread() * NullPair(0.5, 0.25).spread();
            NullPair direct = NullPair(1.0, 0.5).spread();
            if (std::fabs(hom.lobe() - direct.lobe()) > 1e-9 || std::fabs(hom.null() - direct.null()) > 1e-9) return 1;
            NullPair twice = a.mirror().mirror();
            if (std::fabs(twice.lobe() - 1.0) > 1e-9 || std::fabs(twice.null() - 0.5) > 1e-9) return 2;
            bool threw = false;
            try { NullPair edge(1.0, 1.0); a / edge; } catch (const NullError&) { threw = true; }
            if (!threw) return 3;
            NullPair z = a * a.mirror();
            if (std::fabs(z.lobe() - 0.75) > 1e-9 || std::fabs(z.null()) > 1e-9) return 4;
            NullPair s = a + NullPair(0.25, 0.25);
            if (std::fabs(s.lobe() - 1.25) > 1e-9 || std::fabs(s.null() - 0.75) > 1e-9) return 5;
            NullPair d = a - NullPair(0.25, 0.25);
            if (std::fabs(d.lobe() - 0.75) > 1e-9 || std::fabs(d.null() - 0.25) > 1e-9) return 6;
            NullPair p = a * a;
            if (std::fabs(p.lobe() - 1.25) > 1e-9 || std::fabs(p.null() - 1.0) > 1e-9) return 7;
            return 0;
            """,
            "gauge algebra with an exponential spread helper and a mirror involution that is its own inverse",
            "std::complex, <complex>, or the minus-sign product table; do not use trigonometric helpers inside spread",
            "the spread homomorphism over addition, double-mirror identity, the z-times-mirror gauge identity, and zero-gauge division rejection",
            "homomorphism property of the exponential helper as the hidden oracle in a paired .h/.cpp API",
            "hyperbolic gauge-pair value type",
        ),
        c(
            "f26cpx-glider-shear-window",
            "Glider shear window",
            "shear_window",
            """
            class ShearError : public std::domain_error {
            public:
                explicit ShearError(const std::string& message) : std::domain_error(message) {}
            };
            class ShearPair {
            public:
                ShearPair(double lift, double sink);
                double lift() const;
                double sink() const;
                ShearPair operator+(const ShearPair& other) const;
                ShearPair operator-(const ShearPair& other) const;
                ShearPair operator*(const ShearPair& other) const;
                ShearPair operator/(const ShearPair& other) const;
                ShearPair mirror() const;
                double gauge() const;
                ShearPair boost(double rapidity) const;
                std::string render() const;
            };
            """,
            """
            class ShearError : public std::domain_error {
            public:
                explicit ShearError(const std::string& message) : std::domain_error(message) {}
            };
            class ShearPair {
            public:
                ShearPair(double lift, double sink);
                double lift() const;
                double sink() const;
                ShearPair operator+(const ShearPair& other) const;
                ShearPair operator-(const ShearPair& other) const;
                ShearPair operator*(const ShearPair& other) const;
                ShearPair operator/(const ShearPair& other) const;
                ShearPair mirror() const;
                double gauge() const;
                ShearPair boost(double rapidity) const;
                std::string render() const;
            private:
                double lift_;
                double sink_;
            };
            """,
            """
            ShearPair::ShearPair(double lift, double sink) : lift_(lift), sink_(sink) {}
            double ShearPair::lift() const { return lift_; }
            double ShearPair::sink() const { return sink_; }
            ShearPair ShearPair::operator+(const ShearPair& other) const {
                return ShearPair(lift_ + other.lift_, sink_ + other.sink_);
            }
            ShearPair ShearPair::operator-(const ShearPair& other) const {
                return ShearPair(lift_ - other.lift_, sink_ - other.sink_);
            }
            ShearPair ShearPair::operator*(const ShearPair& other) const {
                return ShearPair(lift_ * other.lift_ + sink_ * other.sink_,
                                 lift_ * other.sink_ + other.lift_ * sink_);
            }
            ShearPair ShearPair::operator/(const ShearPair& other) const {
                double g = other.lift_ * other.lift_ - other.sink_ * other.sink_;
                if (g == 0.0) throw ShearError("divisor has zero gauge");
                return ShearPair((lift_ * other.lift_ - sink_ * other.sink_) / g,
                                 (other.lift_ * sink_ - lift_ * other.sink_) / g);
            }
            ShearPair ShearPair::mirror() const {
                return ShearPair(lift_, -sink_);
            }
            double ShearPair::gauge() const {
                return lift_ * lift_ - sink_ * sink_;
            }
            ShearPair ShearPair::boost(double rapidity) const {
                return (*this) * ShearPair(std::cosh(rapidity), std::sinh(rapidity));
            }
            std::string ShearPair::render() const {
                std::ostringstream out;
                out << "lift=" << std::fixed << std::setprecision(6) << lift_ << ";sink=" << sink_;
                return out.str();
            }
            """,
            """
            ShearPair::ShearPair(double lift, double sink) : lift_(lift), sink_(sink) {}
            double ShearPair::lift() const { return lift_; }
            double ShearPair::sink() const { return sink_; }
            ShearPair ShearPair::operator+(const ShearPair& other) const {
                return ShearPair(lift_ + other.lift_, sink_ + other.sink_);
            }
            ShearPair ShearPair::operator-(const ShearPair& other) const {
                return ShearPair(lift_ - other.lift_, sink_ - other.sink_);
            }
            ShearPair ShearPair::operator*(const ShearPair& other) const {
                return ShearPair(lift_ * other.lift_ - sink_ * other.sink_,
                                 lift_ * other.sink_ + other.lift_ * sink_);
            }
            ShearPair ShearPair::operator/(const ShearPair& other) const {
                double g = other.lift_ * other.lift_ - other.sink_ * other.sink_;
                if (g == 0.0) throw ShearError("divisor has zero gauge");
                return ShearPair((lift_ * other.lift_ - sink_ * other.sink_) / g,
                                 (other.lift_ * sink_ - lift_ * other.sink_) / g);
            }
            ShearPair ShearPair::mirror() const {
                return ShearPair(lift_, -sink_);
            }
            double ShearPair::gauge() const {
                return lift_ * lift_ - sink_ * sink_;
            }
            ShearPair ShearPair::boost(double rapidity) const {
                return (*this) * ShearPair(std::cosh(rapidity), std::sinh(rapidity));
            }
            std::string ShearPair::render() const {
                std::ostringstream out;
                out << "lift=" << std::fixed << std::setprecision(6) << lift_ << ";sink=" << sink_;
                return out.str();
            }
            """,
            """
            ShearPair a(3.0, 2.0);
            ShearPair b(2.0, 1.0);
            ShearPair p = a * b;
            if (std::fabs(p.lift() - 8.0) > 1e-9 || std::fabs(p.sink() - 7.0) > 1e-9) return 1;
            ShearPair q = a / b;
            if (std::fabs(q.lift() - 4.0 / 3.0) > 1e-9 || std::fabs(q.sink() - 1.0 / 3.0) > 1e-9) return 2;
            if (std::fabs(a.gauge() - 5.0) > 1e-9) return 3;
            ShearPair bs = a.boost(0.0);
            if (std::fabs(bs.lift() - 3.0) > 1e-9 || std::fabs(bs.sink() - 2.0) > 1e-9) return 4;
            if (a.render() != "lift=3.000000;sink=2.000000") return 5;
            return 0;
            """,
            """
            ShearPair a(2.0, 1.0);
            ShearPair z = a * a.mirror();
            if (std::fabs(z.lift() - 3.0) > 1e-9 || std::fabs(z.sink()) > 1e-9) return 1;
            ShearPair two = a.boost(0.25).boost(0.35);
            ShearPair one = a.boost(0.6);
            if (std::fabs(two.lift() - one.lift()) > 1e-9 || std::fabs(two.sink() - one.sink()) > 1e-9) return 2;
            bool threw = false;
            try { ShearPair edge(1.0, 1.0); a / edge; } catch (const ShearError&) { threw = true; }
            if (!threw) return 3;
            ShearPair m = a.mirror();
            if (m.render() != "lift=2.000000;sink=-1.000000") return 4;
            ShearPair s = a + ShearPair(1.0, 1.0);
            if (std::fabs(s.gauge() - 5.0) > 1e-9) return 5;
            ShearPair d = a - ShearPair(0.5, 0.5);
            if (std::fabs(d.lift() - 1.5) > 1e-9 || std::fabs(d.sink() - 0.5) > 1e-9) return 6;
            threw = false;
            try { ShearPair edge(2.0, -2.0); a / edge; } catch (const ShearError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            "combined boost composition and exact readout over one owned gauge pair",
            "std::complex, <complex>, or the minus-sign product table; do not truncate the readout precision",
            "boost composition, the z-times-mirror gauge identity, negative-component rendering, and zero-gauge division rejection",
            "formatting plus boost composition on one owned pair in a paired .h/.cpp API",
            "hyperbolic gauge-pair value type",
        ),
        c(
            "f26cpx-rocket-burn-split",
            "Rocket burn split",
            "burn_split",
            """
            class BurnError : public std::domain_error {
            public:
                explicit BurnError(const std::string& message) : std::domain_error(message) {}
            };
            class BurnSplit {
            public:
                BurnSplit(double impulse, double sideward);
                double impulse() const;
                double sideward() const;
                BurnSplit mirror() const;
                double gauge() const;
                BurnSplit boost(double rapidity) const;
            };
            BurnSplit operator+(const BurnSplit& left, const BurnSplit& right);
            BurnSplit operator-(const BurnSplit& left, const BurnSplit& right);
            BurnSplit operator*(const BurnSplit& left, const BurnSplit& right);
            BurnSplit operator/(const BurnSplit& left, const BurnSplit& right);
            bool nearly_equal(const BurnSplit& left, const BurnSplit& right, double eps);
            """,
            """
            class BurnError : public std::domain_error {
            public:
                explicit BurnError(const std::string& message) : std::domain_error(message) {}
            };
            class BurnSplit {
            public:
                BurnSplit(double impulse, double sideward);
                double impulse() const;
                double sideward() const;
                BurnSplit mirror() const;
                double gauge() const;
                BurnSplit boost(double rapidity) const;
            private:
                double impulse_;
                double sideward_;
            };
            BurnSplit operator+(const BurnSplit& left, const BurnSplit& right);
            BurnSplit operator-(const BurnSplit& left, const BurnSplit& right);
            BurnSplit operator*(const BurnSplit& left, const BurnSplit& right);
            BurnSplit operator/(const BurnSplit& left, const BurnSplit& right);
            bool nearly_equal(const BurnSplit& left, const BurnSplit& right, double eps);
            """,
            """
            BurnSplit::BurnSplit(double impulse, double sideward) : impulse_(impulse), sideward_(sideward) {}
            double BurnSplit::impulse() const { return impulse_; }
            double BurnSplit::sideward() const { return sideward_; }
            BurnSplit BurnSplit::mirror() const {
                return BurnSplit(impulse_, -sideward_);
            }
            double BurnSplit::gauge() const {
                return impulse_ * impulse_ - sideward_ * sideward_;
            }
            BurnSplit BurnSplit::boost(double rapidity) const {
                return (*this) * BurnSplit(std::cosh(rapidity), std::sinh(rapidity));
            }
            BurnSplit operator+(const BurnSplit& left, const BurnSplit& right) {
                return BurnSplit(left.impulse() + right.impulse(), left.sideward() + right.sideward());
            }
            BurnSplit operator-(const BurnSplit& left, const BurnSplit& right) {
                return BurnSplit(left.impulse() - right.impulse(), left.sideward() - right.sideward());
            }
            BurnSplit operator*(const BurnSplit& left, const BurnSplit& right) {
                return BurnSplit(left.impulse() * right.impulse() + left.sideward() * right.sideward(),
                                 left.impulse() * right.sideward() + right.impulse() * left.sideward());
            }
            BurnSplit operator/(const BurnSplit& left, const BurnSplit& right) {
                double g = right.impulse() * right.impulse() - right.sideward() * right.sideward();
                if (g == 0.0) throw BurnError("divisor has zero gauge");
                return BurnSplit((left.impulse() * right.impulse() - left.sideward() * right.sideward()) / g,
                                 (right.impulse() * left.sideward() - left.impulse() * right.sideward()) / g);
            }
            bool nearly_equal(const BurnSplit& left, const BurnSplit& right, double eps) {
                return std::fabs(left.impulse() - right.impulse()) <= eps
                    && std::fabs(left.sideward() - right.sideward()) <= eps;
            }
            """,
            """
            BurnSplit::BurnSplit(double impulse, double sideward) : impulse_(impulse), sideward_(sideward) {}
            double BurnSplit::impulse() const { return impulse_; }
            double BurnSplit::sideward() const { return sideward_; }
            BurnSplit BurnSplit::mirror() const {
                return BurnSplit(impulse_, -sideward_);
            }
            double BurnSplit::gauge() const {
                return impulse_ * impulse_ - sideward_ * sideward_;
            }
            BurnSplit BurnSplit::boost(double rapidity) const {
                return (*this) * BurnSplit(std::cosh(rapidity), std::sinh(rapidity));
            }
            BurnSplit operator+(const BurnSplit& left, const BurnSplit& right) {
                return BurnSplit(left.impulse() + right.impulse(), left.sideward() + right.sideward());
            }
            BurnSplit operator-(const BurnSplit& left, const BurnSplit& right) {
                return BurnSplit(left.impulse() - right.impulse(), left.sideward() - right.sideward());
            }
            BurnSplit operator*(const BurnSplit& left, const BurnSplit& right) {
                return BurnSplit(left.impulse() * right.impulse() - left.sideward() * right.sideward(),
                                 left.impulse() * right.sideward() + right.impulse() * left.sideward());
            }
            BurnSplit operator/(const BurnSplit& left, const BurnSplit& right) {
                double g = right.impulse() * right.impulse() - right.sideward() * right.sideward();
                if (g == 0.0) throw BurnError("divisor has zero gauge");
                return BurnSplit((left.impulse() * right.impulse() - left.sideward() * right.sideward()) / g,
                                 (right.impulse() * left.sideward() - left.impulse() * right.sideward()) / g);
            }
            bool nearly_equal(const BurnSplit& left, const BurnSplit& right, double eps) {
                return std::fabs(left.impulse() - right.impulse()) <= eps
                    && std::fabs(left.sideward() - right.sideward()) <= eps;
            }
            """,
            """
            BurnSplit a(4.0, 2.0);
            BurnSplit b(2.0, 1.0);
            BurnSplit p = a * b;
            if (std::fabs(p.impulse() - 10.0) > 1e-9 || std::fabs(p.sideward() - 8.0) > 1e-9) return 1;
            BurnSplit q = a / b;
            if (std::fabs(q.impulse() - 2.0) > 1e-9 || std::fabs(q.sideward()) > 1e-9) return 2;
            if (std::fabs(a.gauge() - 12.0) > 1e-9) return 3;
            if (!nearly_equal(a, BurnSplit(4.0 + 1e-12, 2.0), 1e-9)) return 4;
            BurnSplit s = a + b;
            if (std::fabs(s.impulse() - 6.0) > 1e-9 || std::fabs(s.sideward() - 3.0) > 1e-9) return 5;
            return 0;
            """,
            """
            BurnSplit a(3.0, 1.0);
            BurnSplit b(2.0, 0.5);
            BurnSplit cc(1.5, 0.25);
            BurnSplit lhs = (a / b) * cc;
            BurnSplit rhs = (a * cc) / b;
            if (!nearly_equal(lhs, rhs, 1e-9)) return 1;
            bool threw = false;
            try { BurnSplit edge(1.0, 1.0); a / edge; } catch (const BurnError&) { threw = true; }
            if (!threw) return 2;
            BurnSplit zero_boost = a.boost(0.0);
            if (!nearly_equal(zero_boost, a, 1e-12)) return 3;
            BurnSplit z = a * a.mirror();
            if (std::fabs(z.impulse() - 8.0) > 1e-9 || std::fabs(z.sideward()) > 1e-9) return 4;
            BurnSplit boosted = a.boost(0.75);
            if (std::fabs(boosted.gauge() - a.gauge()) > 1e-9) return 5;
            BurnSplit d = a - b;
            if (std::fabs(d.impulse() - 1.0) > 1e-9 || std::fabs(d.sideward() - 0.5) > 1e-9) return 6;
            if (nearly_equal(a, BurnSplit(3.0, 1.0 + 1e-6), 1e-9)) return 7;
            return 0;
            """,
            "free-operator gauge algebra with a distributive-law hidden oracle over division and multiplication",
            "std::complex, <complex>, or the minus-sign product table; do not use trigonometric helpers for the boost",
            "division distributing over multiplication, boost gauge preservation and zero-rapidity identity, and zero-gauge division rejection",
            "distributive-law oracle over a gauge algebra in a paired .h/.cpp API",
            "hyperbolic gauge-pair value type",
        ),
        c(
            "f26cpx-recipe-scaler-ratio",
            "Recipe scaler ratio",
            "recipe_scaler",
            """
            class ScalerError : public std::domain_error {
            public:
                explicit ScalerError(const std::string& message) : std::domain_error(message) {}
            };
            class Scaler {
            public:
                Scaler(long num, long den);
                long num() const;
                long den() const;
                Scaler operator+(const Scaler& other) const;
                Scaler operator-(const Scaler& other) const;
                Scaler operator*(const Scaler& other) const;
                Scaler operator/(const Scaler& other) const;
                bool operator==(const Scaler& other) const;
                bool operator!=(const Scaler& other) const;
                double to_double() const;
                std::string render() const;
            };
            """,
            """
            class ScalerError : public std::domain_error {
            public:
                explicit ScalerError(const std::string& message) : std::domain_error(message) {}
            };
            class Scaler {
            public:
                Scaler(long num, long den);
                long num() const;
                long den() const;
                Scaler operator+(const Scaler& other) const;
                Scaler operator-(const Scaler& other) const;
                Scaler operator*(const Scaler& other) const;
                Scaler operator/(const Scaler& other) const;
                bool operator==(const Scaler& other) const;
                bool operator!=(const Scaler& other) const;
                double to_double() const;
                std::string render() const;
            private:
                long num_;
                long den_;
            };
            """,
            """
            Scaler::Scaler(long num, long den) {
                if (den == 0) throw ScalerError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long Scaler::num() const { return num_; }
            long Scaler::den() const { return den_; }
            Scaler Scaler::operator+(const Scaler& other) const {
                return Scaler(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            Scaler Scaler::operator-(const Scaler& other) const {
                return Scaler(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            Scaler Scaler::operator*(const Scaler& other) const {
                return Scaler(num_ * other.num_, den_ * other.den_);
            }
            Scaler Scaler::operator/(const Scaler& other) const {
                if (other.num_ == 0) throw ScalerError("division by a zero ratio");
                return Scaler(num_ * other.den_, den_ * other.num_);
            }
            bool Scaler::operator==(const Scaler& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            bool Scaler::operator!=(const Scaler& other) const {
                return !(*this == other);
            }
            double Scaler::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            std::string Scaler::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            """,
            """
            Scaler::Scaler(long num, long den) {
                if (den == 0) throw ScalerError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long Scaler::num() const { return num_; }
            long Scaler::den() const { return den_; }
            Scaler Scaler::operator+(const Scaler& other) const {
                return Scaler(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            Scaler Scaler::operator-(const Scaler& other) const {
                return Scaler(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            Scaler Scaler::operator*(const Scaler& other) const {
                return Scaler(num_ * other.num_, den_ * other.den_);
            }
            Scaler Scaler::operator/(const Scaler& other) const {
                if (other.num_ == 0) throw ScalerError("division by a zero ratio");
                return Scaler(num_ * other.den_, den_ * other.num_);
            }
            bool Scaler::operator==(const Scaler& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            bool Scaler::operator!=(const Scaler& other) const {
                return !(*this == other);
            }
            double Scaler::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            std::string Scaler::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            """,
            """
            Scaler a(1, 2);
            Scaler b(1, 3);
            Scaler s = a + b;
            if (s.num() != 5 || s.den() != 6) return 1;
            Scaler p = a * b;
            if (p.num() != 1 || p.den() != 6) return 2;
            Scaler q = a / b;
            if (q.num() != 3 || q.den() != 2) return 3;
            if (!(a == Scaler(2, 4))) return 4;
            if (a != Scaler(1, 2)) return 5;
            if (std::fabs(a.to_double() - 0.5) > 1e-12) return 6;
            if (Scaler(-3, 6).render() != "-1/2") return 7;
            Scaler d = a - b;
            if (d.num() != 1 || d.den() != 6) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { Scaler(1, 0); } catch (const ScalerError&) { threw = true; }
            if (!threw) return 1;
            Scaler neg(3, -4);
            if (neg.num() != -3 || neg.den() != 4) return 2;
            Scaler both_neg(-3, -4);
            if (both_neg.num() != 3 || both_neg.den() != 4) return 3;
            Scaler zero(0, 7);
            if (zero.num() != 0 || zero.den() != 1) return 4;
            threw = false;
            try { Scaler(1, 2) / Scaler(0, 5); } catch (const ScalerError&) { threw = true; }
            if (!threw) return 5;
            if (!(Scaler(10, 15) == Scaler(2, 3))) return 6;
            if (Scaler(5, 10).render() != "1/2") return 7;
            if (std::fabs(Scaler(7, 8).to_double() - 0.875) > 1e-12) return 8;
            Scaler big(1000000, 3000000);
            if (big.num() != 1 || big.den() != 3) return 9;
            return 0;
            """,
            "constructor-time gcd reduction and sign normalization giving exact representation-blind equality",
            "any floating-point internal representation or double-based equality; do not skip reduction or sign normalization",
            "unreduced and negative-denominator construction, zero normalization, zero-denominator and zero-divisor rejection, and reduced render bytes",
            "exact representation-blind equality with no tolerance in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-gearbox-mesh-ratio",
            "Gearbox mesh ratio",
            "gearbox_mesh",
            """
            class MeshError : public std::domain_error {
            public:
                explicit MeshError(const std::string& message) : std::domain_error(message) {}
            };
            class MeshRatio {
            public:
                MeshRatio(long num, long den);
                long num() const;
                long den() const;
                MeshRatio reciprocal() const;
                double to_double() const;
            };
            MeshRatio operator+(const MeshRatio& left, const MeshRatio& right);
            MeshRatio operator-(const MeshRatio& left, const MeshRatio& right);
            MeshRatio operator*(const MeshRatio& left, const MeshRatio& right);
            MeshRatio operator/(const MeshRatio& left, const MeshRatio& right);
            bool operator==(const MeshRatio& left, const MeshRatio& right);
            bool operator<(const MeshRatio& left, const MeshRatio& right);
            """,
            """
            class MeshError : public std::domain_error {
            public:
                explicit MeshError(const std::string& message) : std::domain_error(message) {}
            };
            class MeshRatio {
            public:
                MeshRatio(long num, long den);
                long num() const;
                long den() const;
                MeshRatio reciprocal() const;
                double to_double() const;
            private:
                long num_;
                long den_;
            };
            MeshRatio operator+(const MeshRatio& left, const MeshRatio& right);
            MeshRatio operator-(const MeshRatio& left, const MeshRatio& right);
            MeshRatio operator*(const MeshRatio& left, const MeshRatio& right);
            MeshRatio operator/(const MeshRatio& left, const MeshRatio& right);
            bool operator==(const MeshRatio& left, const MeshRatio& right);
            bool operator<(const MeshRatio& left, const MeshRatio& right);
            """,
            """
            MeshRatio::MeshRatio(long num, long den) {
                if (den == 0) throw MeshError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long MeshRatio::num() const { return num_; }
            long MeshRatio::den() const { return den_; }
            MeshRatio MeshRatio::reciprocal() const {
                if (num_ == 0) throw MeshError("reciprocal of a zero ratio");
                return MeshRatio(den_, num_);
            }
            double MeshRatio::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            MeshRatio operator+(const MeshRatio& left, const MeshRatio& right) {
                return MeshRatio(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            MeshRatio operator-(const MeshRatio& left, const MeshRatio& right) {
                return MeshRatio(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            MeshRatio operator*(const MeshRatio& left, const MeshRatio& right) {
                return MeshRatio(left.num() * right.num(), left.den() * right.den());
            }
            MeshRatio operator/(const MeshRatio& left, const MeshRatio& right) {
                if (right.num() == 0) throw MeshError("division by a zero ratio");
                return MeshRatio(left.num() * right.den(), left.den() * right.num());
            }
            bool operator==(const MeshRatio& left, const MeshRatio& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            bool operator<(const MeshRatio& left, const MeshRatio& right) {
                return left.num() * right.den() < right.num() * left.den();
            }
            """,
            """
            MeshRatio::MeshRatio(long num, long den) {
                if (den == 0) throw MeshError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long MeshRatio::num() const { return num_; }
            long MeshRatio::den() const { return den_; }
            MeshRatio MeshRatio::reciprocal() const {
                if (num_ == 0) throw MeshError("reciprocal of a zero ratio");
                return MeshRatio(den_, num_);
            }
            double MeshRatio::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            MeshRatio operator+(const MeshRatio& left, const MeshRatio& right) {
                return MeshRatio(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            MeshRatio operator-(const MeshRatio& left, const MeshRatio& right) {
                return MeshRatio(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            MeshRatio operator*(const MeshRatio& left, const MeshRatio& right) {
                return MeshRatio(left.num() * right.num(), left.den() * right.den());
            }
            MeshRatio operator/(const MeshRatio& left, const MeshRatio& right) {
                if (right.num() == 0) throw MeshError("division by a zero ratio");
                return MeshRatio(left.num() * right.den(), left.den() * right.num());
            }
            bool operator==(const MeshRatio& left, const MeshRatio& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            bool operator<(const MeshRatio& left, const MeshRatio& right) {
                return left.num() * right.den() < right.num() * left.den();
            }
            """,
            """
            MeshRatio a(3, 4);
            MeshRatio b(2, 5);
            MeshRatio s = a + b;
            if (s.num() != 23 || s.den() != 20) return 1;
            MeshRatio p = a * b;
            if (p.num() != 3 || p.den() != 10) return 2;
            if (!(MeshRatio(1, 2) < MeshRatio(2, 3))) return 3;
            if (MeshRatio(2, 3) < MeshRatio(1, 2)) return 4;
            MeshRatio r = a.reciprocal();
            if (r.num() != 4 || r.den() != 3) return 5;
            if (!(a == MeshRatio(6, 8))) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { MeshRatio(0, 3).reciprocal(); } catch (const MeshError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { MeshRatio(1, 2) / MeshRatio(0, 1); } catch (const MeshError&) { threw = true; }
            if (!threw) return 2;
            if (!(MeshRatio(-1, 2) < MeshRatio(1, 3))) return 3;
            if (!(MeshRatio(-3, 4) < MeshRatio(-1, 2))) return 4;
            MeshRatio d = MeshRatio(1, 2) - MeshRatio(3, 4);
            if (d.num() != -1 || d.den() != 4) return 5;
            MeshRatio q = MeshRatio(3, 4) / MeshRatio(2, 5);
            if (q.num() != 15 || q.den() != 8) return 6;
            if (std::fabs(MeshRatio(5, 4).to_double() - 1.25) > 1e-12) return 7;
            if (!(MeshRatio(4, 6) == MeshRatio(6, 9))) return 8;
            threw = false;
            try { MeshRatio(5, 0); } catch (const MeshError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "exact cross-multiplied ordering over gcd-normalized integer pairs with reciprocal discipline",
            "any floating-point internal representation or ordering through to_double; do not skip reduction or sign normalization",
            "reciprocal of zero, ordering across sign boundaries, exact cross-multiplication, and zero-denominator rejection",
            "exact ordering operators over owned integer pairs in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-atlas-map-scale",
            "Atlas map scale",
            "atlas_scale",
            """
            class ScaleError : public std::domain_error {
            public:
                explicit ScaleError(const std::string& message) : std::domain_error(message) {}
            };
            class MapScale {
            public:
                MapScale(long num, long den);
                long num() const;
                long den() const;
                MapScale operator+(const MapScale& other) const;
                MapScale operator-(const MapScale& other) const;
                MapScale operator*(const MapScale& other) const;
                MapScale operator/(const MapScale& other) const;
                MapScale pow(unsigned exponent) const;
                bool operator==(const MapScale& other) const;
                bool operator<(const MapScale& other) const;
                std::string render() const;
            };
            """,
            """
            class ScaleError : public std::domain_error {
            public:
                explicit ScaleError(const std::string& message) : std::domain_error(message) {}
            };
            class MapScale {
            public:
                MapScale(long num, long den);
                long num() const;
                long den() const;
                MapScale operator+(const MapScale& other) const;
                MapScale operator-(const MapScale& other) const;
                MapScale operator*(const MapScale& other) const;
                MapScale operator/(const MapScale& other) const;
                MapScale pow(unsigned exponent) const;
                bool operator==(const MapScale& other) const;
                bool operator<(const MapScale& other) const;
                std::string render() const;
            private:
                long num_;
                long den_;
            };
            """,
            """
            MapScale::MapScale(long num, long den) {
                if (den == 0) throw ScaleError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long MapScale::num() const { return num_; }
            long MapScale::den() const { return den_; }
            MapScale MapScale::operator+(const MapScale& other) const {
                return MapScale(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            MapScale MapScale::operator-(const MapScale& other) const {
                return MapScale(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            MapScale MapScale::operator*(const MapScale& other) const {
                return MapScale(num_ * other.num_, den_ * other.den_);
            }
            MapScale MapScale::operator/(const MapScale& other) const {
                if (other.num_ == 0) throw ScaleError("division by a zero ratio");
                return MapScale(num_ * other.den_, den_ * other.num_);
            }
            MapScale MapScale::pow(unsigned exponent) const {
                MapScale result(1, 1);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            bool MapScale::operator==(const MapScale& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            bool MapScale::operator<(const MapScale& other) const {
                return num_ * other.den_ < other.num_ * den_;
            }
            std::string MapScale::render() const {
                std::ostringstream out;
                out << num_ << ":" << den_;
                return out.str();
            }
            """,
            """
            MapScale::MapScale(long num, long den) {
                if (den == 0) throw ScaleError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long MapScale::num() const { return num_; }
            long MapScale::den() const { return den_; }
            MapScale MapScale::operator+(const MapScale& other) const {
                return MapScale(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            MapScale MapScale::operator-(const MapScale& other) const {
                return MapScale(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            MapScale MapScale::operator*(const MapScale& other) const {
                return MapScale(num_ * other.num_, den_ * other.den_);
            }
            MapScale MapScale::operator/(const MapScale& other) const {
                if (other.num_ == 0) throw ScaleError("division by a zero ratio");
                return MapScale(num_ * other.den_, den_ * other.num_);
            }
            MapScale MapScale::pow(unsigned exponent) const {
                MapScale result(1, 1);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            bool MapScale::operator==(const MapScale& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            bool MapScale::operator<(const MapScale& other) const {
                return num_ * other.den_ < other.num_ * den_;
            }
            std::string MapScale::render() const {
                std::ostringstream out;
                out << num_ << ":" << den_;
                return out.str();
            }
            """,
            """
            MapScale a(1, 1000);
            MapScale b(1, 500);
            MapScale s = a + b;
            if (s.num() != 3 || s.den() != 1000) return 1;
            MapScale p = a * b;
            if (p.num() != 1 || p.den() != 500000) return 2;
            MapScale sq = b.pow(2);
            if (sq.num() != 1 || sq.den() != 250000) return 3;
            if (!(a < b)) return 4;
            if (!(a == MapScale(2, 2000))) return 5;
            if (b.render() != "1:500") return 6;
            return 0;
            """,
            """
            MapScale z(5, 10);
            MapScale one = z.pow(0);
            if (one.num() != 1 || one.den() != 1) return 1;
            MapScale cube = MapScale(1, 2).pow(3);
            if (cube.num() != 1 || cube.den() != 8) return 2;
            bool threw = false;
            try { MapScale(1, 0); } catch (const ScaleError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { MapScale(1, 2) / MapScale(0, 3); } catch (const ScaleError&) { threw = true; }
            if (!threw) return 4;
            MapScale neg(-2, 6);
            if (neg.num() != -1 || neg.den() != 3) return 5;
            if (neg.render() != "-1:3") return 6;
            if (!(MapScale(-1, 2) < MapScale(1, 100))) return 7;
            MapScale q = MapScale(3, 4) / MapScale(1, 2);
            if (q.num() != 3 || q.den() != 2) return 8;
            MapScale pw = MapScale(2, 3).pow(2);
            if (pw.num() != 4 || pw.den() != 9) return 9;
            return 0;
            """,
            "integer powers over gcd-normalized exact ratios with a colon-delimited readout",
            "any floating-point internal representation or floating-point accumulation for pow; do not skip reduction or sign normalization",
            "pow(0) identity, powers of reduced negatives, exact ordering, colon render shape, and zero-divisor rejection",
            "integer exponentiation over exact ratios with a distinct readout in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-brew-mixture-share",
            "Brew mixture share",
            "brew_mixture",
            """
            class MixtureError : public std::domain_error {
            public:
                explicit MixtureError(const std::string& message) : std::domain_error(message) {}
            };
            class MixtureShare {
            public:
                MixtureShare(long num, long den);
                long num() const;
                long den() const;
                double to_double() const;
                std::string render() const;
            };
            MixtureShare operator+(const MixtureShare& left, const MixtureShare& right);
            MixtureShare operator-(const MixtureShare& left, const MixtureShare& right);
            MixtureShare operator*(const MixtureShare& left, const MixtureShare& right);
            MixtureShare operator/(const MixtureShare& left, const MixtureShare& right);
            MixtureShare median(const MixtureShare& left, const MixtureShare& right);
            MixtureShare smaller(const MixtureShare& left, const MixtureShare& right);
            MixtureShare larger(const MixtureShare& left, const MixtureShare& right);
            bool operator==(const MixtureShare& left, const MixtureShare& right);
            """,
            """
            class MixtureError : public std::domain_error {
            public:
                explicit MixtureError(const std::string& message) : std::domain_error(message) {}
            };
            class MixtureShare {
            public:
                MixtureShare(long num, long den);
                long num() const;
                long den() const;
                double to_double() const;
                std::string render() const;
            private:
                long num_;
                long den_;
            };
            MixtureShare operator+(const MixtureShare& left, const MixtureShare& right);
            MixtureShare operator-(const MixtureShare& left, const MixtureShare& right);
            MixtureShare operator*(const MixtureShare& left, const MixtureShare& right);
            MixtureShare operator/(const MixtureShare& left, const MixtureShare& right);
            MixtureShare median(const MixtureShare& left, const MixtureShare& right);
            MixtureShare smaller(const MixtureShare& left, const MixtureShare& right);
            MixtureShare larger(const MixtureShare& left, const MixtureShare& right);
            bool operator==(const MixtureShare& left, const MixtureShare& right);
            """,
            """
            MixtureShare::MixtureShare(long num, long den) {
                if (den == 0) throw MixtureError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long MixtureShare::num() const { return num_; }
            long MixtureShare::den() const { return den_; }
            double MixtureShare::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            std::string MixtureShare::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            MixtureShare operator+(const MixtureShare& left, const MixtureShare& right) {
                return MixtureShare(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            MixtureShare operator-(const MixtureShare& left, const MixtureShare& right) {
                return MixtureShare(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            MixtureShare operator*(const MixtureShare& left, const MixtureShare& right) {
                return MixtureShare(left.num() * right.num(), left.den() * right.den());
            }
            MixtureShare operator/(const MixtureShare& left, const MixtureShare& right) {
                if (right.num() == 0) throw MixtureError("division by a zero ratio");
                return MixtureShare(left.num() * right.den(), left.den() * right.num());
            }
            MixtureShare median(const MixtureShare& left, const MixtureShare& right) {
                return (left + right) * MixtureShare(1, 2);
            }
            MixtureShare smaller(const MixtureShare& left, const MixtureShare& right) {
                if (left.num() * right.den() <= right.num() * left.den()) return left;
                return right;
            }
            MixtureShare larger(const MixtureShare& left, const MixtureShare& right) {
                if (left.num() * right.den() >= right.num() * left.den()) return left;
                return right;
            }
            bool operator==(const MixtureShare& left, const MixtureShare& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            """,
            """
            MixtureShare::MixtureShare(long num, long den) {
                if (den == 0) throw MixtureError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long MixtureShare::num() const { return num_; }
            long MixtureShare::den() const { return den_; }
            double MixtureShare::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            std::string MixtureShare::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            MixtureShare operator+(const MixtureShare& left, const MixtureShare& right) {
                return MixtureShare(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            MixtureShare operator-(const MixtureShare& left, const MixtureShare& right) {
                return MixtureShare(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            MixtureShare operator*(const MixtureShare& left, const MixtureShare& right) {
                return MixtureShare(left.num() * right.num(), left.den() * right.den());
            }
            MixtureShare operator/(const MixtureShare& left, const MixtureShare& right) {
                if (right.num() == 0) throw MixtureError("division by a zero ratio");
                return MixtureShare(left.num() * right.den(), left.den() * right.num());
            }
            MixtureShare median(const MixtureShare& left, const MixtureShare& right) {
                return (left + right) * MixtureShare(1, 2);
            }
            MixtureShare smaller(const MixtureShare& left, const MixtureShare& right) {
                if (left.num() * right.den() <= right.num() * left.den()) return left;
                return right;
            }
            MixtureShare larger(const MixtureShare& left, const MixtureShare& right) {
                if (left.num() * right.den() >= right.num() * left.den()) return left;
                return right;
            }
            bool operator==(const MixtureShare& left, const MixtureShare& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            """,
            """
            MixtureShare a(1, 4);
            MixtureShare b(1, 2);
            MixtureShare m = median(a, b);
            if (m.num() != 3 || m.den() != 8) return 1;
            if (!(smaller(a, b) == a)) return 2;
            if (!(larger(a, b) == b)) return 3;
            MixtureShare s = a + b;
            if (s.num() != 3 || s.den() != 4) return 4;
            if (a.render() != "1/4") return 5;
            if (std::fabs(b.to_double() - 0.5) > 1e-12) return 6;
            return 0;
            """,
            """
            if (!(median(MixtureShare(-1, 2), MixtureShare(1, 2)) == MixtureShare(0, 1))) return 1;
            if (!(smaller(MixtureShare(-3, 4), MixtureShare(-1, 2)) == MixtureShare(-3, 4))) return 2;
            if (!(larger(MixtureShare(-3, 4), MixtureShare(-1, 2)) == MixtureShare(-1, 2))) return 3;
            bool threw = false;
            try { MixtureShare(2, 0); } catch (const MixtureError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { MixtureShare(1, 2) / MixtureShare(0, 7); } catch (const MixtureError&) { threw = true; }
            if (!threw) return 5;
            MixtureShare p = MixtureShare(2, 3) * MixtureShare(3, 5);
            if (p.num() != 2 || p.den() != 5) return 6;
            MixtureShare q = MixtureShare(2, 3) / MixtureShare(4, 5);
            if (q.num() != 5 || q.den() != 6) return 7;
            if (MixtureShare(-6, 8).render() != "-3/4") return 8;
            if (!(median(MixtureShare(1, 3), MixtureShare(2, 3)) == MixtureShare(1, 2))) return 9;
            return 0;
            """,
            "named combinator free functions over gcd-normalized exact ratios with exact cross-multiplied selection",
            "any floating-point internal representation or selection through to_double; do not skip reduction or sign normalization",
            "median landing exactly between, smaller/larger across sign boundaries, exact render, and zero-divisor rejection",
            "combinator-style free API over exact ratios in a project-context paired .h/.cpp layout",
            "exact normalized fraction value type",
            project_support=True,
        ),
        c(
            "f26cpx-choir-interval-ratio",
            "Choir interval ratio",
            "choir_interval",
            """
            class IntervalError : public std::domain_error {
            public:
                explicit IntervalError(const std::string& message) : std::domain_error(message) {}
            };
            class IntervalRatio {
            public:
                IntervalRatio(long num, long den);
                long num() const;
                long den() const;
                IntervalRatio operator+(const IntervalRatio& other) const;
                IntervalRatio operator-(const IntervalRatio& other) const;
                IntervalRatio operator*(const IntervalRatio& other) const;
                IntervalRatio operator/(const IntervalRatio& other) const;
                IntervalRatio pow(int exponent) const;
                bool operator==(const IntervalRatio& other) const;
                bool operator<(const IntervalRatio& other) const;
                double to_double() const;
            };
            """,
            """
            class IntervalError : public std::domain_error {
            public:
                explicit IntervalError(const std::string& message) : std::domain_error(message) {}
            };
            class IntervalRatio {
            public:
                IntervalRatio(long num, long den);
                long num() const;
                long den() const;
                IntervalRatio operator+(const IntervalRatio& other) const;
                IntervalRatio operator-(const IntervalRatio& other) const;
                IntervalRatio operator*(const IntervalRatio& other) const;
                IntervalRatio operator/(const IntervalRatio& other) const;
                IntervalRatio pow(int exponent) const;
                bool operator==(const IntervalRatio& other) const;
                bool operator<(const IntervalRatio& other) const;
                double to_double() const;
            private:
                long num_;
                long den_;
            };
            """,
            """
            IntervalRatio::IntervalRatio(long num, long den) {
                if (den == 0) throw IntervalError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long IntervalRatio::num() const { return num_; }
            long IntervalRatio::den() const { return den_; }
            IntervalRatio IntervalRatio::operator+(const IntervalRatio& other) const {
                return IntervalRatio(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            IntervalRatio IntervalRatio::operator-(const IntervalRatio& other) const {
                return IntervalRatio(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            IntervalRatio IntervalRatio::operator*(const IntervalRatio& other) const {
                return IntervalRatio(num_ * other.num_, den_ * other.den_);
            }
            IntervalRatio IntervalRatio::operator/(const IntervalRatio& other) const {
                if (other.num_ == 0) throw IntervalError("division by a zero ratio");
                return IntervalRatio(num_ * other.den_, den_ * other.num_);
            }
            IntervalRatio IntervalRatio::pow(int exponent) const {
                IntervalRatio base(1, 1);
                if (exponent < 0) {
                    if (num_ == 0) throw IntervalError("negative power of a zero ratio");
                    base = IntervalRatio(den_, num_);
                } else {
                    base = *this;
                }
                IntervalRatio result(1, 1);
                long remaining = exponent < 0 ? -static_cast<long>(exponent) : static_cast<long>(exponent);
                for (long i = 0; i < remaining; ++i) result = result * base;
                return result;
            }
            bool IntervalRatio::operator==(const IntervalRatio& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            bool IntervalRatio::operator<(const IntervalRatio& other) const {
                return num_ * other.den_ < other.num_ * den_;
            }
            double IntervalRatio::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            """,
            """
            IntervalRatio::IntervalRatio(long num, long den) {
                if (den == 0) throw IntervalError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long IntervalRatio::num() const { return num_; }
            long IntervalRatio::den() const { return den_; }
            IntervalRatio IntervalRatio::operator+(const IntervalRatio& other) const {
                return IntervalRatio(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            IntervalRatio IntervalRatio::operator-(const IntervalRatio& other) const {
                return IntervalRatio(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            IntervalRatio IntervalRatio::operator*(const IntervalRatio& other) const {
                return IntervalRatio(num_ * other.num_, den_ * other.den_);
            }
            IntervalRatio IntervalRatio::operator/(const IntervalRatio& other) const {
                if (other.num_ == 0) throw IntervalError("division by a zero ratio");
                return IntervalRatio(num_ * other.den_, den_ * other.num_);
            }
            IntervalRatio IntervalRatio::pow(int exponent) const {
                IntervalRatio base(1, 1);
                if (exponent < 0) {
                    if (num_ == 0) throw IntervalError("negative power of a zero ratio");
                    base = IntervalRatio(den_, num_);
                } else {
                    base = *this;
                }
                IntervalRatio result(1, 1);
                long remaining = exponent < 0 ? -static_cast<long>(exponent) : static_cast<long>(exponent);
                for (long i = 0; i < remaining; ++i) result = result * base;
                return result;
            }
            bool IntervalRatio::operator==(const IntervalRatio& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            bool IntervalRatio::operator<(const IntervalRatio& other) const {
                return num_ * other.den_ < other.num_ * den_;
            }
            double IntervalRatio::to_double() const {
                return static_cast<double>(num_) / static_cast<double>(den_);
            }
            """,
            """
            IntervalRatio a(3, 2);
            IntervalRatio b(4, 3);
            IntervalRatio p = a * b;
            if (p.num() != 2 || p.den() != 1) return 1;
            IntervalRatio sq = a.pow(2);
            if (sq.num() != 9 || sq.den() != 4) return 2;
            IntervalRatio inv = a.pow(-1);
            if (inv.num() != 2 || inv.den() != 3) return 3;
            if (!(b < a)) return 4;
            if (!(a == IntervalRatio(6, 4))) return 5;
            if (std::fabs(a.to_double() - 1.5) > 1e-12) return 6;
            return 0;
            """,
            """
            IntervalRatio a(2, 3);
            IntervalRatio neg2 = a.pow(-2);
            if (neg2.num() != 9 || neg2.den() != 4) return 1;
            IntervalRatio one = a.pow(0);
            if (one.num() != 1 || one.den() != 1) return 2;
            bool threw = false;
            try { IntervalRatio(0, 5).pow(-1); } catch (const IntervalError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { IntervalRatio(1, 0); } catch (const IntervalError&) { threw = true; }
            if (!threw) return 4;
            if (!(IntervalRatio(4, 5).pow(-1) < IntervalRatio(3, 2))) return 5;
            IntervalRatio d = IntervalRatio(3, 2) - IntervalRatio(4, 3);
            if (d.num() != 1 || d.den() != 6) return 6;
            IntervalRatio q = IntervalRatio(3, 2) / IntervalRatio(4, 3);
            if (q.num() != 9 || q.den() != 8) return 7;
            if (!(IntervalRatio(-2, 3) == IntervalRatio(4, -6))) return 8;
            threw = false;
            try { IntervalRatio(1, 2) / IntervalRatio(0, 9); } catch (const IntervalError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "signed integer powers with exact reciprocation over gcd-normalized ratios",
            "any floating-point internal representation or rejection of negative exponents; do not skip reduction or sign normalization",
            "negative powers reciprocating exactly, pow(0) identity, negative power of zero rejection, and reciprocal ordering",
            "signed-exponent power law over exact ratios in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-canvas-aspect-ratio",
            "Canvas aspect ratio",
            "canvas_aspect",
            """
            class AspectError : public std::domain_error {
            public:
                explicit AspectError(const std::string& message) : std::domain_error(message) {}
            };
            class AspectRatio {
            public:
                AspectRatio(long num, long den);
                long num() const;
                long den() const;
                bool is_unity() const;
                std::string render() const;
            };
            AspectRatio operator+(const AspectRatio& left, const AspectRatio& right);
            AspectRatio operator-(const AspectRatio& left, const AspectRatio& right);
            AspectRatio operator*(const AspectRatio& left, const AspectRatio& right);
            AspectRatio operator/(const AspectRatio& left, const AspectRatio& right);
            bool operator==(const AspectRatio& left, const AspectRatio& right);
            bool operator<(const AspectRatio& left, const AspectRatio& right);
            """,
            """
            class AspectError : public std::domain_error {
            public:
                explicit AspectError(const std::string& message) : std::domain_error(message) {}
            };
            class AspectRatio {
            public:
                AspectRatio(long num, long den);
                long num() const;
                long den() const;
                bool is_unity() const;
                std::string render() const;
            private:
                long num_;
                long den_;
            };
            AspectRatio operator+(const AspectRatio& left, const AspectRatio& right);
            AspectRatio operator-(const AspectRatio& left, const AspectRatio& right);
            AspectRatio operator*(const AspectRatio& left, const AspectRatio& right);
            AspectRatio operator/(const AspectRatio& left, const AspectRatio& right);
            bool operator==(const AspectRatio& left, const AspectRatio& right);
            bool operator<(const AspectRatio& left, const AspectRatio& right);
            """,
            """
            AspectRatio::AspectRatio(long num, long den) {
                if (den == 0) throw AspectError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long AspectRatio::num() const { return num_; }
            long AspectRatio::den() const { return den_; }
            bool AspectRatio::is_unity() const {
                return num_ == den_;
            }
            std::string AspectRatio::render() const {
                std::ostringstream out;
                out << num_ << ":" << den_;
                return out.str();
            }
            AspectRatio operator+(const AspectRatio& left, const AspectRatio& right) {
                return AspectRatio(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            AspectRatio operator-(const AspectRatio& left, const AspectRatio& right) {
                return AspectRatio(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            AspectRatio operator*(const AspectRatio& left, const AspectRatio& right) {
                return AspectRatio(left.num() * right.num(), left.den() * right.den());
            }
            AspectRatio operator/(const AspectRatio& left, const AspectRatio& right) {
                if (right.num() == 0) throw AspectError("division by a zero ratio");
                return AspectRatio(left.num() * right.den(), left.den() * right.num());
            }
            bool operator==(const AspectRatio& left, const AspectRatio& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            bool operator<(const AspectRatio& left, const AspectRatio& right) {
                return left.num() * right.den() < right.num() * left.den();
            }
            """,
            """
            AspectRatio::AspectRatio(long num, long den) {
                if (den == 0) throw AspectError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long AspectRatio::num() const { return num_; }
            long AspectRatio::den() const { return den_; }
            bool AspectRatio::is_unity() const {
                return num_ == den_;
            }
            std::string AspectRatio::render() const {
                std::ostringstream out;
                out << num_ << ":" << den_;
                return out.str();
            }
            AspectRatio operator+(const AspectRatio& left, const AspectRatio& right) {
                return AspectRatio(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            AspectRatio operator-(const AspectRatio& left, const AspectRatio& right) {
                return AspectRatio(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            AspectRatio operator*(const AspectRatio& left, const AspectRatio& right) {
                return AspectRatio(left.num() * right.num(), left.den() * right.den());
            }
            AspectRatio operator/(const AspectRatio& left, const AspectRatio& right) {
                if (right.num() == 0) throw AspectError("division by a zero ratio");
                return AspectRatio(left.num() * right.den(), left.den() * right.num());
            }
            bool operator==(const AspectRatio& left, const AspectRatio& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            bool operator<(const AspectRatio& left, const AspectRatio& right) {
                return left.num() * right.den() < right.num() * left.den();
            }
            """,
            """
            AspectRatio a(16, 9);
            if (a.is_unity()) return 1;
            AspectRatio u(3, 3);
            if (!u.is_unity()) return 2;
            AspectRatio p = a * AspectRatio(1, 2);
            if (p.num() != 8 || p.den() != 9) return 3;
            if (a.render() != "16:9") return 4;
            if (!(AspectRatio(1, 1) < AspectRatio(4, 3))) return 5;
            AspectRatio s = a + u;
            if (s.num() != 25 || s.den() != 9) return 6;
            return 0;
            """,
            """
            if (!AspectRatio(7, 7).is_unity()) return 1;
            if (AspectRatio(14, 7).is_unity()) return 2;
            bool threw = false;
            try { AspectRatio(1, 0); } catch (const AspectError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { AspectRatio(1, 2) / AspectRatio(0, 4); } catch (const AspectError&) { threw = true; }
            if (!threw) return 4;
            AspectRatio neg(-4, 6);
            if (neg.render() != "-2:3") return 5;
            if (!(AspectRatio(2, 4) == AspectRatio(3, 6))) return 6;
            AspectRatio d = AspectRatio(3, 2) - AspectRatio(1, 2);
            if (!d.is_unity()) return 7;
            AspectRatio q = AspectRatio(9, 4) / AspectRatio(3, 2);
            if (q.num() != 3 || q.den() != 2) return 8;
            if (!(AspectRatio(-1, 2) < AspectRatio(0, 1))) return 9;
            return 0;
            """,
            "unity detection over the normalized reduced form of an exact ratio",
            "any floating-point internal representation or floating-point comparison; do not skip reduction or sign normalization",
            "is_unity only at reduced one-to-one, colon render shape, exact ordering, and zero-divisor rejection",
            "normalized-predicate discipline over exact ratios in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-lottery-odds-share",
            "Lottery odds share",
            "lottery_odds",
            """
            class OddsError : public std::domain_error {
            public:
                explicit OddsError(const std::string& message) : std::domain_error(message) {}
            };
            class OddsShare {
            public:
                OddsShare(long num, long den);
                long num() const;
                long den() const;
                OddsShare operator+(const OddsShare& other) const;
                OddsShare operator-(const OddsShare& other) const;
                OddsShare operator*(const OddsShare& other) const;
                OddsShare operator/(const OddsShare& other) const;
                double to_probability() const;
                bool operator==(const OddsShare& other) const;
                std::string render() const;
            };
            """,
            """
            class OddsError : public std::domain_error {
            public:
                explicit OddsError(const std::string& message) : std::domain_error(message) {}
            };
            class OddsShare {
            public:
                OddsShare(long num, long den);
                long num() const;
                long den() const;
                OddsShare operator+(const OddsShare& other) const;
                OddsShare operator-(const OddsShare& other) const;
                OddsShare operator*(const OddsShare& other) const;
                OddsShare operator/(const OddsShare& other) const;
                double to_probability() const;
                bool operator==(const OddsShare& other) const;
                std::string render() const;
            private:
                long num_;
                long den_;
            };
            """,
            """
            OddsShare::OddsShare(long num, long den) {
                if (den == 0) throw OddsError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long OddsShare::num() const { return num_; }
            long OddsShare::den() const { return den_; }
            OddsShare OddsShare::operator+(const OddsShare& other) const {
                return OddsShare(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            OddsShare OddsShare::operator-(const OddsShare& other) const {
                return OddsShare(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            OddsShare OddsShare::operator*(const OddsShare& other) const {
                return OddsShare(num_ * other.num_, den_ * other.den_);
            }
            OddsShare OddsShare::operator/(const OddsShare& other) const {
                if (other.num_ == 0) throw OddsError("division by a zero ratio");
                return OddsShare(num_ * other.den_, den_ * other.num_);
            }
            double OddsShare::to_probability() const {
                return static_cast<double>(num_) / static_cast<double>(num_ + den_);
            }
            bool OddsShare::operator==(const OddsShare& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            std::string OddsShare::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            """,
            """
            OddsShare::OddsShare(long num, long den) {
                if (den == 0) throw OddsError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long OddsShare::num() const { return num_; }
            long OddsShare::den() const { return den_; }
            OddsShare OddsShare::operator+(const OddsShare& other) const {
                return OddsShare(num_ * other.den_ + other.num_ * den_, den_ * other.den_);
            }
            OddsShare OddsShare::operator-(const OddsShare& other) const {
                return OddsShare(num_ * other.den_ - other.num_ * den_, den_ * other.den_);
            }
            OddsShare OddsShare::operator*(const OddsShare& other) const {
                return OddsShare(num_ * other.num_, den_ * other.den_);
            }
            OddsShare OddsShare::operator/(const OddsShare& other) const {
                if (other.num_ == 0) throw OddsError("division by a zero ratio");
                return OddsShare(num_ * other.den_, den_ * other.num_);
            }
            double OddsShare::to_probability() const {
                return static_cast<double>(num_) / static_cast<double>(num_ + den_);
            }
            bool OddsShare::operator==(const OddsShare& other) const {
                return num_ == other.num_ && den_ == other.den_;
            }
            std::string OddsShare::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            """,
            """
            OddsShare a(1, 1);
            if (std::fabs(a.to_probability() - 0.5) > 1e-12) return 1;
            OddsShare b(3, 1);
            if (std::fabs(b.to_probability() - 0.75) > 1e-12) return 2;
            OddsShare s = a + b;
            if (s.num() != 4 || s.den() != 1) return 3;
            OddsShare p = a * b;
            if (p.num() != 3 || p.den() != 1) return 4;
            if (!(a == OddsShare(2, 2))) return 5;
            if (b.render() != "3/1") return 6;
            return 0;
            """,
            """
            OddsShare z(0, 5);
            if (std::fabs(z.to_probability()) > 1e-12) return 1;
            OddsShare big(1000, 1);
            if (std::fabs(big.to_probability() - 1000.0 / 1001.0) > 1e-12) return 2;
            bool threw = false;
            try { OddsShare(1, 0); } catch (const OddsError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { OddsShare(1, 2) / OddsShare(0, 3); } catch (const OddsError&) { threw = true; }
            if (!threw) return 4;
            OddsShare neg(-1, 2);
            if (std::fabs(neg.to_probability() + 1.0) > 1e-12) return 5;
            OddsShare q = OddsShare(2, 3) / OddsShare(1, 3);
            if (q.num() != 2 || q.den() != 1) return 6;
            if (!(OddsShare(6, 9) == OddsShare(2, 3))) return 7;
            if (OddsShare(-4, 6).render() != "-2/3") return 8;
            OddsShare d = OddsShare(3, 4) - OddsShare(1, 4);
            if (d.num() != 1 || d.den() != 2) return 9;
            return 0;
            """,
            "a derived exact-to-double probability conversion that never feeds the exact equality contract",
            "any floating-point internal representation or probability-based equality; do not skip reduction or sign normalization",
            "probability conversion boundaries at zero and large odds, negative-share conversion, reduced render, and zero-divisor rejection",
            "derived conversions kept out of the equality contract in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-trail-grade-slope",
            "Trail grade slope",
            "trail_grade",
            """
            class GradeError : public std::domain_error {
            public:
                explicit GradeError(const std::string& message) : std::domain_error(message) {}
            };
            class SlopeRatio {
            public:
                SlopeRatio(long num, long den);
                long num() const;
                long den() const;
                long permille() const;
                std::string render() const;
            };
            SlopeRatio operator+(const SlopeRatio& left, const SlopeRatio& right);
            SlopeRatio operator-(const SlopeRatio& left, const SlopeRatio& right);
            SlopeRatio operator*(const SlopeRatio& left, const SlopeRatio& right);
            SlopeRatio operator/(const SlopeRatio& left, const SlopeRatio& right);
            bool operator==(const SlopeRatio& left, const SlopeRatio& right);
            bool operator<(const SlopeRatio& left, const SlopeRatio& right);
            """,
            """
            class GradeError : public std::domain_error {
            public:
                explicit GradeError(const std::string& message) : std::domain_error(message) {}
            };
            class SlopeRatio {
            public:
                SlopeRatio(long num, long den);
                long num() const;
                long den() const;
                long permille() const;
                std::string render() const;
            private:
                long num_;
                long den_;
            };
            SlopeRatio operator+(const SlopeRatio& left, const SlopeRatio& right);
            SlopeRatio operator-(const SlopeRatio& left, const SlopeRatio& right);
            SlopeRatio operator*(const SlopeRatio& left, const SlopeRatio& right);
            SlopeRatio operator/(const SlopeRatio& left, const SlopeRatio& right);
            bool operator==(const SlopeRatio& left, const SlopeRatio& right);
            bool operator<(const SlopeRatio& left, const SlopeRatio& right);
            """,
            """
            SlopeRatio::SlopeRatio(long num, long den) {
                if (den == 0) throw GradeError("zero denominator");
                long g = std::gcd(num, den);
                num_ = num / g;
                den_ = den / g;
                if (den_ < 0) { num_ = -num_; den_ = -den_; }
            }
            long SlopeRatio::num() const { return num_; }
            long SlopeRatio::den() const { return den_; }
            long SlopeRatio::permille() const {
                long scaled = 1000L * num_;
                long q = scaled / den_;
                long r = scaled % den_;
                long magnitude = r < 0 ? -r : r;
                if (2 * magnitude >= den_) q += (scaled < 0 ? -1 : 1);
                return q;
            }
            std::string SlopeRatio::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            SlopeRatio operator+(const SlopeRatio& left, const SlopeRatio& right) {
                return SlopeRatio(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            SlopeRatio operator-(const SlopeRatio& left, const SlopeRatio& right) {
                return SlopeRatio(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            SlopeRatio operator*(const SlopeRatio& left, const SlopeRatio& right) {
                return SlopeRatio(left.num() * right.num(), left.den() * right.den());
            }
            SlopeRatio operator/(const SlopeRatio& left, const SlopeRatio& right) {
                if (right.num() == 0) throw GradeError("division by a zero ratio");
                return SlopeRatio(left.num() * right.den(), left.den() * right.num());
            }
            bool operator==(const SlopeRatio& left, const SlopeRatio& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            bool operator<(const SlopeRatio& left, const SlopeRatio& right) {
                return left.num() * right.den() < right.num() * left.den();
            }
            """,
            """
            SlopeRatio::SlopeRatio(long num, long den) {
                if (den == 0) throw GradeError("zero denominator");
                num_ = num;
                den_ = den;
            }
            long SlopeRatio::num() const { return num_; }
            long SlopeRatio::den() const { return den_; }
            long SlopeRatio::permille() const {
                long scaled = 1000L * num_;
                long q = scaled / den_;
                long r = scaled % den_;
                long magnitude = r < 0 ? -r : r;
                if (2 * magnitude >= den_) q += (scaled < 0 ? -1 : 1);
                return q;
            }
            std::string SlopeRatio::render() const {
                std::ostringstream out;
                out << num_ << "/" << den_;
                return out.str();
            }
            SlopeRatio operator+(const SlopeRatio& left, const SlopeRatio& right) {
                return SlopeRatio(left.num() * right.den() + right.num() * left.den(), left.den() * right.den());
            }
            SlopeRatio operator-(const SlopeRatio& left, const SlopeRatio& right) {
                return SlopeRatio(left.num() * right.den() - right.num() * left.den(), left.den() * right.den());
            }
            SlopeRatio operator*(const SlopeRatio& left, const SlopeRatio& right) {
                return SlopeRatio(left.num() * right.num(), left.den() * right.den());
            }
            SlopeRatio operator/(const SlopeRatio& left, const SlopeRatio& right) {
                if (right.num() == 0) throw GradeError("division by a zero ratio");
                return SlopeRatio(left.num() * right.den(), left.den() * right.num());
            }
            bool operator==(const SlopeRatio& left, const SlopeRatio& right) {
                return left.num() == right.num() && left.den() == right.den();
            }
            bool operator<(const SlopeRatio& left, const SlopeRatio& right) {
                return left.num() * right.den() < right.num() * left.den();
            }
            """,
            """
            SlopeRatio a(1, 10);
            if (a.permille() != 100) return 1;
            SlopeRatio b(1, 8);
            if (b.permille() != 125) return 2;
            SlopeRatio s = a + b;
            if (s.num() != 9 || s.den() != 40) return 3;
            if (!(a < b)) return 4;
            if (!(a == SlopeRatio(2, 20))) return 5;
            if (b.render() != "1/8") return 6;
            return 0;
            """,
            """
            if (SlopeRatio(3, 2000).permille() != 2) return 1;
            if (SlopeRatio(-3, 2000).permille() != -2) return 2;
            if (SlopeRatio(1, 400).permille() != 3) return 3;
            if (SlopeRatio(-1, 400).permille() != -3) return 4;
            bool threw = false;
            try { SlopeRatio(1, 0); } catch (const GradeError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { SlopeRatio(1, 2) / SlopeRatio(0, 5); } catch (const GradeError&) { threw = true; }
            if (!threw) return 6;
            SlopeRatio p = SlopeRatio(2, 5) * SlopeRatio(5, 8);
            if (p.num() != 1 || p.den() != 4) return 7;
            if (!(SlopeRatio(-1, 3) < SlopeRatio(0, 100))) return 8;
            SlopeRatio d = SlopeRatio(1, 2) - SlopeRatio(1, 3);
            if (d.num() != 1 || d.den() != 6) return 9;
            if (SlopeRatio(-10, 4).render() != "-5/2") return 10;
            return 0;
            """,
            "a deterministic half-away-from-zero rounding rule over gcd-normalized exact ratios",
            "any floating-point internal representation or a truncating permille; do not skip reduction or sign normalization",
            "half-away rounding at exact halves with both signs, reduced render, exact ordering, and zero-divisor rejection",
            "explicit rounding policy as part of the public contract in a paired .h/.cpp API",
            "exact normalized fraction value type",
        ),
        c(
            "f26cpx-cold-storage-band",
            "Cold storage band",
            "cold_storage",
            """
            class BandError : public std::domain_error {
            public:
                explicit BandError(const std::string& message) : std::domain_error(message) {}
            };
            class TempBand {
            public:
                TempBand(double lo, double hi);
                double lo() const;
                double hi() const;
                TempBand operator+(const TempBand& other) const;
                TempBand operator-(const TempBand& other) const;
                TempBand operator*(const TempBand& other) const;
                TempBand operator/(const TempBand& other) const;
                double width() const;
                double midpoint() const;
                bool contains(double value) const;
                bool overlaps(const TempBand& other) const;
            };
            bool same_band(const TempBand& left, const TempBand& right, double eps);
            """,
            """
            class BandError : public std::domain_error {
            public:
                explicit BandError(const std::string& message) : std::domain_error(message) {}
            };
            class TempBand {
            public:
                TempBand(double lo, double hi);
                double lo() const;
                double hi() const;
                TempBand operator+(const TempBand& other) const;
                TempBand operator-(const TempBand& other) const;
                TempBand operator*(const TempBand& other) const;
                TempBand operator/(const TempBand& other) const;
                double width() const;
                double midpoint() const;
                bool contains(double value) const;
                bool overlaps(const TempBand& other) const;
            private:
                double lo_;
                double hi_;
            };
            bool same_band(const TempBand& left, const TempBand& right, double eps);
            """,
            """
            TempBand::TempBand(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw BandError("lo exceeds hi");
            }
            double TempBand::lo() const { return lo_; }
            double TempBand::hi() const { return hi_; }
            TempBand TempBand::operator+(const TempBand& other) const {
                return TempBand(lo_ + other.lo_, hi_ + other.hi_);
            }
            TempBand TempBand::operator-(const TempBand& other) const {
                return TempBand(lo_ - other.hi_, hi_ - other.lo_);
            }
            TempBand TempBand::operator*(const TempBand& other) const {
                double p1 = lo_ * other.lo_;
                double p2 = lo_ * other.hi_;
                double p3 = hi_ * other.lo_;
                double p4 = hi_ * other.hi_;
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return TempBand(lo, hi);
            }
            TempBand TempBand::operator/(const TempBand& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw BandError("divisor straddles zero");
                return (*this) * TempBand(1.0 / other.hi_, 1.0 / other.lo_);
            }
            double TempBand::width() const { return hi_ - lo_; }
            double TempBand::midpoint() const { return (lo_ + hi_) / 2.0; }
            bool TempBand::contains(double value) const { return lo_ <= value && value <= hi_; }
            bool TempBand::overlaps(const TempBand& other) const {
                return lo_ <= other.hi_ && other.lo_ <= hi_;
            }
            bool same_band(const TempBand& left, const TempBand& right, double eps) {
                return std::fabs(left.lo() - right.lo()) <= eps
                    && std::fabs(left.hi() - right.hi()) <= eps;
            }
            """,
            """
            TempBand::TempBand(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw BandError("lo exceeds hi");
            }
            double TempBand::lo() const { return lo_; }
            double TempBand::hi() const { return hi_; }
            TempBand TempBand::operator+(const TempBand& other) const {
                return TempBand(lo_ + other.lo_, hi_ + other.hi_);
            }
            TempBand TempBand::operator-(const TempBand& other) const {
                return TempBand(lo_ - other.hi_, hi_ - other.lo_);
            }
            TempBand TempBand::operator*(const TempBand& other) const {
                return TempBand(lo_ * other.lo_, hi_ * other.hi_);
            }
            TempBand TempBand::operator/(const TempBand& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw BandError("divisor straddles zero");
                return (*this) * TempBand(1.0 / other.hi_, 1.0 / other.lo_);
            }
            double TempBand::width() const { return hi_ - lo_; }
            double TempBand::midpoint() const { return (lo_ + hi_) / 2.0; }
            bool TempBand::contains(double value) const { return lo_ <= value && value <= hi_; }
            bool TempBand::overlaps(const TempBand& other) const {
                return lo_ <= other.hi_ && other.lo_ <= hi_;
            }
            bool same_band(const TempBand& left, const TempBand& right, double eps) {
                return std::fabs(left.lo() - right.lo()) <= eps
                    && std::fabs(left.hi() - right.hi()) <= eps;
            }
            """,
            """
            TempBand a(1.0, 3.0);
            TempBand b(2.0, 4.0);
            TempBand s = a + b;
            if (std::fabs(s.lo() - 3.0) > 1e-9 || std::fabs(s.hi() - 7.0) > 1e-9) return 1;
            TempBand d = a - b;
            if (std::fabs(d.lo() + 3.0) > 1e-9 || std::fabs(d.hi() - 1.0) > 1e-9) return 2;
            TempBand p = a * b;
            if (std::fabs(p.lo() - 2.0) > 1e-9 || std::fabs(p.hi() - 12.0) > 1e-9) return 3;
            if (std::fabs(a.width() - 2.0) > 1e-9 || std::fabs(a.midpoint() - 2.0) > 1e-9) return 4;
            if (!a.contains(1.0) || !a.contains(3.0) || a.contains(3.5)) return 5;
            if (!a.overlaps(b)) return 6;
            TempBand q = b / a;
            if (std::fabs(q.lo() - 2.0 / 3.0) > 1e-9 || std::fabs(q.hi() - 4.0) > 1e-9) return 7;
            if (!same_band(a, TempBand(1.0 + 1e-12, 3.0), 1e-9)) return 8;
            return 0;
            """,
            """
            TempBand m(-2.0, 3.0);
            TempBand n(4.0, 5.0);
            TempBand p = m * n;
            if (std::fabs(p.lo() + 10.0) > 1e-9 || std::fabs(p.hi() - 15.0) > 1e-9) return 1;
            TempBand p2 = m * m;
            if (std::fabs(p2.lo() + 6.0) > 1e-9 || std::fabs(p2.hi() - 9.0) > 1e-9) return 2;
            bool threw = false;
            try { TempBand bad(2.0, 1.0); } catch (const BandError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { TempBand z(-1.0, 1.0); n / z; } catch (const BandError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { TempBand z(-1.0, 0.0); n / z; } catch (const BandError&) { threw = true; }
            if (!threw) return 5;
            TempBand q = n / TempBand(-4.0, -2.0);
            if (std::fabs(q.lo() + 2.5) > 1e-9 || std::fabs(q.hi() + 1.0) > 1e-9) return 6;
            if (m.overlaps(TempBand(3.5, 6.0))) return 7;
            if (!m.overlaps(TempBand(3.0, 6.0))) return 8;
            if (same_band(m, TempBand(-2.0, 3.0 + 1e-6), 1e-9)) return 9;
            return 0;
            """,
            "endpoint-extrema interval products with a zero-straddle division edge and inclusive containment",
            "the endpoint-naive product (lo*lo, hi*hi) or a division that skips the zero-straddle check",
            "mixed-sign product extrema, self-product extrema, inverted construction, division by zero-touching ranges, and inclusive boundary containment",
            "interval arithmetic with a genuine division edge in a paired .h/.cpp API",
            "bounded range value type",
        ),
        c(
            "f26cpx-vaccine-dose-window",
            "Vaccine dose window",
            "vaccine_dose",
            """
            class DoseError : public std::domain_error {
            public:
                explicit DoseError(const std::string& message) : std::domain_error(message) {}
            };
            class DoseWindow {
            public:
                DoseWindow(double lo, double hi);
                double lo() const;
                double hi() const;
                DoseWindow operator+(const DoseWindow& other) const;
                DoseWindow operator-(const DoseWindow& other) const;
                DoseWindow operator*(const DoseWindow& other) const;
                DoseWindow operator/(const DoseWindow& other) const;
                std::optional<DoseWindow> intersect(const DoseWindow& other) const;
                bool contains(double value) const;
                std::string render() const;
            };
            """,
            """
            class DoseError : public std::domain_error {
            public:
                explicit DoseError(const std::string& message) : std::domain_error(message) {}
            };
            class DoseWindow {
            public:
                DoseWindow(double lo, double hi);
                double lo() const;
                double hi() const;
                DoseWindow operator+(const DoseWindow& other) const;
                DoseWindow operator-(const DoseWindow& other) const;
                DoseWindow operator*(const DoseWindow& other) const;
                DoseWindow operator/(const DoseWindow& other) const;
                std::optional<DoseWindow> intersect(const DoseWindow& other) const;
                bool contains(double value) const;
                std::string render() const;
            private:
                double lo_;
                double hi_;
            };
            """,
            """
            DoseWindow::DoseWindow(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw DoseError("lo exceeds hi");
            }
            double DoseWindow::lo() const { return lo_; }
            double DoseWindow::hi() const { return hi_; }
            DoseWindow DoseWindow::operator+(const DoseWindow& other) const {
                return DoseWindow(lo_ + other.lo_, hi_ + other.hi_);
            }
            DoseWindow DoseWindow::operator-(const DoseWindow& other) const {
                return DoseWindow(lo_ - other.hi_, hi_ - other.lo_);
            }
            DoseWindow DoseWindow::operator*(const DoseWindow& other) const {
                double p1 = lo_ * other.lo_;
                double p2 = lo_ * other.hi_;
                double p3 = hi_ * other.lo_;
                double p4 = hi_ * other.hi_;
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return DoseWindow(lo, hi);
            }
            DoseWindow DoseWindow::operator/(const DoseWindow& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw DoseError("divisor straddles zero");
                return (*this) * DoseWindow(1.0 / other.hi_, 1.0 / other.lo_);
            }
            std::optional<DoseWindow> DoseWindow::intersect(const DoseWindow& other) const {
                double lo = std::max(lo_, other.lo_);
                double hi = std::min(hi_, other.hi_);
                if (lo > hi) return std::nullopt;
                return DoseWindow(lo, hi);
            }
            bool DoseWindow::contains(double value) const { return lo_ <= value && value <= hi_; }
            std::string DoseWindow::render() const {
                std::ostringstream out;
                out << "[" << std::fixed << std::setprecision(2) << lo_ << "|" << hi_ << "]";
                return out.str();
            }
            """,
            """
            DoseWindow::DoseWindow(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw DoseError("lo exceeds hi");
            }
            double DoseWindow::lo() const { return lo_; }
            double DoseWindow::hi() const { return hi_; }
            DoseWindow DoseWindow::operator+(const DoseWindow& other) const {
                return DoseWindow(lo_ + other.lo_, hi_ + other.hi_);
            }
            DoseWindow DoseWindow::operator-(const DoseWindow& other) const {
                return DoseWindow(lo_ - other.hi_, hi_ - other.lo_);
            }
            DoseWindow DoseWindow::operator*(const DoseWindow& other) const {
                return DoseWindow(lo_ * other.lo_, hi_ * other.hi_);
            }
            DoseWindow DoseWindow::operator/(const DoseWindow& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw DoseError("divisor straddles zero");
                return (*this) * DoseWindow(1.0 / other.hi_, 1.0 / other.lo_);
            }
            std::optional<DoseWindow> DoseWindow::intersect(const DoseWindow& other) const {
                double lo = std::max(lo_, other.lo_);
                double hi = std::min(hi_, other.hi_);
                if (lo > hi) return std::nullopt;
                return DoseWindow(lo, hi);
            }
            bool DoseWindow::contains(double value) const { return lo_ <= value && value <= hi_; }
            std::string DoseWindow::render() const {
                std::ostringstream out;
                out << "[" << std::fixed << std::setprecision(2) << lo_ << "|" << hi_ << "]";
                return out.str();
            }
            """,
            """
            DoseWindow a(1.0, 2.0);
            DoseWindow b(1.5, 3.0);
            std::optional<DoseWindow> i = a.intersect(b);
            if (!i.has_value()) return 1;
            if (std::fabs(i->lo() - 1.5) > 1e-9 || std::fabs(i->hi() - 2.0) > 1e-9) return 2;
            if (a.intersect(DoseWindow(5.0, 6.0)).has_value()) return 3;
            DoseWindow s = a + b;
            if (std::fabs(s.lo() - 2.5) > 1e-9 || std::fabs(s.hi() - 5.0) > 1e-9) return 4;
            if (!a.contains(1.5) || a.contains(2.5)) return 5;
            if (a.render() != "[1.00|2.00]") return 6;
            DoseWindow p = a * b;
            if (std::fabs(p.lo() - 1.5) > 1e-9 || std::fabs(p.hi() - 6.0) > 1e-9) return 7;
            return 0;
            """,
            """
            DoseWindow m(-2.0, 1.0);
            DoseWindow n(3.0, 4.0);
            DoseWindow p = m * n;
            if (std::fabs(p.lo() + 8.0) > 1e-9 || std::fabs(p.hi() - 4.0) > 1e-9) return 1;
            std::optional<DoseWindow> touch = DoseWindow(1.0, 2.0).intersect(DoseWindow(2.0, 3.0));
            if (!touch.has_value()) return 2;
            if (std::fabs(touch->lo() - 2.0) > 1e-9 || std::fabs(touch->hi() - 2.0) > 1e-9) return 3;
            bool threw = false;
            try { DoseWindow bad(3.0, 2.0); } catch (const DoseError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { DoseWindow z(0.0, 1.0); n / z; } catch (const DoseError&) { threw = true; }
            if (!threw) return 5;
            DoseWindow q = n / DoseWindow(1.0, 2.0);
            if (std::fabs(q.lo() - 1.5) > 1e-9 || std::fabs(q.hi() - 4.0) > 1e-9) return 6;
            if (touch->render() != "[2.00|2.00]") return 7;
            DoseWindow d = n - m;
            if (std::fabs(d.lo() - 2.0) > 1e-9 || std::fabs(d.hi() - 6.0) > 1e-9) return 8;
            return 0;
            """,
            "empty intersection as std::nullopt with point intersections at touching ranges",
            "the endpoint-naive product (lo*lo, hi*hi) or an intersection that returns an invalid inverted window",
            "disjoint intersection empty, touching ranges intersecting at a point, mixed-sign product extrema, bracketed render bytes, and zero-touching division rejection",
            "optional-returning API over ranges in a project-context paired .h/.cpp layout",
            "bounded range value type",
            project_support=True,
        ),
        c(
            "f26cpx-glacier-altitude-corridor",
            "Glacier altitude corridor",
            "altitude_corridor",
            """
            class CorridorError : public std::domain_error {
            public:
                explicit CorridorError(const std::string& message) : std::domain_error(message) {}
            };
            class Corridor {
            public:
                Corridor(double lo, double hi);
                double lo() const;
                double hi() const;
                double clamp(double value) const;
                Corridor hull(const Corridor& other) const;
                double width() const;
                bool overlaps(const Corridor& other) const;
            };
            Corridor operator+(const Corridor& left, const Corridor& right);
            Corridor operator-(const Corridor& left, const Corridor& right);
            Corridor operator*(const Corridor& left, const Corridor& right);
            Corridor operator/(const Corridor& left, const Corridor& right);
            bool same_band(const Corridor& left, const Corridor& right, double eps);
            """,
            """
            class CorridorError : public std::domain_error {
            public:
                explicit CorridorError(const std::string& message) : std::domain_error(message) {}
            };
            class Corridor {
            public:
                Corridor(double lo, double hi);
                double lo() const;
                double hi() const;
                double clamp(double value) const;
                Corridor hull(const Corridor& other) const;
                double width() const;
                bool overlaps(const Corridor& other) const;
            private:
                double lo_;
                double hi_;
            };
            Corridor operator+(const Corridor& left, const Corridor& right);
            Corridor operator-(const Corridor& left, const Corridor& right);
            Corridor operator*(const Corridor& left, const Corridor& right);
            Corridor operator/(const Corridor& left, const Corridor& right);
            bool same_band(const Corridor& left, const Corridor& right, double eps);
            """,
            """
            Corridor::Corridor(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw CorridorError("lo exceeds hi");
            }
            double Corridor::lo() const { return lo_; }
            double Corridor::hi() const { return hi_; }
            double Corridor::clamp(double value) const {
                return std::min(std::max(value, lo_), hi_);
            }
            Corridor Corridor::hull(const Corridor& other) const {
                return Corridor(std::min(lo_, other.lo_), std::max(hi_, other.hi_));
            }
            double Corridor::width() const { return hi_ - lo_; }
            bool Corridor::overlaps(const Corridor& other) const {
                return lo_ <= other.hi_ && other.lo_ <= hi_;
            }
            Corridor operator+(const Corridor& left, const Corridor& right) {
                return Corridor(left.lo() + right.lo(), left.hi() + right.hi());
            }
            Corridor operator-(const Corridor& left, const Corridor& right) {
                return Corridor(left.lo() - right.hi(), left.hi() - right.lo());
            }
            Corridor operator*(const Corridor& left, const Corridor& right) {
                double p1 = left.lo() * right.lo();
                double p2 = left.lo() * right.hi();
                double p3 = left.hi() * right.lo();
                double p4 = left.hi() * right.hi();
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return Corridor(lo, hi);
            }
            Corridor operator/(const Corridor& left, const Corridor& right) {
                if (right.lo() <= 0.0 && right.hi() >= 0.0) throw CorridorError("divisor straddles zero");
                return left * Corridor(1.0 / right.hi(), 1.0 / right.lo());
            }
            bool same_band(const Corridor& left, const Corridor& right, double eps) {
                return std::fabs(left.lo() - right.lo()) <= eps
                    && std::fabs(left.hi() - right.hi()) <= eps;
            }
            """,
            """
            Corridor::Corridor(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw CorridorError("lo exceeds hi");
            }
            double Corridor::lo() const { return lo_; }
            double Corridor::hi() const { return hi_; }
            double Corridor::clamp(double value) const {
                return std::min(std::max(value, lo_), hi_);
            }
            Corridor Corridor::hull(const Corridor& other) const {
                return Corridor(std::min(lo_, other.lo_), std::max(hi_, other.hi_));
            }
            double Corridor::width() const { return hi_ - lo_; }
            bool Corridor::overlaps(const Corridor& other) const {
                return lo_ <= other.hi_ && other.lo_ <= hi_;
            }
            Corridor operator+(const Corridor& left, const Corridor& right) {
                return Corridor(left.lo() + right.lo(), left.hi() + right.hi());
            }
            Corridor operator-(const Corridor& left, const Corridor& right) {
                return Corridor(left.lo() - right.hi(), left.hi() - right.lo());
            }
            Corridor operator*(const Corridor& left, const Corridor& right) {
                return Corridor(left.lo() * right.lo(), left.hi() * right.hi());
            }
            Corridor operator/(const Corridor& left, const Corridor& right) {
                if (right.lo() <= 0.0 && right.hi() >= 0.0) throw CorridorError("divisor straddles zero");
                return left * Corridor(1.0 / right.hi(), 1.0 / right.lo());
            }
            bool same_band(const Corridor& left, const Corridor& right, double eps) {
                return std::fabs(left.lo() - right.lo()) <= eps
                    && std::fabs(left.hi() - right.hi()) <= eps;
            }
            """,
            """
            Corridor a(100.0, 200.0);
            Corridor b(150.0, 300.0);
            if (std::fabs(a.clamp(50.0) - 100.0) > 1e-9) return 1;
            if (std::fabs(a.clamp(150.0) - 150.0) > 1e-9) return 2;
            if (std::fabs(a.clamp(250.0) - 200.0) > 1e-9) return 3;
            Corridor h = a.hull(b);
            if (std::fabs(h.lo() - 100.0) > 1e-9 || std::fabs(h.hi() - 300.0) > 1e-9) return 4;
            if (std::fabs(a.width() - 100.0) > 1e-9) return 5;
            if (!a.overlaps(b)) return 6;
            Corridor s = a + b;
            if (std::fabs(s.lo() - 250.0) > 1e-9 || std::fabs(s.hi() - 500.0) > 1e-9) return 7;
            if (!same_band(a, Corridor(100.0, 200.0 + 1e-12), 1e-9)) return 8;
            return 0;
            """,
            """
            Corridor m(-20.0, 30.0);
            Corridor n(4.0, 5.0);
            Corridor p = m * n;
            if (std::fabs(p.lo() + 100.0) > 1e-9 || std::fabs(p.hi() - 150.0) > 1e-9) return 1;
            Corridor h = Corridor(0.0, 1.0).hull(Corridor(10.0, 12.0));
            if (std::fabs(h.lo()) > 1e-9 || std::fabs(h.hi() - 12.0) > 1e-9) return 2;
            bool threw = false;
            try { Corridor bad(9.0, 8.0); } catch (const CorridorError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { Corridor z(-1.0, 1.0); n / z; } catch (const CorridorError&) { threw = true; }
            if (!threw) return 4;
            Corridor d = n - m;
            if (std::fabs(d.lo() + 26.0) > 1e-9 || std::fabs(d.hi() - 25.0) > 1e-9) return 5;
            if (Corridor(0.0, 1.0).overlaps(Corridor(2.0, 3.0))) return 6;
            Corridor q = n / Corridor(2.0, 4.0);
            if (std::fabs(q.lo() - 1.0) > 1e-9 || std::fabs(q.hi() - 2.5) > 1e-9) return 7;
            if (same_band(m, Corridor(-20.0 + 1e-6, 30.0), 1e-9)) return 8;
            return 0;
            """,
            "clamp projection and hull combinators over validated endpoint pairs",
            "the endpoint-naive product (lo*lo, hi*hi) or a hull that discards endpoints",
            "clamp at both ends and inside, hull of disjoint ranges, mixed-sign product extrema, and zero-straddle division rejection",
            "projection and hull semantics over owned endpoint pairs in a paired .h/.cpp API",
            "bounded range value type",
        ),
        c(
            "f26cpx-market-price-band",
            "Market price band",
            "market_band",
            """
            class PriceError : public std::domain_error {
            public:
                explicit PriceError(const std::string& message) : std::domain_error(message) {}
            };
            class PriceBand {
            public:
                PriceBand(double lo, double hi);
                double lo() const;
                double hi() const;
                PriceBand operator+(const PriceBand& other) const;
                PriceBand operator-(const PriceBand& other) const;
                PriceBand operator*(const PriceBand& other) const;
                PriceBand operator/(const PriceBand& other) const;
                PriceBand expand(double margin) const;
                double midpoint() const;
                bool overlaps(const PriceBand& other) const;
                std::string render() const;
            };
            """,
            """
            class PriceError : public std::domain_error {
            public:
                explicit PriceError(const std::string& message) : std::domain_error(message) {}
            };
            class PriceBand {
            public:
                PriceBand(double lo, double hi);
                double lo() const;
                double hi() const;
                PriceBand operator+(const PriceBand& other) const;
                PriceBand operator-(const PriceBand& other) const;
                PriceBand operator*(const PriceBand& other) const;
                PriceBand operator/(const PriceBand& other) const;
                PriceBand expand(double margin) const;
                double midpoint() const;
                bool overlaps(const PriceBand& other) const;
                std::string render() const;
            private:
                double lo_;
                double hi_;
            };
            """,
            """
            PriceBand::PriceBand(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw PriceError("lo exceeds hi");
            }
            double PriceBand::lo() const { return lo_; }
            double PriceBand::hi() const { return hi_; }
            PriceBand PriceBand::operator+(const PriceBand& other) const {
                return PriceBand(lo_ + other.lo_, hi_ + other.hi_);
            }
            PriceBand PriceBand::operator-(const PriceBand& other) const {
                return PriceBand(lo_ - other.hi_, hi_ - other.lo_);
            }
            PriceBand PriceBand::operator*(const PriceBand& other) const {
                double p1 = lo_ * other.lo_;
                double p2 = lo_ * other.hi_;
                double p3 = hi_ * other.lo_;
                double p4 = hi_ * other.hi_;
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return PriceBand(lo, hi);
            }
            PriceBand PriceBand::operator/(const PriceBand& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw PriceError("divisor straddles zero");
                return (*this) * PriceBand(1.0 / other.hi_, 1.0 / other.lo_);
            }
            PriceBand PriceBand::expand(double margin) const {
                if (margin < 0.0) throw PriceError("negative margin");
                double mid = (lo_ + hi_) / 2.0;
                double half = (hi_ - lo_) / 2.0 * (1.0 + margin);
                return PriceBand(mid - half, mid + half);
            }
            double PriceBand::midpoint() const { return (lo_ + hi_) / 2.0; }
            bool PriceBand::overlaps(const PriceBand& other) const {
                return lo_ <= other.hi_ && other.lo_ <= hi_;
            }
            std::string PriceBand::render() const {
                std::ostringstream out;
                out << "band=" << std::fixed << std::setprecision(6) << lo_ << ".." << hi_;
                return out.str();
            }
            """,
            """
            PriceBand::PriceBand(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw PriceError("lo exceeds hi");
            }
            double PriceBand::lo() const { return lo_; }
            double PriceBand::hi() const { return hi_; }
            PriceBand PriceBand::operator+(const PriceBand& other) const {
                return PriceBand(lo_ + other.lo_, hi_ + other.hi_);
            }
            PriceBand PriceBand::operator-(const PriceBand& other) const {
                return PriceBand(lo_ - other.hi_, hi_ - other.lo_);
            }
            PriceBand PriceBand::operator*(const PriceBand& other) const {
                return PriceBand(lo_ * other.lo_, hi_ * other.hi_);
            }
            PriceBand PriceBand::operator/(const PriceBand& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw PriceError("divisor straddles zero");
                return (*this) * PriceBand(1.0 / other.hi_, 1.0 / other.lo_);
            }
            PriceBand PriceBand::expand(double margin) const {
                if (margin < 0.0) throw PriceError("negative margin");
                double mid = (lo_ + hi_) / 2.0;
                double half = (hi_ - lo_) / 2.0 * (1.0 + margin);
                return PriceBand(mid - half, mid + half);
            }
            double PriceBand::midpoint() const { return (lo_ + hi_) / 2.0; }
            bool PriceBand::overlaps(const PriceBand& other) const {
                return lo_ <= other.hi_ && other.lo_ <= hi_;
            }
            std::string PriceBand::render() const {
                std::ostringstream out;
                out << "band=" << std::fixed << std::setprecision(6) << lo_ << ".." << hi_;
                return out.str();
            }
            """,
            """
            PriceBand a(10.0, 20.0);
            PriceBand e = a.expand(0.5);
            if (std::fabs(e.lo() - 7.5) > 1e-9 || std::fabs(e.hi() - 22.5) > 1e-9) return 1;
            if (std::fabs(e.midpoint() - 15.0) > 1e-9) return 2;
            PriceBand z = a.expand(0.0);
            if (std::fabs(z.lo() - 10.0) > 1e-9 || std::fabs(z.hi() - 20.0) > 1e-9) return 3;
            PriceBand p = a * PriceBand(2.0, 3.0);
            if (std::fabs(p.lo() - 20.0) > 1e-9 || std::fabs(p.hi() - 60.0) > 1e-9) return 4;
            if (!a.overlaps(PriceBand(20.0, 30.0))) return 5;
            if (a.render() != "band=10.000000..20.000000") return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { PriceBand(10.0, 20.0).expand(-0.5); } catch (const PriceError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PriceBand bad(5.0, 4.0); } catch (const PriceError&) { threw = true; }
            if (!threw) return 2;
            PriceBand m(-10.0, 20.0);
            PriceBand n(4.0, 5.0);
            PriceBand p = m * n;
            if (std::fabs(p.lo() + 50.0) > 1e-9 || std::fabs(p.hi() - 100.0) > 1e-9) return 3;
            PriceBand e = m.expand(1.0);
            if (std::fabs(e.lo() + 25.0) > 1e-9 || std::fabs(e.hi() - 35.0) > 1e-9) return 4;
            threw = false;
            try { PriceBand z(0.0, 2.0); n / z; } catch (const PriceError&) { threw = true; }
            if (!threw) return 5;
            PriceBand q = n / PriceBand(2.0, 4.0);
            if (std::fabs(q.lo() - 1.0) > 1e-9 || std::fabs(q.hi() - 2.5) > 1e-9) return 6;
            PriceBand d = n - m;
            if (std::fabs(d.lo() + 16.0) > 1e-9 || std::fabs(d.hi() - 15.0) > 1e-9) return 7;
            if (PriceBand(0.0, 1.0).overlaps(PriceBand(1.5, 2.0))) return 8;
            if (m.render() != "band=-10.000000..20.000000") return 9;
            return 0;
            """,
            "midpoint-centered width scaling with margin validation over validated endpoint pairs",
            "the endpoint-naive product (lo*lo, hi*hi) or an expand that moves only one endpoint",
            "expand(0) identity, negative margin rejection, midpoint invariance under expand, mixed-sign product extrema, and zero-touching division rejection",
            "centered rescale semantics distinct from plain endpoint arithmetic in a paired .h/.cpp API",
            "bounded range value type",
        ),
        c(
            "f26cpx-greenhouse-humidity-envelope",
            "Greenhouse humidity envelope",
            "humidity_envelope",
            """
            class EnvelopeError : public std::domain_error {
            public:
                explicit EnvelopeError(const std::string& message) : std::domain_error(message) {}
            };
            class HumidityEnvelope {
            public:
                HumidityEnvelope(double lo, double hi);
                double lo() const;
                double hi() const;
                bool contains(double value) const;
                double width() const;
                bool within(const HumidityEnvelope& other, double eps) const;
            };
            HumidityEnvelope operator+(const HumidityEnvelope& left, const HumidityEnvelope& right);
            HumidityEnvelope operator-(const HumidityEnvelope& left, const HumidityEnvelope& right);
            HumidityEnvelope operator*(const HumidityEnvelope& left, const HumidityEnvelope& right);
            HumidityEnvelope operator/(const HumidityEnvelope& left, const HumidityEnvelope& right);
            """,
            """
            class EnvelopeError : public std::domain_error {
            public:
                explicit EnvelopeError(const std::string& message) : std::domain_error(message) {}
            };
            class HumidityEnvelope {
            public:
                HumidityEnvelope(double lo, double hi);
                double lo() const;
                double hi() const;
                bool contains(double value) const;
                double width() const;
                bool within(const HumidityEnvelope& other, double eps) const;
            private:
                double lo_;
                double hi_;
            };
            HumidityEnvelope operator+(const HumidityEnvelope& left, const HumidityEnvelope& right);
            HumidityEnvelope operator-(const HumidityEnvelope& left, const HumidityEnvelope& right);
            HumidityEnvelope operator*(const HumidityEnvelope& left, const HumidityEnvelope& right);
            HumidityEnvelope operator/(const HumidityEnvelope& left, const HumidityEnvelope& right);
            """,
            """
            HumidityEnvelope::HumidityEnvelope(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw EnvelopeError("lo exceeds hi");
            }
            double HumidityEnvelope::lo() const { return lo_; }
            double HumidityEnvelope::hi() const { return hi_; }
            bool HumidityEnvelope::contains(double value) const { return lo_ <= value && value <= hi_; }
            double HumidityEnvelope::width() const { return hi_ - lo_; }
            bool HumidityEnvelope::within(const HumidityEnvelope& other, double eps) const {
                return std::fabs(lo_ - other.lo_) <= eps
                    && std::fabs(hi_ - other.hi_) <= eps;
            }
            HumidityEnvelope operator+(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                return HumidityEnvelope(left.lo() + right.lo(), left.hi() + right.hi());
            }
            HumidityEnvelope operator-(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                return HumidityEnvelope(left.lo() - right.hi(), left.hi() - right.lo());
            }
            HumidityEnvelope operator*(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                double p1 = left.lo() * right.lo();
                double p2 = left.lo() * right.hi();
                double p3 = left.hi() * right.lo();
                double p4 = left.hi() * right.hi();
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return HumidityEnvelope(lo, hi);
            }
            HumidityEnvelope operator/(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                if (right.lo() <= 0.0 && right.hi() >= 0.0) throw EnvelopeError("divisor straddles zero");
                return left * HumidityEnvelope(1.0 / right.hi(), 1.0 / right.lo());
            }
            """,
            """
            HumidityEnvelope::HumidityEnvelope(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw EnvelopeError("lo exceeds hi");
            }
            double HumidityEnvelope::lo() const { return lo_; }
            double HumidityEnvelope::hi() const { return hi_; }
            bool HumidityEnvelope::contains(double value) const { return lo_ <= value && value <= hi_; }
            double HumidityEnvelope::width() const { return hi_ - lo_; }
            bool HumidityEnvelope::within(const HumidityEnvelope& other, double eps) const {
                return std::fabs(lo_ - other.lo_) <= eps
                    && std::fabs(hi_ - other.hi_) <= eps;
            }
            HumidityEnvelope operator+(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                return HumidityEnvelope(left.lo() + right.lo(), left.hi() + right.hi());
            }
            HumidityEnvelope operator-(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                return HumidityEnvelope(left.lo() - right.hi(), left.hi() - right.lo());
            }
            HumidityEnvelope operator*(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                return HumidityEnvelope(left.lo() * right.lo(), left.hi() * right.hi());
            }
            HumidityEnvelope operator/(const HumidityEnvelope& left, const HumidityEnvelope& right) {
                if (right.lo() <= 0.0 && right.hi() >= 0.0) throw EnvelopeError("divisor straddles zero");
                return left * HumidityEnvelope(1.0 / right.hi(), 1.0 / right.lo());
            }
            """,
            """
            HumidityEnvelope a(30.0, 60.0);
            HumidityEnvelope b(10.0, 20.0);
            HumidityEnvelope s = a + b;
            if (std::fabs(s.lo() - 40.0) > 1e-9 || std::fabs(s.hi() - 80.0) > 1e-9) return 1;
            HumidityEnvelope p = a * b;
            if (std::fabs(p.lo() - 300.0) > 1e-9 || std::fabs(p.hi() - 1200.0) > 1e-9) return 2;
            if (!a.contains(45.0) || a.contains(65.0)) return 3;
            if (std::fabs(a.width() - 30.0) > 1e-9) return 4;
            if (!a.within(HumidityEnvelope(30.0 + 1e-12, 60.0), 1e-9)) return 5;
            HumidityEnvelope d = a - b;
            if (std::fabs(d.lo() - 10.0) > 1e-9 || std::fabs(d.hi() - 50.0) > 1e-9) return 6;
            return 0;
            """,
            """
            HumidityEnvelope m(-2.0, 3.0);
            HumidityEnvelope n(4.0, 5.0);
            HumidityEnvelope p = m * n;
            if (std::fabs(p.lo() + 10.0) > 1e-9 || std::fabs(p.hi() - 15.0) > 1e-9) return 1;
            bool threw = false;
            try { HumidityEnvelope bad(60.0, 30.0); } catch (const EnvelopeError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { HumidityEnvelope z(-1.0, 1.0); n / z; } catch (const EnvelopeError&) { threw = true; }
            if (!threw) return 3;
            HumidityEnvelope q = n / HumidityEnvelope(2.0, 4.0);
            if (std::fabs(q.lo() - 1.0) > 1e-9 || std::fabs(q.hi() - 2.5) > 1e-9) return 4;
            if (m.within(HumidityEnvelope(-2.0, 3.0 + 1e-6), 1e-9)) return 5;
            if (!m.contains(-2.0) || !m.contains(3.0)) return 6;
            HumidityEnvelope d = n - m;
            if (std::fabs(d.lo() - 1.0) > 1e-9 || std::fabs(d.hi() - 7.0) > 1e-9) return 7;
            return 0;
            """,
            "member tolerance equality over validated endpoint pairs with free interval operators",
            "the endpoint-naive product (lo*lo, hi*hi) or an exact == on raw doubles as the equality contract",
            "member tolerance just inside and outside eps, mixed-sign product extrema, inclusive containment, and zero-straddle division rejection",
            "member-tolerance contrast with the free-function sibling range roots in a paired .h/.cpp API",
            "bounded range value type",
        ),
        c(
            "f26cpx-battery-voltage-margin",
            "Battery voltage margin",
            "voltage_margin",
            """
            class MarginError : public std::domain_error {
            public:
                explicit MarginError(const std::string& message) : std::domain_error(message) {}
            };
            class VoltageMargin {
            public:
                VoltageMargin(double lo, double hi);
                double lo() const;
                double hi() const;
                VoltageMargin operator+(const VoltageMargin& other) const;
                VoltageMargin operator-(const VoltageMargin& other) const;
                VoltageMargin operator*(const VoltageMargin& other) const;
                VoltageMargin operator/(const VoltageMargin& other) const;
                std::optional<VoltageMargin> intersect(const VoltageMargin& other) const;
                bool is_degenerate() const;
                std::string render() const;
            };
            """,
            """
            class MarginError : public std::domain_error {
            public:
                explicit MarginError(const std::string& message) : std::domain_error(message) {}
            };
            class VoltageMargin {
            public:
                VoltageMargin(double lo, double hi);
                double lo() const;
                double hi() const;
                VoltageMargin operator+(const VoltageMargin& other) const;
                VoltageMargin operator-(const VoltageMargin& other) const;
                VoltageMargin operator*(const VoltageMargin& other) const;
                VoltageMargin operator/(const VoltageMargin& other) const;
                std::optional<VoltageMargin> intersect(const VoltageMargin& other) const;
                bool is_degenerate() const;
                std::string render() const;
            private:
                double lo_;
                double hi_;
            };
            """,
            """
            VoltageMargin::VoltageMargin(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw MarginError("lo exceeds hi");
            }
            double VoltageMargin::lo() const { return lo_; }
            double VoltageMargin::hi() const { return hi_; }
            VoltageMargin VoltageMargin::operator+(const VoltageMargin& other) const {
                return VoltageMargin(lo_ + other.lo_, hi_ + other.hi_);
            }
            VoltageMargin VoltageMargin::operator-(const VoltageMargin& other) const {
                return VoltageMargin(lo_ - other.hi_, hi_ - other.lo_);
            }
            VoltageMargin VoltageMargin::operator*(const VoltageMargin& other) const {
                double p1 = lo_ * other.lo_;
                double p2 = lo_ * other.hi_;
                double p3 = hi_ * other.lo_;
                double p4 = hi_ * other.hi_;
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return VoltageMargin(lo, hi);
            }
            VoltageMargin VoltageMargin::operator/(const VoltageMargin& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw MarginError("divisor straddles zero");
                return (*this) * VoltageMargin(1.0 / other.hi_, 1.0 / other.lo_);
            }
            std::optional<VoltageMargin> VoltageMargin::intersect(const VoltageMargin& other) const {
                double lo = std::max(lo_, other.lo_);
                double hi = std::min(hi_, other.hi_);
                if (lo > hi) return std::nullopt;
                return VoltageMargin(lo, hi);
            }
            bool VoltageMargin::is_degenerate() const { return lo_ == hi_; }
            std::string VoltageMargin::render() const {
                std::ostringstream out;
                out << "lo=" << std::fixed << std::setprecision(6) << lo_ << ";hi=" << hi_;
                return out.str();
            }
            """,
            """
            VoltageMargin::VoltageMargin(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw MarginError("lo exceeds hi");
            }
            double VoltageMargin::lo() const { return lo_; }
            double VoltageMargin::hi() const { return hi_; }
            VoltageMargin VoltageMargin::operator+(const VoltageMargin& other) const {
                return VoltageMargin(lo_ + other.lo_, hi_ + other.hi_);
            }
            VoltageMargin VoltageMargin::operator-(const VoltageMargin& other) const {
                return VoltageMargin(lo_ - other.hi_, hi_ - other.lo_);
            }
            VoltageMargin VoltageMargin::operator*(const VoltageMargin& other) const {
                return VoltageMargin(lo_ * other.lo_, hi_ * other.hi_);
            }
            VoltageMargin VoltageMargin::operator/(const VoltageMargin& other) const {
                if (other.lo_ <= 0.0 && other.hi_ >= 0.0) throw MarginError("divisor straddles zero");
                return (*this) * VoltageMargin(1.0 / other.hi_, 1.0 / other.lo_);
            }
            std::optional<VoltageMargin> VoltageMargin::intersect(const VoltageMargin& other) const {
                double lo = std::max(lo_, other.lo_);
                double hi = std::min(hi_, other.hi_);
                if (lo > hi) return std::nullopt;
                return VoltageMargin(lo, hi);
            }
            bool VoltageMargin::is_degenerate() const { return lo_ == hi_; }
            std::string VoltageMargin::render() const {
                std::ostringstream out;
                out << "lo=" << std::fixed << std::setprecision(6) << lo_ << ";hi=" << hi_;
                return out.str();
            }
            """,
            """
            VoltageMargin a(3.0, 4.2);
            if (a.is_degenerate()) return 1;
            VoltageMargin d(2.5, 2.5);
            if (!d.is_degenerate()) return 2;
            std::optional<VoltageMargin> i = a.intersect(VoltageMargin(4.0, 5.0));
            if (!i.has_value()) return 3;
            if (std::fabs(i->lo() - 4.0) > 1e-9 || std::fabs(i->hi() - 4.2) > 1e-9) return 4;
            if (a.intersect(VoltageMargin(5.0, 6.0)).has_value()) return 5;
            VoltageMargin p = a * VoltageMargin(2.0, 2.0);
            if (std::fabs(p.lo() - 6.0) > 1e-9 || std::fabs(p.hi() - 8.4) > 1e-9) return 6;
            if (a.render() != "lo=3.000000;hi=4.200000") return 7;
            return 0;
            """,
            """
            VoltageMargin m(-1.5, 2.0);
            VoltageMargin n(3.0, 4.0);
            VoltageMargin p = m * n;
            if (std::fabs(p.lo() + 6.0) > 1e-9 || std::fabs(p.hi() - 8.0) > 1e-9) return 1;
            std::optional<VoltageMargin> touch = VoltageMargin(1.0, 2.0).intersect(VoltageMargin(2.0, 3.0));
            if (!touch.has_value() || !touch->is_degenerate()) return 2;
            bool threw = false;
            try { VoltageMargin bad(4.0, 3.0); } catch (const MarginError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { VoltageMargin z(-1.0, 0.0); n / z; } catch (const MarginError&) { threw = true; }
            if (!threw) return 4;
            VoltageMargin q = n / VoltageMargin(1.0, 2.0);
            if (std::fabs(q.lo() - 1.5) > 1e-9 || std::fabs(q.hi() - 4.0) > 1e-9) return 5;
            VoltageMargin s = m + VoltageMargin(0.5, 0.5);
            if (std::fabs(s.lo() + 1.0) > 1e-9 || std::fabs(s.hi() - 2.5) > 1e-9) return 6;
            if (s.render() != "lo=-1.000000;hi=2.500000") return 7;
            VoltageMargin df = n - m;
            if (std::fabs(df.lo() - 1.0) > 1e-9 || std::fabs(df.hi() - 5.5) > 1e-9) return 8;
            return 0;
            """,
            "degenerate-point detection with optional intersection over validated endpoint pairs",
            "the endpoint-naive product (lo*lo, hi*hi) or treating touching ranges as disjoint",
            "degenerate only at equal endpoints, point intersections, mixed-sign product extrema, labeled render, and division by a range ending at zero",
            "degeneracy predicates plus optional intersection in a paired .h/.cpp API",
            "bounded range value type",
        ),
        c(
            "f26cpx-judging-score-bracket",
            "Judging score bracket",
            "score_bracket",
            """
            class BracketError : public std::domain_error {
            public:
                explicit BracketError(const std::string& message) : std::domain_error(message) {}
            };
            class ScoreBracket {
            public:
                ScoreBracket(double lo, double hi);
                double lo() const;
                double hi() const;
                ScoreBracket hull(const ScoreBracket& other) const;
                double midpoint() const;
                bool contains(double value) const;
            };
            ScoreBracket operator+(const ScoreBracket& left, const ScoreBracket& right);
            ScoreBracket operator-(const ScoreBracket& left, const ScoreBracket& right);
            ScoreBracket operator*(const ScoreBracket& left, const ScoreBracket& right);
            ScoreBracket operator/(const ScoreBracket& left, const ScoreBracket& right);
            bool same_band(const ScoreBracket& left, const ScoreBracket& right, double eps);
            """,
            """
            class BracketError : public std::domain_error {
            public:
                explicit BracketError(const std::string& message) : std::domain_error(message) {}
            };
            class ScoreBracket {
            public:
                ScoreBracket(double lo, double hi);
                double lo() const;
                double hi() const;
                ScoreBracket hull(const ScoreBracket& other) const;
                double midpoint() const;
                bool contains(double value) const;
            private:
                double lo_;
                double hi_;
            };
            ScoreBracket operator+(const ScoreBracket& left, const ScoreBracket& right);
            ScoreBracket operator-(const ScoreBracket& left, const ScoreBracket& right);
            ScoreBracket operator*(const ScoreBracket& left, const ScoreBracket& right);
            ScoreBracket operator/(const ScoreBracket& left, const ScoreBracket& right);
            bool same_band(const ScoreBracket& left, const ScoreBracket& right, double eps);
            """,
            """
            ScoreBracket::ScoreBracket(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw BracketError("lo exceeds hi");
            }
            double ScoreBracket::lo() const { return lo_; }
            double ScoreBracket::hi() const { return hi_; }
            ScoreBracket ScoreBracket::hull(const ScoreBracket& other) const {
                return ScoreBracket(std::min(lo_, other.lo_), std::max(hi_, other.hi_));
            }
            double ScoreBracket::midpoint() const { return (lo_ + hi_) / 2.0; }
            bool ScoreBracket::contains(double value) const { return lo_ <= value && value <= hi_; }
            ScoreBracket operator+(const ScoreBracket& left, const ScoreBracket& right) {
                return ScoreBracket(left.lo() + right.lo(), left.hi() + right.hi());
            }
            ScoreBracket operator-(const ScoreBracket& left, const ScoreBracket& right) {
                return ScoreBracket(left.lo() - right.hi(), left.hi() - right.lo());
            }
            ScoreBracket operator*(const ScoreBracket& left, const ScoreBracket& right) {
                double p1 = left.lo() * right.lo();
                double p2 = left.lo() * right.hi();
                double p3 = left.hi() * right.lo();
                double p4 = left.hi() * right.hi();
                double lo = std::min(std::min(p1, p2), std::min(p3, p4));
                double hi = std::max(std::max(p1, p2), std::max(p3, p4));
                return ScoreBracket(lo, hi);
            }
            ScoreBracket operator/(const ScoreBracket& left, const ScoreBracket& right) {
                if (right.lo() <= 0.0 && right.hi() >= 0.0) throw BracketError("divisor straddles zero");
                return left * ScoreBracket(1.0 / right.hi(), 1.0 / right.lo());
            }
            bool same_band(const ScoreBracket& left, const ScoreBracket& right, double eps) {
                return std::fabs(left.lo() - right.lo()) <= eps
                    && std::fabs(left.hi() - right.hi()) <= eps;
            }
            """,
            """
            ScoreBracket::ScoreBracket(double lo, double hi) : lo_(lo), hi_(hi) {
                if (lo_ > hi_) throw BracketError("lo exceeds hi");
            }
            double ScoreBracket::lo() const { return lo_; }
            double ScoreBracket::hi() const { return hi_; }
            ScoreBracket ScoreBracket::hull(const ScoreBracket& other) const {
                return ScoreBracket(std::min(lo_, other.lo_), std::max(hi_, other.hi_));
            }
            double ScoreBracket::midpoint() const { return (lo_ + hi_) / 2.0; }
            bool ScoreBracket::contains(double value) const { return lo_ <= value && value <= hi_; }
            ScoreBracket operator+(const ScoreBracket& left, const ScoreBracket& right) {
                return ScoreBracket(left.lo() + right.lo(), left.hi() + right.hi());
            }
            ScoreBracket operator-(const ScoreBracket& left, const ScoreBracket& right) {
                return ScoreBracket(left.lo() - right.hi(), left.hi() - right.lo());
            }
            ScoreBracket operator*(const ScoreBracket& left, const ScoreBracket& right) {
                return ScoreBracket(left.lo() * right.lo(), left.hi() * right.hi());
            }
            ScoreBracket operator/(const ScoreBracket& left, const ScoreBracket& right) {
                if (right.lo() <= 0.0 && right.hi() >= 0.0) throw BracketError("divisor straddles zero");
                return left * ScoreBracket(1.0 / right.hi(), 1.0 / right.lo());
            }
            bool same_band(const ScoreBracket& left, const ScoreBracket& right, double eps) {
                return std::fabs(left.lo() - right.lo()) <= eps
                    && std::fabs(left.hi() - right.hi()) <= eps;
            }
            """,
            """
            ScoreBracket a(5.0, 8.0);
            ScoreBracket b(6.0, 9.0);
            ScoreBracket h = a.hull(b);
            if (std::fabs(h.lo() - 5.0) > 1e-9 || std::fabs(h.hi() - 9.0) > 1e-9) return 1;
            if (std::fabs(a.midpoint() - 6.5) > 1e-9) return 2;
            if (!a.contains(8.0) || a.contains(8.5)) return 3;
            ScoreBracket s = a + b;
            if (std::fabs(s.lo() - 11.0) > 1e-9 || std::fabs(s.hi() - 17.0) > 1e-9) return 4;
            ScoreBracket p = a * b;
            if (std::fabs(p.lo() - 30.0) > 1e-9 || std::fabs(p.hi() - 72.0) > 1e-9) return 5;
            if (!same_band(a, ScoreBracket(5.0, 8.0 + 1e-12), 1e-9)) return 6;
            return 0;
            """,
            """
            ScoreBracket m(-3.0, 2.0);
            ScoreBracket n(4.0, 5.0);
            ScoreBracket p = m * n;
            if (std::fabs(p.lo() + 15.0) > 1e-9 || std::fabs(p.hi() - 10.0) > 1e-9) return 1;
            ScoreBracket h = (n - m).hull(m);
            if (std::fabs(h.lo() + 3.0) > 1e-9 || std::fabs(h.hi() - 8.0) > 1e-9) return 2;
            bool threw = false;
            try { ScoreBracket bad(9.0, 1.0); } catch (const BracketError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { ScoreBracket z(-0.5, 0.5); n / z; } catch (const BracketError&) { threw = true; }
            if (!threw) return 4;
            ScoreBracket q = n / ScoreBracket(2.0, 4.0);
            if (std::fabs(q.lo() - 1.0) > 1e-9 || std::fabs(q.hi() - 2.5) > 1e-9) return 5;
            if (same_band(m, ScoreBracket(-3.0, 2.0 + 1e-6), 1e-9)) return 6;
            if (std::fabs(ScoreBracket(1.0, 3.0).midpoint() - 2.0) > 1e-9) return 7;
            if (!m.contains(0.0)) return 8;
            return 0;
            """,
            "hull after subtraction with midpoint and containment over validated endpoint pairs",
            "the endpoint-naive product (lo*lo, hi*hi) or a hull that discards endpoints",
            "hull after subtraction, tolerance boundaries, mixed-sign product extrema, inclusive containment, and zero-straddle division rejection",
            "combined hull and tolerance surface distinct from sibling range shapes in a paired .h/.cpp API",
            "bounded range value type",
        ),
        c(
            "f26cpx-sail-trim-heading",
            "Sail trim heading",
            "sail_trim",
            """
            class HeadingError : public std::domain_error {
            public:
                explicit HeadingError(const std::string& message) : std::domain_error(message) {}
            };
            class HeadingVec {
            public:
                HeadingVec(double east, double north);
                double east() const;
                double north() const;
                HeadingVec operator+(const HeadingVec& other) const;
                HeadingVec operator-(const HeadingVec& other) const;
                HeadingVec operator*(double factor) const;
                double dot(const HeadingVec& other) const;
                double perp(const HeadingVec& other) const;
                double length() const;
                HeadingVec unit() const;
                HeadingVec rotate(double radians) const;
            };
            HeadingVec operator*(double factor, const HeadingVec& value);
            bool nearly_equal(const HeadingVec& left, const HeadingVec& right, double eps);
            """,
            """
            class HeadingError : public std::domain_error {
            public:
                explicit HeadingError(const std::string& message) : std::domain_error(message) {}
            };
            class HeadingVec {
            public:
                HeadingVec(double east, double north);
                double east() const;
                double north() const;
                HeadingVec operator+(const HeadingVec& other) const;
                HeadingVec operator-(const HeadingVec& other) const;
                HeadingVec operator*(double factor) const;
                double dot(const HeadingVec& other) const;
                double perp(const HeadingVec& other) const;
                double length() const;
                HeadingVec unit() const;
                HeadingVec rotate(double radians) const;
            private:
                double east_;
                double north_;
            };
            HeadingVec operator*(double factor, const HeadingVec& value);
            bool nearly_equal(const HeadingVec& left, const HeadingVec& right, double eps);
            """,
            """
            HeadingVec::HeadingVec(double east, double north) : east_(east), north_(north) {}
            double HeadingVec::east() const { return east_; }
            double HeadingVec::north() const { return north_; }
            HeadingVec HeadingVec::operator+(const HeadingVec& other) const {
                return HeadingVec(east_ + other.east_, north_ + other.north_);
            }
            HeadingVec HeadingVec::operator-(const HeadingVec& other) const {
                return HeadingVec(east_ - other.east_, north_ - other.north_);
            }
            HeadingVec HeadingVec::operator*(double factor) const {
                return HeadingVec(factor * east_, factor * north_);
            }
            double HeadingVec::dot(const HeadingVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            double HeadingVec::perp(const HeadingVec& other) const {
                return east_ * other.north_ - north_ * other.east_;
            }
            double HeadingVec::length() const {
                return std::sqrt(east_ * east_ + north_ * north_);
            }
            HeadingVec HeadingVec::unit() const {
                double len = length();
                if (len == 0.0) throw HeadingError("unit of a zero vector");
                return HeadingVec(east_ / len, north_ / len);
            }
            HeadingVec HeadingVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return HeadingVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            HeadingVec operator*(double factor, const HeadingVec& value) {
                return value * factor;
            }
            bool nearly_equal(const HeadingVec& left, const HeadingVec& right, double eps) {
                return std::fabs(left.east() - right.east()) <= eps
                    && std::fabs(left.north() - right.north()) <= eps;
            }
            """,
            """
            HeadingVec::HeadingVec(double east, double north) : east_(east), north_(north) {}
            double HeadingVec::east() const { return east_; }
            double HeadingVec::north() const { return north_; }
            HeadingVec HeadingVec::operator+(const HeadingVec& other) const {
                return HeadingVec(east_ + other.east_, north_ + other.north_);
            }
            HeadingVec HeadingVec::operator-(const HeadingVec& other) const {
                return HeadingVec(east_ - other.east_, north_ - other.north_);
            }
            HeadingVec HeadingVec::operator*(double factor) const {
                return HeadingVec(factor * east_, factor * north_);
            }
            double HeadingVec::dot(const HeadingVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            double HeadingVec::perp(const HeadingVec& other) const {
                return east_ * other.north_ - north_ * other.east_;
            }
            double HeadingVec::length() const {
                return std::sqrt(east_ * east_ + north_ * north_);
            }
            HeadingVec HeadingVec::unit() const {
                double len = length();
                if (len == 0.0) throw HeadingError("unit of a zero vector");
                return HeadingVec(east_ / (len * len), north_ / (len * len));
            }
            HeadingVec HeadingVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return HeadingVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            HeadingVec operator*(double factor, const HeadingVec& value) {
                return value * factor;
            }
            bool nearly_equal(const HeadingVec& left, const HeadingVec& right, double eps) {
                return std::fabs(left.east() - right.east()) <= eps
                    && std::fabs(left.north() - right.north()) <= eps;
            }
            """,
            """
            HeadingVec a(3.0, 4.0);
            if (std::fabs(a.length() - 5.0) > 1e-9) return 1;
            HeadingVec b(1.0, -2.0);
            HeadingVec s = a + b;
            if (std::fabs(s.east() - 4.0) > 1e-9 || std::fabs(s.north() - 2.0) > 1e-9) return 2;
            if (std::fabs(a.dot(b) + 5.0) > 1e-9) return 3;
            if (std::fabs(a.perp(b) + 10.0) > 1e-9) return 4;
            HeadingVec r = HeadingVec(1.0, 0.0).rotate(3.14159265358979323846 / 2.0);
            if (std::fabs(r.east()) > 1e-9 || std::fabs(r.north() - 1.0) > 1e-9) return 5;
            HeadingVec u = a.unit();
            if (std::fabs(u.east() - 0.6) > 1e-9 || std::fabs(u.north() - 0.8) > 1e-9) return 6;
            HeadingVec m = 2.0 * b;
            if (std::fabs(m.east() - 2.0) > 1e-9 || std::fabs(m.north() + 4.0) > 1e-9) return 7;
            if (!nearly_equal(a, HeadingVec(3.0, 4.0 + 1e-12), 1e-9)) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { HeadingVec(0.0, 0.0).unit(); } catch (const HeadingError&) { threw = true; }
            if (!threw) return 1;
            const double kPi = 3.14159265358979323846;
            HeadingVec x(1.0, 0.0);
            HeadingVec half = x.rotate(kPi);
            if (std::fabs(half.east() + 1.0) > 1e-9 || std::fabs(half.north()) > 1e-9) return 2;
            HeadingVec two = x.rotate(kPi / 4.0).rotate(kPi / 4.0);
            if (std::fabs(two.east()) > 1e-9 || std::fabs(two.north() - 1.0) > 1e-9) return 3;
            HeadingVec y(0.0, 1.0);
            if (std::fabs(x.perp(y) - 1.0) > 1e-9) return 4;
            if (std::fabs(y.perp(x) + 1.0) > 1e-9) return 5;
            HeadingVec d = x - y;
            if (std::fabs(d.east() - 1.0) > 1e-9 || std::fabs(d.north() + 1.0) > 1e-9) return 6;
            HeadingVec sc = HeadingVec(1.0, 2.0) * -3.0;
            if (std::fabs(sc.east() + 3.0) > 1e-9 || std::fabs(sc.north() + 6.0) > 1e-9) return 7;
            if (nearly_equal(x, HeadingVec(1.0 + 1e-6, 0.0), 1e-9)) return 8;
            HeadingVec rot = HeadingVec(2.0, 1.0).rotate(-kPi / 2.0);
            if (std::fabs(rot.east() - 1.0) > 1e-9 || std::fabs(rot.north() + 2.0) > 1e-9) return 9;
            return 0;
            """,
            "counterclockwise rotation and exact unit direction over an owned coordinate pair",
            "std::complex, <complex>, or any geometry library type; do not rotate clockwise and do not divide by the squared length in unit",
            "unit rejection at the origin, rotation by multiples and compositions of pi/2, perp antisymmetry, and tolerance boundaries",
            "rotation sign discipline as the rejection discriminator in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-rover-steering-offset",
            "Rover steering offset",
            "rover_steering",
            """
            class SteerError : public std::domain_error {
            public:
                explicit SteerError(const std::string& message) : std::domain_error(message) {}
            };
            class SteerVec {
            public:
                SteerVec(double east, double north);
                double east() const;
                double north() const;
                SteerVec operator+(const SteerVec& other) const;
                SteerVec operator-(const SteerVec& other) const;
                double bearing() const;
                SteerVec project_onto(const SteerVec& other) const;
                double length() const;
                std::string render() const;
            };
            SteerVec operator*(double factor, const SteerVec& value);
            """,
            """
            class SteerError : public std::domain_error {
            public:
                explicit SteerError(const std::string& message) : std::domain_error(message) {}
            };
            class SteerVec {
            public:
                SteerVec(double east, double north);
                double east() const;
                double north() const;
                SteerVec operator+(const SteerVec& other) const;
                SteerVec operator-(const SteerVec& other) const;
                double bearing() const;
                SteerVec project_onto(const SteerVec& other) const;
                double length() const;
                std::string render() const;
            private:
                double east_;
                double north_;
            };
            SteerVec operator*(double factor, const SteerVec& value);
            """,
            """
            SteerVec::SteerVec(double east, double north) : east_(east), north_(north) {}
            double SteerVec::east() const { return east_; }
            double SteerVec::north() const { return north_; }
            SteerVec SteerVec::operator+(const SteerVec& other) const {
                return SteerVec(east_ + other.east_, north_ + other.north_);
            }
            SteerVec SteerVec::operator-(const SteerVec& other) const {
                return SteerVec(east_ - other.east_, north_ - other.north_);
            }
            double SteerVec::bearing() const {
                return std::atan2(east_, north_);
            }
            SteerVec SteerVec::project_onto(const SteerVec& other) const {
                double norm = other.east_ * other.east_ + other.north_ * other.north_;
                if (norm == 0.0) throw SteerError("projection onto a zero vector");
                double scale = (east_ * other.east_ + north_ * other.north_) / norm;
                return SteerVec(scale * other.east_, scale * other.north_);
            }
            double SteerVec::length() const {
                return std::sqrt(east_ * east_ + north_ * north_);
            }
            std::string SteerVec::render() const {
                std::ostringstream out;
                out << "east=" << std::fixed << std::setprecision(6) << east_ << ";north=" << north_;
                return out.str();
            }
            SteerVec operator*(double factor, const SteerVec& value) {
                return SteerVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            SteerVec::SteerVec(double east, double north) : east_(east), north_(north) {}
            double SteerVec::east() const { return east_; }
            double SteerVec::north() const { return north_; }
            SteerVec SteerVec::operator+(const SteerVec& other) const {
                return SteerVec(east_ + other.east_, north_ + other.north_);
            }
            SteerVec SteerVec::operator-(const SteerVec& other) const {
                return SteerVec(east_ - other.east_, north_ - other.north_);
            }
            double SteerVec::bearing() const {
                return std::atan2(north_, east_);
            }
            SteerVec SteerVec::project_onto(const SteerVec& other) const {
                double norm = other.east_ * other.east_ + other.north_ * other.north_;
                if (norm == 0.0) throw SteerError("projection onto a zero vector");
                double scale = (east_ * other.east_ + north_ * other.north_) / norm;
                return SteerVec(scale * other.east_, scale * other.north_);
            }
            double SteerVec::length() const {
                return std::sqrt(east_ * east_ + north_ * north_);
            }
            std::string SteerVec::render() const {
                std::ostringstream out;
                out << "east=" << std::fixed << std::setprecision(6) << east_ << ";north=" << north_;
                return out.str();
            }
            SteerVec operator*(double factor, const SteerVec& value) {
                return SteerVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            SteerVec a(0.0, 5.0);
            if (std::fabs(a.bearing()) > 1e-9) return 1;
            SteerVec b(5.0, 0.0);
            if (std::fabs(b.bearing() - 3.14159265358979323846 / 2.0) > 1e-9) return 2;
            SteerVec s = a + b;
            if (std::fabs(s.bearing() - 3.14159265358979323846 / 4.0) > 1e-9) return 3;
            SteerVec target(4.0, 0.0);
            SteerVec p = SteerVec(2.0, 2.0).project_onto(target);
            if (std::fabs(p.east() - 2.0) > 1e-9 || std::fabs(p.north()) > 1e-9) return 4;
            if (std::fabs(s.length() - std::sqrt(50.0)) > 1e-9) return 5;
            if (b.render() != "east=5.000000;north=0.000000") return 6;
            SteerVec m = 3.0 * a;
            if (std::fabs(m.east()) > 1e-9 || std::fabs(m.north() - 15.0) > 1e-9) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { SteerVec(1.0, 1.0).project_onto(SteerVec(0.0, 0.0)); } catch (const SteerError&) { threw = true; }
            if (!threw) return 1;
            const double kPi = 3.14159265358979323846;
            SteerVec south(0.0, -1.0);
            if (std::fabs(std::fabs(south.bearing()) - kPi) > 1e-9) return 2;
            SteerVec west(-1.0, 0.0);
            if (std::fabs(west.bearing() + kPi / 2.0) > 1e-9) return 3;
            SteerVec d = SteerVec(3.0, 4.0) - SteerVec(1.0, 1.0);
            if (std::fabs(d.east() - 2.0) > 1e-9 || std::fabs(d.north() - 3.0) > 1e-9) return 4;
            if (d.render() != "east=2.000000;north=3.000000") return 5;
            SteerVec p = SteerVec(0.0, 5.0).project_onto(SteerVec(0.0, -1.0));
            if (std::fabs(p.east()) > 1e-9 || std::fabs(p.north() - 5.0) > 1e-9) return 6;
            SteerVec n = -2.0 * d;
            if (std::fabs(n.east() + 4.0) > 1e-9 || std::fabs(n.north() + 6.0) > 1e-9) return 7;
            if (std::fabs(SteerVec(1.0, 1.0).bearing() - kPi / 4.0) > 1e-9) return 8;
            return 0;
            """,
            "argument-ordered clockwise-from-north bearing and squared-norm projection over an owned coordinate pair",
            "std::complex, <complex>, or any geometry library type; do not swap the atan2 argument order and do not project by the unsquared length",
            "bearing quadrant boundaries, projection onto a zero vector, exact render bytes, and scalar-left multiplication",
            "bearing argument-order discipline with an exact readout in a project-context paired .h/.cpp layout",
            "planar vector value type",
            project_support=True,
        ),
        c(
            "f26cpx-drone-waypoint-drift",
            "Drone waypoint drift",
            "waypoint_drift",
            """
            class DriftError : public std::domain_error {
            public:
                explicit DriftError(const std::string& message) : std::domain_error(message) {}
            };
            class DriftVec {
            public:
                DriftVec(double east, double north);
                double east() const;
                double north() const;
                double length() const;
                double distance_to(const DriftVec& other) const;
                DriftVec rotate(double radians) const;
                bool within(const DriftVec& other, double eps) const;
            };
            DriftVec operator+(const DriftVec& left, const DriftVec& right);
            DriftVec operator-(const DriftVec& left, const DriftVec& right);
            DriftVec operator*(const DriftVec& value, double factor);
            """,
            """
            class DriftError : public std::domain_error {
            public:
                explicit DriftError(const std::string& message) : std::domain_error(message) {}
            };
            class DriftVec {
            public:
                DriftVec(double east, double north);
                double east() const;
                double north() const;
                double length() const;
                double distance_to(const DriftVec& other) const;
                DriftVec rotate(double radians) const;
                bool within(const DriftVec& other, double eps) const;
            private:
                double east_;
                double north_;
            };
            DriftVec operator+(const DriftVec& left, const DriftVec& right);
            DriftVec operator-(const DriftVec& left, const DriftVec& right);
            DriftVec operator*(const DriftVec& value, double factor);
            """,
            """
            DriftVec::DriftVec(double east, double north) : east_(east), north_(north) {}
            double DriftVec::east() const { return east_; }
            double DriftVec::north() const { return north_; }
            double DriftVec::length() const {
                return std::sqrt(east_ * east_ + north_ * north_);
            }
            double DriftVec::distance_to(const DriftVec& other) const {
                double de = other.east_ - east_;
                double dn = other.north_ - north_;
                return std::sqrt(de * de + dn * dn);
            }
            DriftVec DriftVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return DriftVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            bool DriftVec::within(const DriftVec& other, double eps) const {
                return std::fabs(east_ - other.east_) <= eps
                    && std::fabs(north_ - other.north_) <= eps;
            }
            DriftVec operator+(const DriftVec& left, const DriftVec& right) {
                return DriftVec(left.east() + right.east(), left.north() + right.north());
            }
            DriftVec operator-(const DriftVec& left, const DriftVec& right) {
                return DriftVec(left.east() - right.east(), left.north() - right.north());
            }
            DriftVec operator*(const DriftVec& value, double factor) {
                return DriftVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            DriftVec::DriftVec(double east, double north) : east_(east), north_(north) {}
            double DriftVec::east() const { return east_; }
            double DriftVec::north() const { return north_; }
            double DriftVec::length() const {
                return std::sqrt(east_ * east_ + north_ * north_);
            }
            double DriftVec::distance_to(const DriftVec& other) const {
                double de = other.east_ - east_;
                double dn = other.north_ - north_;
                return std::sqrt(de * de + dn * dn);
            }
            DriftVec DriftVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return DriftVec(east_ * c + north_ * s, -east_ * s + north_ * c);
            }
            bool DriftVec::within(const DriftVec& other, double eps) const {
                return std::fabs(east_ - other.east_) <= eps
                    && std::fabs(north_ - other.north_) <= eps;
            }
            DriftVec operator+(const DriftVec& left, const DriftVec& right) {
                return DriftVec(left.east() + right.east(), left.north() + right.north());
            }
            DriftVec operator-(const DriftVec& left, const DriftVec& right) {
                return DriftVec(left.east() - right.east(), left.north() - right.north());
            }
            DriftVec operator*(const DriftVec& value, double factor) {
                return DriftVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            DriftVec a(1.0, 2.0);
            DriftVec b(4.0, 6.0);
            if (std::fabs(a.distance_to(b) - 5.0) > 1e-9) return 1;
            DriftVec s = a + b;
            if (std::fabs(s.east() - 5.0) > 1e-9 || std::fabs(s.north() - 8.0) > 1e-9) return 2;
            DriftVec r = a.rotate(3.14159265358979323846);
            if (std::fabs(r.east() + 1.0) > 1e-9 || std::fabs(r.north() + 2.0) > 1e-9) return 3;
            if (std::fabs(b.length() - std::sqrt(52.0)) > 1e-9) return 4;
            DriftVec m = b * 0.5;
            if (std::fabs(m.east() - 2.0) > 1e-9 || std::fabs(m.north() - 3.0) > 1e-9) return 5;
            if (!a.within(DriftVec(1.0, 2.0 + 1e-12), 1e-9)) return 6;
            return 0;
            """,
            """
            const double kPi = 3.14159265358979323846;
            DriftVec x(2.0, 0.0);
            DriftVec ccw = x.rotate(kPi / 2.0);
            if (std::fabs(ccw.east()) > 1e-9 || std::fabs(ccw.north() - 2.0) > 1e-9) return 1;
            DriftVec cw = x.rotate(-kPi / 2.0);
            if (std::fabs(cw.east()) > 1e-9 || std::fabs(cw.north() + 2.0) > 1e-9) return 2;
            DriftVec a(1.0, 1.0);
            DriftVec b(1.0, 1.0);
            if (std::fabs(a.distance_to(b)) > 1e-12) return 3;
            if (std::fabs(a.distance_to(DriftVec(-1.0, -1.0)) - std::sqrt(8.0)) > 1e-9) return 4;
            DriftVec d = a - DriftVec(3.0, 4.0);
            if (std::fabs(d.east() + 2.0) > 1e-9 || std::fabs(d.north() + 3.0) > 1e-9) return 5;
            if (a.within(DriftVec(1.0, 1.0 + 1e-6), 1e-9)) return 6;
            DriftVec m = DriftVec(2.0, -4.0) * -1.5;
            if (std::fabs(m.east() + 3.0) > 1e-9 || std::fabs(m.north() - 6.0) > 1e-9) return 7;
            return 0;
            """,
            "free-operator plane geometry with counterclockwise rotation, symmetric distance, and member tolerance",
            "std::complex, <complex>, or any geometry library type; do not rotate clockwise",
            "rotation sign in both directions, distance symmetry and self-distance, member tolerance boundaries, and negative scalar multiplication",
            "distance-plus-rotation surface distinct from the bearing roots in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-billiard-cushion-shot",
            "Billiard cushion shot",
            "cushion_shot",
            """
            class ShotError : public std::domain_error {
            public:
                explicit ShotError(const std::string& message) : std::domain_error(message) {}
            };
            class ShotVec {
            public:
                ShotVec(double east, double north);
                double east() const;
                double north() const;
                ShotVec operator+(const ShotVec& other) const;
                ShotVec operator-(const ShotVec& other) const;
                ShotVec reflect_east() const;
                ShotVec reflect_north() const;
                ShotVec unit() const;
                double dot(const ShotVec& other) const;
                double perp(const ShotVec& other) const;
            };
            """,
            """
            class ShotError : public std::domain_error {
            public:
                explicit ShotError(const std::string& message) : std::domain_error(message) {}
            };
            class ShotVec {
            public:
                ShotVec(double east, double north);
                double east() const;
                double north() const;
                ShotVec operator+(const ShotVec& other) const;
                ShotVec operator-(const ShotVec& other) const;
                ShotVec reflect_east() const;
                ShotVec reflect_north() const;
                ShotVec unit() const;
                double dot(const ShotVec& other) const;
                double perp(const ShotVec& other) const;
            private:
                double east_;
                double north_;
            };
            """,
            """
            ShotVec::ShotVec(double east, double north) : east_(east), north_(north) {}
            double ShotVec::east() const { return east_; }
            double ShotVec::north() const { return north_; }
            ShotVec ShotVec::operator+(const ShotVec& other) const {
                return ShotVec(east_ + other.east_, north_ + other.north_);
            }
            ShotVec ShotVec::operator-(const ShotVec& other) const {
                return ShotVec(east_ - other.east_, north_ - other.north_);
            }
            ShotVec ShotVec::reflect_east() const {
                return ShotVec(-east_, north_);
            }
            ShotVec ShotVec::reflect_north() const {
                return ShotVec(east_, -north_);
            }
            ShotVec ShotVec::unit() const {
                double len = std::sqrt(east_ * east_ + north_ * north_);
                if (len == 0.0) throw ShotError("unit of a zero vector");
                return ShotVec(east_ / len, north_ / len);
            }
            double ShotVec::dot(const ShotVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            double ShotVec::perp(const ShotVec& other) const {
                return east_ * other.north_ - north_ * other.east_;
            }
            """,
            """
            ShotVec::ShotVec(double east, double north) : east_(east), north_(north) {}
            double ShotVec::east() const { return east_; }
            double ShotVec::north() const { return north_; }
            ShotVec ShotVec::operator+(const ShotVec& other) const {
                return ShotVec(east_ + other.east_, north_ + other.north_);
            }
            ShotVec ShotVec::operator-(const ShotVec& other) const {
                return ShotVec(east_ - other.east_, north_ - other.north_);
            }
            ShotVec ShotVec::reflect_east() const {
                return ShotVec(north_, east_);
            }
            ShotVec ShotVec::reflect_north() const {
                return ShotVec(north_, east_);
            }
            ShotVec ShotVec::unit() const {
                double len = std::sqrt(east_ * east_ + north_ * north_);
                if (len == 0.0) throw ShotError("unit of a zero vector");
                return ShotVec(east_ / len, north_ / len);
            }
            double ShotVec::dot(const ShotVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            double ShotVec::perp(const ShotVec& other) const {
                return east_ * other.north_ - north_ * other.east_;
            }
            """,
            """
            ShotVec a(3.0, 4.0);
            ShotVec re = a.reflect_east();
            if (std::fabs(re.east() + 3.0) > 1e-9 || std::fabs(re.north() - 4.0) > 1e-9) return 1;
            ShotVec rn = a.reflect_north();
            if (std::fabs(rn.east() - 3.0) > 1e-9 || std::fabs(rn.north() + 4.0) > 1e-9) return 2;
            ShotVec u = a.unit();
            if (std::fabs(u.east() - 0.6) > 1e-9 || std::fabs(u.north() - 0.8) > 1e-9) return 3;
            ShotVec b(1.0, 2.0);
            if (std::fabs(a.dot(b) - 11.0) > 1e-9) return 4;
            if (std::fabs(a.perp(b) - 2.0) > 1e-9) return 5;
            ShotVec s = a + b;
            if (std::fabs(s.east() - 4.0) > 1e-9 || std::fabs(s.north() - 6.0) > 1e-9) return 6;
            return 0;
            """,
            """
            ShotVec a(2.0, -3.0);
            ShotVec twice = a.reflect_east().reflect_east();
            if (std::fabs(twice.east() - 2.0) > 1e-9 || std::fabs(twice.north() + 3.0) > 1e-9) return 1;
            ShotVec both = a.reflect_east().reflect_north();
            if (std::fabs(both.east() + 2.0) > 1e-9 || std::fabs(both.north() - 3.0) > 1e-9) return 2;
            ShotVec reflected = a.reflect_north();
            if (std::fabs(reflected.dot(reflected) - a.dot(a)) > 1e-9) return 3;
            bool threw = false;
            try { ShotVec(0.0, 0.0).unit(); } catch (const ShotError&) { threw = true; }
            if (!threw) return 4;
            ShotVec d = a - ShotVec(2.0, -3.0);
            if (std::fabs(d.east()) > 1e-12 || std::fabs(d.north()) > 1e-12) return 5;
            ShotVec x(1.0, 0.0);
            ShotVec y(0.0, 1.0);
            if (std::fabs(x.perp(y) - 1.0) > 1e-9) return 6;
            if (std::fabs(y.perp(x) + 1.0) > 1e-9) return 7;
            if (std::fabs(x.dot(y)) > 1e-12) return 8;
            return 0;
            """,
            "single-component reflection involutions that negate rather than swap components",
            "std::complex, <complex>, or any geometry library type; do not swap the two components on reflection",
            "double reflection identity, combined reflections negating both components, length preservation, unit rejection at the origin, and perp antisymmetry",
            "involution semantics as the rejection discriminator in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-lava-flow-front",
            "Lava flow front",
            "lava_flow",
            """
            class FlowError : public std::domain_error {
            public:
                explicit FlowError(const std::string& message) : std::domain_error(message) {}
            };
            class FlowVec {
            public:
                FlowVec(double east, double north);
                double east() const;
                double north() const;
                double length_sq() const;
                double bearing() const;
                FlowVec rotate(double radians) const;
                std::string render() const;
            };
            FlowVec operator+(const FlowVec& left, const FlowVec& right);
            FlowVec operator-(const FlowVec& left, const FlowVec& right);
            FlowVec operator*(double factor, const FlowVec& value);
            """,
            """
            class FlowError : public std::domain_error {
            public:
                explicit FlowError(const std::string& message) : std::domain_error(message) {}
            };
            class FlowVec {
            public:
                FlowVec(double east, double north);
                double east() const;
                double north() const;
                double length_sq() const;
                double bearing() const;
                FlowVec rotate(double radians) const;
                std::string render() const;
            private:
                double east_;
                double north_;
            };
            FlowVec operator+(const FlowVec& left, const FlowVec& right);
            FlowVec operator-(const FlowVec& left, const FlowVec& right);
            FlowVec operator*(double factor, const FlowVec& value);
            """,
            """
            FlowVec::FlowVec(double east, double north) : east_(east), north_(north) {}
            double FlowVec::east() const { return east_; }
            double FlowVec::north() const { return north_; }
            double FlowVec::length_sq() const {
                return east_ * east_ + north_ * north_;
            }
            double FlowVec::bearing() const {
                return std::atan2(north_, east_);
            }
            FlowVec FlowVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return FlowVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            std::string FlowVec::render() const {
                std::ostringstream out;
                out << "east=" << std::fixed << std::setprecision(6) << east_ << ";north=" << north_;
                return out.str();
            }
            FlowVec operator+(const FlowVec& left, const FlowVec& right) {
                return FlowVec(left.east() + right.east(), left.north() + right.north());
            }
            FlowVec operator-(const FlowVec& left, const FlowVec& right) {
                return FlowVec(left.east() - right.east(), left.north() - right.north());
            }
            FlowVec operator*(double factor, const FlowVec& value) {
                return FlowVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            FlowVec::FlowVec(double east, double north) : east_(east), north_(north) {}
            double FlowVec::east() const { return east_; }
            double FlowVec::north() const { return north_; }
            double FlowVec::length_sq() const {
                return east_ * east_ + north_ * north_;
            }
            double FlowVec::bearing() const {
                return std::atan2(east_, north_);
            }
            FlowVec FlowVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return FlowVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            std::string FlowVec::render() const {
                std::ostringstream out;
                out << "east=" << std::fixed << std::setprecision(6) << east_ << ";north=" << north_;
                return out.str();
            }
            FlowVec operator+(const FlowVec& left, const FlowVec& right) {
                return FlowVec(left.east() + right.east(), left.north() + right.north());
            }
            FlowVec operator-(const FlowVec& left, const FlowVec& right) {
                return FlowVec(left.east() - right.east(), left.north() - right.north());
            }
            FlowVec operator*(double factor, const FlowVec& value) {
                return FlowVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            FlowVec a(3.0, 4.0);
            if (std::fabs(a.length_sq() - 25.0) > 1e-9) return 1;
            if (std::fabs(a.bearing() - std::atan2(4.0, 3.0)) > 1e-12) return 2;
            FlowVec b(1.0, 0.0);
            if (std::fabs(b.bearing()) > 1e-12) return 3;
            FlowVec r = b.rotate(3.14159265358979323846 / 2.0);
            if (std::fabs(r.east()) > 1e-9 || std::fabs(r.north() - 1.0) > 1e-9) return 4;
            FlowVec s = a + b;
            if (std::fabs(s.east() - 4.0) > 1e-9 || std::fabs(s.north() - 4.0) > 1e-9) return 5;
            if (a.render() != "east=3.000000;north=4.000000") return 6;
            FlowVec m = 2.0 * a;
            if (std::fabs(m.east() - 6.0) > 1e-9 || std::fabs(m.north() - 8.0) > 1e-9) return 7;
            return 0;
            """,
            """
            const double kPi = 3.14159265358979323846;
            FlowVec y(0.0, 2.0);
            if (std::fabs(y.bearing() - kPi / 2.0) > 1e-9) return 1;
            FlowVec nx(-1.0, 0.0);
            if (std::fabs(std::fabs(nx.bearing()) - kPi) > 1e-9) return 2;
            FlowVec two = FlowVec(1.0, 1.0).rotate(kPi / 4.0).rotate(kPi / 4.0);
            if (std::fabs(two.east() + 1.0) > 1e-9 || std::fabs(two.north() - 1.0) > 1e-9) return 3;
            FlowVec d = FlowVec(5.0, 5.0) - FlowVec(2.0, 1.0);
            if (std::fabs(d.length_sq() - 25.0) > 1e-9) return 4;
            if (d.render() != "east=3.000000;north=4.000000") return 5;
            FlowVec m = -1.0 * d;
            if (std::fabs(m.east() + 3.0) > 1e-9 || std::fabs(m.north() + 4.0) > 1e-9) return 6;
            if (std::fabs(FlowVec(0.0, 0.0).bearing()) > 1e-12) return 7;
            return 0;
            """,
            "squared-length discipline with a standard counterclockwise-from-east bearing and rotation composition",
            "std::complex, <complex>, or any geometry library type; do not swap the atan2 argument order",
            "squared length avoiding the square root, bearing on the axes, rotation composition, and exact render bytes",
            "squared-length contrast with sibling length roots in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-crane-tip-deflection",
            "Crane tip deflection",
            "crane_tip",
            """
            class DeflectionError : public std::domain_error {
            public:
                explicit DeflectionError(const std::string& message) : std::domain_error(message) {}
            };
            class DeflectionVec {
            public:
                DeflectionVec(double east, double north);
                double east() const;
                double north() const;
                DeflectionVec operator+(const DeflectionVec& other) const;
                DeflectionVec operator-(const DeflectionVec& other) const;
                DeflectionVec operator*(double factor) const;
                DeflectionVec unit() const;
                DeflectionVec project_onto(const DeflectionVec& other) const;
                double dot(const DeflectionVec& other) const;
            };
            bool nearly_equal(const DeflectionVec& left, const DeflectionVec& right, double eps);
            """,
            """
            class DeflectionError : public std::domain_error {
            public:
                explicit DeflectionError(const std::string& message) : std::domain_error(message) {}
            };
            class DeflectionVec {
            public:
                DeflectionVec(double east, double north);
                double east() const;
                double north() const;
                DeflectionVec operator+(const DeflectionVec& other) const;
                DeflectionVec operator-(const DeflectionVec& other) const;
                DeflectionVec operator*(double factor) const;
                DeflectionVec unit() const;
                DeflectionVec project_onto(const DeflectionVec& other) const;
                double dot(const DeflectionVec& other) const;
            private:
                double east_;
                double north_;
            };
            bool nearly_equal(const DeflectionVec& left, const DeflectionVec& right, double eps);
            """,
            """
            DeflectionVec::DeflectionVec(double east, double north) : east_(east), north_(north) {}
            double DeflectionVec::east() const { return east_; }
            double DeflectionVec::north() const { return north_; }
            DeflectionVec DeflectionVec::operator+(const DeflectionVec& other) const {
                return DeflectionVec(east_ + other.east_, north_ + other.north_);
            }
            DeflectionVec DeflectionVec::operator-(const DeflectionVec& other) const {
                return DeflectionVec(east_ - other.east_, north_ - other.north_);
            }
            DeflectionVec DeflectionVec::operator*(double factor) const {
                return DeflectionVec(factor * east_, factor * north_);
            }
            DeflectionVec DeflectionVec::unit() const {
                double len = std::sqrt(east_ * east_ + north_ * north_);
                if (len == 0.0) throw DeflectionError("unit of a zero vector");
                return DeflectionVec(east_ / len, north_ / len);
            }
            DeflectionVec DeflectionVec::project_onto(const DeflectionVec& other) const {
                double norm = other.east_ * other.east_ + other.north_ * other.north_;
                if (norm == 0.0) throw DeflectionError("projection onto a zero vector");
                double scale = (east_ * other.east_ + north_ * other.north_) / norm;
                return DeflectionVec(scale * other.east_, scale * other.north_);
            }
            double DeflectionVec::dot(const DeflectionVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            bool nearly_equal(const DeflectionVec& left, const DeflectionVec& right, double eps) {
                return std::fabs(left.east() - right.east()) <= eps
                    && std::fabs(left.north() - right.north()) <= eps;
            }
            """,
            """
            DeflectionVec::DeflectionVec(double east, double north) : east_(east), north_(north) {}
            double DeflectionVec::east() const { return east_; }
            double DeflectionVec::north() const { return north_; }
            DeflectionVec DeflectionVec::operator+(const DeflectionVec& other) const {
                return DeflectionVec(east_ + other.east_, north_ + other.north_);
            }
            DeflectionVec DeflectionVec::operator-(const DeflectionVec& other) const {
                return DeflectionVec(east_ - other.east_, north_ - other.north_);
            }
            DeflectionVec DeflectionVec::operator*(double factor) const {
                return DeflectionVec(factor * east_, factor * north_);
            }
            DeflectionVec DeflectionVec::unit() const {
                double len = std::sqrt(east_ * east_ + north_ * north_);
                if (len == 0.0) throw DeflectionError("unit of a zero vector");
                return DeflectionVec(east_ / len, north_ / len);
            }
            DeflectionVec DeflectionVec::project_onto(const DeflectionVec& other) const {
                double norm = std::sqrt(other.east_ * other.east_ + other.north_ * other.north_);
                if (norm == 0.0) throw DeflectionError("projection onto a zero vector");
                double scale = (east_ * other.east_ + north_ * other.north_) / norm;
                return DeflectionVec(scale * other.east_, scale * other.north_);
            }
            double DeflectionVec::dot(const DeflectionVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            bool nearly_equal(const DeflectionVec& left, const DeflectionVec& right, double eps) {
                return std::fabs(left.east() - right.east()) <= eps
                    && std::fabs(left.north() - right.north()) <= eps;
            }
            """,
            """
            DeflectionVec a(2.0, 2.0);
            DeflectionVec axis(4.0, 0.0);
            DeflectionVec p = a.project_onto(axis);
            if (std::fabs(p.east() - 2.0) > 1e-9 || std::fabs(p.north()) > 1e-9) return 1;
            DeflectionVec u = DeflectionVec(3.0, 4.0).unit();
            if (std::fabs(u.east() - 0.6) > 1e-9 || std::fabs(u.north() - 0.8) > 1e-9) return 2;
            if (std::fabs(a.dot(axis) - 8.0) > 1e-9) return 3;
            DeflectionVec s = a + axis;
            if (std::fabs(s.east() - 6.0) > 1e-9 || std::fabs(s.north() - 2.0) > 1e-9) return 4;
            DeflectionVec m = a * 2.5;
            if (std::fabs(m.east() - 5.0) > 1e-9 || std::fabs(m.north() - 5.0) > 1e-9) return 5;
            if (!nearly_equal(a, DeflectionVec(2.0, 2.0 + 1e-12), 1e-9)) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { DeflectionVec(1.0, 2.0).project_onto(DeflectionVec(0.0, 0.0)); } catch (const DeflectionError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { DeflectionVec(0.0, 0.0).unit(); } catch (const DeflectionError&) { threw = true; }
            if (!threw) return 2;
            DeflectionVec a(0.0, 5.0);
            DeflectionVec neg_axis(0.0, -1.0);
            DeflectionVec p = a.project_onto(neg_axis);
            if (std::fabs(p.east()) > 1e-9 || std::fabs(p.north() - 5.0) > 1e-9) return 3;
            DeflectionVec d = DeflectionVec(1.0, 2.0) - DeflectionVec(3.0, 4.0);
            if (std::fabs(d.east() + 2.0) > 1e-9 || std::fabs(d.north() + 2.0) > 1e-9) return 4;
            DeflectionVec u = d.unit();
            if (std::fabs(u.east() + 1.0 / std::sqrt(2.0)) > 1e-9 || std::fabs(u.north() + 1.0 / std::sqrt(2.0)) > 1e-9) return 5;
            if (std::fabs(u.dot(u) - 1.0) > 1e-9) return 6;
            if (nearly_equal(d, DeflectionVec(-2.0, -2.0 + 1e-6), 1e-9)) return 7;
            DeflectionVec m = DeflectionVec(1.0, -2.0) * -2.0;
            if (std::fabs(m.east() + 2.0) > 1e-9 || std::fabs(m.north() - 4.0) > 1e-9) return 8;
            return 0;
            """,
            "projection by the exactly squared norm with unit direction over an owned coordinate pair",
            "std::complex, <complex>, or any geometry library type; do not divide the projection by the unsquared length",
            "projection onto axis and anti-axis vectors, projection and unit rejection at the origin, unit length one, and tolerance boundaries",
            "projection-norm discipline as the rejection discriminator in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-sprinkler-spray-fan",
            "Sprinkler spray fan",
            "spray_fan",
            """
            class FanError : public std::domain_error {
            public:
                explicit FanError(const std::string& message) : std::domain_error(message) {}
            };
            class FanVec {
            public:
                FanVec(double east, double north);
                double east() const;
                double north() const;
                double dot(const FanVec& other) const;
                double perp(const FanVec& other) const;
                FanVec rotate(double radians) const;
                std::string render() const;
            };
            FanVec operator+(const FanVec& left, const FanVec& right);
            FanVec operator-(const FanVec& left, const FanVec& right);
            FanVec operator*(const FanVec& value, double factor);
            """,
            """
            class FanError : public std::domain_error {
            public:
                explicit FanError(const std::string& message) : std::domain_error(message) {}
            };
            class FanVec {
            public:
                FanVec(double east, double north);
                double east() const;
                double north() const;
                double dot(const FanVec& other) const;
                double perp(const FanVec& other) const;
                FanVec rotate(double radians) const;
                std::string render() const;
            private:
                double east_;
                double north_;
            };
            FanVec operator+(const FanVec& left, const FanVec& right);
            FanVec operator-(const FanVec& left, const FanVec& right);
            FanVec operator*(const FanVec& value, double factor);
            """,
            """
            FanVec::FanVec(double east, double north) : east_(east), north_(north) {}
            double FanVec::east() const { return east_; }
            double FanVec::north() const { return north_; }
            double FanVec::dot(const FanVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            double FanVec::perp(const FanVec& other) const {
                return east_ * other.north_ - north_ * other.east_;
            }
            FanVec FanVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return FanVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            std::string FanVec::render() const {
                std::ostringstream out;
                out << "east=" << std::fixed << std::setprecision(6) << east_ << ";north=" << north_;
                return out.str();
            }
            FanVec operator+(const FanVec& left, const FanVec& right) {
                return FanVec(left.east() + right.east(), left.north() + right.north());
            }
            FanVec operator-(const FanVec& left, const FanVec& right) {
                return FanVec(left.east() - right.east(), left.north() - right.north());
            }
            FanVec operator*(const FanVec& value, double factor) {
                return FanVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            FanVec::FanVec(double east, double north) : east_(east), north_(north) {}
            double FanVec::east() const { return east_; }
            double FanVec::north() const { return north_; }
            double FanVec::dot(const FanVec& other) const {
                return east_ * other.east_ + north_ * other.north_;
            }
            double FanVec::perp(const FanVec& other) const {
                return east_ * other.north_ + north_ * other.east_;
            }
            FanVec FanVec::rotate(double radians) const {
                double c = std::cos(radians);
                double s = std::sin(radians);
                return FanVec(east_ * c - north_ * s, east_ * s + north_ * c);
            }
            std::string FanVec::render() const {
                std::ostringstream out;
                out << "east=" << std::fixed << std::setprecision(6) << east_ << ";north=" << north_;
                return out.str();
            }
            FanVec operator+(const FanVec& left, const FanVec& right) {
                return FanVec(left.east() + right.east(), left.north() + right.north());
            }
            FanVec operator-(const FanVec& left, const FanVec& right) {
                return FanVec(left.east() - right.east(), left.north() - right.north());
            }
            FanVec operator*(const FanVec& value, double factor) {
                return FanVec(factor * value.east(), factor * value.north());
            }
            """,
            """
            FanVec a(1.0, 2.0);
            FanVec b(3.0, 4.0);
            if (std::fabs(a.dot(b) - 11.0) > 1e-9) return 1;
            if (std::fabs(a.perp(b) + 2.0) > 1e-9) return 2;
            FanVec r = b.rotate(3.14159265358979323846);
            if (std::fabs(r.east() + 3.0) > 1e-9 || std::fabs(r.north() + 4.0) > 1e-9) return 3;
            FanVec s = a + b;
            if (std::fabs(s.east() - 4.0) > 1e-9 || std::fabs(s.north() - 6.0) > 1e-9) return 4;
            FanVec m = b * 0.5;
            if (std::fabs(m.east() - 1.5) > 1e-9 || std::fabs(m.north() - 2.0) > 1e-9) return 5;
            if (b.render() != "east=3.000000;north=4.000000") return 6;
            return 0;
            """,
            """
            const double kPi = 3.14159265358979323846;
            FanVec a(2.0, 1.0);
            FanVec rot = a.rotate(kPi / 2.0);
            if (std::fabs(rot.east() + 1.0) > 1e-9 || std::fabs(rot.north() - 2.0) > 1e-9) return 1;
            if (std::fabs(a.dot(rot)) > 1e-9) return 2;
            if (std::fabs(a.perp(rot) - 5.0) > 1e-9) return 3;
            FanVec b(1.0, -1.0);
            if (std::fabs(a.perp(b) + 3.0) > 1e-9) return 4;
            if (std::fabs(b.perp(a) - 3.0) > 1e-9) return 5;
            FanVec d = a - b;
            if (std::fabs(d.east() - 1.0) > 1e-9 || std::fabs(d.north() - 2.0) > 1e-9) return 6;
            FanVec m = d * -3.0;
            if (std::fabs(m.east() + 3.0) > 1e-9 || std::fabs(m.north() + 6.0) > 1e-9) return 7;
            if (m.render() != "east=-3.000000;north=-6.000000") return 8;
            return 0;
            """,
            "inner and perp product pair with rotation invariants and an exact readout",
            "std::complex, <complex>, or any geometry library type; do not compute the perp product with a plus sign",
            "perp antisymmetry, dot symmetry, dot and perp invariants under rotation, negative-component rendering, and scalar multiplication",
            "product-pair invariants under rotation as the hidden oracle in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-telescope-pointing-error",
            "Telescope pointing error",
            "pointing_error",
            """
            class PointingError : public std::domain_error {
            public:
                explicit PointingError(const std::string& message) : std::domain_error(message) {}
            };
            class PointingVec {
            public:
                PointingVec(double east, double north);
                double east() const;
                double north() const;
                PointingVec operator+(const PointingVec& other) const;
                PointingVec operator-(const PointingVec& other) const;
                double bearing() const;
                PointingVec unit() const;
                double distance_to(const PointingVec& other) const;
                bool within(const PointingVec& other, double eps) const;
            };
            """,
            """
            class PointingError : public std::domain_error {
            public:
                explicit PointingError(const std::string& message) : std::domain_error(message) {}
            };
            class PointingVec {
            public:
                PointingVec(double east, double north);
                double east() const;
                double north() const;
                PointingVec operator+(const PointingVec& other) const;
                PointingVec operator-(const PointingVec& other) const;
                double bearing() const;
                PointingVec unit() const;
                double distance_to(const PointingVec& other) const;
                bool within(const PointingVec& other, double eps) const;
            private:
                double east_;
                double north_;
            };
            """,
            """
            PointingVec::PointingVec(double east, double north) : east_(east), north_(north) {}
            double PointingVec::east() const { return east_; }
            double PointingVec::north() const { return north_; }
            PointingVec PointingVec::operator+(const PointingVec& other) const {
                return PointingVec(east_ + other.east_, north_ + other.north_);
            }
            PointingVec PointingVec::operator-(const PointingVec& other) const {
                return PointingVec(east_ - other.east_, north_ - other.north_);
            }
            double PointingVec::bearing() const {
                return std::atan2(east_, north_);
            }
            PointingVec PointingVec::unit() const {
                double len = std::sqrt(east_ * east_ + north_ * north_);
                if (len == 0.0) throw PointingError("unit of a zero vector");
                return PointingVec(east_ / len, north_ / len);
            }
            double PointingVec::distance_to(const PointingVec& other) const {
                double de = other.east_ - east_;
                double dn = other.north_ - north_;
                return std::sqrt(de * de + dn * dn);
            }
            bool PointingVec::within(const PointingVec& other, double eps) const {
                return std::fabs(east_ - other.east_) <= eps
                    && std::fabs(north_ - other.north_) <= eps;
            }
            """,
            """
            PointingVec::PointingVec(double east, double north) : east_(east), north_(north) {}
            double PointingVec::east() const { return east_; }
            double PointingVec::north() const { return north_; }
            PointingVec PointingVec::operator+(const PointingVec& other) const {
                return PointingVec(east_ + other.east_, north_ + other.north_);
            }
            PointingVec PointingVec::operator-(const PointingVec& other) const {
                return PointingVec(east_ - other.east_, north_ - other.north_);
            }
            double PointingVec::bearing() const {
                return std::atan2(north_, east_);
            }
            PointingVec PointingVec::unit() const {
                double len = std::sqrt(east_ * east_ + north_ * north_);
                if (len == 0.0) throw PointingError("unit of a zero vector");
                return PointingVec(east_ / len, north_ / len);
            }
            double PointingVec::distance_to(const PointingVec& other) const {
                double de = other.east_ - east_;
                double dn = other.north_ - north_;
                return std::sqrt(de * de + dn * dn);
            }
            bool PointingVec::within(const PointingVec& other, double eps) const {
                return std::fabs(east_ - other.east_) <= eps
                    && std::fabs(north_ - other.north_) <= eps;
            }
            """,
            """
            PointingVec a(1.0, 0.0);
            if (std::fabs(a.bearing() - 3.14159265358979323846 / 2.0) > 1e-9) return 1;
            PointingVec b(0.0, 1.0);
            if (std::fabs(b.bearing()) > 1e-12) return 2;
            PointingVec u = PointingVec(3.0, 4.0).unit();
            if (std::fabs(u.east() - 0.6) > 1e-9 || std::fabs(u.north() - 0.8) > 1e-9) return 3;
            if (std::fabs(a.distance_to(b) - std::sqrt(2.0)) > 1e-9) return 4;
            PointingVec s = a + b;
            if (std::fabs(s.bearing() - 3.14159265358979323846 / 4.0) > 1e-9) return 5;
            if (!a.within(PointingVec(1.0 + 1e-12, 0.0), 1e-9)) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { PointingVec(0.0, 0.0).unit(); } catch (const PointingError&) { threw = true; }
            if (!threw) return 1;
            const double kPi = 3.14159265358979323846;
            PointingVec w(-1.0, 0.0);
            if (std::fabs(w.bearing() + kPi / 2.0) > 1e-9) return 2;
            PointingVec s(0.0, -2.0);
            if (std::fabs(std::fabs(s.bearing()) - kPi) > 1e-9) return 3;
            PointingVec d = PointingVec(1.0, 2.0) - PointingVec(4.0, 6.0);
            if (std::fabs(d.distance_to(PointingVec(0.0, 0.0)) - 5.0) > 1e-9) return 4;
            if (d.within(PointingVec(-3.0, -4.0 + 1e-6), 1e-9)) return 5;
            PointingVec u = d.unit();
            if (std::fabs(u.east() + 0.6) > 1e-9 || std::fabs(u.north() + 0.8) > 1e-9) return 6;
            if (std::fabs(PointingVec(2.0, 2.0).distance_to(PointingVec(2.0, 2.0))) > 1e-12) return 7;
            return 0;
            """,
            "combined clockwise-from-north bearing, unit direction, and distance over an owned coordinate pair",
            "std::complex, <complex>, or any geometry library type; do not swap the atan2 argument order",
            "bearing quadrant boundaries, unit rejection at the origin, distance symmetry and self-distance, and tolerance boundaries",
            "combined bearing and unit discipline without scalar helpers in a paired .h/.cpp API",
            "planar vector value type",
        ),
        c(
            "f26cpx-radar-range-bearing",
            "Radar range bearing",
            "radar_plot",
            """
            class RangeBearing {
            public:
                RangeBearing(double range, double radians);
                double range() const;
                double radians() const;
                RangeBearing scale(double factor) const;
                RangeBearing sweep(double delta) const;
                double east() const;
                double north() const;
            };
            bool nearly_equal(const RangeBearing& left, const RangeBearing& right, double eps);
            """,
            """
            class RangeBearing {
            public:
                RangeBearing(double range, double radians);
                double range() const;
                double radians() const;
                RangeBearing scale(double factor) const;
                RangeBearing sweep(double delta) const;
                double east() const;
                double north() const;
            private:
                double range_;
                double radians_;
            };
            bool nearly_equal(const RangeBearing& left, const RangeBearing& right, double eps);
            """,
            """
            namespace {
            constexpr double kPi = 3.14159265358979323846;
            double normalize_angle(double angle) {
                double wrapped = std::fmod(angle, 2.0 * kPi);
                if (wrapped <= -kPi) wrapped += 2.0 * kPi;
                else if (wrapped > kPi) wrapped -= 2.0 * kPi;
                return wrapped;
            }
            }
            RangeBearing::RangeBearing(double range, double radians) {
                double r = range;
                double a = radians;
                if (r < 0.0) { r = -r; a += kPi; }
                range_ = r;
                radians_ = normalize_angle(a);
            }
            double RangeBearing::range() const { return range_; }
            double RangeBearing::radians() const { return radians_; }
            RangeBearing RangeBearing::scale(double factor) const {
                return RangeBearing(range_ * factor, radians_);
            }
            RangeBearing RangeBearing::sweep(double delta) const {
                return RangeBearing(range_, radians_ + delta);
            }
            double RangeBearing::east() const { return range_ * std::sin(radians_); }
            double RangeBearing::north() const { return range_ * std::cos(radians_); }
            bool nearly_equal(const RangeBearing& left, const RangeBearing& right, double eps) {
                return std::fabs(left.range() - right.range()) <= eps
                    && std::fabs(left.radians() - right.radians()) <= eps;
            }
            """,
            """
            RangeBearing::RangeBearing(double range, double radians) : range_(range), radians_(radians) {}
            double RangeBearing::range() const { return range_; }
            double RangeBearing::radians() const { return radians_; }
            RangeBearing RangeBearing::scale(double factor) const {
                return RangeBearing(range_ * factor, radians_);
            }
            RangeBearing RangeBearing::sweep(double delta) const {
                return RangeBearing(range_, radians_ + delta);
            }
            double RangeBearing::east() const { return range_ * std::sin(radians_); }
            double RangeBearing::north() const { return range_ * std::cos(radians_); }
            bool nearly_equal(const RangeBearing& left, const RangeBearing& right, double eps) {
                return std::fabs(left.range() - right.range()) <= eps
                    && std::fabs(left.radians() - right.radians()) <= eps;
            }
            """,
            """
            RangeBearing a(2.0, 0.0);
            if (std::fabs(a.range() - 2.0) > 1e-9 || std::fabs(a.radians()) > 1e-9) return 1;
            if (std::fabs(a.east()) > 1e-9 || std::fabs(a.north() - 2.0) > 1e-9) return 2;
            RangeBearing neg(-2.0, 0.0);
            if (std::fabs(neg.range() - 2.0) > 1e-9 || std::fabs(neg.radians() - 3.14159265358979323846) > 1e-9) return 3;
            RangeBearing s = a.sweep(3.14159265358979323846 / 2.0);
            if (std::fabs(s.radians() - 3.14159265358979323846 / 2.0) > 1e-9) return 4;
            if (std::fabs(s.east() - 2.0) > 1e-9 || std::fabs(s.north()) > 1e-9) return 5;
            RangeBearing sc = a.scale(3.0);
            if (std::fabs(sc.range() - 6.0) > 1e-9 || std::fabs(sc.radians()) > 1e-9) return 6;
            if (!nearly_equal(a, RangeBearing(2.0 + 1e-12, 0.0), 1e-9)) return 7;
            return 0;
            """,
            """
            const double kPi = 3.14159265358979323846;
            RangeBearing a(1.0, 3.0);
            RangeBearing over = a.sweep(0.5);
            if (std::fabs(over.radians() - (3.5 - 2.0 * kPi)) > 1e-9) return 1;
            RangeBearing under = RangeBearing(1.0, -3.0).sweep(-0.5);
            if (std::fabs(under.radians() - (-3.5 + 2.0 * kPi)) > 1e-9) return 2;
            RangeBearing neg_scale = a.scale(-2.0);
            if (std::fabs(neg_scale.range() - 2.0) > 1e-9) return 3;
            if (std::fabs(neg_scale.radians() - (3.0 - kPi)) > 1e-9) return 4;
            RangeBearing at_pi(1.0, kPi);
            if (std::fabs(at_pi.radians() - kPi) > 1e-12) return 5;
            RangeBearing seam(1.0, -kPi);
            if (std::fabs(seam.radians() - kPi) > 1e-12) return 6;
            RangeBearing e(4.0, kPi / 2.0);
            if (std::fabs(e.east() - 4.0) > 1e-9 || std::fabs(e.north()) > 1e-9) return 7;
            if (nearly_equal(a, RangeBearing(1.0, 3.0 + 1e-6), 1e-9)) return 8;
            RangeBearing zero = a.scale(0.0);
            if (std::fabs(zero.range()) > 1e-12) return 9;
            return 0;
            """,
            "constructor-time canonicalization of a bearing pair into nonnegative range and the (-pi, pi] angle interval",
            "std::polar, std::complex, <complex>, or raw unnormalized accumulation of range and angle",
            "negative-range flip, sweep across both +-pi seams, negative scale canonicalization, the exact -pi boundary, and east/north conversion",
            "canonicalization-in-constructor discipline over floating pairs in a paired .h/.cpp API",
            "bearing-pair value type",
        ),
        c(
            "f26cpx-compass-survey-point",
            "Compass survey point",
            "survey_point",
            """
            class SurveyPoint {
            public:
                SurveyPoint(double dist, double azimuth);
                double dist() const;
                double azimuth() const;
                SurveyPoint stretch(double factor) const;
                SurveyPoint swing(double delta) const;
                double easting() const;
                double northing() const;
                std::string render() const;
            };
            bool same_point(const SurveyPoint& left, const SurveyPoint& right, double eps);
            """,
            """
            class SurveyPoint {
            public:
                SurveyPoint(double dist, double azimuth);
                double dist() const;
                double azimuth() const;
                SurveyPoint stretch(double factor) const;
                SurveyPoint swing(double delta) const;
                double easting() const;
                double northing() const;
                std::string render() const;
            private:
                double dist_;
                double azimuth_;
            };
            bool same_point(const SurveyPoint& left, const SurveyPoint& right, double eps);
            """,
            """
            namespace {
            constexpr double kPi = 3.14159265358979323846;
            double normalize_azimuth(double angle) {
                double wrapped = std::fmod(angle, 2.0 * kPi);
                if (wrapped < 0.0) wrapped += 2.0 * kPi;
                return wrapped;
            }
            }
            SurveyPoint::SurveyPoint(double dist, double azimuth) {
                double d = dist;
                double a = azimuth;
                if (d < 0.0) { d = -d; a += kPi; }
                dist_ = d;
                azimuth_ = normalize_azimuth(a);
            }
            double SurveyPoint::dist() const { return dist_; }
            double SurveyPoint::azimuth() const { return azimuth_; }
            SurveyPoint SurveyPoint::stretch(double factor) const {
                return SurveyPoint(dist_ * factor, azimuth_);
            }
            SurveyPoint SurveyPoint::swing(double delta) const {
                return SurveyPoint(dist_, azimuth_ + delta);
            }
            double SurveyPoint::easting() const { return dist_ * std::sin(azimuth_); }
            double SurveyPoint::northing() const { return dist_ * std::cos(azimuth_); }
            std::string SurveyPoint::render() const {
                std::ostringstream out;
                out << "dist=" << std::fixed << std::setprecision(6) << dist_ << ";azimuth=" << azimuth_;
                return out.str();
            }
            bool same_point(const SurveyPoint& left, const SurveyPoint& right, double eps) {
                return std::fabs(left.dist() - right.dist()) <= eps
                    && std::fabs(left.azimuth() - right.azimuth()) <= eps;
            }
            """,
            """
            SurveyPoint::SurveyPoint(double dist, double azimuth) : dist_(dist), azimuth_(azimuth) {}
            double SurveyPoint::dist() const { return dist_; }
            double SurveyPoint::azimuth() const { return azimuth_; }
            SurveyPoint SurveyPoint::stretch(double factor) const {
                return SurveyPoint(dist_ * factor, azimuth_);
            }
            SurveyPoint SurveyPoint::swing(double delta) const {
                return SurveyPoint(dist_, azimuth_ + delta);
            }
            double SurveyPoint::easting() const { return dist_ * std::sin(azimuth_); }
            double SurveyPoint::northing() const { return dist_ * std::cos(azimuth_); }
            std::string SurveyPoint::render() const {
                std::ostringstream out;
                out << "dist=" << std::fixed << std::setprecision(6) << dist_ << ";azimuth=" << azimuth_;
                return out.str();
            }
            bool same_point(const SurveyPoint& left, const SurveyPoint& right, double eps) {
                return std::fabs(left.dist() - right.dist()) <= eps
                    && std::fabs(left.azimuth() - right.azimuth()) <= eps;
            }
            """,
            """
            SurveyPoint a(10.0, 0.0);
            if (std::fabs(a.dist() - 10.0) > 1e-9 || std::fabs(a.azimuth()) > 1e-9) return 1;
            if (std::fabs(a.easting()) > 1e-9 || std::fabs(a.northing() - 10.0) > 1e-9) return 2;
            SurveyPoint sw = a.swing(3.14159265358979323846 / 2.0);
            if (std::fabs(sw.easting() - 10.0) > 1e-9 || std::fabs(sw.northing()) > 1e-9) return 3;
            SurveyPoint st = a.stretch(0.5);
            if (std::fabs(st.dist() - 5.0) > 1e-9 || std::fabs(st.azimuth()) > 1e-9) return 4;
            SurveyPoint neg(-4.0, 0.0);
            if (std::fabs(neg.dist() - 4.0) > 1e-9 || std::fabs(neg.azimuth() - 3.14159265358979323846) > 1e-9) return 5;
            if (a.render() != "dist=10.000000;azimuth=0.000000") return 6;
            if (!same_point(a, SurveyPoint(10.0 + 1e-12, 0.0), 1e-9)) return 7;
            return 0;
            """,
            """
            const double kPi = 3.14159265358979323846;
            SurveyPoint a(2.0, 6.0);
            SurveyPoint over = a.swing(1.0);
            if (std::fabs(over.azimuth() - (7.0 - 2.0 * kPi)) > 1e-9) return 1;
            SurveyPoint under = SurveyPoint(2.0, 0.5).swing(-1.0);
            if (std::fabs(under.azimuth() - (-0.5 + 2.0 * kPi)) > 1e-9) return 2;
            SurveyPoint full = a.swing(2.0 * kPi);
            if (std::fabs(full.azimuth() - 6.0) > 1e-9) return 3;
            SurveyPoint neg_stretch = a.stretch(-3.0);
            if (std::fabs(neg_stretch.dist() - 6.0) > 1e-9) return 4;
            if (std::fabs(neg_stretch.azimuth() - (6.0 - kPi)) > 1e-9) return 5;
            SurveyPoint e(3.0, kPi / 2.0);
            if (std::fabs(e.easting() - 3.0) > 1e-9 || std::fabs(e.northing()) > 1e-9) return 6;
            if (e.render() != "dist=3.000000;azimuth=1.570796") return 7;
            if (same_point(a, SurveyPoint(2.0, 6.0 + 1e-6), 1e-9)) return 8;
            SurveyPoint zero_az(1.0, 2.0 * kPi);
            if (std::fabs(zero_az.azimuth()) > 1e-12) return 9;
            return 0;
            """,
            "constructor-time canonicalization of a survey pair into nonnegative distance and the [0, 2*pi) azimuth interval",
            "std::polar, std::complex, <complex>, or raw unnormalized accumulation of distance and azimuth",
            "seam crossing in both directions, full-turn invariance, negative-distance flip, negative stretch canonicalization, exact render bytes, and cardinal conversions",
            "the [0, 2*pi) normalization interval as a materially different contract from the sibling bearing root",
            "bearing-pair value type",
        ),
        c(
            "f26cpx-affine-grid-transform",
            "Affine grid transform",
            "affine_grid",
            """
            class GridError : public std::domain_error {
            public:
                explicit GridError(const std::string& message) : std::domain_error(message) {}
            };
            class GridMatrix {
            public:
                GridMatrix(double a, double b, double c, double d);
                double a() const;
                double b() const;
                double c() const;
                double d() const;
                GridMatrix operator+(const GridMatrix& other) const;
                GridMatrix operator*(const GridMatrix& other) const;
                double det() const;
                double trace() const;
                GridMatrix transpose() const;
                GridMatrix inverse() const;
                std::pair<double, double> apply(double x, double y) const;
            };
            bool nearly_equal(const GridMatrix& left, const GridMatrix& right, double eps);
            """,
            """
            class GridError : public std::domain_error {
            public:
                explicit GridError(const std::string& message) : std::domain_error(message) {}
            };
            class GridMatrix {
            public:
                GridMatrix(double a, double b, double c, double d);
                double a() const;
                double b() const;
                double c() const;
                double d() const;
                GridMatrix operator+(const GridMatrix& other) const;
                GridMatrix operator*(const GridMatrix& other) const;
                double det() const;
                double trace() const;
                GridMatrix transpose() const;
                GridMatrix inverse() const;
                std::pair<double, double> apply(double x, double y) const;
            private:
                double a_;
                double b_;
                double c_;
                double d_;
            };
            bool nearly_equal(const GridMatrix& left, const GridMatrix& right, double eps);
            """,
            """
            GridMatrix::GridMatrix(double a, double b, double c, double d) : a_(a), b_(b), c_(c), d_(d) {}
            double GridMatrix::a() const { return a_; }
            double GridMatrix::b() const { return b_; }
            double GridMatrix::c() const { return c_; }
            double GridMatrix::d() const { return d_; }
            GridMatrix GridMatrix::operator+(const GridMatrix& other) const {
                return GridMatrix(a_ + other.a_, b_ + other.b_, c_ + other.c_, d_ + other.d_);
            }
            GridMatrix GridMatrix::operator*(const GridMatrix& other) const {
                return GridMatrix(a_ * other.a_ + b_ * other.c_,
                                  a_ * other.b_ + b_ * other.d_,
                                  c_ * other.a_ + d_ * other.c_,
                                  c_ * other.b_ + d_ * other.d_);
            }
            double GridMatrix::det() const { return a_ * d_ - b_ * c_; }
            double GridMatrix::trace() const { return a_ + d_; }
            GridMatrix GridMatrix::transpose() const {
                return GridMatrix(a_, c_, b_, d_);
            }
            GridMatrix GridMatrix::inverse() const {
                double dm = det();
                if (dm == 0.0) throw GridError("singular matrix");
                return GridMatrix(d_ / dm, -b_ / dm, -c_ / dm, a_ / dm);
            }
            std::pair<double, double> GridMatrix::apply(double x, double y) const {
                return {a_ * x + b_ * y, c_ * x + d_ * y};
            }
            bool nearly_equal(const GridMatrix& left, const GridMatrix& right, double eps) {
                return std::fabs(left.a() - right.a()) <= eps
                    && std::fabs(left.b() - right.b()) <= eps
                    && std::fabs(left.c() - right.c()) <= eps
                    && std::fabs(left.d() - right.d()) <= eps;
            }
            """,
            """
            GridMatrix::GridMatrix(double a, double b, double c, double d) : a_(a), b_(b), c_(c), d_(d) {}
            double GridMatrix::a() const { return a_; }
            double GridMatrix::b() const { return b_; }
            double GridMatrix::c() const { return c_; }
            double GridMatrix::d() const { return d_; }
            GridMatrix GridMatrix::operator+(const GridMatrix& other) const {
                return GridMatrix(a_ + other.a_, b_ + other.b_, c_ + other.c_, d_ + other.d_);
            }
            GridMatrix GridMatrix::operator*(const GridMatrix& other) const {
                return GridMatrix(a_ * other.a_ + b_ * other.c_,
                                  a_ * other.b_ + b_ * other.d_,
                                  c_ * other.a_ + d_ * other.c_,
                                  c_ * other.b_ + d_ * other.d_);
            }
            double GridMatrix::det() const { return a_ * d_ - b_ * c_; }
            double GridMatrix::trace() const { return a_ + d_; }
            GridMatrix GridMatrix::transpose() const {
                return GridMatrix(a_, c_, b_, d_);
            }
            GridMatrix GridMatrix::inverse() const {
                double dm = det();
                if (dm == 0.0) throw GridError("singular matrix");
                return GridMatrix(a_ / dm, -b_ / dm, -c_ / dm, d_ / dm);
            }
            std::pair<double, double> GridMatrix::apply(double x, double y) const {
                return {a_ * x + b_ * y, c_ * x + d_ * y};
            }
            bool nearly_equal(const GridMatrix& left, const GridMatrix& right, double eps) {
                return std::fabs(left.a() - right.a()) <= eps
                    && std::fabs(left.b() - right.b()) <= eps
                    && std::fabs(left.c() - right.c()) <= eps
                    && std::fabs(left.d() - right.d()) <= eps;
            }
            """,
            """
            GridMatrix m(1.0, 2.0, 3.0, 4.0);
            if (std::fabs(m.det() + 2.0) > 1e-9) return 1;
            if (std::fabs(m.trace() - 5.0) > 1e-9) return 2;
            GridMatrix t = m.transpose();
            if (std::fabs(t.b() - 3.0) > 1e-9 || std::fabs(t.c() - 2.0) > 1e-9) return 3;
            GridMatrix id = m * m.inverse();
            if (!nearly_equal(id, GridMatrix(1.0, 0.0, 0.0, 1.0), 1e-9)) return 4;
            std::pair<double, double> out = m.apply(1.0, 1.0);
            if (std::fabs(out.first - 3.0) > 1e-9 || std::fabs(out.second - 7.0) > 1e-9) return 5;
            GridMatrix s = m + GridMatrix(1.0, 1.0, 1.0, 1.0);
            if (std::fabs(s.a() - 2.0) > 1e-9 || std::fabs(s.d() - 5.0) > 1e-9) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { GridMatrix(1.0, 2.0, 2.0, 4.0).inverse(); } catch (const GridError&) { threw = true; }
            if (!threw) return 1;
            GridMatrix m(0.0, 1.0, -1.0, 0.0);
            std::pair<double, double> x = m.apply(1.0, 0.0);
            if (std::fabs(x.first) > 1e-9 || std::fabs(x.second + 1.0) > 1e-9) return 2;
            GridMatrix p = m * m;
            if (!nearly_equal(p, GridMatrix(-1.0, 0.0, 0.0, -1.0), 1e-12)) return 3;
            GridMatrix q = m * m * m * m;
            if (!nearly_equal(q, GridMatrix(1.0, 0.0, 0.0, 1.0), 1e-9)) return 4;
            GridMatrix a(2.0, 0.0, 0.0, 3.0);
            if (std::fabs(a.det() - 6.0) > 1e-9) return 5;
            GridMatrix inv = a.inverse();
            if (std::fabs(inv.a() - 0.5) > 1e-9 || std::fabs(inv.d() - 1.0 / 3.0) > 1e-9) return 6;
            if (std::fabs((a * m).det() - a.det() * m.det()) > 1e-9) return 7;
            if (nearly_equal(a, GridMatrix(2.0, 0.0, 0.0, 3.0 + 1e-6), 1e-9)) return 8;
            threw = false;
            try { GridMatrix(0.0, 0.0, 0.0, 0.0).inverse(); } catch (const GridError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "the 2x2 bilinear product with an adjugate inverse that swaps the diagonal",
            "any linear-algebra library, std::complex, <complex>, or an adjugate that forgets the diagonal swap",
            "inverse rejection at exactly singular matrices, m times inverse identity within tolerance, rotation composition, the product-determinant law, and apply on basis vectors",
            "norm-free inversion with a singularity edge and an application surface in a project-context paired .h/.cpp layout",
            "2x2 matrix value type",
            project_support=True,
        ),
        c(
            "f26cpx-loom-pattern-matrix",
            "Loom pattern matrix",
            "loom_pattern",
            """
            class PatternError : public std::domain_error {
            public:
                explicit PatternError(const std::string& message) : std::domain_error(message) {}
            };
            class PatternMatrix {
            public:
                PatternMatrix(double a, double b, double c, double d);
                double a() const;
                double b() const;
                double c() const;
                double d() const;
                PatternMatrix operator+(const PatternMatrix& other) const;
                PatternMatrix operator*(const PatternMatrix& other) const;
                PatternMatrix pow(unsigned exponent) const;
                double det() const;
                bool is_singular() const;
                PatternMatrix inverse() const;
                std::string render() const;
            };
            """,
            """
            class PatternError : public std::domain_error {
            public:
                explicit PatternError(const std::string& message) : std::domain_error(message) {}
            };
            class PatternMatrix {
            public:
                PatternMatrix(double a, double b, double c, double d);
                double a() const;
                double b() const;
                double c() const;
                double d() const;
                PatternMatrix operator+(const PatternMatrix& other) const;
                PatternMatrix operator*(const PatternMatrix& other) const;
                PatternMatrix pow(unsigned exponent) const;
                double det() const;
                bool is_singular() const;
                PatternMatrix inverse() const;
                std::string render() const;
            private:
                double a_;
                double b_;
                double c_;
                double d_;
            };
            """,
            """
            PatternMatrix::PatternMatrix(double a, double b, double c, double d) : a_(a), b_(b), c_(c), d_(d) {}
            double PatternMatrix::a() const { return a_; }
            double PatternMatrix::b() const { return b_; }
            double PatternMatrix::c() const { return c_; }
            double PatternMatrix::d() const { return d_; }
            PatternMatrix PatternMatrix::operator+(const PatternMatrix& other) const {
                return PatternMatrix(a_ + other.a_, b_ + other.b_, c_ + other.c_, d_ + other.d_);
            }
            PatternMatrix PatternMatrix::operator*(const PatternMatrix& other) const {
                return PatternMatrix(a_ * other.a_ + b_ * other.c_,
                                     a_ * other.b_ + b_ * other.d_,
                                     c_ * other.a_ + d_ * other.c_,
                                     c_ * other.b_ + d_ * other.d_);
            }
            PatternMatrix PatternMatrix::pow(unsigned exponent) const {
                PatternMatrix result(1.0, 0.0, 0.0, 1.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            double PatternMatrix::det() const { return a_ * d_ - b_ * c_; }
            bool PatternMatrix::is_singular() const { return det() == 0.0; }
            PatternMatrix PatternMatrix::inverse() const {
                double dm = det();
                if (dm == 0.0) throw PatternError("singular matrix");
                return PatternMatrix(d_ / dm, -b_ / dm, -c_ / dm, a_ / dm);
            }
            std::string PatternMatrix::render() const {
                std::ostringstream out;
                out << std::fixed << std::setprecision(6) << a_ << "|" << b_ << ";" << c_ << "|" << d_;
                return out.str();
            }
            """,
            """
            PatternMatrix::PatternMatrix(double a, double b, double c, double d) : a_(a), b_(b), c_(c), d_(d) {}
            double PatternMatrix::a() const { return a_; }
            double PatternMatrix::b() const { return b_; }
            double PatternMatrix::c() const { return c_; }
            double PatternMatrix::d() const { return d_; }
            PatternMatrix PatternMatrix::operator+(const PatternMatrix& other) const {
                return PatternMatrix(a_ + other.a_, b_ + other.b_, c_ + other.c_, d_ + other.d_);
            }
            PatternMatrix PatternMatrix::operator*(const PatternMatrix& other) const {
                return PatternMatrix(a_ * other.a_ + b_ * other.c_,
                                     a_ * other.b_ + b_ * other.d_,
                                     c_ * other.a_ + d_ * other.c_,
                                     c_ * other.b_ + d_ * other.d_);
            }
            PatternMatrix PatternMatrix::pow(unsigned exponent) const {
                PatternMatrix result(1.0, 0.0, 0.0, 1.0);
                for (unsigned i = 0; i < exponent; ++i) result = result * (*this);
                return result;
            }
            double PatternMatrix::det() const { return a_ * d_ + b_ * c_; }
            bool PatternMatrix::is_singular() const { return det() == 0.0; }
            PatternMatrix PatternMatrix::inverse() const {
                double dm = det();
                if (dm == 0.0) throw PatternError("singular matrix");
                return PatternMatrix(d_ / dm, -b_ / dm, -c_ / dm, a_ / dm);
            }
            std::string PatternMatrix::render() const {
                std::ostringstream out;
                out << std::fixed << std::setprecision(6) << a_ << "|" << b_ << ";" << c_ << "|" << d_;
                return out.str();
            }
            """,
            """
            PatternMatrix m(1.0, 2.0, 0.0, 1.0);
            PatternMatrix sq = m.pow(2);
            if (std::fabs(sq.b() - 4.0) > 1e-9) return 1;
            if (std::fabs(m.det() - 1.0) > 1e-9) return 2;
            if (m.is_singular()) return 3;
            PatternMatrix id = m.pow(0);
            if (std::fabs(id.a() - 1.0) > 1e-9 || std::fabs(id.b()) > 1e-9 || std::fabs(id.c()) > 1e-9 || std::fabs(id.d() - 1.0) > 1e-9) return 4;
            PatternMatrix inv = m.inverse();
            if (std::fabs(inv.b() + 2.0) > 1e-9) return 5;
            if (m.render() != "1.000000|2.000000;0.000000|1.000000") return 6;
            PatternMatrix s = m + PatternMatrix(0.0, 0.0, 3.0, 0.0);
            if (std::fabs(s.c() - 3.0) > 1e-9) return 7;
            return 0;
            """,
            """
            PatternMatrix z(2.0, 4.0, 1.0, 2.0);
            if (!z.is_singular()) return 1;
            bool threw = false;
            try { z.inverse(); } catch (const PatternError&) { threw = true; }
            if (!threw) return 2;
            PatternMatrix m(2.0, 0.0, 0.0, 2.0);
            PatternMatrix cube = m.pow(3);
            if (std::fabs(cube.a() - 8.0) > 1e-9 || std::fabs(cube.d() - 8.0) > 1e-9) return 3;
            if (std::fabs(cube.det() - 64.0) > 1e-9) return 4;
            PatternMatrix n(1.0, 1.0, 1.0, 0.0);
            if (std::fabs(n.det() + 1.0) > 1e-9) return 5;
            PatternMatrix ni = n.inverse();
            if (std::fabs(ni.a()) > 1e-9 || std::fabs(ni.b() - 1.0) > 1e-9 || std::fabs(ni.c() - 1.0) > 1e-9 || std::fabs(ni.d() + 1.0) > 1e-9) return 6;
            PatternMatrix prod = m * n;
            if (std::fabs(prod.det() + 4.0) > 1e-9) return 7;
            if (prod.render() != "2.000000|2.000000;2.000000|0.000000") return 8;
            threw = false;
            try { PatternMatrix(0.0, 0.0, 0.0, 0.0).inverse(); } catch (const PatternError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "matrix powers and exact singularity detection over the 2x2 bilinear product",
            "any linear-algebra library, std::complex, <complex>, or a det computed with a plus sign",
            "pow(0) identity, the product-determinant law, singularity boundaries, adjugate inverse, and exact render bytes",
            "determinant-law oracle with a sign-flip discriminator in a paired .h/.cpp API",
            "2x2 matrix value type",
        ),
        c(
            "f26cpx-freight-tonnage-ledger",
            "Freight tonnage ledger",
            "freight_tonnage",
            """
            class TonnageError : public std::domain_error {
            public:
                explicit TonnageError(const std::string& message) : std::domain_error(message) {}
            };
            class Tonnes {
            public:
                explicit Tonnes(long millis);
                static Tonnes from_whole(long whole);
                static Tonnes from_millis(long millis);
                long millis() const;
                Tonnes operator+(const Tonnes& other) const;
                Tonnes operator-(const Tonnes& other) const;
                Tonnes scale(long num, long den) const;
                Tonnes share(long parts) const;
                bool operator==(const Tonnes& other) const;
                bool operator<(const Tonnes& other) const;
                std::string render() const;
            };
            """,
            """
            class TonnageError : public std::domain_error {
            public:
                explicit TonnageError(const std::string& message) : std::domain_error(message) {}
            };
            class Tonnes {
            public:
                explicit Tonnes(long millis);
                static Tonnes from_whole(long whole);
                static Tonnes from_millis(long millis);
                long millis() const;
                Tonnes operator+(const Tonnes& other) const;
                Tonnes operator-(const Tonnes& other) const;
                Tonnes scale(long num, long den) const;
                Tonnes share(long parts) const;
                bool operator==(const Tonnes& other) const;
                bool operator<(const Tonnes& other) const;
                std::string render() const;
            private:
                long millis_;
            };
            """,
            """
            Tonnes::Tonnes(long millis) : millis_(millis) {}
            Tonnes Tonnes::from_whole(long whole) { return Tonnes(whole * 1000L); }
            Tonnes Tonnes::from_millis(long millis) { return Tonnes(millis); }
            long Tonnes::millis() const { return millis_; }
            Tonnes Tonnes::operator+(const Tonnes& other) const {
                return Tonnes(millis_ + other.millis_);
            }
            Tonnes Tonnes::operator-(const Tonnes& other) const {
                return Tonnes(millis_ - other.millis_);
            }
            Tonnes Tonnes::scale(long num, long den) const {
                if (den == 0) throw TonnageError("zero denominator");
                long n = millis_ * num;
                long d = den;
                if (d < 0) { d = -d; n = -n; }
                long q = n / d;
                long r = n % d;
                long magnitude = r < 0 ? -r : r;
                if (2 * magnitude > d || (2 * magnitude == d && (q % 2 != 0))) {
                    q += (n < 0 ? -1 : 1);
                }
                return Tonnes(q);
            }
            Tonnes Tonnes::share(long parts) const {
                if (parts <= 0) throw TonnageError("non-positive share count");
                return scale(1, parts);
            }
            bool Tonnes::operator==(const Tonnes& other) const { return millis_ == other.millis_; }
            bool Tonnes::operator<(const Tonnes& other) const { return millis_ < other.millis_; }
            std::string Tonnes::render() const {
                long value = millis_;
                std::string sign;
                if (value < 0) { sign = "-"; value = -value; }
                std::ostringstream out;
                out << sign << (value / 1000) << "." << std::setw(3) << std::setfill('0') << (value % 1000);
                return out.str();
            }
            """,
            """
            Tonnes::Tonnes(long millis) : millis_(millis) {}
            Tonnes Tonnes::from_whole(long whole) { return Tonnes(whole * 1000L); }
            Tonnes Tonnes::from_millis(long millis) { return Tonnes(millis); }
            long Tonnes::millis() const { return millis_; }
            Tonnes Tonnes::operator+(const Tonnes& other) const {
                return Tonnes(millis_ + other.millis_);
            }
            Tonnes Tonnes::operator-(const Tonnes& other) const {
                return Tonnes(millis_ - other.millis_);
            }
            Tonnes Tonnes::scale(long num, long den) const {
                if (den == 0) throw TonnageError("zero denominator");
                long n = millis_ * num;
                long d = den;
                if (d < 0) { d = -d; n = -n; }
                return Tonnes(n / d);
            }
            Tonnes Tonnes::share(long parts) const {
                if (parts <= 0) throw TonnageError("non-positive share count");
                return scale(1, parts);
            }
            bool Tonnes::operator==(const Tonnes& other) const { return millis_ == other.millis_; }
            bool Tonnes::operator<(const Tonnes& other) const { return millis_ < other.millis_; }
            std::string Tonnes::render() const {
                long value = millis_;
                std::string sign;
                if (value < 0) { sign = "-"; value = -value; }
                std::ostringstream out;
                out << sign << (value / 1000) << "." << std::setw(3) << std::setfill('0') << (value % 1000);
                return out.str();
            }
            """,
            """
            Tonnes a = Tonnes::from_whole(12);
            if (a.millis() != 12000) return 1;
            Tonnes b = Tonnes::from_millis(3450);
            if (b.millis() != 3450) return 2;
            Tonnes s = a + b;
            if (s.millis() != 15450) return 3;
            if (s.render() != "15.450") return 4;
            Tonnes d = a - b;
            if (d.render() != "8.550") return 5;
            Tonnes h = a.share(2);
            if (h.millis() != 6000) return 6;
            if (!(b < a)) return 7;
            if (!(a == Tonnes::from_whole(12))) return 8;
            return 0;
            """,
            """
            if (Tonnes::from_millis(5).scale(1, 2).millis() != 2) return 1;
            if (Tonnes::from_millis(7).scale(1, 2).millis() != 4) return 2;
            if (Tonnes::from_millis(-5).scale(1, 2).millis() != -2) return 3;
            if (Tonnes::from_millis(-7).scale(1, 2).millis() != -4) return 4;
            if (Tonnes::from_millis(3).scale(1, 2).millis() != 2) return 5;
            if (Tonnes::from_millis(10).scale(3, 4).millis() != 8) return 6;
            if (Tonnes::from_millis(1).share(3).millis() != 0) return 7;
            bool threw = false;
            try { Tonnes::from_millis(5).scale(1, 0); } catch (const TonnageError&) { threw = true; }
            if (!threw) return 8;
            threw = false;
            try { Tonnes::from_millis(5).share(0); } catch (const TonnageError&) { threw = true; }
            if (!threw) return 9;
            threw = false;
            try { Tonnes::from_millis(5).share(-2); } catch (const TonnageError&) { threw = true; }
            if (!threw) return 10;
            if (Tonnes::from_millis(-12340).render() != "-12.340") return 11;
            if (Tonnes::from_millis(-5).render() != "-0.005") return 12;
            if (Tonnes::from_millis(1000001).render() != "1000.001") return 13;
            if (Tonnes::from_millis(5).scale(-1, -2).millis() != 2) return 14;
            if (!(Tonnes::from_millis(-1) < Tonnes::from_millis(0))) return 15;
            return 0;
            """,
            "integer-millis fixed-point arithmetic with round-half-to-even scaling and exact equality",
            "any double internal representation or a truncating scale; do not use floating-point rounding helpers",
            "half-even rounding at exact halves with both signs, negative-denominator scaling, exact render including small negatives, and share rejection",
            "banker's-rounding policy with exact integer equality in a project-context paired .h/.cpp layout",
            "fixed-point value type",
            project_support=True,
        ),
        c(
            "f26cpx-lab-reagent-mass",
            "Lab reagent mass",
            "reagent_mass",
            """
            class ReagentError : public std::domain_error {
            public:
                explicit ReagentError(const std::string& message) : std::domain_error(message) {}
            };
            class Micrograms {
            public:
                explicit Micrograms(long micros);
                static Micrograms from_milligrams(long milligrams);
                long micros() const;
                Micrograms operator+(const Micrograms& other) const;
                Micrograms operator-(const Micrograms& other) const;
                Micrograms dilute(long num, long den) const;
                std::vector<Micrograms> split(long parts) const;
                bool operator==(const Micrograms& other) const;
                bool operator<(const Micrograms& other) const;
                std::string render() const;
            };
            """,
            """
            class ReagentError : public std::domain_error {
            public:
                explicit ReagentError(const std::string& message) : std::domain_error(message) {}
            };
            class Micrograms {
            public:
                explicit Micrograms(long micros);
                static Micrograms from_milligrams(long milligrams);
                long micros() const;
                Micrograms operator+(const Micrograms& other) const;
                Micrograms operator-(const Micrograms& other) const;
                Micrograms dilute(long num, long den) const;
                std::vector<Micrograms> split(long parts) const;
                bool operator==(const Micrograms& other) const;
                bool operator<(const Micrograms& other) const;
                std::string render() const;
            private:
                long micros_;
            };
            """,
            """
            Micrograms::Micrograms(long micros) : micros_(micros) {}
            Micrograms Micrograms::from_milligrams(long milligrams) { return Micrograms(milligrams * 1000L); }
            long Micrograms::micros() const { return micros_; }
            Micrograms Micrograms::operator+(const Micrograms& other) const {
                return Micrograms(micros_ + other.micros_);
            }
            Micrograms Micrograms::operator-(const Micrograms& other) const {
                return Micrograms(micros_ - other.micros_);
            }
            Micrograms Micrograms::dilute(long num, long den) const {
                if (den <= 0) throw ReagentError("non-positive denominator");
                long n = micros_ * num;
                long q = n / den;
                long r = n % den;
                long magnitude = r < 0 ? -r : r;
                if (2 * magnitude >= den) q += (n < 0 ? -1 : 1);
                return Micrograms(q);
            }
            std::vector<Micrograms> Micrograms::split(long parts) const {
                if (parts <= 0) throw ReagentError("non-positive split count");
                long base = micros_ / parts;
                long rem = micros_ % parts;
                long step = (rem > 0) - (rem < 0);
                long extra = rem < 0 ? -rem : rem;
                std::vector<Micrograms> out;
                out.reserve(static_cast<std::size_t>(parts));
                for (long i = 0; i < parts; ++i) {
                    out.emplace_back(base + (i < extra ? step : 0));
                }
                return out;
            }
            bool Micrograms::operator==(const Micrograms& other) const { return micros_ == other.micros_; }
            bool Micrograms::operator<(const Micrograms& other) const { return micros_ < other.micros_; }
            std::string Micrograms::render() const {
                long value = micros_;
                std::string sign;
                if (value < 0) { sign = "-"; value = -value; }
                std::ostringstream out;
                out << sign << (value / 1000000) << "." << std::setw(6) << std::setfill('0') << (value % 1000000);
                return out.str();
            }
            """,
            """
            Micrograms::Micrograms(long micros) : micros_(micros) {}
            Micrograms Micrograms::from_milligrams(long milligrams) { return Micrograms(milligrams * 1000L); }
            long Micrograms::micros() const { return micros_; }
            Micrograms Micrograms::operator+(const Micrograms& other) const {
                return Micrograms(micros_ + other.micros_);
            }
            Micrograms Micrograms::operator-(const Micrograms& other) const {
                return Micrograms(micros_ - other.micros_);
            }
            Micrograms Micrograms::dilute(long num, long den) const {
                if (den <= 0) throw ReagentError("non-positive denominator");
                long n = micros_ * num;
                long q = n / den;
                long r = n % den;
                long magnitude = r < 0 ? -r : r;
                if (2 * magnitude >= den) q += (n < 0 ? -1 : 1);
                return Micrograms(q);
            }
            std::vector<Micrograms> Micrograms::split(long parts) const {
                if (parts <= 0) throw ReagentError("non-positive split count");
                long base = micros_ / parts;
                std::vector<Micrograms> out;
                out.reserve(static_cast<std::size_t>(parts));
                for (long i = 0; i < parts; ++i) {
                    out.emplace_back(base);
                }
                return out;
            }
            bool Micrograms::operator==(const Micrograms& other) const { return micros_ == other.micros_; }
            bool Micrograms::operator<(const Micrograms& other) const { return micros_ < other.micros_; }
            std::string Micrograms::render() const {
                long value = micros_;
                std::string sign;
                if (value < 0) { sign = "-"; value = -value; }
                std::ostringstream out;
                out << sign << (value / 1000000) << "." << std::setw(6) << std::setfill('0') << (value % 1000000);
                return out.str();
            }
            """,
            """
            Micrograms a = Micrograms::from_milligrams(2000);
            if (a.micros() != 2000000) return 1;
            Micrograms b(1500000);
            Micrograms s = a + b;
            if (s.micros() != 3500000) return 2;
            if (s.render() != "3.500000") return 3;
            Micrograms d = a - b;
            if (d.render() != "0.500000") return 4;
            std::vector<Micrograms> parts = b.split(2);
            if (parts.size() != 2 || parts[0].micros() != 750000 || parts[1].micros() != 750000) return 5;
            Micrograms dl = a.dilute(1, 2);
            if (dl.micros() != 1000000) return 6;
            if (!(b < a)) return 7;
            if (!(a == Micrograms(2000000))) return 8;
            return 0;
            """,
            """
            std::vector<Micrograms> parts = Micrograms(10).split(3);
            if (parts.size() != 3) return 1;
            if (parts[0].micros() != 4 || parts[1].micros() != 3 || parts[2].micros() != 3) return 2;
            long total = 0;
            for (const Micrograms& p : parts) total += p.micros();
            if (total != 10) return 3;
            std::vector<Micrograms> neg_parts = Micrograms(-10).split(3);
            if (neg_parts[0].micros() != -4 || neg_parts[1].micros() != -3 || neg_parts[2].micros() != -3) return 4;
            long neg_total = 0;
            for (const Micrograms& p : neg_parts) neg_total += p.micros();
            if (neg_total != -10) return 5;
            if (Micrograms(5).dilute(1, 2).micros() != 3) return 6;
            if (Micrograms(-5).dilute(1, 2).micros() != -3) return 7;
            if (Micrograms(7).dilute(1, 2).micros() != 4) return 8;
            bool threw = false;
            try { Micrograms(5).dilute(1, 0); } catch (const ReagentError&) { threw = true; }
            if (!threw) return 9;
            threw = false;
            try { Micrograms(5).dilute(1, -2); } catch (const ReagentError&) { threw = true; }
            if (!threw) return 10;
            threw = false;
            try { Micrograms(5).split(0); } catch (const ReagentError&) { threw = true; }
            if (!threw) return 11;
            if (Micrograms(-1234567).render() != "-1.234567") return 12;
            if (Micrograms(42).render() != "0.000042") return 13;
            if (!(Micrograms(-1) < Micrograms(0))) return 14;
            std::vector<Micrograms> one = Micrograms(7).split(1);
            if (one.size() != 1 || one[0].micros() != 7) return 15;
            return 0;
            """,
            "integer-microgram fixed-point with half-away dilution and a deterministic remainder-distributing split",
            "any double internal representation or a split that drops the remainder; do not use floating-point rounding helpers",
            "split portions summing exactly to the source with remainder on the first portions in order, negative splits, half-away rounding at exact halves, and exact render",
            "deterministic partitioning oracle over fixed-point values in a paired .h/.cpp API",
            "fixed-point value type",
        ),
        c(
            "f26cpx-gyro-orientation-frame",
            "Gyro orientation frame",
            "gyro_frame",
            """
            class FrameError : public std::domain_error {
            public:
                explicit FrameError(const std::string& message) : std::domain_error(message) {}
            };
            class Frame {
            public:
                Frame(double w, double x, double y, double z);
                double w() const;
                double x() const;
                double y() const;
                double z() const;
                Frame operator+(const Frame& other) const;
                Frame operator*(const Frame& other) const;
                Frame flip() const;
                double gauge() const;
                Frame inverse() const;
                Frame scale(double factor) const;
            };
            bool nearly_equal(const Frame& left, const Frame& right, double eps);
            """,
            """
            class FrameError : public std::domain_error {
            public:
                explicit FrameError(const std::string& message) : std::domain_error(message) {}
            };
            class Frame {
            public:
                Frame(double w, double x, double y, double z);
                double w() const;
                double x() const;
                double y() const;
                double z() const;
                Frame operator+(const Frame& other) const;
                Frame operator*(const Frame& other) const;
                Frame flip() const;
                double gauge() const;
                Frame inverse() const;
                Frame scale(double factor) const;
            private:
                double w_;
                double x_;
                double y_;
                double z_;
            };
            bool nearly_equal(const Frame& left, const Frame& right, double eps);
            """,
            """
            Frame::Frame(double w, double x, double y, double z) : w_(w), x_(x), y_(y), z_(z) {}
            double Frame::w() const { return w_; }
            double Frame::x() const { return x_; }
            double Frame::y() const { return y_; }
            double Frame::z() const { return z_; }
            Frame Frame::operator+(const Frame& other) const {
                return Frame(w_ + other.w_, x_ + other.x_, y_ + other.y_, z_ + other.z_);
            }
            Frame Frame::operator*(const Frame& other) const {
                return Frame(w_ * other.w_ - x_ * other.x_ - y_ * other.y_ - z_ * other.z_,
                             w_ * other.x_ + x_ * other.w_ + y_ * other.z_ - z_ * other.y_,
                             w_ * other.y_ - x_ * other.z_ + y_ * other.w_ + z_ * other.x_,
                             w_ * other.z_ + x_ * other.y_ - y_ * other.x_ + z_ * other.w_);
            }
            Frame Frame::flip() const {
                return Frame(w_, -x_, -y_, -z_);
            }
            double Frame::gauge() const {
                return w_ * w_ + x_ * x_ + y_ * y_ + z_ * z_;
            }
            Frame Frame::inverse() const {
                double g = gauge();
                if (g == 0.0) throw FrameError("zero-gauge frame");
                return Frame(w_ / g, -x_ / g, -y_ / g, -z_ / g);
            }
            Frame Frame::scale(double factor) const {
                return Frame(factor * w_, factor * x_, factor * y_, factor * z_);
            }
            bool nearly_equal(const Frame& left, const Frame& right, double eps) {
                return std::fabs(left.w() - right.w()) <= eps
                    && std::fabs(left.x() - right.x()) <= eps
                    && std::fabs(left.y() - right.y()) <= eps
                    && std::fabs(left.z() - right.z()) <= eps;
            }
            """,
            """
            Frame::Frame(double w, double x, double y, double z) : w_(w), x_(x), y_(y), z_(z) {}
            double Frame::w() const { return w_; }
            double Frame::x() const { return x_; }
            double Frame::y() const { return y_; }
            double Frame::z() const { return z_; }
            Frame Frame::operator+(const Frame& other) const {
                return Frame(w_ + other.w_, x_ + other.x_, y_ + other.y_, z_ + other.z_);
            }
            Frame Frame::operator*(const Frame& other) const {
                return Frame(w_ * other.w_ - x_ * other.x_ - y_ * other.y_ - z_ * other.z_,
                             w_ * other.x_ + x_ * other.w_ + y_ * other.z_ - z_ * other.y_,
                             w_ * other.y_ - x_ * other.z_ + y_ * other.w_ + z_ * other.x_,
                             w_ * other.z_ - x_ * other.y_ - y_ * other.x_ + z_ * other.w_);
            }
            Frame Frame::flip() const {
                return Frame(w_, -x_, -y_, -z_);
            }
            double Frame::gauge() const {
                return w_ * w_ + x_ * x_ + y_ * y_ + z_ * z_;
            }
            Frame Frame::inverse() const {
                double g = gauge();
                if (g == 0.0) throw FrameError("zero-gauge frame");
                return Frame(w_ / g, -x_ / g, -y_ / g, -z_ / g);
            }
            Frame Frame::scale(double factor) const {
                return Frame(factor * w_, factor * x_, factor * y_, factor * z_);
            }
            bool nearly_equal(const Frame& left, const Frame& right, double eps) {
                return std::fabs(left.w() - right.w()) <= eps
                    && std::fabs(left.x() - right.x()) <= eps
                    && std::fabs(left.y() - right.y()) <= eps
                    && std::fabs(left.z() - right.z()) <= eps;
            }
            """,
            """
            Frame i(1.0, 0.0, 0.0, 0.0);
            Frame qx(0.0, 1.0, 0.0, 0.0);
            Frame qy(0.0, 0.0, 1.0, 0.0);
            Frame qz(0.0, 0.0, 0.0, 1.0);
            Frame xy = qx * qy;
            if (std::fabs(xy.w()) > 1e-12 || std::fabs(xy.x()) > 1e-12 || std::fabs(xy.y()) > 1e-12 || std::fabs(xy.z() - 1.0) > 1e-12) return 1;
            Frame yx = qy * qx;
            if (std::fabs(yx.z() + 1.0) > 1e-12) return 2;
            Frame xx = qx * qx;
            if (std::fabs(xx.w() + 1.0) > 1e-12) return 3;
            Frame f(1.0, 2.0, 3.0, 4.0);
            if (std::fabs(f.gauge() - 30.0) > 1e-9) return 4;
            Frame fl = f.flip();
            if (std::fabs(fl.w() - 1.0) > 1e-9 || std::fabs(fl.x() + 2.0) > 1e-9 || std::fabs(fl.y() + 3.0) > 1e-9 || std::fabs(fl.z() + 4.0) > 1e-9) return 5;
            Frame id = f * f.inverse();
            if (!nearly_equal(id, i, 1e-9)) return 6;
            Frame sc = i.scale(2.0);
            if (std::fabs(sc.w() - 2.0) > 1e-12) return 7;
            return 0;
            """,
            """
            Frame a(1.0, 1.0, 0.0, 0.0);
            Frame b(0.0, 0.0, 1.0, 1.0);
            Frame ab = a * b;
            if (std::fabs(ab.w()) > 1e-12 || std::fabs(ab.z() - 2.0) > 1e-12) return 1;
            Frame ba = b * a;
            if (std::fabs(ba.y() - 2.0) > 1e-12 || std::fabs(ba.z()) > 1e-12) return 2;
            if (nearly_equal(ab, ba, 1e-9)) return 3;
            Frame z = a * a.flip();
            if (std::fabs(z.w() - 2.0) > 1e-9 || std::fabs(z.x()) > 1e-9 || std::fabs(z.y()) > 1e-9 || std::fabs(z.z()) > 1e-9) return 4;
            bool threw = false;
            try { Frame(0.0, 0.0, 0.0, 0.0).inverse(); } catch (const FrameError&) { threw = true; }
            if (!threw) return 5;
            Frame inv = a.inverse();
            if (std::fabs(inv.w() - 0.5) > 1e-9 || std::fabs(inv.x() + 0.5) > 1e-9) return 6;
            Frame s = a + b;
            if (std::fabs(s.gauge() - 4.0) > 1e-9) return 7;
            if (nearly_equal(a, Frame(1.0, 1.0 + 1e-6, 0.0, 0.0), 1e-9)) return 8;
            Frame rt = (a * b) * b.inverse();
            if (!nearly_equal(rt, a, 1e-9)) return 9;
            return 0;
            """,
            "the 16-term Hamilton product table with flip involution, squared gauge, and gauge-based inversion",
            "std::complex, <complex>, or any rotation library; do not flip the sign of any product-table term",
            "non-commutativity on named pairs, the q-times-flip gauge identity, the inverse round trip, and zero-gauge rejection",
            "non-commutative bilinear product with a norm-based inverse in a project-context paired .h/.cpp layout",
            "orientation quadruple value type",
            project_support=True,
        ),
        c(
            "f26cpx-satellite-attitude-ring",
            "Satellite attitude ring",
            "attitude_ring",
            """
            class AttitudeError : public std::domain_error {
            public:
                explicit AttitudeError(const std::string& message) : std::domain_error(message) {}
            };
            class AttitudeRing {
            public:
                AttitudeRing(double w, double x, double y, double z);
                double w() const;
                double x() const;
                double y() const;
                double z() const;
                AttitudeRing operator+(const AttitudeRing& other) const;
                AttitudeRing operator*(const AttitudeRing& other) const;
                AttitudeRing flip() const;
                double gauge() const;
                AttitudeRing inverse() const;
                std::array<double, 3> rotate3(double px, double py, double pz) const;
                std::string render() const;
            };
            """,
            """
            class AttitudeError : public std::domain_error {
            public:
                explicit AttitudeError(const std::string& message) : std::domain_error(message) {}
            };
            class AttitudeRing {
            public:
                AttitudeRing(double w, double x, double y, double z);
                double w() const;
                double x() const;
                double y() const;
                double z() const;
                AttitudeRing operator+(const AttitudeRing& other) const;
                AttitudeRing operator*(const AttitudeRing& other) const;
                AttitudeRing flip() const;
                double gauge() const;
                AttitudeRing inverse() const;
                std::array<double, 3> rotate3(double px, double py, double pz) const;
                std::string render() const;
            private:
                double w_;
                double x_;
                double y_;
                double z_;
            };
            """,
            """
            AttitudeRing::AttitudeRing(double w, double x, double y, double z) : w_(w), x_(x), y_(y), z_(z) {}
            double AttitudeRing::w() const { return w_; }
            double AttitudeRing::x() const { return x_; }
            double AttitudeRing::y() const { return y_; }
            double AttitudeRing::z() const { return z_; }
            AttitudeRing AttitudeRing::operator+(const AttitudeRing& other) const {
                return AttitudeRing(w_ + other.w_, x_ + other.x_, y_ + other.y_, z_ + other.z_);
            }
            AttitudeRing AttitudeRing::operator*(const AttitudeRing& other) const {
                return AttitudeRing(w_ * other.w_ - x_ * other.x_ - y_ * other.y_ - z_ * other.z_,
                                    w_ * other.x_ + x_ * other.w_ + y_ * other.z_ - z_ * other.y_,
                                    w_ * other.y_ - x_ * other.z_ + y_ * other.w_ + z_ * other.x_,
                                    w_ * other.z_ + x_ * other.y_ - y_ * other.x_ + z_ * other.w_);
            }
            AttitudeRing AttitudeRing::flip() const {
                return AttitudeRing(w_, -x_, -y_, -z_);
            }
            double AttitudeRing::gauge() const {
                return w_ * w_ + x_ * x_ + y_ * y_ + z_ * z_;
            }
            AttitudeRing AttitudeRing::inverse() const {
                double g = gauge();
                if (g == 0.0) throw AttitudeError("zero-gauge ring");
                return AttitudeRing(w_ / g, -x_ / g, -y_ / g, -z_ / g);
            }
            std::array<double, 3> AttitudeRing::rotate3(double px, double py, double pz) const {
                double g = gauge();
                if (g == 0.0) throw AttitudeError("zero-gauge ring");
                double len = std::sqrt(g);
                AttitudeRing unit(w_ / len, x_ / len, y_ / len, z_ / len);
                AttitudeRing point(0.0, px, py, pz);
                AttitudeRing rotated = unit * point * unit.inverse();
                return {rotated.x(), rotated.y(), rotated.z()};
            }
            std::string AttitudeRing::render() const {
                std::ostringstream out;
                out << std::fixed << std::setprecision(6) << w_ << ";" << x_ << ";" << y_ << ";" << z_;
                return out.str();
            }
            """,
            """
            AttitudeRing::AttitudeRing(double w, double x, double y, double z) : w_(w), x_(x), y_(y), z_(z) {}
            double AttitudeRing::w() const { return w_; }
            double AttitudeRing::x() const { return x_; }
            double AttitudeRing::y() const { return y_; }
            double AttitudeRing::z() const { return z_; }
            AttitudeRing AttitudeRing::operator+(const AttitudeRing& other) const {
                return AttitudeRing(w_ + other.w_, x_ + other.x_, y_ + other.y_, z_ + other.z_);
            }
            AttitudeRing AttitudeRing::operator*(const AttitudeRing& other) const {
                return AttitudeRing(w_ * other.w_ - x_ * other.x_ - y_ * other.y_ - z_ * other.z_,
                                    w_ * other.x_ + x_ * other.w_ + y_ * other.z_ - z_ * other.y_,
                                    w_ * other.y_ - x_ * other.z_ + y_ * other.w_ + z_ * other.x_,
                                    w_ * other.z_ + x_ * other.y_ - y_ * other.x_ + z_ * other.w_);
            }
            AttitudeRing AttitudeRing::flip() const {
                return AttitudeRing(w_, -x_, -y_, -z_);
            }
            double AttitudeRing::gauge() const {
                return w_ * w_ + x_ * x_ + y_ * y_ + z_ * z_;
            }
            AttitudeRing AttitudeRing::inverse() const {
                double g = gauge();
                if (g == 0.0) throw AttitudeError("zero-gauge ring");
                return AttitudeRing(w_ / g, -x_ / g, -y_ / g, -z_ / g);
            }
            std::array<double, 3> AttitudeRing::rotate3(double px, double py, double pz) const {
                double g = gauge();
                if (g == 0.0) throw AttitudeError("zero-gauge ring");
                double len = std::sqrt(g);
                AttitudeRing unit(w_ / len, x_ / len, y_ / len, z_ / len);
                AttitudeRing point(0.0, px, py, pz);
                AttitudeRing rotated = unit.inverse() * point * unit;
                return {rotated.x(), rotated.y(), rotated.z()};
            }
            std::string AttitudeRing::render() const {
                std::ostringstream out;
                out << std::fixed << std::setprecision(6) << w_ << ";" << x_ << ";" << y_ << ";" << z_;
                return out.str();
            }
            """,
            """
            const double kHalf = 0.7071067811865476;
            AttitudeRing q(kHalf, 0.0, 0.0, kHalf);
            std::array<double, 3> out = q.rotate3(1.0, 0.0, 0.0);
            if (std::fabs(out[0]) > 1e-9 || std::fabs(out[1] - 1.0) > 1e-9 || std::fabs(out[2]) > 1e-9) return 1;
            AttitudeRing big = q * AttitudeRing(2.0, 0.0, 0.0, 0.0);
            std::array<double, 3> out2 = big.rotate3(1.0, 0.0, 0.0);
            if (std::fabs(out2[0]) > 1e-9 || std::fabs(out2[1] - 1.0) > 1e-9 || std::fabs(out2[2]) > 1e-9) return 2;
            AttitudeRing i(1.0, 0.0, 0.0, 0.0);
            std::array<double, 3> same = i.rotate3(3.0, 4.0, 5.0);
            if (std::fabs(same[0] - 3.0) > 1e-9 || std::fabs(same[1] - 4.0) > 1e-9 || std::fabs(same[2] - 5.0) > 1e-9) return 3;
            if (q.render() != "0.707107;0.000000;0.000000;0.707107") return 4;
            AttitudeRing s = q + i;
            if (std::fabs(s.w() - (1.0 + kHalf)) > 1e-9) return 5;
            if (std::fabs(q.gauge() - 1.0) > 1e-9) return 6;
            return 0;
            """,
            """
            const double kHalf = 0.7071067811865476;
            AttitudeRing q(kHalf, 0.0, 0.0, kHalf);
            std::array<double, 3> y = q.rotate3(0.0, 1.0, 0.0);
            if (std::fabs(y[0] + 1.0) > 1e-9 || std::fabs(y[1]) > 1e-9 || std::fabs(y[2]) > 1e-9) return 1;
            std::array<double, 3> len = q.rotate3(3.0, 4.0, 0.0);
            double mag = std::sqrt(len[0] * len[0] + len[1] * len[1] + len[2] * len[2]);
            if (std::fabs(mag - 5.0) > 1e-9) return 2;
            bool threw = false;
            try { AttitudeRing(0.0, 0.0, 0.0, 0.0).rotate3(1.0, 0.0, 0.0); } catch (const AttitudeError&) { threw = true; }
            if (!threw) return 3;
            AttitudeRing about_x(kHalf, kHalf, 0.0, 0.0);
            std::array<double, 3> z = about_x.rotate3(0.0, 1.0, 0.0);
            if (std::fabs(z[0]) > 1e-9 || std::fabs(z[1]) > 1e-9 || std::fabs(z[2] - 1.0) > 1e-9) return 4;
            AttitudeRing f(1.0, 2.0, 3.0, 4.0);
            if (std::fabs(f.gauge() - 30.0) > 1e-9) return 5;
            AttitudeRing inv = f.inverse();
            AttitudeRing id = f * inv;
            if (std::fabs(id.w() - 1.0) > 1e-9 || std::fabs(id.x()) > 1e-9 || std::fabs(id.y()) > 1e-9 || std::fabs(id.z()) > 1e-9) return 6;
            if (f.render() != "1.000000;2.000000;3.000000;4.000000") return 7;
            AttitudeRing fl = f.flip();
            if (std::fabs(fl.x() + 2.0) > 1e-9 || std::fabs(fl.w() - 1.0) > 1e-9) return 8;
            threw = false;
            try { AttitudeRing(0.0, 0.0, 0.0, 0.0).inverse(); } catch (const AttitudeError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "normalized sandwich-product vector rotation over the Hamilton product table",
            "std::complex, <complex>, or any rotation library; do not skip normalization and do not apply the sandwich in reverse order",
            "a quarter turn about z mapping x to y and y to negative x, rotation preserving vector length, unnormalized rings normalized internally, and zero-gauge rejection",
            "composition-of-product surface with a normalization precondition in a paired .h/.cpp API",
            "orientation quadruple value type",
        ),
        c(
            "f26cpx-wind-tunnel-force",
            "Wind tunnel force",
            "wind_tunnel",
            """
            class ForceError : public std::domain_error {
            public:
                explicit ForceError(const std::string& message) : std::domain_error(message) {}
            };
            class ForceVec {
            public:
                ForceVec(double fx, double fy, double fz);
                double fx() const;
                double fy() const;
                double fz() const;
                ForceVec operator+(const ForceVec& other) const;
                ForceVec operator-(const ForceVec& other) const;
                ForceVec scale(double factor) const;
                double dot(const ForceVec& other) const;
                ForceVec cross(const ForceVec& other) const;
                double magnitude() const;
                ForceVec unit() const;
            };
            bool nearly_equal(const ForceVec& left, const ForceVec& right, double eps);
            """,
            """
            class ForceError : public std::domain_error {
            public:
                explicit ForceError(const std::string& message) : std::domain_error(message) {}
            };
            class ForceVec {
            public:
                ForceVec(double fx, double fy, double fz);
                double fx() const;
                double fy() const;
                double fz() const;
                ForceVec operator+(const ForceVec& other) const;
                ForceVec operator-(const ForceVec& other) const;
                ForceVec scale(double factor) const;
                double dot(const ForceVec& other) const;
                ForceVec cross(const ForceVec& other) const;
                double magnitude() const;
                ForceVec unit() const;
            private:
                double fx_;
                double fy_;
                double fz_;
            };
            bool nearly_equal(const ForceVec& left, const ForceVec& right, double eps);
            """,
            """
            ForceVec::ForceVec(double fx, double fy, double fz) : fx_(fx), fy_(fy), fz_(fz) {}
            double ForceVec::fx() const { return fx_; }
            double ForceVec::fy() const { return fy_; }
            double ForceVec::fz() const { return fz_; }
            ForceVec ForceVec::operator+(const ForceVec& other) const {
                return ForceVec(fx_ + other.fx_, fy_ + other.fy_, fz_ + other.fz_);
            }
            ForceVec ForceVec::operator-(const ForceVec& other) const {
                return ForceVec(fx_ - other.fx_, fy_ - other.fy_, fz_ - other.fz_);
            }
            ForceVec ForceVec::scale(double factor) const {
                return ForceVec(factor * fx_, factor * fy_, factor * fz_);
            }
            double ForceVec::dot(const ForceVec& other) const {
                return fx_ * other.fx_ + fy_ * other.fy_ + fz_ * other.fz_;
            }
            ForceVec ForceVec::cross(const ForceVec& other) const {
                return ForceVec(fy_ * other.fz_ - fz_ * other.fy_,
                                fz_ * other.fx_ - fx_ * other.fz_,
                                fx_ * other.fy_ - fy_ * other.fx_);
            }
            double ForceVec::magnitude() const {
                return std::sqrt(fx_ * fx_ + fy_ * fy_ + fz_ * fz_);
            }
            ForceVec ForceVec::unit() const {
                double mag = magnitude();
                if (mag == 0.0) throw ForceError("unit of a zero vector");
                return ForceVec(fx_ / mag, fy_ / mag, fz_ / mag);
            }
            bool nearly_equal(const ForceVec& left, const ForceVec& right, double eps) {
                return std::fabs(left.fx() - right.fx()) <= eps
                    && std::fabs(left.fy() - right.fy()) <= eps
                    && std::fabs(left.fz() - right.fz()) <= eps;
            }
            """,
            """
            ForceVec::ForceVec(double fx, double fy, double fz) : fx_(fx), fy_(fy), fz_(fz) {}
            double ForceVec::fx() const { return fx_; }
            double ForceVec::fy() const { return fy_; }
            double ForceVec::fz() const { return fz_; }
            ForceVec ForceVec::operator+(const ForceVec& other) const {
                return ForceVec(fx_ + other.fx_, fy_ + other.fy_, fz_ + other.fz_);
            }
            ForceVec ForceVec::operator-(const ForceVec& other) const {
                return ForceVec(fx_ - other.fx_, fy_ - other.fy_, fz_ - other.fz_);
            }
            ForceVec ForceVec::scale(double factor) const {
                return ForceVec(factor * fx_, factor * fy_, factor * fz_);
            }
            double ForceVec::dot(const ForceVec& other) const {
                return fx_ * other.fx_ + fy_ * other.fy_ + fz_ * other.fz_;
            }
            ForceVec ForceVec::cross(const ForceVec& other) const {
                return ForceVec(other.fy_ * fz_ - other.fz_ * fy_,
                                other.fz_ * fx_ - other.fx_ * fz_,
                                other.fx_ * fy_ - other.fy_ * fx_);
            }
            double ForceVec::magnitude() const {
                return std::sqrt(fx_ * fx_ + fy_ * fy_ + fz_ * fz_);
            }
            ForceVec ForceVec::unit() const {
                double mag = magnitude();
                if (mag == 0.0) throw ForceError("unit of a zero vector");
                return ForceVec(fx_ / mag, fy_ / mag, fz_ / mag);
            }
            bool nearly_equal(const ForceVec& left, const ForceVec& right, double eps) {
                return std::fabs(left.fx() - right.fx()) <= eps
                    && std::fabs(left.fy() - right.fy()) <= eps
                    && std::fabs(left.fz() - right.fz()) <= eps;
            }
            """,
            """
            ForceVec x(1.0, 0.0, 0.0);
            ForceVec y(0.0, 1.0, 0.0);
            ForceVec z = x.cross(y);
            if (std::fabs(z.fx()) > 1e-12 || std::fabs(z.fy()) > 1e-12 || std::fabs(z.fz() - 1.0) > 1e-12) return 1;
            ForceVec a(1.0, 2.0, 3.0);
            ForceVec b(4.0, 5.0, 6.0);
            if (std::fabs(a.dot(b) - 32.0) > 1e-9) return 2;
            if (std::fabs(a.magnitude() - std::sqrt(14.0)) > 1e-9) return 3;
            ForceVec s = a + b;
            if (std::fabs(s.fx() - 5.0) > 1e-9 || std::fabs(s.fz() - 9.0) > 1e-9) return 4;
            ForceVec u = ForceVec(0.0, 3.0, 4.0).unit();
            if (std::fabs(u.fy() - 0.6) > 1e-9 || std::fabs(u.fz() - 0.8) > 1e-9) return 5;
            ForceVec m = a.scale(2.0);
            if (std::fabs(m.fy() - 4.0) > 1e-9) return 6;
            if (!nearly_equal(a, ForceVec(1.0, 2.0, 3.0 + 1e-12), 1e-9)) return 7;
            return 0;
            """,
            """
            ForceVec x(1.0, 0.0, 0.0);
            ForceVec y(0.0, 1.0, 0.0);
            ForceVec rev = y.cross(x);
            if (std::fabs(rev.fz() + 1.0) > 1e-12) return 1;
            ForceVec par(2.0, 4.0, 6.0);
            ForceVec base(1.0, 2.0, 3.0);
            ForceVec zero = base.cross(par);
            if (std::fabs(zero.fx()) > 1e-12 || std::fabs(zero.fy()) > 1e-12 || std::fabs(zero.fz()) > 1e-12) return 2;
            ForceVec a(1.0, 1.0, 1.0);
            ForceVec b(2.0, -1.0, 0.5);
            ForceVec c = a.cross(b);
            if (std::fabs(c.fx() - 1.5) > 1e-9 || std::fabs(c.fy() - 1.5) > 1e-9 || std::fabs(c.fz() + 3.0) > 1e-9) return 3;
            if (std::fabs(a.dot(c)) > 1e-9) return 4;
            if (std::fabs(b.dot(c)) > 1e-9) return 5;
            bool threw = false;
            try { ForceVec(0.0, 0.0, 0.0).unit(); } catch (const ForceError&) { threw = true; }
            if (!threw) return 6;
            ForceVec d = a - b;
            if (std::fabs(d.fx() + 1.0) > 1e-9 || std::fabs(d.fy() - 2.0) > 1e-9 || std::fabs(d.fz() - 0.5) > 1e-9) return 7;
            ForceVec m = a.scale(-1.0);
            if (std::fabs(m.fx() + 1.0) > 1e-9) return 8;
            if (nearly_equal(a, ForceVec(1.0, 1.0 + 1e-6, 1.0), 1e-9)) return 9;
            return 0;
            """,
            "the right-handed cross product with dot, magnitude, and unit direction over three owned components",
            "any geometry library type, std::complex, <complex>, or the reversed cross-product operand order",
            "cross antisymmetry, cross of parallel vectors, cross perpendicular to both operands, unit rejection at the origin, and tolerance boundaries",
            "antisymmetric product oracle in three components in a paired .h/.cpp API",
            "3D vector value type",
        ),
        c(
            "f26cpx-rigging-load-path",
            "Rigging load path",
            "rigging_load",
            """
            class LoadError : public std::domain_error {
            public:
                explicit LoadError(const std::string& message) : std::domain_error(message) {}
            };
            class LoadVec {
            public:
                LoadVec(double fx, double fy, double fz);
                double fx() const;
                double fy() const;
                double fz() const;
                LoadVec operator+(const LoadVec& other) const;
                LoadVec operator-(const LoadVec& other) const;
                LoadVec scale(double factor) const;
                double dot(const LoadVec& other) const;
                LoadVec cross(const LoadVec& other) const;
                LoadVec project_onto(const LoadVec& other) const;
                double magnitude() const;
                std::string render() const;
            };
            """,
            """
            class LoadError : public std::domain_error {
            public:
                explicit LoadError(const std::string& message) : std::domain_error(message) {}
            };
            class LoadVec {
            public:
                LoadVec(double fx, double fy, double fz);
                double fx() const;
                double fy() const;
                double fz() const;
                LoadVec operator+(const LoadVec& other) const;
                LoadVec operator-(const LoadVec& other) const;
                LoadVec scale(double factor) const;
                double dot(const LoadVec& other) const;
                LoadVec cross(const LoadVec& other) const;
                LoadVec project_onto(const LoadVec& other) const;
                double magnitude() const;
                std::string render() const;
            private:
                double fx_;
                double fy_;
                double fz_;
            };
            """,
            """
            LoadVec::LoadVec(double fx, double fy, double fz) : fx_(fx), fy_(fy), fz_(fz) {}
            double LoadVec::fx() const { return fx_; }
            double LoadVec::fy() const { return fy_; }
            double LoadVec::fz() const { return fz_; }
            LoadVec LoadVec::operator+(const LoadVec& other) const {
                return LoadVec(fx_ + other.fx_, fy_ + other.fy_, fz_ + other.fz_);
            }
            LoadVec LoadVec::operator-(const LoadVec& other) const {
                return LoadVec(fx_ - other.fx_, fy_ - other.fy_, fz_ - other.fz_);
            }
            LoadVec LoadVec::scale(double factor) const {
                return LoadVec(factor * fx_, factor * fy_, factor * fz_);
            }
            double LoadVec::dot(const LoadVec& other) const {
                return fx_ * other.fx_ + fy_ * other.fy_ + fz_ * other.fz_;
            }
            LoadVec LoadVec::cross(const LoadVec& other) const {
                return LoadVec(fy_ * other.fz_ - fz_ * other.fy_,
                                fz_ * other.fx_ - fx_ * other.fz_,
                                fx_ * other.fy_ - fy_ * other.fx_);
            }
            LoadVec LoadVec::project_onto(const LoadVec& other) const {
                double norm = other.fx_ * other.fx_ + other.fy_ * other.fy_ + other.fz_ * other.fz_;
                if (norm == 0.0) throw LoadError("projection onto a zero vector");
                double k = (fx_ * other.fx_ + fy_ * other.fy_ + fz_ * other.fz_) / norm;
                return LoadVec(k * other.fx_, k * other.fy_, k * other.fz_);
            }
            double LoadVec::magnitude() const {
                return std::sqrt(fx_ * fx_ + fy_ * fy_ + fz_ * fz_);
            }
            std::string LoadVec::render() const {
                std::ostringstream out;
                out << "fx=" << std::fixed << std::setprecision(6) << fx_ << ";fy=" << fy_ << ";fz=" << fz_;
                return out.str();
            }
            """,
            """
            LoadVec::LoadVec(double fx, double fy, double fz) : fx_(fx), fy_(fy), fz_(fz) {}
            double LoadVec::fx() const { return fx_; }
            double LoadVec::fy() const { return fy_; }
            double LoadVec::fz() const { return fz_; }
            LoadVec LoadVec::operator+(const LoadVec& other) const {
                return LoadVec(fx_ + other.fx_, fy_ + other.fy_, fz_ + other.fz_);
            }
            LoadVec LoadVec::operator-(const LoadVec& other) const {
                return LoadVec(fx_ - other.fx_, fy_ - other.fy_, fz_ - other.fz_);
            }
            LoadVec LoadVec::scale(double factor) const {
                return LoadVec(factor * fx_, factor * fy_, factor * fz_);
            }
            double LoadVec::dot(const LoadVec& other) const {
                return fx_ * other.fx_ + fy_ * other.fy_ + fz_ * other.fz_;
            }
            LoadVec LoadVec::cross(const LoadVec& other) const {
                return LoadVec(fy_ * other.fz_ - fz_ * other.fy_,
                                fz_ * other.fx_ - fx_ * other.fz_,
                                fx_ * other.fy_ - fy_ * other.fx_);
            }
            LoadVec LoadVec::project_onto(const LoadVec& other) const {
                double norm = std::sqrt(other.fx_ * other.fx_ + other.fy_ * other.fy_ + other.fz_ * other.fz_);
                if (norm == 0.0) throw LoadError("projection onto a zero vector");
                double k = (fx_ * other.fx_ + fy_ * other.fy_ + fz_ * other.fz_) / norm;
                return LoadVec(k * other.fx_, k * other.fy_, k * other.fz_);
            }
            double LoadVec::magnitude() const {
                return std::sqrt(fx_ * fx_ + fy_ * fy_ + fz_ * fz_);
            }
            std::string LoadVec::render() const {
                std::ostringstream out;
                out << "fx=" << std::fixed << std::setprecision(6) << fx_ << ";fy=" << fy_ << ";fz=" << fz_;
                return out.str();
            }
            """,
            """
            LoadVec a(1.0, 2.0, 3.0);
            LoadVec axis(4.0, 0.0, 0.0);
            LoadVec p = a.project_onto(axis);
            if (std::fabs(p.fx() - 1.0) > 1e-9 || std::fabs(p.fy()) > 1e-9 || std::fabs(p.fz()) > 1e-9) return 1;
            LoadVec c = LoadVec(1.0, 0.0, 0.0).cross(LoadVec(0.0, 1.0, 0.0));
            if (std::fabs(c.fz() - 1.0) > 1e-12) return 2;
            if (std::fabs(a.magnitude() - std::sqrt(14.0)) > 1e-9) return 3;
            if (std::fabs(a.dot(axis) - 4.0) > 1e-9) return 4;
            LoadVec s = a + axis;
            if (std::fabs(s.fx() - 5.0) > 1e-9) return 5;
            LoadVec m = a.scale(0.5);
            if (std::fabs(m.fz() - 1.5) > 1e-9) return 6;
            if (a.render() != "fx=1.000000;fy=2.000000;fz=3.000000") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { LoadVec(1.0, 1.0, 1.0).project_onto(LoadVec(0.0, 0.0, 0.0)); } catch (const LoadError&) { threw = true; }
            if (!threw) return 1;
            LoadVec a(0.0, 0.0, 5.0);
            LoadVec neg_axis(0.0, 0.0, -1.0);
            LoadVec p = a.project_onto(neg_axis);
            if (std::fabs(p.fz() - 5.0) > 1e-9) return 2;
            LoadVec x(1.0, 0.0, 0.0);
            LoadVec y(0.0, 1.0, 0.0);
            LoadVec rev = y.cross(x);
            if (std::fabs(rev.fz() + 1.0) > 1e-12) return 3;
            LoadVec d = LoadVec(3.0, 4.0, 5.0) - LoadVec(1.0, 1.0, 1.0);
            if (std::fabs(d.fx() - 2.0) > 1e-9 || std::fabs(d.fy() - 3.0) > 1e-9 || std::fabs(d.fz() - 4.0) > 1e-9) return 4;
            if (d.render() != "fx=2.000000;fy=3.000000;fz=4.000000") return 5;
            LoadVec c = d.cross(LoadVec(0.0, 0.0, 1.0));
            if (std::fabs(c.fx() - 3.0) > 1e-9 || std::fabs(c.fy() + 2.0) > 1e-9 || std::fabs(c.fz()) > 1e-9) return 6;
            if (std::fabs(c.dot(d)) > 1e-9) return 7;
            LoadVec m = d.scale(-2.0);
            if (std::fabs(m.fx() + 4.0) > 1e-9) return 8;
            if (std::fabs(LoadVec(2.0, 3.0, 6.0).magnitude() - 7.0) > 1e-9) return 9;
            return 0;
            """,
            "3D projection by the exactly squared norm with cross product and an exact readout",
            "any geometry library type, std::complex, <complex>, or a projection divided by the unsquared magnitude",
            "projection onto axis and anti-axis vectors, projection rejection at the origin, cross perpendicular to both operands, and exact render bytes",
            "projection norm discipline in three components in a project-context paired .h/.cpp layout",
            "3D vector value type",
            project_support=True,
        ),
        c(
            "f26cpx-studio-master-gain",
            "Studio master gain",
            "studio_gain",
            """
            class GainError : public std::domain_error {
            public:
                explicit GainError(const std::string& message) : std::domain_error(message) {}
            };
            class Gain {
            public:
                explicit Gain(double linear);
                static Gain from_db(double db);
                double linear() const;
                double to_db() const;
                Gain combine(const Gain& other) const;
                Gain attenuate(const Gain& other) const;
            };
            bool nearly_equal_db(const Gain& left, const Gain& right, double eps_db);
            """,
            """
            class GainError : public std::domain_error {
            public:
                explicit GainError(const std::string& message) : std::domain_error(message) {}
            };
            class Gain {
            public:
                explicit Gain(double linear);
                static Gain from_db(double db);
                double linear() const;
                double to_db() const;
                Gain combine(const Gain& other) const;
                Gain attenuate(const Gain& other) const;
            private:
                double linear_;
            };
            bool nearly_equal_db(const Gain& left, const Gain& right, double eps_db);
            """,
            """
            Gain::Gain(double linear) : linear_(linear) {}
            Gain Gain::from_db(double db) {
                return Gain(std::pow(10.0, db / 20.0));
            }
            double Gain::linear() const { return linear_; }
            double Gain::to_db() const {
                if (linear_ <= 0.0) throw GainError("non-positive linear gain");
                return 20.0 * std::log10(linear_);
            }
            Gain Gain::combine(const Gain& other) const {
                return Gain(linear_ * other.linear_);
            }
            Gain Gain::attenuate(const Gain& other) const {
                if (other.linear_ == 0.0) throw GainError("zero divisor gain");
                return Gain(linear_ / other.linear_);
            }
            bool nearly_equal_db(const Gain& left, const Gain& right, double eps_db) {
                return std::fabs(left.to_db() - right.to_db()) <= eps_db;
            }
            """,
            """
            Gain::Gain(double linear) : linear_(linear) {}
            Gain Gain::from_db(double db) {
                return Gain(std::pow(10.0, db / 20.0));
            }
            double Gain::linear() const { return linear_; }
            double Gain::to_db() const {
                if (linear_ <= 0.0) throw GainError("non-positive linear gain");
                return 10.0 * std::log10(linear_);
            }
            Gain Gain::combine(const Gain& other) const {
                return Gain(linear_ * other.linear_);
            }
            Gain Gain::attenuate(const Gain& other) const {
                if (other.linear_ == 0.0) throw GainError("zero divisor gain");
                return Gain(linear_ / other.linear_);
            }
            bool nearly_equal_db(const Gain& left, const Gain& right, double eps_db) {
                return std::fabs(left.to_db() - right.to_db()) <= eps_db;
            }
            """,
            """
            Gain g = Gain::from_db(20.0);
            if (std::fabs(g.linear() - 10.0) > 1e-9) return 1;
            Gain h(2.0);
            if (std::fabs(h.to_db() - 6.020599913279624) > 1e-9) return 2;
            Gain c = h.combine(h);
            if (std::fabs(c.linear() - 4.0) > 1e-9) return 3;
            if (std::fabs(c.to_db() - 12.041199826559248) > 1e-9) return 4;
            Gain a = c.attenuate(h);
            if (std::fabs(a.linear() - 2.0) > 1e-9) return 5;
            if (!nearly_equal_db(Gain(2.0), Gain(2.0 * 1.0000001), 1e-3)) return 6;
            return 0;
            """,
            """
            Gain g(1.0);
            if (std::fabs(g.to_db()) > 1e-12) return 1;
            bool threw = false;
            try { Gain(0.0).to_db(); } catch (const GainError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { Gain(-1.0).to_db(); } catch (const GainError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { Gain(1.0).attenuate(Gain(0.0)); } catch (const GainError&) { threw = true; }
            if (!threw) return 4;
            Gain rt = Gain::from_db(3.010299956639812);
            if (std::fabs(rt.to_db() - 3.010299956639812) > 1e-9) return 5;
            Gain doubled = Gain(1.0).combine(Gain(2.0));
            if (std::fabs(doubled.to_db() - 6.020599913279624) > 1e-9) return 6;
            Gain quarter = Gain(1.0).attenuate(Gain(4.0));
            if (std::fabs(quarter.to_db() + 12.041199826559248) > 1e-9) return 7;
            if (nearly_equal_db(Gain(1.0), Gain(2.0), 1e-3)) return 8;
            Gain small = Gain::from_db(-6.020599913279624);
            if (std::fabs(small.linear() - 0.5) > 1e-9) return 9;
            return 0;
            """,
            "amplitude-domain 20-log10 decibel conversion with linear-domain combine and attenuate",
            "the 10*log10 power-domain factor or storing the dB value instead of the linear value",
            "the from_db/to_db round trip, exactly 6.020599913279624 dB per doubling, rejection at zero and negative linears, and zero-divisor attenuation",
            "domain-factor discrimination between two plausible logarithmic rules in a paired .h/.cpp API",
            "logarithmic gain value type",
        ),
        c(
            "f26cpx-hatchery-batch-stats",
            "Hatchery batch stats",
            "hatchery_stats",
            """
            class StatsError : public std::domain_error {
            public:
                explicit StatsError(const std::string& message) : std::domain_error(message) {}
            };
            class BatchStats {
            public:
                BatchStats();
                void add(double value);
                long count() const;
                double mean() const;
                double variance() const;
                double deviation() const;
                void merge(const BatchStats& other);
                void reset();
            };
            """,
            """
            class StatsError : public std::domain_error {
            public:
                explicit StatsError(const std::string& message) : std::domain_error(message) {}
            };
            class BatchStats {
            public:
                BatchStats();
                void add(double value);
                long count() const;
                double mean() const;
                double variance() const;
                double deviation() const;
                void merge(const BatchStats& other);
                void reset();
            private:
                long count_;
                double mean_;
                double m2_;
            };
            """,
            """
            BatchStats::BatchStats() : count_(0), mean_(0.0), m2_(0.0) {}
            void BatchStats::add(double value) {
                ++count_;
                double delta = value - mean_;
                mean_ += delta / static_cast<double>(count_);
                double delta2 = value - mean_;
                m2_ += delta * delta2;
            }
            long BatchStats::count() const { return count_; }
            double BatchStats::mean() const {
                if (count_ == 0) throw StatsError("mean of an empty batch");
                return mean_;
            }
            double BatchStats::variance() const {
                if (count_ < 2) throw StatsError("variance needs at least two samples");
                return m2_ / static_cast<double>(count_ - 1);
            }
            double BatchStats::deviation() const {
                return std::sqrt(variance());
            }
            void BatchStats::merge(const BatchStats& other) {
                if (other.count_ == 0) return;
                if (count_ == 0) {
                    count_ = other.count_;
                    mean_ = other.mean_;
                    m2_ = other.m2_;
                    return;
                }
                double delta = other.mean_ - mean_;
                double total = static_cast<double>(count_ + other.count_);
                m2_ += other.m2_ + delta * delta * static_cast<double>(count_) * static_cast<double>(other.count_) / total;
                mean_ += delta * static_cast<double>(other.count_) / total;
                count_ += other.count_;
            }
            void BatchStats::reset() {
                count_ = 0;
                mean_ = 0.0;
                m2_ = 0.0;
            }
            """,
            """
            BatchStats::BatchStats() : count_(0), mean_(0.0), m2_(0.0) {}
            void BatchStats::add(double value) {
                ++count_;
                double delta = value - mean_;
                mean_ += delta / static_cast<double>(count_);
                double delta2 = value - mean_;
                m2_ += delta * delta2;
            }
            long BatchStats::count() const { return count_; }
            double BatchStats::mean() const {
                if (count_ == 0) throw StatsError("mean of an empty batch");
                return mean_;
            }
            double BatchStats::variance() const {
                if (count_ < 2) throw StatsError("variance needs at least two samples");
                return m2_ / static_cast<double>(count_);
            }
            double BatchStats::deviation() const {
                return std::sqrt(variance());
            }
            void BatchStats::merge(const BatchStats& other) {
                if (other.count_ == 0) return;
                if (count_ == 0) {
                    count_ = other.count_;
                    mean_ = other.mean_;
                    m2_ = other.m2_;
                    return;
                }
                double delta = other.mean_ - mean_;
                double total = static_cast<double>(count_ + other.count_);
                m2_ += other.m2_ + delta * delta * static_cast<double>(count_) * static_cast<double>(other.count_) / total;
                mean_ += delta * static_cast<double>(other.count_) / total;
                count_ += other.count_;
            }
            void BatchStats::reset() {
                count_ = 0;
                mean_ = 0.0;
                m2_ = 0.0;
            }
            """,
            """
            BatchStats s;
            s.add(1.0);
            s.add(2.0);
            s.add(3.0);
            if (s.count() != 3) return 1;
            if (std::fabs(s.mean() - 2.0) > 1e-12) return 2;
            if (std::fabs(s.variance() - 1.0) > 1e-12) return 3;
            if (std::fabs(s.deviation() - 1.0) > 1e-12) return 4;
            BatchStats t;
            t.add(4.0);
            t.add(5.0);
            s.merge(t);
            if (s.count() != 5) return 5;
            if (std::fabs(s.mean() - 3.0) > 1e-12) return 6;
            if (std::fabs(s.variance() - 2.5) > 1e-12) return 7;
            s.reset();
            if (s.count() != 0) return 8;
            return 0;
            """,
            """
            BatchStats s;
            bool threw = false;
            try { s.mean(); } catch (const StatsError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { s.variance(); } catch (const StatsError&) { threw = true; }
            if (!threw) return 2;
            s.add(10.0);
            threw = false;
            try { s.variance(); } catch (const StatsError&) { threw = true; }
            if (!threw) return 3;
            if (std::fabs(s.mean() - 10.0) > 1e-12) return 4;
            s.add(12.0);
            if (std::fabs(s.variance() - 2.0) > 1e-12) return 5;
            BatchStats left;
            left.add(1.0);
            left.add(2.0);
            BatchStats right;
            right.add(3.0);
            right.add(4.0);
            right.add(5.0);
            left.merge(right);
            if (left.count() != 5) return 6;
            if (std::fabs(left.mean() - 3.0) > 1e-12) return 7;
            if (std::fabs(left.variance() - 2.5) > 1e-12) return 8;
            BatchStats empty;
            left.merge(empty);
            if (left.count() != 5 || std::fabs(left.mean() - 3.0) > 1e-12) return 9;
            BatchStats fresh;
            fresh.merge(left);
            if (fresh.count() != 5 || std::fabs(fresh.variance() - 2.5) > 1e-12) return 10;
            BatchStats big;
            big.add(1000000001.0);
            big.add(1000000002.0);
            big.add(1000000003.0);
            if (std::fabs(big.mean() - 1000000002.0) > 1e-6) return 11;
            if (std::fabs(big.variance() - 1.0) > 1e-6) return 12;
            big.reset();
            if (big.count() != 0) return 13;
            big.add(7.0);
            if (std::fabs(big.mean() - 7.0) > 1e-12) return 14;
            return 0;
            """,
            "Welford one-pass running mean and M2 with the parallel merge formula and the sample n-1 denominator",
            "the population denominator n or a two-pass sum-of-squares accumulation; do not answer undersampled queries without throwing",
            "the sample denominator at n=2, merge equalling one-pass accumulation of the concatenation, merge into and from empty accumulators, large-offset stability, undersampled rejection, and reset reuse",
            "stateful numeric lifecycle with an exact merge law in a project-context paired .h/.cpp layout",
            "streaming accumulator value type",
            project_support=True,
        ),
    )
    return rows


CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-cpx-seven-dimension-artifacts-v1"
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


_TEST_INCLUDES = """#include "{task_id}.h"

#include <array>
#include <cmath>
#include <optional>
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

Implement a clean-room C++17 numeric value-type component for a local
complex-numbers skill analog. This root is independently authored for SFT
task-family construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep operator and free-function semantics, product and quotient tables,
norm or gauge based inversion, division edges, tolerance or exact equality,
precision rules, involutions, and readout shapes deterministic and explicit for
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
                "source": "w8-biayn clean-room fixed26 complex-numbers analog curriculum",
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
description = "{spec.title}: normalization, division edges, tolerance boundaries, involutions, precision rules, and wrong-substitute rejection"

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
    if spec.task_id != "f26cpx-forge-heating-curve":
        _fail("control_mutation_drift", f"controls are bound to f26cpx-forge-heating-curve, got {spec.task_id}")
    if name == "domain-identifier-renamed":
        renamed_id = "f26cpx-kiln-heating-curve"
        mutated: dict[str, str] = {}
        for relative, content in sorted(files.items()):
            mutated[relative.replace(spec.task_id, renamed_id)] = content.replace(spec.task_id, renamed_id)
        changed = sorted(relative for relative, content in mutated.items() if files.get(relative) != content)
        return mutated, changed
    if name == "constants-or-policy-only":
        mutated = dict(files)
        visible = _apply_replacements(
            mutated["visible_test.cpp"],
            (
                ("1e-9", "1e-7"),
                ("a.scale(-2.0)", "a.scale(-3.0)"),
                (
                    "std::fabs(sc.temp() + 4.0) > 1e-7 || std::fabs(sc.rate() + 1.0) > 1e-7",
                    "std::fabs(sc.temp() + 6.0) > 1e-7 || std::fabs(sc.rate() + 1.5) > 1e-7",
                ),
            ),
            context="constants-or-policy-only:visible",
        )
        mutated["visible_test.cpp"] = visible
        mutated[".meta/private_test.cpp"] = _apply_replacements(
            mutated[".meta/private_test.cpp"],
            (("1e-9", "1e-7"), ("1e-6", "3e-7")),
            context="constants-or-policy-only:private",
        )
        return mutated, ["visible_test.cpp", ".meta/private_test.cpp"]
    if name == "opposite-end-selection":
        mutated = dict(files)
        mutated["visible_test.cpp"] = _apply_replacements(
            mutated["visible_test.cpp"],
            (
                ("HeatCurve a(2.0, 0.5);", "HeatCurve a(0.5, 2.0);"),
                ("HeatCurve b(3.0, -1.0);", "HeatCurve b(2.5, -11.0);"),
                (
                    "if (std::fabs(s.temp() - 5.0) > 1e-9 || std::fabs(s.rate() + 0.5) > 1e-9) return 1;",
                    "if (std::fabs(s.temp() - 3.0) > 1e-9 || std::fabs(s.rate() + 9.0) > 1e-9) return 1;",
                ),
                (
                    "if (std::fabs(p.temp() - 6.0) > 1e-9) return 2;",
                    "if (std::fabs(p.temp() - 1.25) > 1e-9) return 2;",
                ),
                (
                    "if (std::fabs(q.temp() - 2.0 / 3.0) > 1e-9) return 4;",
                    "if (std::fabs(q.temp() - 1.0 / 5.0) > 1e-9) return 4;",
                ),
                (
                    "if (std::fabs(q.rate() - 3.5 / 9.0) > 1e-9) return 5;",
                    "if (std::fabs(q.rate() - 8.4 / 5.0) > 1e-9) return 5;",
                ),
                (
                    "if (std::fabs(e.temp() - std::exp(2.0)) > 1e-9) return 6;",
                    "if (std::fabs(e.temp() - std::exp(0.5)) > 1e-9) return 6;",
                ),
                (
                    "if (std::fabs(e.rate() - 0.5 * std::exp(2.0)) > 1e-9) return 7;",
                    "if (std::fabs(e.rate() - 2.0 * std::exp(0.5)) > 1e-9) return 7;",
                ),
                (
                    "if (!nearly_equal(a, HeatCurve(2.0 + 1e-12, 0.5), 1e-9)) return 8;",
                    "if (!nearly_equal(a, HeatCurve(0.5 + 1e-12, 2.0), 1e-9)) return 8;",
                ),
                (
                    "if (std::fabs(sc.temp() + 4.0) > 1e-9 || std::fabs(sc.rate() + 1.0) > 1e-9) return 9;",
                    "if (std::fabs(sc.temp() + 1.0) > 1e-9 || std::fabs(sc.rate() + 4.0) > 1e-9) return 9;",
                ),
            ),
            context="opposite-end-selection:visible",
        )
        mutated[".meta/private_test.cpp"] = _apply_replacements(
            mutated[".meta/private_test.cpp"],
            (
                ("HeatCurve a(1.5, 2.0);", "HeatCurve a(2.0, 1.5);"),
                ("HeatCurve b(0.5, 0.25);", "HeatCurve b(0.5, 0.125);"),
                (
                    "if (std::fabs(q.temp() - 3.0) > 1e-9) return 1;",
                    "if (std::fabs(q.temp() - 4.0) > 1e-9) return 1;",
                ),
                (
                    "if (std::fabs(q.rate() - 2.5) > 1e-9) return 2;",
                    "if (std::fabs(q.rate() - 2.0) > 1e-9) return 2;",
                ),
                (
                    "if (std::fabs(p.temp() - 2.25) > 1e-9 || std::fabs(p.rate() - 6.0) > 1e-9) return 4;",
                    "if (std::fabs(p.temp() - 4.0) > 1e-9 || std::fabs(p.rate() - 6.0) > 1e-9) return 4;",
                ),
                (
                    "if (nearly_equal(a, HeatCurve(1.5 + 1e-6, 2.0), 1e-9)) return 6;",
                    "if (nearly_equal(a, HeatCurve(2.0 + 1e-6, 1.5), 1e-9)) return 6;",
                ),
                (
                    "if (std::fabs(d.temp() - 1.0) > 1e-9 || std::fabs(d.rate() - 1.75) > 1e-9) return 8;",
                    "if (std::fabs(d.temp() - 1.5) > 1e-9 || std::fabs(d.rate() - 1.375) > 1e-9) return 8;",
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
            "family": "complex-numbers",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "complex-numbers",
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
    text = re.sub(r"\bf26cpx[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        control_headers = sorted(path.name for path in control_root.glob("f26cpx-*.h"))
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
        "schema_version": "fixed26-cpx-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-cpx-fresh-") as temporary:
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
        "schema_version": "fixed26-cpx-core-v1",
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
for task_root in sorted(ROOT.glob("f26cpx-*")):
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
            "schema_version": "fixed26-cpx-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-cpx-docker-") as temporary:
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
        "schema_version": "fixed26-cpx-docker-sanity-v1",
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
        "schema_version": "fixed26-cpx-creator-preflight-v1",
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
        "capability": "fixed26-complex-analog",
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
            "task": "implement clean-room fixed26 complex-numbers analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned component fields with task-owned product and quotient tables; norm or gauge based inversion with explicit division edges; exact or tolerance-based equality through declared channels; deterministic precision and rounding rules; component involutions; exact deterministic readouts; rejected operations never mutate",
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
            "target_family": "complex-numbers",
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
