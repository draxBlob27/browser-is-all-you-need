"""Create and verify the fixed-26 binary-search-tree clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b004-binary-search-tree.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b004-binary-search-tree"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_bst_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_bst_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b004-binary-search-tree"
FAMILY_ID = "aider-fixed26-binary-search-tree-analogs-v1"
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
        "f26bst-observatory-star-chart",
        "f26bst-archive-box-ranges",
        "f26bst-museum-case-layout",
        "f26bst-terminal-gate-holds",
        "f26bst-mill-gear-train",
        "f26bst-parcel-chute-map",
        "f26bst-pantry-jar-counts",
        "f26bst-turnstile-scan-counts",
        "f26bst-elevator-stop-tree",
        "f26bst-greenhouse-row-journal",
        "f26bst-lighthouse-beam-index",
        "f26bst-ranch-paddock-gates",
        "f26bst-glacier-stake-grid",
        "f26bst-tunnel-bolt-map",
        "f26bst-desert-well-index",
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
            "f26bst-tide-gauge-ledger",
            "Tide gauge ledger",
            "tide_gauge",
            """
            class TideDuplicateError : public std::logic_error {
            public:
                explicit TideDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class TideAbsentError : public std::runtime_error {
            public:
                explicit TideAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class TideEmptyError : public std::domain_error {
            public:
                explicit TideEmptyError(const std::string& message) : std::domain_error(message) {}
            };
            class TideGaugeLedger {
            public:
                void record(std::int32_t station);
                void retire(std::int32_t station);
                bool has(std::int32_t station) const;
                std::size_t size() const;
                std::string channel_path(std::int32_t station) const;
                std::int32_t channel_depth(std::int32_t station) const;
                std::int32_t first_station() const;
            };
            """,
            """
            class TideDuplicateError : public std::logic_error {
            public:
                explicit TideDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class TideAbsentError : public std::runtime_error {
            public:
                explicit TideAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class TideEmptyError : public std::domain_error {
            public:
                explicit TideEmptyError(const std::string& message) : std::domain_error(message) {}
            };
            class TideGaugeLedger {
            public:
                void record(std::int32_t station);
                void retire(std::int32_t station);
                bool has(std::int32_t station) const;
                std::size_t size() const;
                std::string channel_path(std::int32_t station) const;
                std::int32_t channel_depth(std::int32_t station) const;
                std::int32_t first_station() const;
            private:
                struct Node {
                    std::int32_t station;
                    std::unique_ptr<Node> lower;
                    std::unique_ptr<Node> higher;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> head_;
                std::size_t count_ = 0;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t station, bool& removed);
            };
            """,
            """
            TideGaugeLedger::Node::Node(std::int32_t value) : station(value) {}
            bool TideGaugeLedger::has(std::int32_t station) const {
                const Node* current = head_.get();
                while (current) {
                    if (station == current->station) return true;
                    current = station < current->station ? current->lower.get() : current->higher.get();
                }
                return false;
            }
            std::size_t TideGaugeLedger::size() const { return count_; }
            void TideGaugeLedger::record(std::int32_t station) {
                if (!head_) {
                    head_ = std::make_unique<Node>(station);
                    count_ = 1;
                    return;
                }
                Node* current = head_.get();
                for (;;) {
                    if (station == current->station) throw TideDuplicateError("station already recorded");
                    if (station < current->station) {
                        if (!current->lower) {
                            current->lower = std::make_unique<Node>(station);
                            ++count_;
                            return;
                        }
                        current = current->lower.get();
                    } else {
                        if (!current->higher) {
                            current->higher = std::make_unique<Node>(station);
                            ++count_;
                            return;
                        }
                        current = current->higher.get();
                    }
                }
            }
            std::unique_ptr<TideGaugeLedger::Node> TideGaugeLedger::unlink(std::unique_ptr<Node> node, std::int32_t station, bool& removed) {
                if (!node) return nullptr;
                if (station < node->station) {
                    node->lower = unlink(std::move(node->lower), station, removed);
                    return node;
                }
                if (node->station < station) {
                    node->higher = unlink(std::move(node->higher), station, removed);
                    return node;
                }
                removed = true;
                if (!node->lower) return std::move(node->higher);
                if (!node->higher) return std::move(node->lower);
                Node* successor = node->higher.get();
                while (successor->lower) successor = successor->lower.get();
                node->station = successor->station;
                bool ignored = false;
                node->higher = unlink(std::move(node->higher), successor->station, ignored);
                return node;
            }
            void TideGaugeLedger::retire(std::int32_t station) {
                bool removed = false;
                head_ = unlink(std::move(head_), station, removed);
                if (!removed) throw TideAbsentError("station is not recorded");
                --count_;
            }
            std::string TideGaugeLedger::channel_path(std::int32_t station) const {
                const Node* current = head_.get();
                std::string path = "root";
                while (current) {
                    if (station == current->station) return path;
                    if (station < current->station) {
                        path += ">L";
                        current = current->lower.get();
                    } else {
                        path += ">R";
                        current = current->higher.get();
                    }
                }
                throw TideAbsentError("station is not recorded");
            }
            std::int32_t TideGaugeLedger::channel_depth(std::int32_t station) const {
                const Node* current = head_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (station == current->station) return depth;
                    ++depth;
                    current = station < current->station ? current->lower.get() : current->higher.get();
                }
                throw TideAbsentError("station is not recorded");
            }
            std::int32_t TideGaugeLedger::first_station() const {
                if (!head_) throw TideEmptyError("ledger is empty");
                return head_->station;
            }
            """,
            """
            TideGaugeLedger::Node::Node(std::int32_t value) : station(value) {}
            bool TideGaugeLedger::has(std::int32_t station) const {
                const Node* current = head_.get();
                while (current) {
                    if (station == current->station) return true;
                    current = current->higher.get();
                }
                return false;
            }
            std::size_t TideGaugeLedger::size() const { return count_; }
            void TideGaugeLedger::record(std::int32_t station) {
                if (has(station)) throw TideDuplicateError("station already recorded");
                if (!head_) {
                    head_ = std::make_unique<Node>(station);
                    count_ = 1;
                    return;
                }
                Node* current = head_.get();
                while (current->higher) current = current->higher.get();
                current->higher = std::make_unique<Node>(station);
                ++count_;
            }
            void TideGaugeLedger::retire(std::int32_t station) {
                if (!head_) throw TideAbsentError("station is not recorded");
                if (head_->station == station) {
                    head_ = std::move(head_->higher);
                    --count_;
                    return;
                }
                Node* parent = head_.get();
                while (parent->higher && parent->higher->station != station) parent = parent->higher.get();
                if (!parent->higher) throw TideAbsentError("station is not recorded");
                parent->higher = std::move(parent->higher->higher);
                --count_;
            }
            std::string TideGaugeLedger::channel_path(std::int32_t station) const {
                const Node* current = head_.get();
                std::string path = "root";
                while (current) {
                    if (station == current->station) return path;
                    path += ">R";
                    current = current->higher.get();
                }
                throw TideAbsentError("station is not recorded");
            }
            std::int32_t TideGaugeLedger::channel_depth(std::int32_t station) const {
                const Node* current = head_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (station == current->station) return depth;
                    ++depth;
                    current = current->higher.get();
                }
                throw TideAbsentError("station is not recorded");
            }
            std::int32_t TideGaugeLedger::first_station() const {
                if (!head_) throw TideEmptyError("ledger is empty");
                return head_->station;
            }
            """,
            """
            TideGaugeLedger ledger;
            ledger.record(42);
            ledger.record(17);
            ledger.record(68);
            ledger.record(9);
            ledger.record(25);
            ledger.record(54);
            ledger.record(71);
            if (!ledger.has(25) || !ledger.has(9)) return 1;
            if (ledger.size() != 7U) return 2;
            ledger.retire(17);
            if (ledger.has(17)) return 3;
            if (ledger.size() != 6U) return 4;
            if (!ledger.has(25) || !ledger.has(54) || !ledger.has(71)) return 5;
            return 0;
            """,
            """
            TideGaugeLedger ledger;
            bool threw = false;
            try { ledger.channel_depth(42); } catch (const TideAbsentError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ledger.first_station(); } catch (const TideEmptyError&) { threw = true; }
            if (!threw) return 2;
            ledger.record(42);
            ledger.record(17);
            ledger.record(68);
            ledger.record(9);
            ledger.record(25);
            ledger.record(54);
            ledger.record(71);
            if (ledger.first_station() != 42) return 3;
            threw = false;
            try { ledger.record(25); } catch (const TideDuplicateError&) { threw = true; }
            if (!threw) return 4;
            if (ledger.size() != 7U) return 5;
            if (ledger.channel_path(25) != "root>L>R") return 6;
            if (ledger.channel_path(54) != "root>R>L") return 7;
            if (ledger.channel_path(42) != "root") return 8;
            if (ledger.channel_depth(9) != 2) return 9;
            if (ledger.channel_depth(68) != 1) return 10;
            ledger.retire(17);
            if (ledger.channel_path(9) != "root>L>L") return 11;
            if (ledger.channel_path(25) != "root>L") return 12;
            if (ledger.channel_depth(25) != 1) return 13;
            threw = false;
            try { ledger.retire(17); } catch (const TideAbsentError&) { threw = true; }
            if (!threw) return 14;
            if (ledger.size() != 6U) return 15;
            return 0;
            """,
            "iterative insertion-ordered linked stations whose descent path, depth, and root identity stay observable through exact turn strings",
            "an ordered associative container (std::set, std::map, std::multiset), a sorted std::vector, or a single-sided chain that ignores ordering decisions as the core store",
            "exact root>L>R paths and depths after 42,17,68,9,25,54,71, successor-side removal of 17, duplicate and absent channels, and empty-root behavior",
            "insertion-ordered structural path queries in a two-file API",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-depot-bay-index",
            "Depot bay index",
            "depot_bay",
            """
            class BayDuplicateError : public std::invalid_argument {
            public:
                explicit BayDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BayAbsentError : public std::out_of_range {
            public:
                explicit BayAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class DepotBayIndex {
            public:
                void register_bay(std::int32_t bay);
                void retire_bay(std::int32_t bay);
                bool holds(std::int32_t bay) const;
                std::size_t registered() const;
                std::string route_to(std::int32_t bay) const;
                std::int32_t route_depth(std::int32_t bay) const;
            };
            """,
            """
            class BayDuplicateError : public std::invalid_argument {
            public:
                explicit BayDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BayAbsentError : public std::out_of_range {
            public:
                explicit BayAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class DepotBayIndex {
            public:
                void register_bay(std::int32_t bay);
                void retire_bay(std::int32_t bay);
                bool holds(std::int32_t bay) const;
                std::size_t registered() const;
                std::string route_to(std::int32_t bay) const;
                std::int32_t route_depth(std::int32_t bay) const;
            private:
                struct Node {
                    std::int32_t bay;
                    std::unique_ptr<Node> west;
                    std::unique_ptr<Node> east;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> yard_;
                std::size_t total_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t bay, bool& removed);
            };
            """,
            """
            DepotBayIndex::Node::Node(std::int32_t value) : bay(value) {}
            bool DepotBayIndex::holds(std::int32_t bay) const {
                const Node* current = yard_.get();
                while (current) {
                    if (bay == current->bay) return true;
                    current = bay < current->bay ? current->west.get() : current->east.get();
                }
                return false;
            }
            std::size_t DepotBayIndex::registered() const { return total_; }
            void DepotBayIndex::register_bay(std::int32_t bay) {
                if (!yard_) {
                    yard_ = std::make_unique<Node>(bay);
                    total_ = 1;
                    return;
                }
                Node* current = yard_.get();
                for (;;) {
                    if (bay == current->bay) throw BayDuplicateError("bay already registered");
                    if (bay < current->bay) {
                        if (!current->west) {
                            current->west = std::make_unique<Node>(bay);
                            ++total_;
                            return;
                        }
                        current = current->west.get();
                    } else {
                        if (!current->east) {
                            current->east = std::make_unique<Node>(bay);
                            ++total_;
                            return;
                        }
                        current = current->east.get();
                    }
                }
            }
            std::unique_ptr<DepotBayIndex::Node> DepotBayIndex::detach(std::unique_ptr<Node> node, std::int32_t bay, bool& removed) {
                if (!node) return nullptr;
                if (bay < node->bay) {
                    node->west = detach(std::move(node->west), bay, removed);
                    return node;
                }
                if (node->bay < bay) {
                    node->east = detach(std::move(node->east), bay, removed);
                    return node;
                }
                removed = true;
                if (!node->west) return std::move(node->east);
                if (!node->east) return std::move(node->west);
                Node* successor = node->east.get();
                while (successor->west) successor = successor->west.get();
                node->bay = successor->bay;
                bool ignored = false;
                node->east = detach(std::move(node->east), successor->bay, ignored);
                return node;
            }
            void DepotBayIndex::retire_bay(std::int32_t bay) {
                bool removed = false;
                yard_ = detach(std::move(yard_), bay, removed);
                if (!removed) throw BayAbsentError("bay is not registered");
                --total_;
            }
            std::string DepotBayIndex::route_to(std::int32_t bay) const {
                const Node* current = yard_.get();
                std::string route = "root";
                while (current) {
                    if (bay == current->bay) return route;
                    if (bay < current->bay) {
                        route += ",west";
                        current = current->west.get();
                    } else {
                        route += ",east";
                        current = current->east.get();
                    }
                }
                throw BayAbsentError("bay is not registered");
            }
            std::int32_t DepotBayIndex::route_depth(std::int32_t bay) const {
                const Node* current = yard_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bay == current->bay) return depth;
                    ++depth;
                    current = bay < current->bay ? current->west.get() : current->east.get();
                }
                throw BayAbsentError("bay is not registered");
            }
            """,
            """
            DepotBayIndex::Node::Node(std::int32_t value) : bay(value) {}
            bool DepotBayIndex::holds(std::int32_t bay) const {
                const Node* current = yard_.get();
                while (current) {
                    if (bay == current->bay) return true;
                    current = current->west.get();
                }
                return false;
            }
            std::size_t DepotBayIndex::registered() const { return total_; }
            void DepotBayIndex::register_bay(std::int32_t bay) {
                if (holds(bay)) throw BayDuplicateError("bay already registered");
                if (!yard_) {
                    yard_ = std::make_unique<Node>(bay);
                    total_ = 1;
                    return;
                }
                Node* current = yard_.get();
                while (current->west) current = current->west.get();
                current->west = std::make_unique<Node>(bay);
                ++total_;
            }
            void DepotBayIndex::retire_bay(std::int32_t bay) {
                if (!yard_) throw BayAbsentError("bay is not registered");
                if (yard_->bay == bay) {
                    yard_ = std::move(yard_->west);
                    --total_;
                    return;
                }
                Node* parent = yard_.get();
                while (parent->west && parent->west->bay != bay) parent = parent->west.get();
                if (!parent->west) throw BayAbsentError("bay is not registered");
                parent->west = std::move(parent->west->west);
                --total_;
            }
            std::string DepotBayIndex::route_to(std::int32_t bay) const {
                const Node* current = yard_.get();
                std::string route = "root";
                while (current) {
                    if (bay == current->bay) return route;
                    route += ",west";
                    current = current->west.get();
                }
                throw BayAbsentError("bay is not registered");
            }
            std::int32_t DepotBayIndex::route_depth(std::int32_t bay) const {
                const Node* current = yard_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bay == current->bay) return depth;
                    ++depth;
                    current = current->west.get();
                }
                throw BayAbsentError("bay is not registered");
            }
            """,
            """
            DepotBayIndex index;
            index.register_bay(500);
            index.register_bay(300);
            index.register_bay(700);
            index.register_bay(200);
            index.register_bay(400);
            index.register_bay(600);
            index.register_bay(800);
            index.register_bay(350);
            if (!index.holds(350) || !index.holds(200)) return 1;
            if (index.registered() != 8U) return 2;
            index.retire_bay(300);
            if (index.holds(300)) return 3;
            if (index.registered() != 7U) return 4;
            if (!index.holds(400) || !index.holds(350)) return 5;
            return 0;
            """,
            """
            DepotBayIndex index;
            bool threw = false;
            try { index.route_depth(500); } catch (const BayAbsentError&) { threw = true; }
            if (!threw) return 1;
            index.register_bay(500);
            index.register_bay(300);
            index.register_bay(700);
            index.register_bay(200);
            index.register_bay(400);
            index.register_bay(600);
            index.register_bay(800);
            index.register_bay(350);
            threw = false;
            try { index.register_bay(400); } catch (const BayDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (index.registered() != 8U) return 3;
            if (index.route_to(350) != "root,west,east,west") return 4;
            if (index.route_to(600) != "root,east,west") return 5;
            if (index.route_to(500) != "root") return 6;
            if (index.route_depth(350) != 3) return 7;
            if (index.route_depth(700) != 1) return 8;
            index.retire_bay(300);
            if (index.route_to(400) != "root,west,east") return 9;
            if (index.route_to(350) != "root,west") return 10;
            if (index.route_depth(350) != 1) return 11;
            threw = false;
            try { index.retire_bay(300); } catch (const BayAbsentError&) { threw = true; }
            if (!threw) return 12;
            if (index.registered() != 7U) return 13;
            return 0;
            """,
            "iterative insertion-ordered linked bays with word-form west/east descent routes",
            "an ordered container, a sorted std::vector, or a single-sided west chain that ignores ordering decisions as the core store",
            "exact root,west,east routes and depths after 500,300,700,200,400,600,800,350, successor-side removal of 300, and duplicate/absent channels",
            "word-form structural routes with distinct typed errors",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-observatory-star-chart",
            "Observatory star chart",
            "star_chart",
            """
            class ChartDuplicateError : public std::logic_error {
            public:
                explicit ChartDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class ChartAbsentError : public std::runtime_error {
            public:
                explicit ChartAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class StarChart {
            public:
                void catalog(const std::string& designation);
                void drop(const std::string& designation);
                bool charted(const std::string& designation) const;
                std::size_t entries() const;
                std::string descent_to(const std::string& designation) const;
                std::int32_t depth_of(const std::string& designation) const;
            };
            """,
            """
            class ChartDuplicateError : public std::logic_error {
            public:
                explicit ChartDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class ChartAbsentError : public std::runtime_error {
            public:
                explicit ChartAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class StarChart {
            public:
                void catalog(const std::string& designation);
                void drop(const std::string& designation);
                bool charted(const std::string& designation) const;
                std::size_t entries() const;
                std::string descent_to(const std::string& designation) const;
                std::int32_t depth_of(const std::string& designation) const;
            private:
                struct Node {
                    std::string designation;
                    std::unique_ptr<Node> faint;
                    std::unique_ptr<Node> bright;
                    explicit Node(std::string value);
                };
                std::unique_ptr<Node> vault_;
                std::size_t size_ = 0;
                static std::unique_ptr<Node> erase(std::unique_ptr<Node> node, const std::string& designation, bool& removed);
            };
            """,
            """
            StarChart::Node::Node(std::string value) : designation(std::move(value)) {}
            bool StarChart::charted(const std::string& designation) const {
                const Node* current = vault_.get();
                while (current) {
                    if (designation == current->designation) return true;
                    current = designation < current->designation ? current->faint.get() : current->bright.get();
                }
                return false;
            }
            std::size_t StarChart::entries() const { return size_; }
            void StarChart::catalog(const std::string& designation) {
                if (!vault_) {
                    vault_ = std::make_unique<Node>(designation);
                    size_ = 1;
                    return;
                }
                Node* current = vault_.get();
                for (;;) {
                    if (designation == current->designation) throw ChartDuplicateError("designation already cataloged");
                    if (designation < current->designation) {
                        if (!current->faint) {
                            current->faint = std::make_unique<Node>(designation);
                            ++size_;
                            return;
                        }
                        current = current->faint.get();
                    } else {
                        if (!current->bright) {
                            current->bright = std::make_unique<Node>(designation);
                            ++size_;
                            return;
                        }
                        current = current->bright.get();
                    }
                }
            }
            std::unique_ptr<StarChart::Node> StarChart::erase(std::unique_ptr<Node> node, const std::string& designation, bool& removed) {
                if (!node) return nullptr;
                if (designation < node->designation) {
                    node->faint = erase(std::move(node->faint), designation, removed);
                    return node;
                }
                if (node->designation < designation) {
                    node->bright = erase(std::move(node->bright), designation, removed);
                    return node;
                }
                removed = true;
                if (!node->faint) return std::move(node->bright);
                if (!node->bright) return std::move(node->faint);
                Node* successor = node->bright.get();
                while (successor->faint) successor = successor->faint.get();
                node->designation = successor->designation;
                bool ignored = false;
                node->bright = erase(std::move(node->bright), successor->designation, ignored);
                return node;
            }
            void StarChart::drop(const std::string& designation) {
                bool removed = false;
                vault_ = erase(std::move(vault_), designation, removed);
                if (!removed) throw ChartAbsentError("designation is not charted");
                --size_;
            }
            std::string StarChart::descent_to(const std::string& designation) const {
                const Node* current = vault_.get();
                std::string descent = "root";
                while (current) {
                    if (designation == current->designation) return descent;
                    if (designation < current->designation) {
                        descent += ".l";
                        current = current->faint.get();
                    } else {
                        descent += ".r";
                        current = current->bright.get();
                    }
                }
                throw ChartAbsentError("designation is not charted");
            }
            std::int32_t StarChart::depth_of(const std::string& designation) const {
                const Node* current = vault_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (designation == current->designation) return depth;
                    ++depth;
                    current = designation < current->designation ? current->faint.get() : current->bright.get();
                }
                throw ChartAbsentError("designation is not charted");
            }
            """,
            """
            StarChart::Node::Node(std::string value) : designation(std::move(value)) {}
            bool StarChart::charted(const std::string& designation) const {
                const Node* current = vault_.get();
                while (current) {
                    if (designation == current->designation) return true;
                    current = current->bright.get();
                }
                return false;
            }
            std::size_t StarChart::entries() const { return size_; }
            void StarChart::catalog(const std::string& designation) {
                if (charted(designation)) throw ChartDuplicateError("designation already cataloged");
                if (!vault_) {
                    vault_ = std::make_unique<Node>(designation);
                    size_ = 1;
                    return;
                }
                Node* current = vault_.get();
                while (current->bright) current = current->bright.get();
                current->bright = std::make_unique<Node>(designation);
                ++size_;
            }
            void StarChart::drop(const std::string& designation) {
                if (!vault_) throw ChartAbsentError("designation is not charted");
                if (vault_->designation == designation) {
                    vault_ = std::move(vault_->bright);
                    --size_;
                    return;
                }
                Node* parent = vault_.get();
                while (parent->bright && parent->bright->designation != designation) parent = parent->bright.get();
                if (!parent->bright) throw ChartAbsentError("designation is not charted");
                parent->bright = std::move(parent->bright->bright);
                --size_;
            }
            std::string StarChart::descent_to(const std::string& designation) const {
                const Node* current = vault_.get();
                std::string descent = "root";
                while (current) {
                    if (designation == current->designation) return descent;
                    descent += ".r";
                    current = current->bright.get();
                }
                throw ChartAbsentError("designation is not charted");
            }
            std::int32_t StarChart::depth_of(const std::string& designation) const {
                const Node* current = vault_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (designation == current->designation) return depth;
                    ++depth;
                    current = current->bright.get();
                }
                throw ChartAbsentError("designation is not charted");
            }
            """,
            """
            StarChart chart;
            chart.catalog("HD-50");
            chart.catalog("HD-20");
            chart.catalog("HD-80");
            chart.catalog("HD-10");
            chart.catalog("HD-30");
            chart.catalog("HD-70");
            chart.catalog("HD-90");
            chart.catalog("HD-65");
            if (!chart.charted("HD-65") || !chart.charted("HD-10")) return 1;
            if (chart.entries() != 8U) return 2;
            chart.drop("HD-20");
            if (chart.charted("HD-20")) return 3;
            if (chart.entries() != 7U) return 4;
            if (!chart.charted("HD-30") || !chart.charted("HD-65")) return 5;
            return 0;
            """,
            """
            StarChart chart;
            bool threw = false;
            try { chart.depth_of("HD-50"); } catch (const ChartAbsentError&) { threw = true; }
            if (!threw) return 1;
            chart.catalog("HD-50");
            chart.catalog("HD-20");
            chart.catalog("HD-80");
            chart.catalog("HD-10");
            chart.catalog("HD-30");
            chart.catalog("HD-70");
            chart.catalog("HD-90");
            chart.catalog("HD-65");
            threw = false;
            try { chart.catalog("HD-70"); } catch (const ChartDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (chart.entries() != 8U) return 3;
            if (chart.descent_to("HD-65") != "root.r.l.l") return 4;
            if (chart.descent_to("HD-30") != "root.l.r") return 5;
            if (chart.descent_to("HD-50") != "root") return 6;
            if (chart.depth_of("HD-65") != 3) return 7;
            if (chart.depth_of("HD-80") != 1) return 8;
            chart.drop("HD-20");
            if (chart.descent_to("HD-10") != "root.l.l") return 9;
            if (chart.descent_to("HD-30") != "root.l") return 10;
            if (chart.depth_of("HD-30") != 1) return 11;
            threw = false;
            try { chart.drop("HD-20"); } catch (const ChartAbsentError&) { threw = true; }
            if (!threw) return 12;
            if (chart.entries() != 7U) return 13;
            return 0;
            """,
            "lexicographically ordered linked designations with dotted root.l.r descent rendering",
            "an ordered container, a sorted std::vector, or a single-sided bright chain that ignores ordering decisions as the core store",
            "exact root.l.r descents after HD-50,HD-20,HD-80,HD-10,HD-30,HD-70,HD-90,HD-65, successor-side drop of HD-20, and duplicate/absent channels",
            "lexicographic string keys with exact structural output",
            "exception-throwing ordered tree with structural path/depth queries",
            project_support=True,
        ),
        c(
            "f26bst-rail-siding-order",
            "Rail siding order",
            "rail_siding",
            """
            class SidingDuplicateError : public std::runtime_error {
            public:
                explicit SidingDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class SidingAbsentError : public std::logic_error {
            public:
                explicit SidingAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class RailSidingOrder {
            public:
                void couple(std::int32_t siding);
                void uncouple(std::int32_t siding);
                bool present(std::int32_t siding) const;
                std::size_t count() const;
                std::vector<std::string> switches_to(std::int32_t siding) const;
                std::int32_t switch_depth(std::int32_t siding) const;
            };
            """,
            """
            class SidingDuplicateError : public std::runtime_error {
            public:
                explicit SidingDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class SidingAbsentError : public std::logic_error {
            public:
                explicit SidingAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class RailSidingOrder {
            public:
                void couple(std::int32_t siding);
                void uncouple(std::int32_t siding);
                bool present(std::int32_t siding) const;
                std::size_t count() const;
                std::vector<std::string> switches_to(std::int32_t siding) const;
                std::int32_t switch_depth(std::int32_t siding) const;
            private:
                struct Node {
                    std::int32_t siding;
                    std::unique_ptr<Node> near_track;
                    std::unique_ptr<Node> far_track;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> lead_;
                std::size_t total_ = 0;
                static std::unique_ptr<Node> link(std::unique_ptr<Node> node, std::int32_t siding, bool& linked);
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t siding, bool& removed);
            };
            """,
            """
            RailSidingOrder::Node::Node(std::int32_t value) : siding(value) {}
            bool RailSidingOrder::present(std::int32_t siding) const {
                const Node* current = lead_.get();
                while (current) {
                    if (siding == current->siding) return true;
                    current = siding < current->siding ? current->near_track.get() : current->far_track.get();
                }
                return false;
            }
            std::size_t RailSidingOrder::count() const { return total_; }
            std::unique_ptr<RailSidingOrder::Node> RailSidingOrder::link(std::unique_ptr<Node> node, std::int32_t siding, bool& linked) {
                if (!node) {
                    linked = true;
                    return std::make_unique<Node>(siding);
                }
                if (siding == node->siding) return node;
                if (siding < node->siding) {
                    node->near_track = link(std::move(node->near_track), siding, linked);
                } else {
                    node->far_track = link(std::move(node->far_track), siding, linked);
                }
                return node;
            }
            void RailSidingOrder::couple(std::int32_t siding) {
                bool linked = false;
                lead_ = link(std::move(lead_), siding, linked);
                if (!linked) throw SidingDuplicateError("siding already coupled");
                ++total_;
            }
            std::unique_ptr<RailSidingOrder::Node> RailSidingOrder::unlink(std::unique_ptr<Node> node, std::int32_t siding, bool& removed) {
                if (!node) return nullptr;
                if (siding < node->siding) {
                    node->near_track = unlink(std::move(node->near_track), siding, removed);
                    return node;
                }
                if (node->siding < siding) {
                    node->far_track = unlink(std::move(node->far_track), siding, removed);
                    return node;
                }
                removed = true;
                if (!node->near_track) return std::move(node->far_track);
                if (!node->far_track) return std::move(node->near_track);
                Node* successor = node->far_track.get();
                while (successor->near_track) successor = successor->near_track.get();
                node->siding = successor->siding;
                bool ignored = false;
                node->far_track = unlink(std::move(node->far_track), successor->siding, ignored);
                return node;
            }
            void RailSidingOrder::uncouple(std::int32_t siding) {
                bool removed = false;
                lead_ = unlink(std::move(lead_), siding, removed);
                if (!removed) throw SidingAbsentError("siding is not coupled");
                --total_;
            }
            std::vector<std::string> RailSidingOrder::switches_to(std::int32_t siding) const {
                const Node* current = lead_.get();
                std::vector<std::string> turns;
                while (current) {
                    if (siding == current->siding) return turns;
                    if (siding < current->siding) {
                        turns.push_back("left");
                        current = current->near_track.get();
                    } else {
                        turns.push_back("right");
                        current = current->far_track.get();
                    }
                }
                throw SidingAbsentError("siding is not coupled");
            }
            std::int32_t RailSidingOrder::switch_depth(std::int32_t siding) const {
                const Node* current = lead_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (siding == current->siding) return depth;
                    ++depth;
                    current = siding < current->siding ? current->near_track.get() : current->far_track.get();
                }
                throw SidingAbsentError("siding is not coupled");
            }
            """,
            """
            RailSidingOrder::Node::Node(std::int32_t value) : siding(value) {}
            bool RailSidingOrder::present(std::int32_t siding) const {
                const Node* current = lead_.get();
                while (current) {
                    if (siding == current->siding) return true;
                    current = current->near_track.get();
                }
                return false;
            }
            std::size_t RailSidingOrder::count() const { return total_; }
            void RailSidingOrder::couple(std::int32_t siding) {
                if (present(siding)) throw SidingDuplicateError("siding already coupled");
                if (!lead_) {
                    lead_ = std::make_unique<Node>(siding);
                    total_ = 1;
                    return;
                }
                Node* current = lead_.get();
                while (current->near_track) current = current->near_track.get();
                current->near_track = std::make_unique<Node>(siding);
                ++total_;
            }
            void RailSidingOrder::uncouple(std::int32_t siding) {
                if (!lead_) throw SidingAbsentError("siding is not coupled");
                if (lead_->siding == siding) {
                    lead_ = std::move(lead_->near_track);
                    --total_;
                    return;
                }
                Node* parent = lead_.get();
                while (parent->near_track && parent->near_track->siding != siding) parent = parent->near_track.get();
                if (!parent->near_track) throw SidingAbsentError("siding is not coupled");
                parent->near_track = std::move(parent->near_track->near_track);
                --total_;
            }
            std::vector<std::string> RailSidingOrder::switches_to(std::int32_t siding) const {
                const Node* current = lead_.get();
                std::vector<std::string> turns;
                while (current) {
                    if (siding == current->siding) return turns;
                    turns.push_back("left");
                    current = current->near_track.get();
                }
                throw SidingAbsentError("siding is not coupled");
            }
            std::int32_t RailSidingOrder::switch_depth(std::int32_t siding) const {
                const Node* current = lead_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (siding == current->siding) return depth;
                    ++depth;
                    current = current->near_track.get();
                }
                throw SidingAbsentError("siding is not coupled");
            }
            """,
            """
            RailSidingOrder order;
            order.couple(260);
            order.couple(130);
            order.couple(390);
            order.couple(65);
            order.couple(195);
            order.couple(325);
            order.couple(455);
            order.couple(160);
            if (!order.present(160) || !order.present(65)) return 1;
            if (order.count() != 8U) return 2;
            order.uncouple(130);
            if (order.present(130)) return 3;
            if (order.count() != 7U) return 4;
            if (!order.present(160) || !order.present(195)) return 5;
            return 0;
            """,
            """
            RailSidingOrder order;
            bool threw = false;
            try { order.switch_depth(260); } catch (const SidingAbsentError&) { threw = true; }
            if (!threw) return 1;
            order.couple(260);
            order.couple(130);
            order.couple(390);
            order.couple(65);
            order.couple(195);
            order.couple(325);
            order.couple(455);
            order.couple(160);
            threw = false;
            try { order.couple(195); } catch (const SidingDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (order.count() != 8U) return 3;
            std::vector<std::string> expected_160 = {"left", "right", "left"};
            if (order.switches_to(160) != expected_160) return 4;
            std::vector<std::string> expected_325 = {"right", "left"};
            if (order.switches_to(325) != expected_325) return 5;
            if (!order.switches_to(260).empty()) return 6;
            if (order.switch_depth(160) != 3) return 7;
            if (order.switch_depth(390) != 1) return 8;
            order.uncouple(130);
            std::vector<std::string> expected_after_160 = {"left"};
            if (order.switches_to(160) != expected_after_160) return 9;
            std::vector<std::string> expected_after_195 = {"left", "right"};
            if (order.switches_to(195) != expected_after_195) return 10;
            if (order.switch_depth(160) != 1) return 11;
            threw = false;
            try { order.uncouple(130); } catch (const SidingAbsentError&) { threw = true; }
            if (!threw) return 12;
            if (order.count() != 7U) return 13;
            return 0;
            """,
            "recursively linked sidings with left/right turn vectors and successor-side removal",
            "an ordered container, a sorted std::vector, or a single-sided near-track chain that ignores ordering decisions as the core store",
            "exact left/right turn vectors after 260,130,390,65,195,325,455,160, recursive successor-side removal of 130, and duplicate/absent channels",
            "recursive descent contrasted with iterative roots",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-mooring-field-chart",
            "Mooring field chart",
            "mooring_field",
            """
            class MooringDuplicateError : public std::domain_error {
            public:
                explicit MooringDuplicateError(const std::string& message) : std::domain_error(message) {}
            };
            class MooringAbsentError : public std::out_of_range {
            public:
                explicit MooringAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class MooringFieldChart {
            public:
                void assign(std::int32_t mooring);
                void release(std::int32_t mooring);
                bool assigned(std::int32_t mooring) const;
                std::size_t taken() const;
                std::string bearing_path(std::int32_t mooring) const;
                std::optional<std::int32_t> parent_of(std::int32_t mooring) const;
            };
            """,
            """
            class MooringDuplicateError : public std::domain_error {
            public:
                explicit MooringDuplicateError(const std::string& message) : std::domain_error(message) {}
            };
            class MooringAbsentError : public std::out_of_range {
            public:
                explicit MooringAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class MooringFieldChart {
            public:
                void assign(std::int32_t mooring);
                void release(std::int32_t mooring);
                bool assigned(std::int32_t mooring) const;
                std::size_t taken() const;
                std::string bearing_path(std::int32_t mooring) const;
                std::optional<std::int32_t> parent_of(std::int32_t mooring) const;
            private:
                struct Node {
                    std::int32_t mooring;
                    std::unique_ptr<Node> port;
                    std::unique_ptr<Node> starboard;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> anchorage_;
                std::size_t count_ = 0;
                static std::unique_ptr<Node> lift(std::unique_ptr<Node> node, std::int32_t mooring, bool& removed);
            };
            """,
            """
            MooringFieldChart::Node::Node(std::int32_t value) : mooring(value) {}
            bool MooringFieldChart::assigned(std::int32_t mooring) const {
                const Node* current = anchorage_.get();
                while (current) {
                    if (mooring == current->mooring) return true;
                    current = mooring < current->mooring ? current->port.get() : current->starboard.get();
                }
                return false;
            }
            std::size_t MooringFieldChart::taken() const { return count_; }
            void MooringFieldChart::assign(std::int32_t mooring) {
                if (!anchorage_) {
                    anchorage_ = std::make_unique<Node>(mooring);
                    count_ = 1;
                    return;
                }
                Node* current = anchorage_.get();
                for (;;) {
                    if (mooring == current->mooring) throw MooringDuplicateError("mooring already assigned");
                    if (mooring < current->mooring) {
                        if (!current->port) {
                            current->port = std::make_unique<Node>(mooring);
                            ++count_;
                            return;
                        }
                        current = current->port.get();
                    } else {
                        if (!current->starboard) {
                            current->starboard = std::make_unique<Node>(mooring);
                            ++count_;
                            return;
                        }
                        current = current->starboard.get();
                    }
                }
            }
            std::unique_ptr<MooringFieldChart::Node> MooringFieldChart::lift(std::unique_ptr<Node> node, std::int32_t mooring, bool& removed) {
                if (!node) return nullptr;
                if (mooring < node->mooring) {
                    node->port = lift(std::move(node->port), mooring, removed);
                    return node;
                }
                if (node->mooring < mooring) {
                    node->starboard = lift(std::move(node->starboard), mooring, removed);
                    return node;
                }
                removed = true;
                if (!node->port) return std::move(node->starboard);
                if (!node->starboard) return std::move(node->port);
                Node* successor = node->starboard.get();
                while (successor->port) successor = successor->port.get();
                node->mooring = successor->mooring;
                bool ignored = false;
                node->starboard = lift(std::move(node->starboard), successor->mooring, ignored);
                return node;
            }
            void MooringFieldChart::release(std::int32_t mooring) {
                bool removed = false;
                anchorage_ = lift(std::move(anchorage_), mooring, removed);
                if (!removed) throw MooringAbsentError("mooring is not assigned");
                --count_;
            }
            std::string MooringFieldChart::bearing_path(std::int32_t mooring) const {
                const Node* current = anchorage_.get();
                std::string path = "root";
                while (current) {
                    if (mooring == current->mooring) return path;
                    if (mooring < current->mooring) {
                        path += "-port";
                        current = current->port.get();
                    } else {
                        path += "-starboard";
                        current = current->starboard.get();
                    }
                }
                throw MooringAbsentError("mooring is not assigned");
            }
            std::optional<std::int32_t> MooringFieldChart::parent_of(std::int32_t mooring) const {
                const Node* current = anchorage_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (mooring == current->mooring) {
                        if (!parent) return std::nullopt;
                        return parent->mooring;
                    }
                    parent = current;
                    current = mooring < current->mooring ? current->port.get() : current->starboard.get();
                }
                return std::nullopt;
            }
            """,
            """
            MooringFieldChart::Node::Node(std::int32_t value) : mooring(value) {}
            bool MooringFieldChart::assigned(std::int32_t mooring) const {
                const Node* current = anchorage_.get();
                while (current) {
                    if (mooring == current->mooring) return true;
                    current = current->starboard.get();
                }
                return false;
            }
            std::size_t MooringFieldChart::taken() const { return count_; }
            void MooringFieldChart::assign(std::int32_t mooring) {
                if (assigned(mooring)) throw MooringDuplicateError("mooring already assigned");
                if (!anchorage_) {
                    anchorage_ = std::make_unique<Node>(mooring);
                    count_ = 1;
                    return;
                }
                Node* current = anchorage_.get();
                while (current->starboard) current = current->starboard.get();
                current->starboard = std::make_unique<Node>(mooring);
                ++count_;
            }
            void MooringFieldChart::release(std::int32_t mooring) {
                if (!anchorage_) throw MooringAbsentError("mooring is not assigned");
                if (anchorage_->mooring == mooring) {
                    anchorage_ = std::move(anchorage_->starboard);
                    --count_;
                    return;
                }
                Node* parent = anchorage_.get();
                while (parent->starboard && parent->starboard->mooring != mooring) parent = parent->starboard.get();
                if (!parent->starboard) throw MooringAbsentError("mooring is not assigned");
                parent->starboard = std::move(parent->starboard->starboard);
                --count_;
            }
            std::string MooringFieldChart::bearing_path(std::int32_t mooring) const {
                const Node* current = anchorage_.get();
                std::string path = "root";
                while (current) {
                    if (mooring == current->mooring) return path;
                    path += "-starboard";
                    current = current->starboard.get();
                }
                throw MooringAbsentError("mooring is not assigned");
            }
            std::optional<std::int32_t> MooringFieldChart::parent_of(std::int32_t mooring) const {
                const Node* current = anchorage_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (mooring == current->mooring) {
                        if (!parent) return std::nullopt;
                        return parent->mooring;
                    }
                    parent = current;
                    current = current->starboard.get();
                }
                return std::nullopt;
            }
            """,
            """
            MooringFieldChart chart;
            chart.assign(88);
            chart.assign(44);
            chart.assign(132);
            chart.assign(22);
            chart.assign(66);
            chart.assign(110);
            chart.assign(154);
            chart.assign(55);
            if (!chart.assigned(55) || !chart.assigned(22)) return 1;
            if (chart.taken() != 8U) return 2;
            chart.release(44);
            if (chart.assigned(44)) return 3;
            if (chart.taken() != 7U) return 4;
            if (!chart.assigned(55) || !chart.assigned(66)) return 5;
            return 0;
            """,
            """
            MooringFieldChart chart;
            bool threw = false;
            try { chart.bearing_path(88); } catch (const MooringAbsentError&) { threw = true; }
            if (!threw) return 1;
            chart.assign(88);
            chart.assign(44);
            chart.assign(132);
            chart.assign(22);
            chart.assign(66);
            chart.assign(110);
            chart.assign(154);
            chart.assign(55);
            threw = false;
            try { chart.assign(66); } catch (const MooringDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (chart.taken() != 8U) return 3;
            if (chart.bearing_path(55) != "root-port-starboard-port") return 4;
            if (chart.bearing_path(110) != "root-starboard-port") return 5;
            if (chart.bearing_path(88) != "root") return 6;
            if (chart.parent_of(55) != 66) return 7;
            if (chart.parent_of(88).has_value()) return 8;
            if (chart.parent_of(999).has_value()) return 9;
            chart.release(44);
            if (chart.bearing_path(55) != "root-port") return 10;
            if (chart.parent_of(55) != 88) return 11;
            if (chart.bearing_path(66) != "root-port-starboard") return 12;
            threw = false;
            try { chart.release(44); } catch (const MooringAbsentError&) { threw = true; }
            if (!threw) return 13;
            if (chart.taken() != 7U) return 14;
            return 0;
            """,
            "insertion-ordered linked moorings with parent navigation and port/starboard turn words",
            "an ordered container, a sorted std::vector, or a single-sided starboard chain that ignores ordering decisions as the core store",
            "exact port-starboard paths and parents after 88,44,132,22,66,110,154,55, successor-side release of 44, and duplicate/absent channels",
            "parent navigation as a structure-dependent observable",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-archive-box-ranges",
            "Archive box ranges",
            "archive_box",
            """
            class BoxDuplicateError : public std::invalid_argument {
            public:
                explicit BoxDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BoxAbsentError : public std::runtime_error {
            public:
                explicit BoxAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class BoxEmptyError : public std::logic_error {
            public:
                explicit BoxEmptyError(const std::string& message) : std::logic_error(message) {}
            };
            class ArchiveBoxRanges {
            public:
                void shelve(std::int64_t box);
                void pull(std::int64_t box);
                bool shelved(std::int64_t box) const;
                std::size_t held() const;
                std::string aisle_path(std::int64_t box) const;
                std::int64_t top_box() const;
                std::int32_t aisle_depth(std::int64_t box) const;
            };
            """,
            """
            class BoxDuplicateError : public std::invalid_argument {
            public:
                explicit BoxDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BoxAbsentError : public std::runtime_error {
            public:
                explicit BoxAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class BoxEmptyError : public std::logic_error {
            public:
                explicit BoxEmptyError(const std::string& message) : std::logic_error(message) {}
            };
            class ArchiveBoxRanges {
            public:
                void shelve(std::int64_t box);
                void pull(std::int64_t box);
                bool shelved(std::int64_t box) const;
                std::size_t held() const;
                std::string aisle_path(std::int64_t box) const;
                std::int64_t top_box() const;
                std::int32_t aisle_depth(std::int64_t box) const;
            private:
                struct Node {
                    std::int64_t box;
                    std::unique_ptr<Node> low;
                    std::unique_ptr<Node> high;
                    explicit Node(std::int64_t value);
                };
                std::unique_ptr<Node> stack_;
                std::size_t kept_ = 0;
                static std::unique_ptr<Node> withdraw(std::unique_ptr<Node> node, std::int64_t box, bool& removed);
            };
            """,
            """
            ArchiveBoxRanges::Node::Node(std::int64_t value) : box(value) {}
            bool ArchiveBoxRanges::shelved(std::int64_t box) const {
                const Node* current = stack_.get();
                while (current) {
                    if (box == current->box) return true;
                    current = box < current->box ? current->low.get() : current->high.get();
                }
                return false;
            }
            std::size_t ArchiveBoxRanges::held() const { return kept_; }
            void ArchiveBoxRanges::shelve(std::int64_t box) {
                if (!stack_) {
                    stack_ = std::make_unique<Node>(box);
                    kept_ = 1;
                    return;
                }
                Node* current = stack_.get();
                for (;;) {
                    if (box == current->box) throw BoxDuplicateError("box already shelved");
                    if (box < current->box) {
                        if (!current->low) {
                            current->low = std::make_unique<Node>(box);
                            ++kept_;
                            return;
                        }
                        current = current->low.get();
                    } else {
                        if (!current->high) {
                            current->high = std::make_unique<Node>(box);
                            ++kept_;
                            return;
                        }
                        current = current->high.get();
                    }
                }
            }
            std::unique_ptr<ArchiveBoxRanges::Node> ArchiveBoxRanges::withdraw(std::unique_ptr<Node> node, std::int64_t box, bool& removed) {
                if (!node) return nullptr;
                if (box < node->box) {
                    node->low = withdraw(std::move(node->low), box, removed);
                    return node;
                }
                if (node->box < box) {
                    node->high = withdraw(std::move(node->high), box, removed);
                    return node;
                }
                removed = true;
                if (!node->low) return std::move(node->high);
                if (!node->high) return std::move(node->low);
                Node* successor = node->high.get();
                while (successor->low) successor = successor->low.get();
                node->box = successor->box;
                bool ignored = false;
                node->high = withdraw(std::move(node->high), successor->box, ignored);
                return node;
            }
            void ArchiveBoxRanges::pull(std::int64_t box) {
                bool removed = false;
                stack_ = withdraw(std::move(stack_), box, removed);
                if (!removed) throw BoxAbsentError("box is not shelved");
                --kept_;
            }
            std::string ArchiveBoxRanges::aisle_path(std::int64_t box) const {
                const Node* current = stack_.get();
                std::string path = "top";
                while (current) {
                    if (box == current->box) return path;
                    if (box < current->box) {
                        path += "|low";
                        current = current->low.get();
                    } else {
                        path += "|high";
                        current = current->high.get();
                    }
                }
                throw BoxAbsentError("box is not shelved");
            }
            std::int64_t ArchiveBoxRanges::top_box() const {
                if (!stack_) throw BoxEmptyError("range is empty");
                return stack_->box;
            }
            std::int32_t ArchiveBoxRanges::aisle_depth(std::int64_t box) const {
                const Node* current = stack_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (box == current->box) return depth;
                    ++depth;
                    current = box < current->box ? current->low.get() : current->high.get();
                }
                throw BoxAbsentError("box is not shelved");
            }
            """,
            """
            ArchiveBoxRanges::Node::Node(std::int64_t value) : box(value) {}
            bool ArchiveBoxRanges::shelved(std::int64_t box) const {
                const Node* current = stack_.get();
                while (current) {
                    if (box == current->box) return true;
                    current = current->low.get();
                }
                return false;
            }
            std::size_t ArchiveBoxRanges::held() const { return kept_; }
            void ArchiveBoxRanges::shelve(std::int64_t box) {
                if (shelved(box)) throw BoxDuplicateError("box already shelved");
                if (!stack_) {
                    stack_ = std::make_unique<Node>(box);
                    kept_ = 1;
                    return;
                }
                Node* current = stack_.get();
                while (current->low) current = current->low.get();
                current->low = std::make_unique<Node>(box);
                ++kept_;
            }
            void ArchiveBoxRanges::pull(std::int64_t box) {
                if (!stack_) throw BoxAbsentError("box is not shelved");
                if (stack_->box == box) {
                    stack_ = std::move(stack_->low);
                    --kept_;
                    return;
                }
                Node* parent = stack_.get();
                while (parent->low && parent->low->box != box) parent = parent->low.get();
                if (!parent->low) throw BoxAbsentError("box is not shelved");
                parent->low = std::move(parent->low->low);
                --kept_;
            }
            std::string ArchiveBoxRanges::aisle_path(std::int64_t box) const {
                const Node* current = stack_.get();
                std::string path = "top";
                while (current) {
                    if (box == current->box) return path;
                    path += "|low";
                    current = current->low.get();
                }
                throw BoxAbsentError("box is not shelved");
            }
            std::int64_t ArchiveBoxRanges::top_box() const {
                if (!stack_) throw BoxEmptyError("range is empty");
                return stack_->box;
            }
            std::int32_t ArchiveBoxRanges::aisle_depth(std::int64_t box) const {
                const Node* current = stack_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (box == current->box) return depth;
                    ++depth;
                    current = current->low.get();
                }
                throw BoxAbsentError("box is not shelved");
            }
            """,
            """
            ArchiveBoxRanges ranges;
            ranges.shelve(9000);
            ranges.shelve(4000);
            ranges.shelve(14000);
            ranges.shelve(2000);
            ranges.shelve(6000);
            ranges.shelve(12000);
            ranges.shelve(16000);
            ranges.shelve(5000);
            if (!ranges.shelved(5000) || !ranges.shelved(2000)) return 1;
            if (ranges.held() != 8U) return 2;
            ranges.pull(4000);
            if (ranges.shelved(4000)) return 3;
            if (ranges.held() != 7U) return 4;
            if (!ranges.shelved(5000) || !ranges.shelved(6000)) return 5;
            return 0;
            """,
            """
            ArchiveBoxRanges ranges;
            bool threw = false;
            try { ranges.aisle_depth(9000); } catch (const BoxAbsentError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ranges.top_box(); } catch (const BoxEmptyError&) { threw = true; }
            if (!threw) return 2;
            ranges.shelve(9000);
            ranges.shelve(4000);
            ranges.shelve(14000);
            ranges.shelve(2000);
            ranges.shelve(6000);
            ranges.shelve(12000);
            ranges.shelve(16000);
            ranges.shelve(5000);
            if (ranges.top_box() != 9000) return 3;
            threw = false;
            try { ranges.shelve(6000); } catch (const BoxDuplicateError&) { threw = true; }
            if (!threw) return 4;
            if (ranges.held() != 8U) return 5;
            if (ranges.aisle_path(5000) != "top|low|high|low") return 6;
            if (ranges.aisle_path(12000) != "top|high|low") return 7;
            if (ranges.aisle_path(9000) != "top") return 8;
            if (ranges.aisle_depth(5000) != 3) return 9;
            if (ranges.aisle_depth(14000) != 1) return 10;
            ranges.pull(4000);
            if (ranges.aisle_path(5000) != "top|low") return 11;
            if (ranges.aisle_path(6000) != "top|low|high") return 12;
            if (ranges.aisle_depth(5000) != 1) return 13;
            threw = false;
            try { ranges.pull(4000); } catch (const BoxAbsentError&) { threw = true; }
            if (!threw) return 14;
            if (ranges.held() != 7U) return 15;
            return 0;
            """,
            "wide-key linked archive with low/high turn vocabulary and successor-side pulls",
            "an ordered container, a sorted std::vector, or a single-sided low chain that ignores ordering decisions as the core store",
            "exact top|low|high paths after 9000,4000,14000,2000,6000,12000,16000,5000, successor-side pull of 4000, and empty/duplicate/absent channels",
            "64-bit keys and a third turn vocabulary",
            "exception-throwing ordered tree with structural path/depth queries",
            project_support=True,
        ),
        c(
            "f26bst-summit-cairn-line",
            "Summit cairn line",
            "summit_cairn",
            """
            class CairnDuplicateError : public std::logic_error {
            public:
                explicit CairnDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class CairnAbsentError : public std::domain_error {
            public:
                explicit CairnAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class SummitCairnLine {
            public:
                void stack(std::int64_t elevation);
                void unstack(std::int64_t elevation);
                bool stacked(std::int64_t elevation) const;
                std::size_t cairns() const;
                std::string trail_to(std::int64_t elevation) const;
                std::int32_t trail_depth(std::int64_t elevation) const;
            };
            """,
            """
            class CairnDuplicateError : public std::logic_error {
            public:
                explicit CairnDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class CairnAbsentError : public std::domain_error {
            public:
                explicit CairnAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class SummitCairnLine {
            public:
                void stack(std::int64_t elevation);
                void unstack(std::int64_t elevation);
                bool stacked(std::int64_t elevation) const;
                std::size_t cairns() const;
                std::string trail_to(std::int64_t elevation) const;
                std::int32_t trail_depth(std::int64_t elevation) const;
            private:
                struct Node {
                    std::int64_t elevation;
                    std::unique_ptr<Node> down;
                    std::unique_ptr<Node> up;
                    explicit Node(std::int64_t value);
                };
                std::unique_ptr<Node> peak_;
                std::size_t piled_ = 0;
                static std::unique_ptr<Node> crumble(std::unique_ptr<Node> node, std::int64_t elevation, bool& removed);
            };
            """,
            """
            SummitCairnLine::Node::Node(std::int64_t value) : elevation(value) {}
            bool SummitCairnLine::stacked(std::int64_t elevation) const {
                const Node* current = peak_.get();
                while (current) {
                    if (elevation == current->elevation) return true;
                    current = elevation < current->elevation ? current->down.get() : current->up.get();
                }
                return false;
            }
            std::size_t SummitCairnLine::cairns() const { return piled_; }
            void SummitCairnLine::stack(std::int64_t elevation) {
                if (!peak_) {
                    peak_ = std::make_unique<Node>(elevation);
                    piled_ = 1;
                    return;
                }
                Node* current = peak_.get();
                for (;;) {
                    if (elevation == current->elevation) throw CairnDuplicateError("elevation already stacked");
                    if (elevation < current->elevation) {
                        if (!current->down) {
                            current->down = std::make_unique<Node>(elevation);
                            ++piled_;
                            return;
                        }
                        current = current->down.get();
                    } else {
                        if (!current->up) {
                            current->up = std::make_unique<Node>(elevation);
                            ++piled_;
                            return;
                        }
                        current = current->up.get();
                    }
                }
            }
            std::unique_ptr<SummitCairnLine::Node> SummitCairnLine::crumble(std::unique_ptr<Node> node, std::int64_t elevation, bool& removed) {
                if (!node) return nullptr;
                if (elevation < node->elevation) {
                    node->down = crumble(std::move(node->down), elevation, removed);
                    return node;
                }
                if (node->elevation < elevation) {
                    node->up = crumble(std::move(node->up), elevation, removed);
                    return node;
                }
                removed = true;
                if (!node->down) return std::move(node->up);
                if (!node->up) return std::move(node->down);
                Node* successor = node->up.get();
                while (successor->down) successor = successor->down.get();
                node->elevation = successor->elevation;
                bool ignored = false;
                node->up = crumble(std::move(node->up), successor->elevation, ignored);
                return node;
            }
            void SummitCairnLine::unstack(std::int64_t elevation) {
                bool removed = false;
                peak_ = crumble(std::move(peak_), elevation, removed);
                if (!removed) throw CairnAbsentError("elevation is not stacked");
                --piled_;
            }
            std::string SummitCairnLine::trail_to(std::int64_t elevation) const {
                const Node* current = peak_.get();
                std::string trail = "peak";
                while (current) {
                    if (elevation == current->elevation) return trail;
                    if (elevation < current->elevation) {
                        trail += ">down";
                        current = current->down.get();
                    } else {
                        trail += ">up";
                        current = current->up.get();
                    }
                }
                throw CairnAbsentError("elevation is not stacked");
            }
            std::int32_t SummitCairnLine::trail_depth(std::int64_t elevation) const {
                const Node* current = peak_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (elevation == current->elevation) return depth;
                    ++depth;
                    current = elevation < current->elevation ? current->down.get() : current->up.get();
                }
                throw CairnAbsentError("elevation is not stacked");
            }
            """,
            """
            SummitCairnLine::Node::Node(std::int64_t value) : elevation(value) {}
            bool SummitCairnLine::stacked(std::int64_t elevation) const {
                const Node* current = peak_.get();
                while (current) {
                    if (elevation == current->elevation) return true;
                    current = current->up.get();
                }
                return false;
            }
            std::size_t SummitCairnLine::cairns() const { return piled_; }
            void SummitCairnLine::stack(std::int64_t elevation) {
                if (stacked(elevation)) throw CairnDuplicateError("elevation already stacked");
                if (!peak_) {
                    peak_ = std::make_unique<Node>(elevation);
                    piled_ = 1;
                    return;
                }
                Node* current = peak_.get();
                while (current->up) current = current->up.get();
                current->up = std::make_unique<Node>(elevation);
                ++piled_;
            }
            void SummitCairnLine::unstack(std::int64_t elevation) {
                if (!peak_) throw CairnAbsentError("elevation is not stacked");
                if (peak_->elevation == elevation) {
                    peak_ = std::move(peak_->up);
                    --piled_;
                    return;
                }
                Node* parent = peak_.get();
                while (parent->up && parent->up->elevation != elevation) parent = parent->up.get();
                if (!parent->up) throw CairnAbsentError("elevation is not stacked");
                parent->up = std::move(parent->up->up);
                --piled_;
            }
            std::string SummitCairnLine::trail_to(std::int64_t elevation) const {
                const Node* current = peak_.get();
                std::string trail = "peak";
                while (current) {
                    if (elevation == current->elevation) return trail;
                    trail += ">up";
                    current = current->up.get();
                }
                throw CairnAbsentError("elevation is not stacked");
            }
            std::int32_t SummitCairnLine::trail_depth(std::int64_t elevation) const {
                const Node* current = peak_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (elevation == current->elevation) return depth;
                    ++depth;
                    current = current->up.get();
                }
                throw CairnAbsentError("elevation is not stacked");
            }
            """,
            """
            SummitCairnLine line;
            line.stack(2400);
            line.stack(1200);
            line.stack(3600);
            line.stack(600);
            line.stack(1800);
            line.stack(3000);
            line.stack(4200);
            line.stack(1500);
            if (!line.stacked(1500) || !line.stacked(600)) return 1;
            if (line.cairns() != 8U) return 2;
            line.unstack(1200);
            if (line.stacked(1200)) return 3;
            if (line.cairns() != 7U) return 4;
            if (!line.stacked(1500) || !line.stacked(1800)) return 5;
            return 0;
            """,
            """
            SummitCairnLine line;
            bool threw = false;
            try { line.trail_depth(2400); } catch (const CairnAbsentError&) { threw = true; }
            if (!threw) return 1;
            line.stack(2400);
            line.stack(1200);
            line.stack(3600);
            line.stack(600);
            line.stack(1800);
            line.stack(3000);
            line.stack(4200);
            line.stack(1500);
            threw = false;
            try { line.stack(1800); } catch (const CairnDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (line.cairns() != 8U) return 3;
            if (line.trail_to(1500) != "peak>down>up>down") return 4;
            if (line.trail_to(3000) != "peak>up>down") return 5;
            if (line.trail_to(2400) != "peak") return 6;
            if (line.trail_depth(1500) != 3) return 7;
            if (line.trail_depth(3600) != 1) return 8;
            line.unstack(1200);
            if (line.trail_to(1500) != "peak>down") return 9;
            if (line.trail_to(1800) != "peak>down>up") return 10;
            if (line.trail_depth(1500) != 1) return 11;
            threw = false;
            try { line.unstack(1200); } catch (const CairnAbsentError&) { threw = true; }
            if (!threw) return 12;
            if (line.cairns() != 7U) return 13;
            return 0;
            """,
            "elevation-keyed linked cairns with peak/down/up trail rendering",
            "an ordered container, a sorted std::vector, or a single-sided up chain that ignores ordering decisions as the core store",
            "exact peak>down>up trails after 2400,1200,3600,600,1800,3000,4200,1500, successor-side unstack of 1200, and duplicate/absent channels",
            "elevation domain with another rendering grammar",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-terrace-vine-rows",
            "Terrace vine rows",
            "terrace_vine",
            """
            class RowDuplicateError : public std::runtime_error {
            public:
                explicit RowDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class RowAbsentError : public std::invalid_argument {
            public:
                explicit RowAbsentError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TerraceVineRows {
            public:
                void plant(std::int32_t row);
                void uproot(std::int32_t row);
                bool planted(std::int32_t row) const;
                std::size_t rows() const;
                std::string level_path(std::int32_t row) const;
                std::int32_t level_of(std::int32_t row) const;
            };
            """,
            """
            class RowDuplicateError : public std::runtime_error {
            public:
                explicit RowDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class RowAbsentError : public std::invalid_argument {
            public:
                explicit RowAbsentError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TerraceVineRows {
            public:
                void plant(std::int32_t row);
                void uproot(std::int32_t row);
                bool planted(std::int32_t row) const;
                std::size_t rows() const;
                std::string level_path(std::int32_t row) const;
                std::int32_t level_of(std::int32_t row) const;
            private:
                struct Node {
                    std::int32_t row;
                    std::unique_ptr<Node> downhill;
                    std::unique_ptr<Node> uphill;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> crown_;
                std::size_t planted_ = 0;
                static std::unique_ptr<Node> graft(std::unique_ptr<Node> node, std::int32_t row, bool& linked);
                static std::unique_ptr<Node> prune(std::unique_ptr<Node> node, std::int32_t row, bool& removed);
            };
            """,
            """
            TerraceVineRows::Node::Node(std::int32_t value) : row(value) {}
            bool TerraceVineRows::planted(std::int32_t row) const {
                const Node* current = crown_.get();
                while (current) {
                    if (row == current->row) return true;
                    current = row < current->row ? current->downhill.get() : current->uphill.get();
                }
                return false;
            }
            std::size_t TerraceVineRows::rows() const { return planted_; }
            std::unique_ptr<TerraceVineRows::Node> TerraceVineRows::graft(std::unique_ptr<Node> node, std::int32_t row, bool& linked) {
                if (!node) {
                    linked = true;
                    return std::make_unique<Node>(row);
                }
                if (row == node->row) return node;
                if (row < node->row) {
                    node->downhill = graft(std::move(node->downhill), row, linked);
                } else {
                    node->uphill = graft(std::move(node->uphill), row, linked);
                }
                return node;
            }
            void TerraceVineRows::plant(std::int32_t row) {
                bool linked = false;
                crown_ = graft(std::move(crown_), row, linked);
                if (!linked) throw RowDuplicateError("row already planted");
                ++planted_;
            }
            std::unique_ptr<TerraceVineRows::Node> TerraceVineRows::prune(std::unique_ptr<Node> node, std::int32_t row, bool& removed) {
                if (!node) return nullptr;
                if (row < node->row) {
                    node->downhill = prune(std::move(node->downhill), row, removed);
                    return node;
                }
                if (node->row < row) {
                    node->uphill = prune(std::move(node->uphill), row, removed);
                    return node;
                }
                removed = true;
                if (!node->downhill) return std::move(node->uphill);
                if (!node->uphill) return std::move(node->downhill);
                Node* successor = node->uphill.get();
                while (successor->downhill) successor = successor->downhill.get();
                node->row = successor->row;
                bool ignored = false;
                node->uphill = prune(std::move(node->uphill), successor->row, ignored);
                return node;
            }
            void TerraceVineRows::uproot(std::int32_t row) {
                bool removed = false;
                crown_ = prune(std::move(crown_), row, removed);
                if (!removed) throw RowAbsentError("row is not planted");
                --planted_;
            }
            std::string TerraceVineRows::level_path(std::int32_t row) const {
                const Node* current = crown_.get();
                std::string path = "crown";
                while (current) {
                    if (row == current->row) return path;
                    if (row < current->row) {
                        path += ",left";
                        current = current->downhill.get();
                    } else {
                        path += ",right";
                        current = current->uphill.get();
                    }
                }
                throw RowAbsentError("row is not planted");
            }
            std::int32_t TerraceVineRows::level_of(std::int32_t row) const {
                const Node* current = crown_.get();
                std::int32_t level = 0;
                while (current) {
                    if (row == current->row) return level;
                    ++level;
                    current = row < current->row ? current->downhill.get() : current->uphill.get();
                }
                throw RowAbsentError("row is not planted");
            }
            """,
            """
            TerraceVineRows::Node::Node(std::int32_t value) : row(value) {}
            bool TerraceVineRows::planted(std::int32_t row) const {
                const Node* current = crown_.get();
                while (current) {
                    if (row == current->row) return true;
                    current = current->downhill.get();
                }
                return false;
            }
            std::size_t TerraceVineRows::rows() const { return planted_; }
            void TerraceVineRows::plant(std::int32_t row) {
                if (planted(row)) throw RowDuplicateError("row already planted");
                if (!crown_) {
                    crown_ = std::make_unique<Node>(row);
                    planted_ = 1;
                    return;
                }
                Node* current = crown_.get();
                while (current->downhill) current = current->downhill.get();
                current->downhill = std::make_unique<Node>(row);
                ++planted_;
            }
            void TerraceVineRows::uproot(std::int32_t row) {
                if (!crown_) throw RowAbsentError("row is not planted");
                if (crown_->row == row) {
                    crown_ = std::move(crown_->downhill);
                    --planted_;
                    return;
                }
                Node* parent = crown_.get();
                while (parent->downhill && parent->downhill->row != row) parent = parent->downhill.get();
                if (!parent->downhill) throw RowAbsentError("row is not planted");
                parent->downhill = std::move(parent->downhill->downhill);
                --planted_;
            }
            std::string TerraceVineRows::level_path(std::int32_t row) const {
                const Node* current = crown_.get();
                std::string path = "crown";
                while (current) {
                    if (row == current->row) return path;
                    path += ",left";
                    current = current->downhill.get();
                }
                throw RowAbsentError("row is not planted");
            }
            std::int32_t TerraceVineRows::level_of(std::int32_t row) const {
                const Node* current = crown_.get();
                std::int32_t level = 0;
                while (current) {
                    if (row == current->row) return level;
                    ++level;
                    current = current->downhill.get();
                }
                throw RowAbsentError("row is not planted");
            }
            """,
            """
            TerraceVineRows rows_obj;
            rows_obj.plant(75);
            rows_obj.plant(38);
            rows_obj.plant(113);
            rows_obj.plant(19);
            rows_obj.plant(57);
            rows_obj.plant(94);
            rows_obj.plant(132);
            rows_obj.plant(47);
            if (!rows_obj.planted(47) || !rows_obj.planted(19)) return 1;
            if (rows_obj.rows() != 8U) return 2;
            rows_obj.uproot(38);
            if (rows_obj.planted(38)) return 3;
            if (rows_obj.rows() != 7U) return 4;
            if (!rows_obj.planted(47) || !rows_obj.planted(57)) return 5;
            return 0;
            """,
            """
            TerraceVineRows rows_obj;
            bool threw = false;
            try { rows_obj.level_of(75); } catch (const RowAbsentError&) { threw = true; }
            if (!threw) return 1;
            rows_obj.plant(75);
            rows_obj.plant(38);
            rows_obj.plant(113);
            rows_obj.plant(19);
            rows_obj.plant(57);
            rows_obj.plant(94);
            rows_obj.plant(132);
            rows_obj.plant(47);
            threw = false;
            try { rows_obj.plant(57); } catch (const RowDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (rows_obj.rows() != 8U) return 3;
            if (rows_obj.level_path(47) != "crown,left,right,left") return 4;
            if (rows_obj.level_path(94) != "crown,right,left") return 5;
            if (rows_obj.level_path(75) != "crown") return 6;
            if (rows_obj.level_of(47) != 3) return 7;
            if (rows_obj.level_of(113) != 1) return 8;
            rows_obj.uproot(38);
            if (rows_obj.level_path(47) != "crown,left") return 9;
            if (rows_obj.level_path(57) != "crown,left,right") return 10;
            if (rows_obj.level_of(47) != 1) return 11;
            threw = false;
            try { rows_obj.uproot(38); } catch (const RowAbsentError&) { threw = true; }
            if (!threw) return 12;
            if (rows_obj.rows() != 7U) return 13;
            return 0;
            """,
            "recursively maintained linked rows with crown/left/right level rendering",
            "an ordered container, a sorted std::vector, or a single-sided downhill chain that ignores ordering decisions as the core store",
            "exact crown,left,right paths after 75,38,113,19,57,94,132,47, recursive successor-side uproot of 38, and duplicate/absent channels",
            "a second recursive grammar with distinct vocabulary",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-beacon-hill-posts",
            "Beacon hill posts",
            "beacon_hill",
            """
            class PostDuplicateError : public std::out_of_range {
            public:
                explicit PostDuplicateError(const std::string& message) : std::out_of_range(message) {}
            };
            class PostAbsentError : public std::logic_error {
            public:
                explicit PostAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class BeaconHillPosts {
            public:
                void raise_post(std::int32_t post);
                void fell_post(std::int32_t post);
                bool raised(std::int32_t post) const;
                std::size_t standing() const;
                std::string signal_code(std::int32_t post) const;
                std::int32_t signal_depth(std::int32_t post) const;
            };
            """,
            """
            class PostDuplicateError : public std::out_of_range {
            public:
                explicit PostDuplicateError(const std::string& message) : std::out_of_range(message) {}
            };
            class PostAbsentError : public std::logic_error {
            public:
                explicit PostAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class BeaconHillPosts {
            public:
                void raise_post(std::int32_t post);
                void fell_post(std::int32_t post);
                bool raised(std::int32_t post) const;
                std::size_t standing() const;
                std::string signal_code(std::int32_t post) const;
                std::int32_t signal_depth(std::int32_t post) const;
            private:
                struct Node {
                    std::int32_t post;
                    std::unique_ptr<Node> lesser;
                    std::unique_ptr<Node> greater;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> summit_;
                std::size_t upright_ = 0;
                static std::unique_ptr<Node> raze(std::unique_ptr<Node> node, std::int32_t post, bool& removed);
            };
            """,
            """
            BeaconHillPosts::Node::Node(std::int32_t value) : post(value) {}
            bool BeaconHillPosts::raised(std::int32_t post) const {
                const Node* current = summit_.get();
                while (current) {
                    if (post == current->post) return true;
                    current = post < current->post ? current->lesser.get() : current->greater.get();
                }
                return false;
            }
            std::size_t BeaconHillPosts::standing() const { return upright_; }
            void BeaconHillPosts::raise_post(std::int32_t post) {
                if (!summit_) {
                    summit_ = std::make_unique<Node>(post);
                    upright_ = 1;
                    return;
                }
                Node* current = summit_.get();
                for (;;) {
                    if (post == current->post) throw PostDuplicateError("post already raised");
                    if (post < current->post) {
                        if (!current->lesser) {
                            current->lesser = std::make_unique<Node>(post);
                            ++upright_;
                            return;
                        }
                        current = current->lesser.get();
                    } else {
                        if (!current->greater) {
                            current->greater = std::make_unique<Node>(post);
                            ++upright_;
                            return;
                        }
                        current = current->greater.get();
                    }
                }
            }
            std::unique_ptr<BeaconHillPosts::Node> BeaconHillPosts::raze(std::unique_ptr<Node> node, std::int32_t post, bool& removed) {
                if (!node) return nullptr;
                if (post < node->post) {
                    node->lesser = raze(std::move(node->lesser), post, removed);
                    return node;
                }
                if (node->post < post) {
                    node->greater = raze(std::move(node->greater), post, removed);
                    return node;
                }
                removed = true;
                if (!node->lesser) return std::move(node->greater);
                if (!node->greater) return std::move(node->lesser);
                Node* successor = node->greater.get();
                while (successor->lesser) successor = successor->lesser.get();
                node->post = successor->post;
                bool ignored = false;
                node->greater = raze(std::move(node->greater), successor->post, ignored);
                return node;
            }
            void BeaconHillPosts::fell_post(std::int32_t post) {
                bool removed = false;
                summit_ = raze(std::move(summit_), post, removed);
                if (!removed) throw PostAbsentError("post is not raised");
                --upright_;
            }
            std::string BeaconHillPosts::signal_code(std::int32_t post) const {
                const Node* current = summit_.get();
                std::string code = "s";
                while (current) {
                    if (post == current->post) return code;
                    if (post < current->post) {
                        code += "l";
                        current = current->lesser.get();
                    } else {
                        code += "r";
                        current = current->greater.get();
                    }
                }
                throw PostAbsentError("post is not raised");
            }
            std::int32_t BeaconHillPosts::signal_depth(std::int32_t post) const {
                const Node* current = summit_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (post == current->post) return depth;
                    ++depth;
                    current = post < current->post ? current->lesser.get() : current->greater.get();
                }
                throw PostAbsentError("post is not raised");
            }
            """,
            """
            BeaconHillPosts::Node::Node(std::int32_t value) : post(value) {}
            bool BeaconHillPosts::raised(std::int32_t post) const {
                const Node* current = summit_.get();
                while (current) {
                    if (post == current->post) return true;
                    current = current->greater.get();
                }
                return false;
            }
            std::size_t BeaconHillPosts::standing() const { return upright_; }
            void BeaconHillPosts::raise_post(std::int32_t post) {
                if (raised(post)) throw PostDuplicateError("post already raised");
                if (!summit_) {
                    summit_ = std::make_unique<Node>(post);
                    upright_ = 1;
                    return;
                }
                Node* current = summit_.get();
                while (current->greater) current = current->greater.get();
                current->greater = std::make_unique<Node>(post);
                ++upright_;
            }
            void BeaconHillPosts::fell_post(std::int32_t post) {
                if (!summit_) throw PostAbsentError("post is not raised");
                if (summit_->post == post) {
                    summit_ = std::move(summit_->greater);
                    --upright_;
                    return;
                }
                Node* parent = summit_.get();
                while (parent->greater && parent->greater->post != post) parent = parent->greater.get();
                if (!parent->greater) throw PostAbsentError("post is not raised");
                parent->greater = std::move(parent->greater->greater);
                --upright_;
            }
            std::string BeaconHillPosts::signal_code(std::int32_t post) const {
                const Node* current = summit_.get();
                std::string code = "s";
                while (current) {
                    if (post == current->post) return code;
                    code += "r";
                    current = current->greater.get();
                }
                throw PostAbsentError("post is not raised");
            }
            std::int32_t BeaconHillPosts::signal_depth(std::int32_t post) const {
                const Node* current = summit_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (post == current->post) return depth;
                    ++depth;
                    current = current->greater.get();
                }
                throw PostAbsentError("post is not raised");
            }
            """,
            """
            BeaconHillPosts posts;
            posts.raise_post(512);
            posts.raise_post(256);
            posts.raise_post(768);
            posts.raise_post(128);
            posts.raise_post(384);
            posts.raise_post(640);
            posts.raise_post(896);
            posts.raise_post(320);
            if (!posts.raised(320) || !posts.raised(128)) return 1;
            if (posts.standing() != 8U) return 2;
            posts.fell_post(256);
            if (posts.raised(256)) return 3;
            if (posts.standing() != 7U) return 4;
            if (!posts.raised(320) || !posts.raised(384)) return 5;
            return 0;
            """,
            """
            BeaconHillPosts posts;
            bool threw = false;
            try { posts.signal_depth(512); } catch (const PostAbsentError&) { threw = true; }
            if (!threw) return 1;
            posts.raise_post(512);
            posts.raise_post(256);
            posts.raise_post(768);
            posts.raise_post(128);
            posts.raise_post(384);
            posts.raise_post(640);
            posts.raise_post(896);
            posts.raise_post(320);
            threw = false;
            try { posts.raise_post(384); } catch (const PostDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (posts.standing() != 8U) return 3;
            if (posts.signal_code(320) != "slrl") return 4;
            if (posts.signal_code(640) != "srl") return 5;
            if (posts.signal_code(512) != "s") return 6;
            if (posts.signal_depth(320) != 3) return 7;
            if (posts.signal_depth(768) != 1) return 8;
            posts.fell_post(256);
            if (posts.signal_code(320) != "sl") return 9;
            if (posts.signal_code(384) != "slr") return 10;
            if (posts.signal_depth(320) != 1) return 11;
            threw = false;
            try { posts.fell_post(256); } catch (const PostAbsentError&) { threw = true; }
            if (!threw) return 12;
            if (posts.standing() != 7U) return 13;
            return 0;
            """,
            "insertion-ordered linked posts with compact single-letter signal codes",
            "an ordered container, a sorted std::vector, or a single-sided greater chain that ignores ordering decisions as the core store",
            "exact slr codes and depths after 512,256,768,128,384,640,896,320, successor-side fell of 256, and duplicate/absent channels",
            "compact code rendering on structural queries",
            "exception-throwing ordered tree with structural path/depth queries",
        ),
        c(
            "f26bst-courier-locker-grid",
            "Courier locker grid",
            "courier_locker",
            """
            class CourierLockerGrid {
            public:
                bool assign(std::int32_t locker);
                bool release(std::int32_t locker);
                bool occupied(std::int32_t locker) const;
                std::size_t taken() const;
                std::optional<std::int32_t> depth_of(std::int32_t locker) const;
                std::optional<std::int32_t> parent_of(std::int32_t locker) const;
            };
            """,
            """
            class CourierLockerGrid {
            public:
                bool assign(std::int32_t locker);
                bool release(std::int32_t locker);
                bool occupied(std::int32_t locker) const;
                std::size_t taken() const;
                std::optional<std::int32_t> depth_of(std::int32_t locker) const;
                std::optional<std::int32_t> parent_of(std::int32_t locker) const;
            private:
                struct Node {
                    std::int32_t locker;
                    std::unique_ptr<Node> small;
                    std::unique_ptr<Node> large;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> hub_;
                std::size_t taken_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t locker, bool& removed);
            };
            """,
            """
            CourierLockerGrid::Node::Node(std::int32_t value) : locker(value) {}
            bool CourierLockerGrid::occupied(std::int32_t locker) const {
                const Node* current = hub_.get();
                while (current) {
                    if (locker == current->locker) return true;
                    current = locker < current->locker ? current->small.get() : current->large.get();
                }
                return false;
            }
            std::size_t CourierLockerGrid::taken() const { return taken_; }
            bool CourierLockerGrid::assign(std::int32_t locker) {
                if (!hub_) {
                    hub_ = std::make_unique<Node>(locker);
                    taken_ = 1;
                    return true;
                }
                Node* current = hub_.get();
                for (;;) {
                    if (locker == current->locker) return false;
                    if (locker < current->locker) {
                        if (!current->small) {
                            current->small = std::make_unique<Node>(locker);
                            ++taken_;
                            return true;
                        }
                        current = current->small.get();
                    } else {
                        if (!current->large) {
                            current->large = std::make_unique<Node>(locker);
                            ++taken_;
                            return true;
                        }
                        current = current->large.get();
                    }
                }
            }
            std::unique_ptr<CourierLockerGrid::Node> CourierLockerGrid::detach(std::unique_ptr<Node> node, std::int32_t locker, bool& removed) {
                if (!node) return nullptr;
                if (locker < node->locker) {
                    node->small = detach(std::move(node->small), locker, removed);
                    return node;
                }
                if (node->locker < locker) {
                    node->large = detach(std::move(node->large), locker, removed);
                    return node;
                }
                removed = true;
                if (!node->small) return std::move(node->large);
                if (!node->large) return std::move(node->small);
                Node* successor = node->large.get();
                while (successor->small) successor = successor->small.get();
                node->locker = successor->locker;
                bool ignored = false;
                node->large = detach(std::move(node->large), successor->locker, ignored);
                return node;
            }
            bool CourierLockerGrid::release(std::int32_t locker) {
                bool removed = false;
                hub_ = detach(std::move(hub_), locker, removed);
                if (!removed) return false;
                --taken_;
                return true;
            }
            std::optional<std::int32_t> CourierLockerGrid::depth_of(std::int32_t locker) const {
                const Node* current = hub_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (locker == current->locker) return depth;
                    ++depth;
                    current = locker < current->locker ? current->small.get() : current->large.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> CourierLockerGrid::parent_of(std::int32_t locker) const {
                const Node* current = hub_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (locker == current->locker) {
                        if (!parent) return std::nullopt;
                        return parent->locker;
                    }
                    parent = current;
                    current = locker < current->locker ? current->small.get() : current->large.get();
                }
                return std::nullopt;
            }
            """,
            """
            CourierLockerGrid::Node::Node(std::int32_t value) : locker(value) {}
            bool CourierLockerGrid::occupied(std::int32_t locker) const {
                const Node* current = hub_.get();
                while (current) {
                    if (locker == current->locker) return true;
                    current = current->small.get();
                }
                return false;
            }
            std::size_t CourierLockerGrid::taken() const { return taken_; }
            bool CourierLockerGrid::assign(std::int32_t locker) {
                if (occupied(locker)) return false;
                if (!hub_) {
                    hub_ = std::make_unique<Node>(locker);
                    taken_ = 1;
                    return true;
                }
                Node* current = hub_.get();
                while (current->small) current = current->small.get();
                current->small = std::make_unique<Node>(locker);
                ++taken_;
                return true;
            }
            bool CourierLockerGrid::release(std::int32_t locker) {
                if (!hub_) return false;
                if (hub_->locker == locker) {
                    hub_ = std::move(hub_->small);
                    --taken_;
                    return true;
                }
                Node* parent = hub_.get();
                while (parent->small && parent->small->locker != locker) parent = parent->small.get();
                if (!parent->small) return false;
                parent->small = std::move(parent->small->small);
                --taken_;
                return true;
            }
            std::optional<std::int32_t> CourierLockerGrid::depth_of(std::int32_t locker) const {
                const Node* current = hub_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (locker == current->locker) return depth;
                    ++depth;
                    current = current->small.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> CourierLockerGrid::parent_of(std::int32_t locker) const {
                const Node* current = hub_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (locker == current->locker) {
                        if (!parent) return std::nullopt;
                        return parent->locker;
                    }
                    parent = current;
                    current = current->small.get();
                }
                return std::nullopt;
            }
            """,
            """
            CourierLockerGrid grid;
            if (!grid.assign(45)) return 1;
            grid.assign(23);
            grid.assign(67);
            grid.assign(12);
            grid.assign(34);
            grid.assign(56);
            grid.assign(78);
            grid.assign(29);
            if (!grid.occupied(29) || grid.occupied(99)) return 2;
            if (grid.taken() != 8U) return 3;
            if (grid.assign(34)) return 4;
            if (!grid.release(23)) return 5;
            if (grid.occupied(23)) return 6;
            if (grid.release(23)) return 7;
            if (grid.taken() != 7U) return 8;
            return 0;
            """,
            """
            CourierLockerGrid grid;
            if (grid.depth_of(45).has_value()) return 1;
            grid.assign(45);
            grid.assign(23);
            grid.assign(67);
            grid.assign(12);
            grid.assign(34);
            grid.assign(56);
            grid.assign(78);
            grid.assign(29);
            if (grid.assign(34)) return 2;
            if (grid.taken() != 8U) return 3;
            if (grid.depth_of(29) != 3) return 4;
            if (grid.depth_of(45) != 0) return 5;
            if (grid.parent_of(29) != 34) return 6;
            if (grid.parent_of(45).has_value()) return 7;
            if (grid.depth_of(999).has_value()) return 8;
            if (grid.parent_of(999).has_value()) return 9;
            if (grid.release(999)) return 10;
            if (!grid.release(23)) return 11;
            if (grid.depth_of(34) != 2) return 12;
            if (grid.parent_of(34) != 29) return 13;
            if (grid.depth_of(29) != 1) return 14;
            if (grid.taken() != 7U) return 15;
            return 0;
            """,
            "boolean-channel linked lockers with optional structural depth and parent queries",
            "an ordered container, a sorted std::vector, or a single-sided small chain that ignores ordering decisions as the core store",
            "duplicate/absent false results, exact depths and parents after 45,23,67,12,34,56,78,29, successor-side release of 23, and root-parent nullopt",
            "the bool/optional channel over linked structure",
            "status-returning ordered tree (bool/optional channels)",
        ),
        c(
            "f26bst-museum-case-layout",
            "Museum case layout",
            "museum_case",
            """
            class MuseumCaseLayout {
            public:
                bool install(std::int32_t case_no);
                bool uninstall(std::int32_t case_no);
                bool installed(std::int32_t case_no) const;
                std::size_t cases() const;
                std::optional<std::vector<std::string>> corridor_to(std::int32_t case_no) const;
                std::optional<std::int32_t> parent_of(std::int32_t case_no) const;
            };
            """,
            """
            class MuseumCaseLayout {
            public:
                bool install(std::int32_t case_no);
                bool uninstall(std::int32_t case_no);
                bool installed(std::int32_t case_no) const;
                std::size_t cases() const;
                std::optional<std::vector<std::string>> corridor_to(std::int32_t case_no) const;
                std::optional<std::int32_t> parent_of(std::int32_t case_no) const;
            private:
                struct Node {
                    std::int32_t case_no;
                    std::unique_ptr<Node> near_wing;
                    std::unique_ptr<Node> far_wing;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> hall_;
                std::size_t installed_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t case_no, bool& removed);
            };
            """,
            """
            MuseumCaseLayout::Node::Node(std::int32_t value) : case_no(value) {}
            bool MuseumCaseLayout::installed(std::int32_t case_no) const {
                const Node* current = hall_.get();
                while (current) {
                    if (case_no == current->case_no) return true;
                    current = case_no < current->case_no ? current->near_wing.get() : current->far_wing.get();
                }
                return false;
            }
            std::size_t MuseumCaseLayout::cases() const { return installed_; }
            bool MuseumCaseLayout::install(std::int32_t case_no) {
                if (!hall_) {
                    hall_ = std::make_unique<Node>(case_no);
                    installed_ = 1;
                    return true;
                }
                Node* current = hall_.get();
                for (;;) {
                    if (case_no == current->case_no) return false;
                    if (case_no < current->case_no) {
                        if (!current->near_wing) {
                            current->near_wing = std::make_unique<Node>(case_no);
                            ++installed_;
                            return true;
                        }
                        current = current->near_wing.get();
                    } else {
                        if (!current->far_wing) {
                            current->far_wing = std::make_unique<Node>(case_no);
                            ++installed_;
                            return true;
                        }
                        current = current->far_wing.get();
                    }
                }
            }
            std::unique_ptr<MuseumCaseLayout::Node> MuseumCaseLayout::detach(std::unique_ptr<Node> node, std::int32_t case_no, bool& removed) {
                if (!node) return nullptr;
                if (case_no < node->case_no) {
                    node->near_wing = detach(std::move(node->near_wing), case_no, removed);
                    return node;
                }
                if (node->case_no < case_no) {
                    node->far_wing = detach(std::move(node->far_wing), case_no, removed);
                    return node;
                }
                removed = true;
                if (!node->near_wing) return std::move(node->far_wing);
                if (!node->far_wing) return std::move(node->near_wing);
                Node* successor = node->far_wing.get();
                while (successor->near_wing) successor = successor->near_wing.get();
                node->case_no = successor->case_no;
                bool ignored = false;
                node->far_wing = detach(std::move(node->far_wing), successor->case_no, ignored);
                return node;
            }
            bool MuseumCaseLayout::uninstall(std::int32_t case_no) {
                bool removed = false;
                hall_ = detach(std::move(hall_), case_no, removed);
                if (!removed) return false;
                --installed_;
                return true;
            }
            std::optional<std::vector<std::string>> MuseumCaseLayout::corridor_to(std::int32_t case_no) const {
                const Node* current = hall_.get();
                std::vector<std::string> turns;
                while (current) {
                    if (case_no == current->case_no) return turns;
                    if (case_no < current->case_no) {
                        turns.push_back("left");
                        current = current->near_wing.get();
                    } else {
                        turns.push_back("right");
                        current = current->far_wing.get();
                    }
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> MuseumCaseLayout::parent_of(std::int32_t case_no) const {
                const Node* current = hall_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (case_no == current->case_no) {
                        if (!parent) return std::nullopt;
                        return parent->case_no;
                    }
                    parent = current;
                    current = case_no < current->case_no ? current->near_wing.get() : current->far_wing.get();
                }
                return std::nullopt;
            }
            """,
            """
            MuseumCaseLayout::Node::Node(std::int32_t value) : case_no(value) {}
            bool MuseumCaseLayout::installed(std::int32_t case_no) const {
                const Node* current = hall_.get();
                while (current) {
                    if (case_no == current->case_no) return true;
                    current = current->far_wing.get();
                }
                return false;
            }
            std::size_t MuseumCaseLayout::cases() const { return installed_; }
            bool MuseumCaseLayout::install(std::int32_t case_no) {
                if (installed(case_no)) return false;
                if (!hall_) {
                    hall_ = std::make_unique<Node>(case_no);
                    installed_ = 1;
                    return true;
                }
                Node* current = hall_.get();
                while (current->far_wing) current = current->far_wing.get();
                current->far_wing = std::make_unique<Node>(case_no);
                ++installed_;
                return true;
            }
            bool MuseumCaseLayout::uninstall(std::int32_t case_no) {
                if (!hall_) return false;
                if (hall_->case_no == case_no) {
                    hall_ = std::move(hall_->far_wing);
                    --installed_;
                    return true;
                }
                Node* parent = hall_.get();
                while (parent->far_wing && parent->far_wing->case_no != case_no) parent = parent->far_wing.get();
                if (!parent->far_wing) return false;
                parent->far_wing = std::move(parent->far_wing->far_wing);
                --installed_;
                return true;
            }
            std::optional<std::vector<std::string>> MuseumCaseLayout::corridor_to(std::int32_t case_no) const {
                const Node* current = hall_.get();
                std::vector<std::string> turns;
                while (current) {
                    if (case_no == current->case_no) return turns;
                    turns.push_back("right");
                    current = current->far_wing.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> MuseumCaseLayout::parent_of(std::int32_t case_no) const {
                const Node* current = hall_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (case_no == current->case_no) {
                        if (!parent) return std::nullopt;
                        return parent->case_no;
                    }
                    parent = current;
                    current = current->far_wing.get();
                }
                return std::nullopt;
            }
            """,
            """
            MuseumCaseLayout layout;
            layout.install(210);
            layout.install(105);
            layout.install(315);
            layout.install(53);
            layout.install(158);
            layout.install(263);
            layout.install(368);
            layout.install(131);
            if (!layout.installed(131) || layout.installed(999)) return 1;
            if (layout.cases() != 8U) return 2;
            if (layout.install(158)) return 3;
            if (!layout.uninstall(105)) return 4;
            if (layout.installed(105)) return 5;
            if (layout.cases() != 7U) return 6;
            return 0;
            """,
            """
            MuseumCaseLayout layout;
            if (layout.corridor_to(210).has_value()) return 1;
            layout.install(210);
            layout.install(105);
            layout.install(315);
            layout.install(53);
            layout.install(158);
            layout.install(263);
            layout.install(368);
            layout.install(131);
            if (layout.install(158)) return 2;
            std::vector<std::string> expected_131 = {"left", "right", "left"};
            if (layout.corridor_to(131) != expected_131) return 3;
            std::vector<std::string> expected_263 = {"right", "left"};
            if (layout.corridor_to(263) != expected_263) return 4;
            std::vector<std::string> expected_210 = {};
            if (layout.corridor_to(210) != expected_210) return 5;
            if (layout.parent_of(131) != 158) return 6;
            if (layout.parent_of(210).has_value()) return 7;
            if (layout.corridor_to(999).has_value()) return 8;
            if (!layout.uninstall(105)) return 9;
            std::vector<std::string> expected_after_131 = {"left"};
            if (layout.corridor_to(131) != expected_after_131) return 10;
            std::vector<std::string> expected_after_158 = {"left", "right"};
            if (layout.corridor_to(158) != expected_after_158) return 11;
            if (layout.parent_of(131) != 210) return 12;
            if (layout.cases() != 7U) return 13;
            return 0;
            """,
            "optional-vector corridor output over insertion-ordered linked cases",
            "an ordered container, a sorted std::vector, or a single-sided far-wing chain that ignores ordering decisions as the core store",
            "exact corridor vectors and parents after 210,105,315,53,158,263,368,131, successor-side uninstall of 105, and absent nullopt results",
            "optional turn-vector queries",
            "status-returning ordered tree (bool/optional channels)",
            project_support=True,
        ),
        c(
            "f26bst-robot-bay-scheduler",
            "Robot bay scheduler",
            "robot_bay",
            """
            class RobotBayScheduler {
            public:
                bool book(std::int32_t bay);
                bool cancel(std::int32_t bay);
                bool booked(std::int32_t bay) const;
                std::size_t booked_count() const;
                std::optional<std::int32_t> next_after(std::int32_t bay) const;
                std::optional<std::int32_t> depth_of(std::int32_t bay) const;
            };
            """,
            """
            class RobotBayScheduler {
            public:
                bool book(std::int32_t bay);
                bool cancel(std::int32_t bay);
                bool booked(std::int32_t bay) const;
                std::size_t booked_count() const;
                std::optional<std::int32_t> next_after(std::int32_t bay) const;
                std::optional<std::int32_t> depth_of(std::int32_t bay) const;
            private:
                struct Node {
                    std::int32_t bay;
                    std::unique_ptr<Node> light;
                    std::unique_ptr<Node> heavy;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> dock_;
                std::size_t booked_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t bay, bool& removed);
            };
            """,
            """
            RobotBayScheduler::Node::Node(std::int32_t value) : bay(value) {}
            bool RobotBayScheduler::booked(std::int32_t bay) const {
                const Node* current = dock_.get();
                while (current) {
                    if (bay == current->bay) return true;
                    current = bay < current->bay ? current->light.get() : current->heavy.get();
                }
                return false;
            }
            std::size_t RobotBayScheduler::booked_count() const { return booked_; }
            bool RobotBayScheduler::book(std::int32_t bay) {
                if (!dock_) {
                    dock_ = std::make_unique<Node>(bay);
                    booked_ = 1;
                    return true;
                }
                Node* current = dock_.get();
                for (;;) {
                    if (bay == current->bay) return false;
                    if (bay < current->bay) {
                        if (!current->light) {
                            current->light = std::make_unique<Node>(bay);
                            ++booked_;
                            return true;
                        }
                        current = current->light.get();
                    } else {
                        if (!current->heavy) {
                            current->heavy = std::make_unique<Node>(bay);
                            ++booked_;
                            return true;
                        }
                        current = current->heavy.get();
                    }
                }
            }
            std::unique_ptr<RobotBayScheduler::Node> RobotBayScheduler::detach(std::unique_ptr<Node> node, std::int32_t bay, bool& removed) {
                if (!node) return nullptr;
                if (bay < node->bay) {
                    node->light = detach(std::move(node->light), bay, removed);
                    return node;
                }
                if (node->bay < bay) {
                    node->heavy = detach(std::move(node->heavy), bay, removed);
                    return node;
                }
                removed = true;
                if (!node->light) return std::move(node->heavy);
                if (!node->heavy) return std::move(node->light);
                Node* successor = node->heavy.get();
                while (successor->light) successor = successor->light.get();
                node->bay = successor->bay;
                bool ignored = false;
                node->heavy = detach(std::move(node->heavy), successor->bay, ignored);
                return node;
            }
            bool RobotBayScheduler::cancel(std::int32_t bay) {
                bool removed = false;
                dock_ = detach(std::move(dock_), bay, removed);
                if (!removed) return false;
                --booked_;
                return true;
            }
            std::optional<std::int32_t> RobotBayScheduler::next_after(std::int32_t bay) const {
                if (!booked(bay)) return std::nullopt;
                const Node* current = dock_.get();
                const Node* candidate = nullptr;
                while (current) {
                    if (bay < current->bay) {
                        candidate = current;
                        current = current->light.get();
                    } else {
                        current = current->heavy.get();
                    }
                }
                if (!candidate) return std::nullopt;
                return candidate->bay;
            }
            std::optional<std::int32_t> RobotBayScheduler::depth_of(std::int32_t bay) const {
                const Node* current = dock_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bay == current->bay) return depth;
                    ++depth;
                    current = bay < current->bay ? current->light.get() : current->heavy.get();
                }
                return std::nullopt;
            }
            """,
            """
            RobotBayScheduler::Node::Node(std::int32_t value) : bay(value) {}
            bool RobotBayScheduler::booked(std::int32_t bay) const {
                const Node* current = dock_.get();
                while (current) {
                    if (bay == current->bay) return true;
                    current = current->light.get();
                }
                return false;
            }
            std::size_t RobotBayScheduler::booked_count() const { return booked_; }
            bool RobotBayScheduler::book(std::int32_t bay) {
                if (booked(bay)) return false;
                if (!dock_) {
                    dock_ = std::make_unique<Node>(bay);
                    booked_ = 1;
                    return true;
                }
                Node* current = dock_.get();
                while (current->light) current = current->light.get();
                current->light = std::make_unique<Node>(bay);
                ++booked_;
                return true;
            }
            bool RobotBayScheduler::cancel(std::int32_t bay) {
                if (!dock_) return false;
                if (dock_->bay == bay) {
                    dock_ = std::move(dock_->light);
                    --booked_;
                    return true;
                }
                Node* parent = dock_.get();
                while (parent->light && parent->light->bay != bay) parent = parent->light.get();
                if (!parent->light) return false;
                parent->light = std::move(parent->light->light);
                --booked_;
                return true;
            }
            std::optional<std::int32_t> RobotBayScheduler::next_after(std::int32_t bay) const {
                if (!booked(bay)) return std::nullopt;
                const Node* current = dock_.get();
                const Node* candidate = nullptr;
                while (current) {
                    if (bay < current->bay) {
                        candidate = current;
                        current = current->light.get();
                    } else {
                        current = current->heavy.get();
                    }
                }
                if (!candidate) return std::nullopt;
                return candidate->bay;
            }
            std::optional<std::int32_t> RobotBayScheduler::depth_of(std::int32_t bay) const {
                const Node* current = dock_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bay == current->bay) return depth;
                    ++depth;
                    current = current->light.get();
                }
                return std::nullopt;
            }
            """,
            """
            RobotBayScheduler scheduler;
            scheduler.book(91);
            scheduler.book(46);
            scheduler.book(136);
            scheduler.book(23);
            scheduler.book(68);
            scheduler.book(114);
            scheduler.book(159);
            scheduler.book(57);
            if (!scheduler.booked(57) || scheduler.booked(999)) return 1;
            if (scheduler.booked_count() != 8U) return 2;
            if (scheduler.book(68)) return 3;
            if (!scheduler.cancel(46)) return 4;
            if (scheduler.booked(46)) return 5;
            if (scheduler.booked_count() != 7U) return 6;
            return 0;
            """,
            """
            RobotBayScheduler scheduler;
            if (scheduler.next_after(91).has_value()) return 1;
            scheduler.book(91);
            scheduler.book(46);
            scheduler.book(136);
            scheduler.book(23);
            scheduler.book(68);
            scheduler.book(114);
            scheduler.book(159);
            scheduler.book(57);
            if (scheduler.book(68)) return 2;
            if (scheduler.next_after(57) != 68) return 3;
            if (scheduler.next_after(91) != 114) return 4;
            if (scheduler.next_after(159).has_value()) return 5;
            if (scheduler.depth_of(57) != 3) return 6;
            if (scheduler.depth_of(91) != 0) return 7;
            if (scheduler.depth_of(999).has_value()) return 8;
            if (!scheduler.cancel(46)) return 9;
            if (scheduler.next_after(23) != 57) return 10;
            if (scheduler.depth_of(57) != 1) return 11;
            if (scheduler.depth_of(68) != 2) return 12;
            if (scheduler.cancel(46)) return 13;
            if (scheduler.booked_count() != 7U) return 14;
            return 0;
            """,
            "linked bays pairing in-order successor lookup with structural depth",
            "an ordered container, a sorted std::vector, or a single-sided light chain that ignores ordering decisions as the core store",
            "exact successors and depths after 91,46,136,23,68,114,159,57, successor-side cancel of 46, and nullopt edges",
            "order-statistic queries paired with structure",
            "status-returning ordered tree (bool/optional channels)",
        ),
        c(
            "f26bst-garden-bed-planner",
            "Garden bed planner",
            "garden_bed",
            """
            class GardenBedPlanner {
            public:
                bool stake(std::int32_t bed);
                bool unstake(std::int32_t bed);
                bool staked(std::int32_t bed) const;
                std::size_t beds() const;
                std::optional<std::int32_t> smallest_bed() const;
                std::optional<std::int32_t> largest_bed() const;
                std::optional<std::int32_t> depth_of(std::int32_t bed) const;
            };
            """,
            """
            class GardenBedPlanner {
            public:
                bool stake(std::int32_t bed);
                bool unstake(std::int32_t bed);
                bool staked(std::int32_t bed) const;
                std::size_t beds() const;
                std::optional<std::int32_t> smallest_bed() const;
                std::optional<std::int32_t> largest_bed() const;
                std::optional<std::int32_t> depth_of(std::int32_t bed) const;
            private:
                struct Node {
                    std::int32_t bed;
                    std::unique_ptr<Node> shade;
                    std::unique_ptr<Node> sun;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> plot_;
                std::size_t beds_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t bed, bool& removed);
            };
            """,
            """
            GardenBedPlanner::Node::Node(std::int32_t value) : bed(value) {}
            bool GardenBedPlanner::staked(std::int32_t bed) const {
                const Node* current = plot_.get();
                while (current) {
                    if (bed == current->bed) return true;
                    current = bed < current->bed ? current->shade.get() : current->sun.get();
                }
                return false;
            }
            std::size_t GardenBedPlanner::beds() const { return beds_; }
            bool GardenBedPlanner::stake(std::int32_t bed) {
                if (!plot_) {
                    plot_ = std::make_unique<Node>(bed);
                    beds_ = 1;
                    return true;
                }
                Node* current = plot_.get();
                for (;;) {
                    if (bed == current->bed) return false;
                    if (bed < current->bed) {
                        if (!current->shade) {
                            current->shade = std::make_unique<Node>(bed);
                            ++beds_;
                            return true;
                        }
                        current = current->shade.get();
                    } else {
                        if (!current->sun) {
                            current->sun = std::make_unique<Node>(bed);
                            ++beds_;
                            return true;
                        }
                        current = current->sun.get();
                    }
                }
            }
            std::unique_ptr<GardenBedPlanner::Node> GardenBedPlanner::detach(std::unique_ptr<Node> node, std::int32_t bed, bool& removed) {
                if (!node) return nullptr;
                if (bed < node->bed) {
                    node->shade = detach(std::move(node->shade), bed, removed);
                    return node;
                }
                if (node->bed < bed) {
                    node->sun = detach(std::move(node->sun), bed, removed);
                    return node;
                }
                removed = true;
                if (!node->shade) return std::move(node->sun);
                if (!node->sun) return std::move(node->shade);
                Node* successor = node->sun.get();
                while (successor->shade) successor = successor->shade.get();
                node->bed = successor->bed;
                bool ignored = false;
                node->sun = detach(std::move(node->sun), successor->bed, ignored);
                return node;
            }
            bool GardenBedPlanner::unstake(std::int32_t bed) {
                bool removed = false;
                plot_ = detach(std::move(plot_), bed, removed);
                if (!removed) return false;
                --beds_;
                return true;
            }
            std::optional<std::int32_t> GardenBedPlanner::smallest_bed() const {
                if (!plot_) return std::nullopt;
                const Node* current = plot_.get();
                while (current->shade) current = current->shade.get();
                return current->bed;
            }
            std::optional<std::int32_t> GardenBedPlanner::largest_bed() const {
                if (!plot_) return std::nullopt;
                const Node* current = plot_.get();
                while (current->sun) current = current->sun.get();
                return current->bed;
            }
            std::optional<std::int32_t> GardenBedPlanner::depth_of(std::int32_t bed) const {
                const Node* current = plot_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bed == current->bed) return depth;
                    ++depth;
                    current = bed < current->bed ? current->shade.get() : current->sun.get();
                }
                return std::nullopt;
            }
            """,
            """
            GardenBedPlanner::Node::Node(std::int32_t value) : bed(value) {}
            bool GardenBedPlanner::staked(std::int32_t bed) const {
                const Node* current = plot_.get();
                while (current) {
                    if (bed == current->bed) return true;
                    current = current->sun.get();
                }
                return false;
            }
            std::size_t GardenBedPlanner::beds() const { return beds_; }
            bool GardenBedPlanner::stake(std::int32_t bed) {
                if (staked(bed)) return false;
                if (!plot_) {
                    plot_ = std::make_unique<Node>(bed);
                    beds_ = 1;
                    return true;
                }
                Node* current = plot_.get();
                while (current->sun) current = current->sun.get();
                current->sun = std::make_unique<Node>(bed);
                ++beds_;
                return true;
            }
            bool GardenBedPlanner::unstake(std::int32_t bed) {
                if (!plot_) return false;
                if (plot_->bed == bed) {
                    plot_ = std::move(plot_->sun);
                    --beds_;
                    return true;
                }
                Node* parent = plot_.get();
                while (parent->sun && parent->sun->bed != bed) parent = parent->sun.get();
                if (!parent->sun) return false;
                parent->sun = std::move(parent->sun->sun);
                --beds_;
                return true;
            }
            std::optional<std::int32_t> GardenBedPlanner::smallest_bed() const {
                if (!plot_) return std::nullopt;
                const Node* current = plot_.get();
                while (current->sun) current = current->sun.get();
                return current->bed;
            }
            std::optional<std::int32_t> GardenBedPlanner::largest_bed() const {
                if (!plot_) return std::nullopt;
                return plot_->bed;
            }
            std::optional<std::int32_t> GardenBedPlanner::depth_of(std::int32_t bed) const {
                const Node* current = plot_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bed == current->bed) return depth;
                    ++depth;
                    current = current->sun.get();
                }
                return std::nullopt;
            }
            """,
            """
            GardenBedPlanner planner;
            planner.stake(34);
            planner.stake(17);
            planner.stake(51);
            planner.stake(9);
            planner.stake(26);
            planner.stake(43);
            planner.stake(60);
            planner.stake(22);
            if (!planner.staked(22) || planner.staked(999)) return 1;
            if (planner.beds() != 8U) return 2;
            if (planner.stake(26)) return 3;
            if (!planner.unstake(17)) return 4;
            if (planner.staked(17)) return 5;
            if (planner.beds() != 7U) return 6;
            return 0;
            """,
            """
            GardenBedPlanner planner;
            if (planner.smallest_bed().has_value()) return 1;
            if (planner.largest_bed().has_value()) return 2;
            planner.stake(34);
            planner.stake(17);
            planner.stake(51);
            planner.stake(9);
            planner.stake(26);
            planner.stake(43);
            planner.stake(60);
            planner.stake(22);
            if (planner.stake(26)) return 3;
            if (planner.smallest_bed() != 9) return 4;
            if (planner.largest_bed() != 60) return 5;
            if (planner.depth_of(22) != 3) return 6;
            if (planner.depth_of(34) != 0) return 7;
            if (planner.depth_of(999).has_value()) return 8;
            if (!planner.unstake(17)) return 9;
            if (planner.depth_of(22) != 1) return 10;
            if (planner.depth_of(26) != 2) return 11;
            if (planner.smallest_bed() != 9) return 12;
            if (planner.unstake(17)) return 13;
            if (planner.beds() != 7U) return 14;
            return 0;
            """,
            "linked beds with endpoint and structural depth queries",
            "an ordered container, a sorted std::vector, or a single-sided sun chain that ignores ordering decisions as the core store",
            "endpoints, exact depths after 34,17,51,9,26,43,60,22, successor-side unstake of 17, and empty/absent nullopt results",
            "endpoint queries beside structural depth",
            "status-returning ordered tree (bool/optional channels)",
        ),
        c(
            "f26bst-terminal-gate-holds",
            "Terminal gate holds",
            "gate_hold",
            """
            class TerminalGateHolds {
            public:
                bool hold(std::int32_t gate);
                bool release(std::int32_t gate);
                bool held(std::int32_t gate) const;
                std::size_t holds() const;
                std::optional<std::int32_t> depth_of(std::int32_t gate) const;
                std::optional<std::int32_t> parent_of(std::int32_t gate) const;
                std::optional<std::int32_t> first_gate() const;
            };
            """,
            """
            class TerminalGateHolds {
            public:
                bool hold(std::int32_t gate);
                bool release(std::int32_t gate);
                bool held(std::int32_t gate) const;
                std::size_t holds() const;
                std::optional<std::int32_t> depth_of(std::int32_t gate) const;
                std::optional<std::int32_t> parent_of(std::int32_t gate) const;
                std::optional<std::int32_t> first_gate() const;
            private:
                struct Node {
                    std::int32_t gate;
                    std::unique_ptr<Node> inner;
                    std::unique_ptr<Node> outer;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> tower_;
                std::size_t held_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t gate, bool& removed);
            };
            """,
            """
            TerminalGateHolds::Node::Node(std::int32_t value) : gate(value) {}
            bool TerminalGateHolds::held(std::int32_t gate) const {
                const Node* current = tower_.get();
                while (current) {
                    if (gate == current->gate) return true;
                    current = gate < current->gate ? current->inner.get() : current->outer.get();
                }
                return false;
            }
            std::size_t TerminalGateHolds::holds() const { return held_; }
            bool TerminalGateHolds::hold(std::int32_t gate) {
                if (!tower_) {
                    tower_ = std::make_unique<Node>(gate);
                    held_ = 1;
                    return true;
                }
                Node* current = tower_.get();
                for (;;) {
                    if (gate == current->gate) return false;
                    if (gate < current->gate) {
                        if (!current->inner) {
                            current->inner = std::make_unique<Node>(gate);
                            ++held_;
                            return true;
                        }
                        current = current->inner.get();
                    } else {
                        if (!current->outer) {
                            current->outer = std::make_unique<Node>(gate);
                            ++held_;
                            return true;
                        }
                        current = current->outer.get();
                    }
                }
            }
            std::unique_ptr<TerminalGateHolds::Node> TerminalGateHolds::detach(std::unique_ptr<Node> node, std::int32_t gate, bool& removed) {
                if (!node) return nullptr;
                if (gate < node->gate) {
                    node->inner = detach(std::move(node->inner), gate, removed);
                    return node;
                }
                if (node->gate < gate) {
                    node->outer = detach(std::move(node->outer), gate, removed);
                    return node;
                }
                removed = true;
                if (!node->inner) return std::move(node->outer);
                if (!node->outer) return std::move(node->inner);
                Node* successor = node->outer.get();
                while (successor->inner) successor = successor->inner.get();
                node->gate = successor->gate;
                bool ignored = false;
                node->outer = detach(std::move(node->outer), successor->gate, ignored);
                return node;
            }
            bool TerminalGateHolds::release(std::int32_t gate) {
                bool removed = false;
                tower_ = detach(std::move(tower_), gate, removed);
                if (!removed) return false;
                --held_;
                return true;
            }
            std::optional<std::int32_t> TerminalGateHolds::depth_of(std::int32_t gate) const {
                const Node* current = tower_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gate == current->gate) return depth;
                    ++depth;
                    current = gate < current->gate ? current->inner.get() : current->outer.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> TerminalGateHolds::parent_of(std::int32_t gate) const {
                const Node* current = tower_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (gate == current->gate) {
                        if (!parent) return std::nullopt;
                        return parent->gate;
                    }
                    parent = current;
                    current = gate < current->gate ? current->inner.get() : current->outer.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> TerminalGateHolds::first_gate() const {
                if (!tower_) return std::nullopt;
                return tower_->gate;
            }
            """,
            """
            TerminalGateHolds::Node::Node(std::int32_t value) : gate(value) {}
            bool TerminalGateHolds::held(std::int32_t gate) const {
                const Node* current = tower_.get();
                while (current) {
                    if (gate == current->gate) return true;
                    current = current->inner.get();
                }
                return false;
            }
            std::size_t TerminalGateHolds::holds() const { return held_; }
            bool TerminalGateHolds::hold(std::int32_t gate) {
                if (held(gate)) return false;
                if (!tower_) {
                    tower_ = std::make_unique<Node>(gate);
                    held_ = 1;
                    return true;
                }
                Node* current = tower_.get();
                while (current->inner) current = current->inner.get();
                current->inner = std::make_unique<Node>(gate);
                ++held_;
                return true;
            }
            bool TerminalGateHolds::release(std::int32_t gate) {
                if (!tower_) return false;
                if (tower_->gate == gate) {
                    tower_ = std::move(tower_->inner);
                    --held_;
                    return true;
                }
                Node* parent = tower_.get();
                while (parent->inner && parent->inner->gate != gate) parent = parent->inner.get();
                if (!parent->inner) return false;
                parent->inner = std::move(parent->inner->inner);
                --held_;
                return true;
            }
            std::optional<std::int32_t> TerminalGateHolds::depth_of(std::int32_t gate) const {
                const Node* current = tower_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gate == current->gate) return depth;
                    ++depth;
                    current = current->inner.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> TerminalGateHolds::parent_of(std::int32_t gate) const {
                const Node* current = tower_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (gate == current->gate) {
                        if (!parent) return std::nullopt;
                        return parent->gate;
                    }
                    parent = current;
                    current = current->inner.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> TerminalGateHolds::first_gate() const {
                if (!tower_) return std::nullopt;
                return tower_->gate;
            }
            """,
            """
            TerminalGateHolds holds_obj;
            holds_obj.hold(305);
            holds_obj.hold(152);
            holds_obj.hold(458);
            holds_obj.hold(76);
            holds_obj.hold(229);
            holds_obj.hold(381);
            holds_obj.hold(534);
            holds_obj.hold(190);
            if (!holds_obj.held(190) || holds_obj.held(999)) return 1;
            if (holds_obj.holds() != 8U) return 2;
            if (holds_obj.hold(229)) return 3;
            if (!holds_obj.release(305)) return 4;
            if (holds_obj.held(305)) return 5;
            if (holds_obj.holds() != 7U) return 6;
            return 0;
            """,
            """
            TerminalGateHolds holds_obj;
            if (holds_obj.first_gate().has_value()) return 1;
            holds_obj.hold(305);
            holds_obj.hold(152);
            holds_obj.hold(458);
            holds_obj.hold(76);
            holds_obj.hold(229);
            holds_obj.hold(381);
            holds_obj.hold(534);
            holds_obj.hold(190);
            if (holds_obj.hold(229)) return 2;
            if (holds_obj.first_gate() != 305) return 3;
            if (holds_obj.depth_of(190) != 3) return 4;
            if (holds_obj.parent_of(190) != 229) return 5;
            if (holds_obj.parent_of(305).has_value()) return 6;
            if (holds_obj.depth_of(999).has_value()) return 7;
            if (!holds_obj.release(305)) return 8;
            if (holds_obj.first_gate() != 381) return 9;
            if (holds_obj.parent_of(152) != 381) return 10;
            if (holds_obj.depth_of(190) != 3) return 11;
            if (holds_obj.depth_of(534) != 2) return 12;
            if (holds_obj.release(305)) return 13;
            if (holds_obj.holds() != 7U) return 14;
            return 0;
            """,
            "linked holds exposing the live root gate as a structural observable",
            "an ordered container, a sorted std::vector, or a single-sided inner chain that ignores ordering decisions as the core store",
            "first_gate, depths, and parents after 305,152,458,76,229,381,534,190, successor-side release of the root 305, and nullopt edges",
            "root identity as observable structure",
            "status-returning ordered tree (bool/optional channels)",
            project_support=True,
        ),
        c(
            "f26bst-workshop-hook-wall",
            "Workshop hook wall",
            "workshop_hook",
            """
            class WorkshopHookWall {
            public:
                bool hang(std::int32_t hook);
                bool unhang(std::int32_t hook);
                bool hanging(std::int32_t hook) const;
                std::size_t hung() const;
                std::optional<std::int32_t> depth_of(std::int32_t hook) const;
                std::optional<std::int32_t> parent_of(std::int32_t hook) const;
            };
            """,
            """
            class WorkshopHookWall {
            public:
                bool hang(std::int32_t hook);
                bool unhang(std::int32_t hook);
                bool hanging(std::int32_t hook) const;
                std::size_t hung() const;
                std::optional<std::int32_t> depth_of(std::int32_t hook) const;
                std::optional<std::int32_t> parent_of(std::int32_t hook) const;
            private:
                struct Node {
                    std::int32_t hook;
                    std::unique_ptr<Node> fewer;
                    std::unique_ptr<Node> more;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> panel_;
                std::size_t hung_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t hook, bool& removed);
            };
            """,
            """
            WorkshopHookWall::Node::Node(std::int32_t value) : hook(value) {}
            bool WorkshopHookWall::hanging(std::int32_t hook) const {
                const Node* current = panel_.get();
                while (current) {
                    if (hook == current->hook) return true;
                    current = hook < current->hook ? current->fewer.get() : current->more.get();
                }
                return false;
            }
            std::size_t WorkshopHookWall::hung() const { return hung_; }
            bool WorkshopHookWall::hang(std::int32_t hook) {
                if (!panel_) {
                    panel_ = std::make_unique<Node>(hook);
                    hung_ = 1;
                    return true;
                }
                Node* current = panel_.get();
                for (;;) {
                    if (hook == current->hook) return false;
                    if (hook < current->hook) {
                        if (!current->fewer) {
                            current->fewer = std::make_unique<Node>(hook);
                            ++hung_;
                            return true;
                        }
                        current = current->fewer.get();
                    } else {
                        if (!current->more) {
                            current->more = std::make_unique<Node>(hook);
                            ++hung_;
                            return true;
                        }
                        current = current->more.get();
                    }
                }
            }
            std::unique_ptr<WorkshopHookWall::Node> WorkshopHookWall::detach(std::unique_ptr<Node> node, std::int32_t hook, bool& removed) {
                if (!node) return nullptr;
                if (hook < node->hook) {
                    node->fewer = detach(std::move(node->fewer), hook, removed);
                    return node;
                }
                if (node->hook < hook) {
                    node->more = detach(std::move(node->more), hook, removed);
                    return node;
                }
                removed = true;
                if (!node->fewer) return std::move(node->more);
                if (!node->more) return std::move(node->fewer);
                Node* successor = node->more.get();
                while (successor->fewer) successor = successor->fewer.get();
                node->hook = successor->hook;
                bool ignored = false;
                node->more = detach(std::move(node->more), successor->hook, ignored);
                return node;
            }
            bool WorkshopHookWall::unhang(std::int32_t hook) {
                bool removed = false;
                panel_ = detach(std::move(panel_), hook, removed);
                if (!removed) return false;
                --hung_;
                return true;
            }
            std::optional<std::int32_t> WorkshopHookWall::depth_of(std::int32_t hook) const {
                const Node* current = panel_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (hook == current->hook) return depth;
                    ++depth;
                    current = hook < current->hook ? current->fewer.get() : current->more.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> WorkshopHookWall::parent_of(std::int32_t hook) const {
                const Node* current = panel_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (hook == current->hook) {
                        if (!parent) return std::nullopt;
                        return parent->hook;
                    }
                    parent = current;
                    current = hook < current->hook ? current->fewer.get() : current->more.get();
                }
                return std::nullopt;
            }
            """,
            """
            WorkshopHookWall::Node::Node(std::int32_t value) : hook(value) {}
            bool WorkshopHookWall::hanging(std::int32_t hook) const {
                const Node* current = panel_.get();
                while (current) {
                    if (hook == current->hook) return true;
                    current = current->more.get();
                }
                return false;
            }
            std::size_t WorkshopHookWall::hung() const { return hung_; }
            bool WorkshopHookWall::hang(std::int32_t hook) {
                if (hanging(hook)) return false;
                if (!panel_) {
                    panel_ = std::make_unique<Node>(hook);
                    hung_ = 1;
                    return true;
                }
                Node* current = panel_.get();
                while (current->more) current = current->more.get();
                current->more = std::make_unique<Node>(hook);
                ++hung_;
                return true;
            }
            bool WorkshopHookWall::unhang(std::int32_t hook) {
                if (!panel_) return false;
                if (panel_->hook == hook) {
                    panel_ = std::move(panel_->more);
                    --hung_;
                    return true;
                }
                Node* parent = panel_.get();
                while (parent->more && parent->more->hook != hook) parent = parent->more.get();
                if (!parent->more) return false;
                parent->more = std::move(parent->more->more);
                --hung_;
                return true;
            }
            std::optional<std::int32_t> WorkshopHookWall::depth_of(std::int32_t hook) const {
                const Node* current = panel_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (hook == current->hook) return depth;
                    ++depth;
                    current = current->more.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> WorkshopHookWall::parent_of(std::int32_t hook) const {
                const Node* current = panel_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (hook == current->hook) {
                        if (!parent) return std::nullopt;
                        return parent->hook;
                    }
                    parent = current;
                    current = current->more.get();
                }
                return std::nullopt;
            }
            """,
            """
            WorkshopHookWall wall;
            wall.hang(64);
            wall.hang(32);
            wall.hang(96);
            wall.hang(16);
            wall.hang(48);
            wall.hang(80);
            wall.hang(112);
            wall.hang(40);
            if (!wall.hanging(40) || wall.hanging(999)) return 1;
            if (wall.hung() != 8U) return 2;
            if (wall.hang(48)) return 3;
            if (!wall.unhang(32)) return 4;
            if (wall.hanging(32)) return 5;
            if (wall.hung() != 7U) return 6;
            return 0;
            """,
            """
            WorkshopHookWall wall;
            if (wall.depth_of(64).has_value()) return 1;
            wall.hang(64);
            wall.hang(32);
            wall.hang(96);
            wall.hang(16);
            wall.hang(48);
            wall.hang(80);
            wall.hang(112);
            wall.hang(40);
            if (wall.hang(48)) return 2;
            if (wall.hung() != 8U) return 3;
            if (wall.depth_of(40) != 3) return 4;
            if (wall.depth_of(64) != 0) return 5;
            if (wall.parent_of(40) != 48) return 6;
            if (wall.parent_of(64).has_value()) return 7;
            if (wall.depth_of(999).has_value()) return 8;
            if (wall.unhang(999)) return 9;
            if (!wall.unhang(32)) return 10;
            if (wall.depth_of(40) != 1) return 11;
            if (wall.parent_of(40) != 64) return 12;
            if (wall.depth_of(48) != 2) return 13;
            if (wall.hung() != 7U) return 14;
            return 0;
            """,
            "linked hooks with optional depth and parent channels",
            "an ordered container, a sorted std::vector, or a single-sided more chain that ignores ordering decisions as the core store",
            "exact depths and parents after 64,32,96,16,48,80,112,40, successor-side unhang of 32, and absent nullopt results",
            "a third status-channel domain with structural reads",
            "status-returning ordered tree (bool/optional channels)",
        ),
        c(
            "f26bst-festival-booth-lanes",
            "Festival booth lanes",
            "booth_lane",
            """
            class FestivalBoothLanes {
            public:
                bool claim(std::int32_t lane);
                bool release(std::int32_t lane);
                bool claimed(std::int32_t lane) const;
                std::size_t lanes() const;
                std::optional<std::int32_t> depth_of(std::int32_t lane) const;
                std::optional<std::int32_t> parent_of(std::int32_t lane) const;
                std::optional<std::int32_t> widest_lane() const;
            };
            """,
            """
            class FestivalBoothLanes {
            public:
                bool claim(std::int32_t lane);
                bool release(std::int32_t lane);
                bool claimed(std::int32_t lane) const;
                std::size_t lanes() const;
                std::optional<std::int32_t> depth_of(std::int32_t lane) const;
                std::optional<std::int32_t> parent_of(std::int32_t lane) const;
                std::optional<std::int32_t> widest_lane() const;
            private:
                struct Node {
                    std::int32_t lane;
                    std::unique_ptr<Node> narrow;
                    std::unique_ptr<Node> wide;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> midway_;
                std::size_t claimed_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t lane, bool& removed);
            };
            """,
            """
            FestivalBoothLanes::Node::Node(std::int32_t value) : lane(value) {}
            bool FestivalBoothLanes::claimed(std::int32_t lane) const {
                const Node* current = midway_.get();
                while (current) {
                    if (lane == current->lane) return true;
                    current = lane < current->lane ? current->narrow.get() : current->wide.get();
                }
                return false;
            }
            std::size_t FestivalBoothLanes::lanes() const { return claimed_; }
            bool FestivalBoothLanes::claim(std::int32_t lane) {
                if (!midway_) {
                    midway_ = std::make_unique<Node>(lane);
                    claimed_ = 1;
                    return true;
                }
                Node* current = midway_.get();
                for (;;) {
                    if (lane == current->lane) return false;
                    if (lane < current->lane) {
                        if (!current->narrow) {
                            current->narrow = std::make_unique<Node>(lane);
                            ++claimed_;
                            return true;
                        }
                        current = current->narrow.get();
                    } else {
                        if (!current->wide) {
                            current->wide = std::make_unique<Node>(lane);
                            ++claimed_;
                            return true;
                        }
                        current = current->wide.get();
                    }
                }
            }
            std::unique_ptr<FestivalBoothLanes::Node> FestivalBoothLanes::detach(std::unique_ptr<Node> node, std::int32_t lane, bool& removed) {
                if (!node) return nullptr;
                if (lane < node->lane) {
                    node->narrow = detach(std::move(node->narrow), lane, removed);
                    return node;
                }
                if (node->lane < lane) {
                    node->wide = detach(std::move(node->wide), lane, removed);
                    return node;
                }
                removed = true;
                if (!node->narrow) return std::move(node->wide);
                if (!node->wide) return std::move(node->narrow);
                Node* successor = node->wide.get();
                while (successor->narrow) successor = successor->narrow.get();
                node->lane = successor->lane;
                bool ignored = false;
                node->wide = detach(std::move(node->wide), successor->lane, ignored);
                return node;
            }
            bool FestivalBoothLanes::release(std::int32_t lane) {
                bool removed = false;
                midway_ = detach(std::move(midway_), lane, removed);
                if (!removed) return false;
                --claimed_;
                return true;
            }
            std::optional<std::int32_t> FestivalBoothLanes::depth_of(std::int32_t lane) const {
                const Node* current = midway_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (lane == current->lane) return depth;
                    ++depth;
                    current = lane < current->lane ? current->narrow.get() : current->wide.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> FestivalBoothLanes::parent_of(std::int32_t lane) const {
                const Node* current = midway_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (lane == current->lane) {
                        if (!parent) return std::nullopt;
                        return parent->lane;
                    }
                    parent = current;
                    current = lane < current->lane ? current->narrow.get() : current->wide.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> FestivalBoothLanes::widest_lane() const {
                if (!midway_) return std::nullopt;
                const Node* current = midway_.get();
                while (current->wide) current = current->wide.get();
                return current->lane;
            }
            """,
            """
            FestivalBoothLanes::Node::Node(std::int32_t value) : lane(value) {}
            bool FestivalBoothLanes::claimed(std::int32_t lane) const {
                const Node* current = midway_.get();
                while (current) {
                    if (lane == current->lane) return true;
                    current = current->narrow.get();
                }
                return false;
            }
            std::size_t FestivalBoothLanes::lanes() const { return claimed_; }
            bool FestivalBoothLanes::claim(std::int32_t lane) {
                if (claimed(lane)) return false;
                if (!midway_) {
                    midway_ = std::make_unique<Node>(lane);
                    claimed_ = 1;
                    return true;
                }
                Node* current = midway_.get();
                while (current->narrow) current = current->narrow.get();
                current->narrow = std::make_unique<Node>(lane);
                ++claimed_;
                return true;
            }
            bool FestivalBoothLanes::release(std::int32_t lane) {
                if (!midway_) return false;
                if (midway_->lane == lane) {
                    midway_ = std::move(midway_->narrow);
                    --claimed_;
                    return true;
                }
                Node* parent = midway_.get();
                while (parent->narrow && parent->narrow->lane != lane) parent = parent->narrow.get();
                if (!parent->narrow) return false;
                parent->narrow = std::move(parent->narrow->narrow);
                --claimed_;
                return true;
            }
            std::optional<std::int32_t> FestivalBoothLanes::depth_of(std::int32_t lane) const {
                const Node* current = midway_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (lane == current->lane) return depth;
                    ++depth;
                    current = current->narrow.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> FestivalBoothLanes::parent_of(std::int32_t lane) const {
                const Node* current = midway_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (lane == current->lane) {
                        if (!parent) return std::nullopt;
                        return parent->lane;
                    }
                    parent = current;
                    current = current->narrow.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> FestivalBoothLanes::widest_lane() const {
                if (!midway_) return std::nullopt;
                return midway_->lane;
            }
            """,
            """
            FestivalBoothLanes lanes_obj;
            lanes_obj.claim(52);
            lanes_obj.claim(26);
            lanes_obj.claim(78);
            lanes_obj.claim(13);
            lanes_obj.claim(39);
            lanes_obj.claim(65);
            lanes_obj.claim(91);
            lanes_obj.claim(33);
            if (!lanes_obj.claimed(33) || lanes_obj.claimed(999)) return 1;
            if (lanes_obj.lanes() != 8U) return 2;
            if (lanes_obj.claim(39)) return 3;
            if (!lanes_obj.release(26)) return 4;
            if (lanes_obj.claimed(26)) return 5;
            if (lanes_obj.lanes() != 7U) return 6;
            return 0;
            """,
            """
            FestivalBoothLanes lanes_obj;
            if (lanes_obj.widest_lane().has_value()) return 1;
            lanes_obj.claim(52);
            lanes_obj.claim(26);
            lanes_obj.claim(78);
            lanes_obj.claim(13);
            lanes_obj.claim(39);
            lanes_obj.claim(65);
            lanes_obj.claim(91);
            lanes_obj.claim(33);
            if (lanes_obj.claim(39)) return 2;
            if (lanes_obj.widest_lane() != 91) return 3;
            if (lanes_obj.depth_of(33) != 3) return 4;
            if (lanes_obj.depth_of(52) != 0) return 5;
            if (lanes_obj.parent_of(33) != 39) return 6;
            if (lanes_obj.parent_of(52).has_value()) return 7;
            if (lanes_obj.depth_of(999).has_value()) return 8;
            if (lanes_obj.release(999)) return 9;
            if (!lanes_obj.release(26)) return 10;
            if (lanes_obj.depth_of(33) != 1) return 11;
            if (lanes_obj.parent_of(33) != 52) return 12;
            if (lanes_obj.depth_of(39) != 2) return 13;
            if (lanes_obj.lanes() != 7U) return 14;
            return 0;
            """,
            "linked lanes with maximum-key and structural queries",
            "an ordered container, a sorted std::vector, or a single-sided narrow chain that ignores ordering decisions as the core store",
            "widest_lane, depths, and parents after 52,26,78,13,39,65,91,33, successor-side release of 26, and empty nullopt results",
            "maximum-key queries beside parents and depths",
            "status-returning ordered tree (bool/optional channels)",
        ),
        c(
            "f26bst-lab-vial-shelves",
            "Lab vial shelves",
            "lab_vial",
            """
            class LabVialShelves {
            public:
                bool shelve(std::int32_t vial);
                bool draw(std::int32_t vial);
                bool shelved(std::int32_t vial) const;
                std::size_t vials() const;
                std::optional<std::int32_t> depth_of(std::int32_t vial) const;
                std::optional<std::int32_t> parent_of(std::int32_t vial) const;
            };
            """,
            """
            class LabVialShelves {
            public:
                bool shelve(std::int32_t vial);
                bool draw(std::int32_t vial);
                bool shelved(std::int32_t vial) const;
                std::size_t vials() const;
                std::optional<std::int32_t> depth_of(std::int32_t vial) const;
                std::optional<std::int32_t> parent_of(std::int32_t vial) const;
            private:
                struct Node {
                    std::int32_t vial;
                    std::unique_ptr<Node> cool;
                    std::unique_ptr<Node> warm;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> bench_;
                std::size_t shelved_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t vial, bool& removed);
            };
            """,
            """
            LabVialShelves::Node::Node(std::int32_t value) : vial(value) {}
            bool LabVialShelves::shelved(std::int32_t vial) const {
                const Node* current = bench_.get();
                while (current) {
                    if (vial == current->vial) return true;
                    current = vial < current->vial ? current->cool.get() : current->warm.get();
                }
                return false;
            }
            std::size_t LabVialShelves::vials() const { return shelved_; }
            bool LabVialShelves::shelve(std::int32_t vial) {
                if (!bench_) {
                    bench_ = std::make_unique<Node>(vial);
                    shelved_ = 1;
                    return true;
                }
                Node* current = bench_.get();
                for (;;) {
                    if (vial == current->vial) return false;
                    if (vial < current->vial) {
                        if (!current->cool) {
                            current->cool = std::make_unique<Node>(vial);
                            ++shelved_;
                            return true;
                        }
                        current = current->cool.get();
                    } else {
                        if (!current->warm) {
                            current->warm = std::make_unique<Node>(vial);
                            ++shelved_;
                            return true;
                        }
                        current = current->warm.get();
                    }
                }
            }
            std::unique_ptr<LabVialShelves::Node> LabVialShelves::detach(std::unique_ptr<Node> node, std::int32_t vial, bool& removed) {
                if (!node) return nullptr;
                if (vial < node->vial) {
                    node->cool = detach(std::move(node->cool), vial, removed);
                    return node;
                }
                if (node->vial < vial) {
                    node->warm = detach(std::move(node->warm), vial, removed);
                    return node;
                }
                removed = true;
                if (!node->cool) return std::move(node->warm);
                if (!node->warm) return std::move(node->cool);
                Node* successor = node->warm.get();
                while (successor->cool) successor = successor->cool.get();
                node->vial = successor->vial;
                bool ignored = false;
                node->warm = detach(std::move(node->warm), successor->vial, ignored);
                return node;
            }
            bool LabVialShelves::draw(std::int32_t vial) {
                bool removed = false;
                bench_ = detach(std::move(bench_), vial, removed);
                if (!removed) return false;
                --shelved_;
                return true;
            }
            std::optional<std::int32_t> LabVialShelves::depth_of(std::int32_t vial) const {
                const Node* current = bench_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (vial == current->vial) return depth;
                    ++depth;
                    current = vial < current->vial ? current->cool.get() : current->warm.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> LabVialShelves::parent_of(std::int32_t vial) const {
                const Node* current = bench_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (vial == current->vial) {
                        if (!parent) return std::nullopt;
                        return parent->vial;
                    }
                    parent = current;
                    current = vial < current->vial ? current->cool.get() : current->warm.get();
                }
                return std::nullopt;
            }
            """,
            """
            LabVialShelves::Node::Node(std::int32_t value) : vial(value) {}
            bool LabVialShelves::shelved(std::int32_t vial) const {
                const Node* current = bench_.get();
                while (current) {
                    if (vial == current->vial) return true;
                    current = current->warm.get();
                }
                return false;
            }
            std::size_t LabVialShelves::vials() const { return shelved_; }
            bool LabVialShelves::shelve(std::int32_t vial) {
                if (shelved(vial)) return false;
                if (!bench_) {
                    bench_ = std::make_unique<Node>(vial);
                    shelved_ = 1;
                    return true;
                }
                Node* current = bench_.get();
                while (current->warm) current = current->warm.get();
                current->warm = std::make_unique<Node>(vial);
                ++shelved_;
                return true;
            }
            bool LabVialShelves::draw(std::int32_t vial) {
                if (!bench_) return false;
                if (bench_->vial == vial) {
                    bench_ = std::move(bench_->warm);
                    --shelved_;
                    return true;
                }
                Node* parent = bench_.get();
                while (parent->warm && parent->warm->vial != vial) parent = parent->warm.get();
                if (!parent->warm) return false;
                parent->warm = std::move(parent->warm->warm);
                --shelved_;
                return true;
            }
            std::optional<std::int32_t> LabVialShelves::depth_of(std::int32_t vial) const {
                const Node* current = bench_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (vial == current->vial) return depth;
                    ++depth;
                    current = current->warm.get();
                }
                return std::nullopt;
            }
            std::optional<std::int32_t> LabVialShelves::parent_of(std::int32_t vial) const {
                const Node* current = bench_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (vial == current->vial) {
                        if (!parent) return std::nullopt;
                        return parent->vial;
                    }
                    parent = current;
                    current = current->warm.get();
                }
                return std::nullopt;
            }
            """,
            """
            LabVialShelves shelves;
            shelves.shelve(420);
            shelves.shelve(210);
            shelves.shelve(630);
            shelves.shelve(105);
            shelves.shelve(315);
            shelves.shelve(525);
            shelves.shelve(735);
            shelves.shelve(262);
            if (!shelves.shelved(262) || shelves.shelved(999)) return 1;
            if (shelves.vials() != 8U) return 2;
            if (shelves.shelve(315)) return 3;
            if (!shelves.draw(210)) return 4;
            if (shelves.shelved(210)) return 5;
            if (shelves.vials() != 7U) return 6;
            return 0;
            """,
            """
            LabVialShelves shelves;
            if (shelves.depth_of(420).has_value()) return 1;
            shelves.shelve(420);
            shelves.shelve(210);
            shelves.shelve(630);
            shelves.shelve(105);
            shelves.shelve(315);
            shelves.shelve(525);
            shelves.shelve(735);
            shelves.shelve(262);
            if (shelves.shelve(315)) return 2;
            if (shelves.vials() != 8U) return 3;
            if (shelves.depth_of(262) != 3) return 4;
            if (shelves.depth_of(420) != 0) return 5;
            if (shelves.parent_of(262) != 315) return 6;
            if (shelves.parent_of(420).has_value()) return 7;
            if (shelves.depth_of(999).has_value()) return 8;
            if (shelves.draw(999)) return 9;
            if (!shelves.draw(210)) return 10;
            if (shelves.depth_of(262) != 1) return 11;
            if (shelves.parent_of(262) != 420) return 12;
            if (shelves.depth_of(315) != 2) return 13;
            if (shelves.vials() != 7U) return 14;
            return 0;
            """,
            "linked vials with optional structural queries",
            "an ordered container, a sorted std::vector, or a single-sided warm chain that ignores ordering decisions as the core store",
            "exact depths and parents after 420,210,630,105,315,525,735,262, successor-side draw of 210, and absent nullopt results",
            "the status-channel octet completed with a lab domain",
            "status-returning ordered tree (bool/optional channels)",
        ),
        c(
            "f26bst-atlas-grid-index",
            "Atlas grid index",
            "atlas_grid",
            """
            class AtlasDuplicateError : public std::logic_error {
            public:
                explicit AtlasDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class AtlasAbsentError : public std::runtime_error {
            public:
                explicit AtlasAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class AtlasGridIndex {
            public:
                void index(std::int32_t cell);
                bool indexed(std::int32_t cell) const;
                std::size_t cells() const;
                std::string preorder_index() const;
                std::string inorder_index() const;
                std::int32_t depth_of(std::int32_t cell) const;
            };
            """,
            """
            class AtlasDuplicateError : public std::logic_error {
            public:
                explicit AtlasDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class AtlasAbsentError : public std::runtime_error {
            public:
                explicit AtlasAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class AtlasGridIndex {
            public:
                void index(std::int32_t cell);
                bool indexed(std::int32_t cell) const;
                std::size_t cells() const;
                std::string preorder_index() const;
                std::string inorder_index() const;
                std::int32_t depth_of(std::int32_t cell) const;
            private:
                struct Node {
                    std::int32_t cell;
                    std::unique_ptr<Node> south;
                    std::unique_ptr<Node> north;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> origin_;
                std::size_t cells_ = 0;
                static void forward_walk(const Node* node, std::vector<std::int32_t>& out);
                static void ordered_walk(const Node* node, std::vector<std::int32_t>& out);
            };
            """,
            """
            AtlasGridIndex::Node::Node(std::int32_t value) : cell(value) {}
            bool AtlasGridIndex::indexed(std::int32_t cell) const {
                const Node* current = origin_.get();
                while (current) {
                    if (cell == current->cell) return true;
                    current = cell < current->cell ? current->south.get() : current->north.get();
                }
                return false;
            }
            std::size_t AtlasGridIndex::cells() const { return cells_; }
            void AtlasGridIndex::index(std::int32_t cell) {
                if (!origin_) {
                    origin_ = std::make_unique<Node>(cell);
                    cells_ = 1;
                    return;
                }
                Node* current = origin_.get();
                for (;;) {
                    if (cell == current->cell) throw AtlasDuplicateError("cell already indexed");
                    if (cell < current->cell) {
                        if (!current->south) {
                            current->south = std::make_unique<Node>(cell);
                            ++cells_;
                            return;
                        }
                        current = current->south.get();
                    } else {
                        if (!current->north) {
                            current->north = std::make_unique<Node>(cell);
                            ++cells_;
                            return;
                        }
                        current = current->north.get();
                    }
                }
            }
            void AtlasGridIndex::forward_walk(const Node* node, std::vector<std::int32_t>& out) {
                if (!node) return;
                out.push_back(node->cell);
                forward_walk(node->south.get(), out);
                forward_walk(node->north.get(), out);
            }
            void AtlasGridIndex::ordered_walk(const Node* node, std::vector<std::int32_t>& out) {
                if (!node) return;
                ordered_walk(node->south.get(), out);
                out.push_back(node->cell);
                ordered_walk(node->north.get(), out);
            }
            std::string AtlasGridIndex::preorder_index() const {
                std::vector<std::int32_t> keys;
                forward_walk(origin_.get(), keys);
                std::string out;
                for (std::size_t i = 0; i < keys.size(); ++i) {
                    if (i) out += ",";
                    out += std::to_string(keys[i]);
                }
                return out;
            }
            std::string AtlasGridIndex::inorder_index() const {
                std::vector<std::int32_t> keys;
                ordered_walk(origin_.get(), keys);
                std::string out;
                for (std::size_t i = 0; i < keys.size(); ++i) {
                    if (i) out += ",";
                    out += std::to_string(keys[i]);
                }
                return out;
            }
            std::int32_t AtlasGridIndex::depth_of(std::int32_t cell) const {
                const Node* current = origin_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (cell == current->cell) return depth;
                    ++depth;
                    current = cell < current->cell ? current->south.get() : current->north.get();
                }
                throw AtlasAbsentError("cell is not indexed");
            }
            """,
            """
            AtlasGridIndex::Node::Node(std::int32_t value) : cell(value) {}
            bool AtlasGridIndex::indexed(std::int32_t cell) const {
                const Node* current = origin_.get();
                while (current) {
                    if (cell == current->cell) return true;
                    current = current->north.get();
                }
                return false;
            }
            std::size_t AtlasGridIndex::cells() const { return cells_; }
            void AtlasGridIndex::index(std::int32_t cell) {
                if (indexed(cell)) throw AtlasDuplicateError("cell already indexed");
                if (!origin_) {
                    origin_ = std::make_unique<Node>(cell);
                    cells_ = 1;
                    return;
                }
                Node* current = origin_.get();
                while (current->north) current = current->north.get();
                current->north = std::make_unique<Node>(cell);
                ++cells_;
            }
            std::string AtlasGridIndex::preorder_index() const {
                std::string out;
                bool first = true;
                const Node* current = origin_.get();
                while (current) {
                    if (!first) out += ",";
                    first = false;
                    out += std::to_string(current->cell);
                    current = current->north.get();
                }
                return out;
            }
            std::string AtlasGridIndex::inorder_index() const {
                std::string out;
                bool first = true;
                const Node* current = origin_.get();
                while (current) {
                    if (!first) out += ",";
                    first = false;
                    out += std::to_string(current->cell);
                    current = current->north.get();
                }
                return out;
            }
            std::int32_t AtlasGridIndex::depth_of(std::int32_t cell) const {
                const Node* current = origin_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (cell == current->cell) return depth;
                    ++depth;
                    current = current->north.get();
                }
                throw AtlasAbsentError("cell is not indexed");
            }
            """,
            """
            AtlasGridIndex atlas;
            atlas.index(42);
            atlas.index(17);
            atlas.index(68);
            atlas.index(9);
            if (!atlas.indexed(9) || !atlas.indexed(68)) return 1;
            if (atlas.indexed(100)) return 2;
            if (atlas.cells() != 4U) return 3;
            atlas.index(25);
            atlas.index(54);
            atlas.index(71);
            if (atlas.cells() != 7U) return 4;
            return 0;
            """,
            """
            AtlasGridIndex atlas;
            bool threw = false;
            try { atlas.depth_of(42); } catch (const AtlasAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (atlas.preorder_index() != "") return 2;
            if (atlas.inorder_index() != "") return 3;
            atlas.index(42);
            atlas.index(17);
            atlas.index(68);
            atlas.index(9);
            atlas.index(25);
            atlas.index(54);
            atlas.index(71);
            threw = false;
            try { atlas.index(25); } catch (const AtlasDuplicateError&) { threw = true; }
            if (!threw) return 4;
            if (atlas.cells() != 7U) return 5;
            if (atlas.preorder_index() != "42,17,9,25,68,54,71") return 6;
            if (atlas.inorder_index() != "9,17,25,42,54,68,71") return 7;
            if (atlas.depth_of(54) != 2) return 8;
            if (atlas.depth_of(42) != 0) return 9;
            if (atlas.depth_of(9) != 2) return 10;
            threw = false;
            try { atlas.depth_of(100); } catch (const AtlasAbsentError&) { threw = true; }
            if (!threw) return 11;
            return 0;
            """,
            "linked cells with exact pre-order rendering that exposes insertion-ordered shape",
            "an ordered container, a sorted std::vector, or a single-sided north chain that ignores ordering decisions as the core store",
            "exact pre-order and in-order strings after 42,17,68,9,25,54,71, depths, and duplicate/absent channels",
            "pre-order output as tree-shape evidence",
            "traversal-rendering ordered tree with exact string output",
        ),
        c(
            "f26bst-mill-gear-train",
            "Mill gear train",
            "mill_gear",
            """
            class GearDuplicateError : public std::runtime_error {
            public:
                explicit GearDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class GearAbsentError : public std::logic_error {
            public:
                explicit GearAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class MillGearTrain {
            public:
                void mesh(std::int32_t gear);
                bool meshed(std::int32_t gear) const;
                std::size_t gears() const;
                std::string level_order() const;
                std::int32_t depth_of(std::int32_t gear) const;
            };
            """,
            """
            class GearDuplicateError : public std::runtime_error {
            public:
                explicit GearDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class GearAbsentError : public std::logic_error {
            public:
                explicit GearAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class MillGearTrain {
            public:
                void mesh(std::int32_t gear);
                bool meshed(std::int32_t gear) const;
                std::size_t gears() const;
                std::string level_order() const;
                std::int32_t depth_of(std::int32_t gear) const;
            private:
                struct Node {
                    std::int32_t gear;
                    std::unique_ptr<Node> slow;
                    std::unique_ptr<Node> fast;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> shaft_;
                std::size_t gears_ = 0;
            };
            """,
            """
            MillGearTrain::Node::Node(std::int32_t value) : gear(value) {}
            bool MillGearTrain::meshed(std::int32_t gear) const {
                const Node* current = shaft_.get();
                while (current) {
                    if (gear == current->gear) return true;
                    current = gear < current->gear ? current->slow.get() : current->fast.get();
                }
                return false;
            }
            std::size_t MillGearTrain::gears() const { return gears_; }
            void MillGearTrain::mesh(std::int32_t gear) {
                if (!shaft_) {
                    shaft_ = std::make_unique<Node>(gear);
                    gears_ = 1;
                    return;
                }
                Node* current = shaft_.get();
                for (;;) {
                    if (gear == current->gear) throw GearDuplicateError("gear already meshed");
                    if (gear < current->gear) {
                        if (!current->slow) {
                            current->slow = std::make_unique<Node>(gear);
                            ++gears_;
                            return;
                        }
                        current = current->slow.get();
                    } else {
                        if (!current->fast) {
                            current->fast = std::make_unique<Node>(gear);
                            ++gears_;
                            return;
                        }
                        current = current->fast.get();
                    }
                }
            }
            std::string MillGearTrain::level_order() const {
                if (!shaft_) return "";
                std::string out;
                std::deque<const Node*> wave;
                wave.push_back(shaft_.get());
                bool first_level = true;
                while (!wave.empty()) {
                    if (!first_level) out += "|";
                    first_level = false;
                    std::size_t width = wave.size();
                    for (std::size_t i = 0; i < width; ++i) {
                        const Node* node = wave.front();
                        wave.pop_front();
                        if (i) out += ",";
                        out += std::to_string(node->gear);
                        if (node->slow) wave.push_back(node->slow.get());
                        if (node->fast) wave.push_back(node->fast.get());
                    }
                }
                return out;
            }
            std::int32_t MillGearTrain::depth_of(std::int32_t gear) const {
                const Node* current = shaft_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gear == current->gear) return depth;
                    ++depth;
                    current = gear < current->gear ? current->slow.get() : current->fast.get();
                }
                throw GearAbsentError("gear is not meshed");
            }
            """,
            """
            MillGearTrain::Node::Node(std::int32_t value) : gear(value) {}
            bool MillGearTrain::meshed(std::int32_t gear) const {
                const Node* current = shaft_.get();
                while (current) {
                    if (gear == current->gear) return true;
                    current = current->fast.get();
                }
                return false;
            }
            std::size_t MillGearTrain::gears() const { return gears_; }
            void MillGearTrain::mesh(std::int32_t gear) {
                if (meshed(gear)) throw GearDuplicateError("gear already meshed");
                if (!shaft_) {
                    shaft_ = std::make_unique<Node>(gear);
                    gears_ = 1;
                    return;
                }
                Node* current = shaft_.get();
                while (current->fast) current = current->fast.get();
                current->fast = std::make_unique<Node>(gear);
                ++gears_;
            }
            std::string MillGearTrain::level_order() const {
                std::string out;
                bool first = true;
                const Node* current = shaft_.get();
                while (current) {
                    if (!first) out += "|";
                    first = false;
                    out += std::to_string(current->gear);
                    current = current->fast.get();
                }
                return out;
            }
            std::int32_t MillGearTrain::depth_of(std::int32_t gear) const {
                const Node* current = shaft_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gear == current->gear) return depth;
                    ++depth;
                    current = current->fast.get();
                }
                throw GearAbsentError("gear is not meshed");
            }
            """,
            """
            MillGearTrain train;
            train.mesh(30);
            train.mesh(15);
            train.mesh(45);
            train.mesh(8);
            train.mesh(22);
            train.mesh(38);
            train.mesh(52);
            train.mesh(18);
            if (!train.meshed(18) || train.meshed(100)) return 1;
            if (train.gears() != 8U) return 2;
            return 0;
            """,
            """
            MillGearTrain train;
            bool threw = false;
            try { train.depth_of(30); } catch (const GearAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (train.level_order() != "") return 2;
            train.mesh(30);
            train.mesh(15);
            train.mesh(45);
            train.mesh(8);
            train.mesh(22);
            train.mesh(38);
            train.mesh(52);
            train.mesh(18);
            threw = false;
            try { train.mesh(22); } catch (const GearDuplicateError&) { threw = true; }
            if (!threw) return 3;
            if (train.gears() != 8U) return 4;
            if (train.level_order() != "30|15,45|8,22,38,52|18") return 5;
            if (train.depth_of(18) != 3) return 6;
            if (train.depth_of(30) != 0) return 7;
            if (train.depth_of(38) != 2) return 8;
            threw = false;
            try { train.depth_of(100); } catch (const GearAbsentError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "queue-driven breadth-first rendering over linked gears",
            "an ordered container, a sorted std::vector, or a single-sided fast chain that ignores ordering decisions as the core store",
            "exact 30|15,45|8,22,38,52|18 level strings after 30,15,45,8,22,38,52,18 plus depths and duplicate/absent channels",
            "breadth-first rendering as shape evidence",
            "traversal-rendering ordered tree with exact string output",
            project_support=True,
        ),
        c(
            "f26bst-bakery-rack-order",
            "Bakery rack order",
            "bakery_rack",
            """
            class RackDuplicateError : public std::invalid_argument {
            public:
                explicit RackDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RackAbsentError : public std::out_of_range {
            public:
                explicit RackAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class BakeryRackOrder {
            public:
                void rack(std::int32_t tray);
                bool racked(std::int32_t tray) const;
                std::size_t trays() const;
                std::string postorder_rack() const;
                std::int32_t depth_of(std::int32_t tray) const;
            };
            """,
            """
            class RackDuplicateError : public std::invalid_argument {
            public:
                explicit RackDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RackAbsentError : public std::out_of_range {
            public:
                explicit RackAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class BakeryRackOrder {
            public:
                void rack(std::int32_t tray);
                bool racked(std::int32_t tray) const;
                std::size_t trays() const;
                std::string postorder_rack() const;
                std::int32_t depth_of(std::int32_t tray) const;
            private:
                struct Node {
                    std::int32_t tray;
                    std::unique_ptr<Node> cool_side;
                    std::unique_ptr<Node> hot_side;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> oven_;
                std::size_t trays_ = 0;
                static void cooling_walk(const Node* node, std::vector<std::int32_t>& out);
            };
            """,
            """
            BakeryRackOrder::Node::Node(std::int32_t value) : tray(value) {}
            bool BakeryRackOrder::racked(std::int32_t tray) const {
                const Node* current = oven_.get();
                while (current) {
                    if (tray == current->tray) return true;
                    current = tray < current->tray ? current->cool_side.get() : current->hot_side.get();
                }
                return false;
            }
            std::size_t BakeryRackOrder::trays() const { return trays_; }
            void BakeryRackOrder::rack(std::int32_t tray) {
                if (!oven_) {
                    oven_ = std::make_unique<Node>(tray);
                    trays_ = 1;
                    return;
                }
                Node* current = oven_.get();
                for (;;) {
                    if (tray == current->tray) throw RackDuplicateError("tray already racked");
                    if (tray < current->tray) {
                        if (!current->cool_side) {
                            current->cool_side = std::make_unique<Node>(tray);
                            ++trays_;
                            return;
                        }
                        current = current->cool_side.get();
                    } else {
                        if (!current->hot_side) {
                            current->hot_side = std::make_unique<Node>(tray);
                            ++trays_;
                            return;
                        }
                        current = current->hot_side.get();
                    }
                }
            }
            void BakeryRackOrder::cooling_walk(const Node* node, std::vector<std::int32_t>& out) {
                if (!node) return;
                cooling_walk(node->cool_side.get(), out);
                cooling_walk(node->hot_side.get(), out);
                out.push_back(node->tray);
            }
            std::string BakeryRackOrder::postorder_rack() const {
                std::vector<std::int32_t> keys;
                cooling_walk(oven_.get(), keys);
                std::string out;
                for (std::size_t i = 0; i < keys.size(); ++i) {
                    if (i) out += ",";
                    out += std::to_string(keys[i]);
                }
                return out;
            }
            std::int32_t BakeryRackOrder::depth_of(std::int32_t tray) const {
                const Node* current = oven_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (tray == current->tray) return depth;
                    ++depth;
                    current = tray < current->tray ? current->cool_side.get() : current->hot_side.get();
                }
                throw RackAbsentError("tray is not racked");
            }
            """,
            """
            BakeryRackOrder::Node::Node(std::int32_t value) : tray(value) {}
            bool BakeryRackOrder::racked(std::int32_t tray) const {
                const Node* current = oven_.get();
                while (current) {
                    if (tray == current->tray) return true;
                    current = current->cool_side.get();
                }
                return false;
            }
            std::size_t BakeryRackOrder::trays() const { return trays_; }
            void BakeryRackOrder::rack(std::int32_t tray) {
                if (racked(tray)) throw RackDuplicateError("tray already racked");
                if (!oven_) {
                    oven_ = std::make_unique<Node>(tray);
                    trays_ = 1;
                    return;
                }
                Node* current = oven_.get();
                while (current->cool_side) current = current->cool_side.get();
                current->cool_side = std::make_unique<Node>(tray);
                ++trays_;
            }
            std::string BakeryRackOrder::postorder_rack() const {
                std::vector<std::int32_t> keys;
                const Node* current = oven_.get();
                while (current) {
                    keys.push_back(current->tray);
                    current = current->cool_side.get();
                }
                std::string out;
                for (std::size_t i = 0; i < keys.size(); ++i) {
                    if (i) out += ",";
                    out += std::to_string(keys[keys.size() - 1 - i]);
                }
                return out;
            }
            std::int32_t BakeryRackOrder::depth_of(std::int32_t tray) const {
                const Node* current = oven_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (tray == current->tray) return depth;
                    ++depth;
                    current = current->cool_side.get();
                }
                throw RackAbsentError("tray is not racked");
            }
            """,
            """
            BakeryRackOrder order;
            order.rack(84);
            order.rack(42);
            order.rack(126);
            order.rack(21);
            order.rack(63);
            order.rack(105);
            order.rack(147);
            order.rack(52);
            if (!order.racked(52) || order.racked(100)) return 1;
            if (order.trays() != 8U) return 2;
            return 0;
            """,
            """
            BakeryRackOrder order;
            bool threw = false;
            try { order.depth_of(84); } catch (const RackAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (order.postorder_rack() != "") return 2;
            order.rack(84);
            order.rack(42);
            order.rack(126);
            order.rack(21);
            order.rack(63);
            order.rack(105);
            order.rack(147);
            order.rack(52);
            threw = false;
            try { order.rack(63); } catch (const RackDuplicateError&) { threw = true; }
            if (!threw) return 3;
            if (order.trays() != 8U) return 4;
            if (order.postorder_rack() != "21,52,63,42,105,147,126,84") return 5;
            if (order.depth_of(52) != 3) return 6;
            if (order.depth_of(84) != 0) return 7;
            if (order.depth_of(105) != 2) return 8;
            threw = false;
            try { order.depth_of(100); } catch (const RackAbsentError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "linked trays with exact post-order rendering",
            "an ordered container, a sorted std::vector, or a single-sided cool-side chain that ignores ordering decisions as the core store",
            "exact post-order strings after 84,42,126,21,63,105,147,52 plus depths and duplicate/absent channels",
            "post-order rendering in the traversal set",
            "traversal-rendering ordered tree with exact string output",
        ),
        c(
            "f26bst-theater-row-seats",
            "Theater row seats",
            "theater_row",
            """
            class SeatDuplicateError : public std::logic_error {
            public:
                explicit SeatDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class SeatAbsentError : public std::domain_error {
            public:
                explicit SeatAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class TheaterRowSeats {
            public:
                void reserve(std::int32_t seat);
                bool reserved(std::int32_t seat) const;
                std::size_t seats() const;
                std::string seating_chart() const;
                std::int32_t depth_of(std::int32_t seat) const;
            };
            """,
            """
            class SeatDuplicateError : public std::logic_error {
            public:
                explicit SeatDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class SeatAbsentError : public std::domain_error {
            public:
                explicit SeatAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class TheaterRowSeats {
            public:
                void reserve(std::int32_t seat);
                bool reserved(std::int32_t seat) const;
                std::size_t seats() const;
                std::string seating_chart() const;
                std::int32_t depth_of(std::int32_t seat) const;
            private:
                struct Node {
                    std::int32_t seat;
                    std::unique_ptr<Node> cheaper;
                    std::unique_ptr<Node> pricier;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> stage_;
                std::size_t seats_ = 0;
                static void chart_walk(const Node* node, std::int32_t depth, std::vector<std::string>& out);
            };
            """,
            """
            TheaterRowSeats::Node::Node(std::int32_t value) : seat(value) {}
            bool TheaterRowSeats::reserved(std::int32_t seat) const {
                const Node* current = stage_.get();
                while (current) {
                    if (seat == current->seat) return true;
                    current = seat < current->seat ? current->cheaper.get() : current->pricier.get();
                }
                return false;
            }
            std::size_t TheaterRowSeats::seats() const { return seats_; }
            void TheaterRowSeats::reserve(std::int32_t seat) {
                if (!stage_) {
                    stage_ = std::make_unique<Node>(seat);
                    seats_ = 1;
                    return;
                }
                Node* current = stage_.get();
                for (;;) {
                    if (seat == current->seat) throw SeatDuplicateError("seat already reserved");
                    if (seat < current->seat) {
                        if (!current->cheaper) {
                            current->cheaper = std::make_unique<Node>(seat);
                            ++seats_;
                            return;
                        }
                        current = current->cheaper.get();
                    } else {
                        if (!current->pricier) {
                            current->pricier = std::make_unique<Node>(seat);
                            ++seats_;
                            return;
                        }
                        current = current->pricier.get();
                    }
                }
            }
            void TheaterRowSeats::chart_walk(const Node* node, std::int32_t depth, std::vector<std::string>& out) {
                if (!node) return;
                chart_walk(node->cheaper.get(), depth + 1, out);
                out.push_back(std::to_string(node->seat) + "(d" + std::to_string(depth) + ")");
                chart_walk(node->pricier.get(), depth + 1, out);
            }
            std::string TheaterRowSeats::seating_chart() const {
                std::vector<std::string> entries;
                chart_walk(stage_.get(), 0, entries);
                std::string out;
                for (std::size_t i = 0; i < entries.size(); ++i) {
                    if (i) out += ",";
                    out += entries[i];
                }
                return out;
            }
            std::int32_t TheaterRowSeats::depth_of(std::int32_t seat) const {
                const Node* current = stage_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (seat == current->seat) return depth;
                    ++depth;
                    current = seat < current->seat ? current->cheaper.get() : current->pricier.get();
                }
                throw SeatAbsentError("seat is not reserved");
            }
            """,
            """
            TheaterRowSeats::Node::Node(std::int32_t value) : seat(value) {}
            bool TheaterRowSeats::reserved(std::int32_t seat) const {
                const Node* current = stage_.get();
                while (current) {
                    if (seat == current->seat) return true;
                    current = current->pricier.get();
                }
                return false;
            }
            std::size_t TheaterRowSeats::seats() const { return seats_; }
            void TheaterRowSeats::reserve(std::int32_t seat) {
                if (reserved(seat)) throw SeatDuplicateError("seat already reserved");
                if (!stage_) {
                    stage_ = std::make_unique<Node>(seat);
                    seats_ = 1;
                    return;
                }
                Node* current = stage_.get();
                while (current->pricier) current = current->pricier.get();
                current->pricier = std::make_unique<Node>(seat);
                ++seats_;
            }
            std::string TheaterRowSeats::seating_chart() const {
                std::string out;
                bool first = true;
                const Node* current = stage_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (!first) out += ",";
                    first = false;
                    out += std::to_string(current->seat) + "(d" + std::to_string(depth) + ")";
                    ++depth;
                    current = current->pricier.get();
                }
                return out;
            }
            std::int32_t TheaterRowSeats::depth_of(std::int32_t seat) const {
                const Node* current = stage_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (seat == current->seat) return depth;
                    ++depth;
                    current = current->pricier.get();
                }
                throw SeatAbsentError("seat is not reserved");
            }
            """,
            """
            TheaterRowSeats seats_obj;
            seats_obj.reserve(55);
            seats_obj.reserve(28);
            seats_obj.reserve(82);
            seats_obj.reserve(14);
            seats_obj.reserve(41);
            seats_obj.reserve(69);
            seats_obj.reserve(96);
            seats_obj.reserve(35);
            if (!seats_obj.reserved(35) || seats_obj.reserved(100)) return 1;
            if (seats_obj.seats() != 8U) return 2;
            return 0;
            """,
            """
            TheaterRowSeats seats_obj;
            bool threw = false;
            try { seats_obj.depth_of(55); } catch (const SeatAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (seats_obj.seating_chart() != "") return 2;
            seats_obj.reserve(55);
            seats_obj.reserve(28);
            seats_obj.reserve(82);
            seats_obj.reserve(14);
            seats_obj.reserve(41);
            seats_obj.reserve(69);
            seats_obj.reserve(96);
            seats_obj.reserve(35);
            threw = false;
            try { seats_obj.reserve(41); } catch (const SeatDuplicateError&) { threw = true; }
            if (!threw) return 3;
            if (seats_obj.seats() != 8U) return 4;
            if (seats_obj.seating_chart() != "14(d2),28(d1),35(d3),41(d2),55(d0),69(d2),82(d1),96(d2)") return 5;
            if (seats_obj.depth_of(35) != 3) return 6;
            if (seats_obj.depth_of(55) != 0) return 7;
            threw = false;
            try { seats_obj.depth_of(100); } catch (const SeatAbsentError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "linked seats with depth-annotated in-order rendering",
            "an ordered container, a sorted std::vector, or a single-sided pricier chain that ignores ordering decisions as the core store",
            "exact annotated chart strings after 55,28,82,14,41,69,96,35 plus duplicate/absent channels",
            "in-order order coupled with per-key depth",
            "traversal-rendering ordered tree with exact string output",
        ),
        c(
            "f26bst-parcel-chute-map",
            "Parcel chute map",
            "parcel_chute",
            """
            class ChuteDuplicateError : public std::out_of_range {
            public:
                explicit ChuteDuplicateError(const std::string& message) : std::out_of_range(message) {}
            };
            class ChuteAbsentError : public std::runtime_error {
            public:
                explicit ChuteAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class ParcelChuteMap {
            public:
                void route(std::int32_t chute);
                bool routed(std::int32_t chute) const;
                std::size_t chutes() const;
                std::string route_map() const;
                std::int32_t depth_of(std::int32_t chute) const;
            };
            """,
            """
            class ChuteDuplicateError : public std::out_of_range {
            public:
                explicit ChuteDuplicateError(const std::string& message) : std::out_of_range(message) {}
            };
            class ChuteAbsentError : public std::runtime_error {
            public:
                explicit ChuteAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class ParcelChuteMap {
            public:
                void route(std::int32_t chute);
                bool routed(std::int32_t chute) const;
                std::size_t chutes() const;
                std::string route_map() const;
                std::int32_t depth_of(std::int32_t chute) const;
            private:
                struct Node {
                    std::int32_t chute;
                    std::unique_ptr<Node> slim_chute;
                    std::unique_ptr<Node> wide_chute;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> hub_;
                std::size_t chutes_ = 0;
                static void map_walk(const Node* node, std::int32_t depth, std::vector<std::string>& out);
            };
            """,
            """
            ParcelChuteMap::Node::Node(std::int32_t value) : chute(value) {}
            bool ParcelChuteMap::routed(std::int32_t chute) const {
                const Node* current = hub_.get();
                while (current) {
                    if (chute == current->chute) return true;
                    current = chute < current->chute ? current->slim_chute.get() : current->wide_chute.get();
                }
                return false;
            }
            std::size_t ParcelChuteMap::chutes() const { return chutes_; }
            void ParcelChuteMap::route(std::int32_t chute) {
                if (!hub_) {
                    hub_ = std::make_unique<Node>(chute);
                    chutes_ = 1;
                    return;
                }
                Node* current = hub_.get();
                for (;;) {
                    if (chute == current->chute) throw ChuteDuplicateError("chute already routed");
                    if (chute < current->chute) {
                        if (!current->slim_chute) {
                            current->slim_chute = std::make_unique<Node>(chute);
                            ++chutes_;
                            return;
                        }
                        current = current->slim_chute.get();
                    } else {
                        if (!current->wide_chute) {
                            current->wide_chute = std::make_unique<Node>(chute);
                            ++chutes_;
                            return;
                        }
                        current = current->wide_chute.get();
                    }
                }
            }
            void ParcelChuteMap::map_walk(const Node* node, std::int32_t depth, std::vector<std::string>& out) {
                if (!node) return;
                out.push_back(std::to_string(node->chute) + ":" + std::to_string(depth));
                map_walk(node->slim_chute.get(), depth + 1, out);
                map_walk(node->wide_chute.get(), depth + 1, out);
            }
            std::string ParcelChuteMap::route_map() const {
                std::vector<std::string> entries;
                map_walk(hub_.get(), 0, entries);
                std::string out;
                for (std::size_t i = 0; i < entries.size(); ++i) {
                    if (i) out += ",";
                    out += entries[i];
                }
                return out;
            }
            std::int32_t ParcelChuteMap::depth_of(std::int32_t chute) const {
                const Node* current = hub_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (chute == current->chute) return depth;
                    ++depth;
                    current = chute < current->chute ? current->slim_chute.get() : current->wide_chute.get();
                }
                throw ChuteAbsentError("chute is not routed");
            }
            """,
            """
            ParcelChuteMap::Node::Node(std::int32_t value) : chute(value) {}
            bool ParcelChuteMap::routed(std::int32_t chute) const {
                const Node* current = hub_.get();
                while (current) {
                    if (chute == current->chute) return true;
                    current = current->slim_chute.get();
                }
                return false;
            }
            std::size_t ParcelChuteMap::chutes() const { return chutes_; }
            void ParcelChuteMap::route(std::int32_t chute) {
                if (routed(chute)) throw ChuteDuplicateError("chute already routed");
                if (!hub_) {
                    hub_ = std::make_unique<Node>(chute);
                    chutes_ = 1;
                    return;
                }
                Node* current = hub_.get();
                while (current->slim_chute) current = current->slim_chute.get();
                current->slim_chute = std::make_unique<Node>(chute);
                ++chutes_;
            }
            std::string ParcelChuteMap::route_map() const {
                std::string out;
                bool first = true;
                const Node* current = hub_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (!first) out += ",";
                    first = false;
                    out += std::to_string(current->chute) + ":" + std::to_string(depth);
                    ++depth;
                    current = current->slim_chute.get();
                }
                return out;
            }
            std::int32_t ParcelChuteMap::depth_of(std::int32_t chute) const {
                const Node* current = hub_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (chute == current->chute) return depth;
                    ++depth;
                    current = current->slim_chute.get();
                }
                throw ChuteAbsentError("chute is not routed");
            }
            """,
            """
            ParcelChuteMap map;
            map.route(66);
            map.route(33);
            map.route(99);
            map.route(17);
            map.route(50);
            map.route(83);
            map.route(116);
            map.route(41);
            if (!map.routed(41) || map.routed(100)) return 1;
            if (map.chutes() != 8U) return 2;
            return 0;
            """,
            """
            ParcelChuteMap map;
            bool threw = false;
            try { map.depth_of(66); } catch (const ChuteAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (map.route_map() != "") return 2;
            map.route(66);
            map.route(33);
            map.route(99);
            map.route(17);
            map.route(50);
            map.route(83);
            map.route(116);
            map.route(41);
            threw = false;
            try { map.route(50); } catch (const ChuteDuplicateError&) { threw = true; }
            if (!threw) return 3;
            if (map.chutes() != 8U) return 4;
            if (map.route_map() != "66:0,33:1,17:2,50:2,41:3,99:1,83:2,116:2") return 5;
            if (map.depth_of(41) != 3) return 6;
            if (map.depth_of(66) != 0) return 7;
            threw = false;
            try { map.depth_of(100); } catch (const ChuteAbsentError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "linked chutes with depth-annotated pre-order rendering",
            "an ordered container, a sorted std::vector, or a single-sided slim-chute chain that ignores ordering decisions as the core store",
            "exact annotated route maps after 66,33,99,17,50,83,116,41 plus duplicate/absent channels",
            "annotated pre-order output",
            "traversal-rendering ordered tree with exact string output",
            project_support=True,
        ),
        c(
            "f26bst-cellar-bin-ledger",
            "Cellar bin ledger",
            "cellar_bin",
            """
            class CellarAbsentError : public std::runtime_error {
            public:
                explicit CellarAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class CellarBinLedger {
            public:
                void bin(std::int32_t crate);
                bool binned(std::int32_t crate) const;
                std::size_t crates() const;
                std::string level_ledger() const;
                std::int32_t depth_of(std::int32_t crate) const;
            };
            """,
            """
            class CellarAbsentError : public std::runtime_error {
            public:
                explicit CellarAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class CellarBinLedger {
            public:
                void bin(std::int32_t crate);
                bool binned(std::int32_t crate) const;
                std::size_t crates() const;
                std::string level_ledger() const;
                std::int32_t depth_of(std::int32_t crate) const;
            private:
                struct Node {
                    std::int32_t crate;
                    std::unique_ptr<Node> damp;
                    std::unique_ptr<Node> dry;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> cellar_;
                std::size_t crates_ = 0;
            };
            """,
            """
            CellarBinLedger::Node::Node(std::int32_t value) : crate(value) {}
            bool CellarBinLedger::binned(std::int32_t crate) const {
                const Node* current = cellar_.get();
                while (current) {
                    if (crate == current->crate) return true;
                    current = crate < current->crate ? current->damp.get() : current->dry.get();
                }
                return false;
            }
            std::size_t CellarBinLedger::crates() const { return crates_; }
            void CellarBinLedger::bin(std::int32_t crate) {
                if (!cellar_) {
                    cellar_ = std::make_unique<Node>(crate);
                    crates_ = 1;
                    return;
                }
                Node* current = cellar_.get();
                for (;;) {
                    if (crate < current->crate) {
                        if (!current->damp) {
                            current->damp = std::make_unique<Node>(crate);
                            ++crates_;
                            return;
                        }
                        current = current->damp.get();
                    } else {
                        if (!current->dry) {
                            current->dry = std::make_unique<Node>(crate);
                            ++crates_;
                            return;
                        }
                        current = current->dry.get();
                    }
                }
            }
            std::string CellarBinLedger::level_ledger() const {
                if (!cellar_) return "";
                std::string out;
                std::deque<const Node*> wave;
                wave.push_back(cellar_.get());
                bool first_level = true;
                while (!wave.empty()) {
                    if (!first_level) out += "|";
                    first_level = false;
                    std::size_t width = wave.size();
                    for (std::size_t i = 0; i < width; ++i) {
                        const Node* node = wave.front();
                        wave.pop_front();
                        if (i) out += ",";
                        out += std::to_string(node->crate);
                        if (node->damp) wave.push_back(node->damp.get());
                        if (node->dry) wave.push_back(node->dry.get());
                    }
                }
                return out;
            }
            std::int32_t CellarBinLedger::depth_of(std::int32_t crate) const {
                const Node* current = cellar_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (crate == current->crate) return depth;
                    ++depth;
                    current = crate < current->crate ? current->damp.get() : current->dry.get();
                }
                throw CellarAbsentError("crate is not binned");
            }
            """,
            """
            CellarBinLedger::Node::Node(std::int32_t value) : crate(value) {}
            bool CellarBinLedger::binned(std::int32_t crate) const {
                const Node* current = cellar_.get();
                while (current) {
                    if (crate == current->crate) return true;
                    current = current->dry.get();
                }
                return false;
            }
            std::size_t CellarBinLedger::crates() const { return crates_; }
            void CellarBinLedger::bin(std::int32_t crate) {
                if (!cellar_) {
                    cellar_ = std::make_unique<Node>(crate);
                    crates_ = 1;
                    return;
                }
                Node* current = cellar_.get();
                while (current->dry) current = current->dry.get();
                current->dry = std::make_unique<Node>(crate);
                ++crates_;
            }
            std::string CellarBinLedger::level_ledger() const {
                std::string out;
                bool first = true;
                const Node* current = cellar_.get();
                while (current) {
                    if (!first) out += "|";
                    first = false;
                    out += std::to_string(current->crate);
                    current = current->dry.get();
                }
                return out;
            }
            std::int32_t CellarBinLedger::depth_of(std::int32_t crate) const {
                const Node* current = cellar_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (crate == current->crate) return depth;
                    ++depth;
                    current = current->dry.get();
                }
                throw CellarAbsentError("crate is not binned");
            }
            """,
            """
            CellarBinLedger ledger;
            ledger.bin(30);
            ledger.bin(15);
            ledger.bin(45);
            ledger.bin(8);
            ledger.bin(22);
            ledger.bin(38);
            ledger.bin(52);
            ledger.bin(22);
            if (!ledger.binned(22) || ledger.binned(100)) return 1;
            if (ledger.crates() != 8U) return 2;
            return 0;
            """,
            """
            CellarBinLedger ledger;
            bool threw = false;
            try { ledger.depth_of(30); } catch (const CellarAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (ledger.level_ledger() != "") return 2;
            ledger.bin(30);
            ledger.bin(15);
            ledger.bin(45);
            ledger.bin(8);
            ledger.bin(22);
            ledger.bin(38);
            ledger.bin(52);
            ledger.bin(22);
            if (ledger.crates() != 8U) return 3;
            if (ledger.level_ledger() != "30|15,45|8,22,38,52|22") return 4;
            if (ledger.depth_of(22) != 2) return 5;
            if (ledger.depth_of(8) != 2) return 6;
            if (ledger.depth_of(30) != 0) return 7;
            threw = false;
            try { ledger.depth_of(100); } catch (const CellarAbsentError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "duplicates-descend-right placement over linked bins, observable in level order",
            "an ordered container, a sorted std::vector, or a single-sided dry chain that ignores ordering decisions as the core store",
            "exact level strings after 30,15,45,8,22,38,52,22, the duplicate node at depth three, and total node count eight",
            "an explicit duplicates-descend-right policy distinct from any benchmark contract",
            "traversal-rendering ordered tree with exact string output",
        ),
        c(
            "f26bst-print-plate-registry",
            "Print plate registry",
            "print_plate",
            """
            class PlateDuplicateError : public std::logic_error {
            public:
                explicit PlateDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class PlateAbsentError : public std::invalid_argument {
            public:
                explicit PlateAbsentError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PrintPlateRegistry {
            public:
                void register_plate(const std::string& plate);
                bool registered(const std::string& plate) const;
                std::size_t plates() const;
                std::string shape_signature() const;
                std::int32_t depth_of(const std::string& plate) const;
            };
            """,
            """
            class PlateDuplicateError : public std::logic_error {
            public:
                explicit PlateDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class PlateAbsentError : public std::invalid_argument {
            public:
                explicit PlateAbsentError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PrintPlateRegistry {
            public:
                void register_plate(const std::string& plate);
                bool registered(const std::string& plate) const;
                std::size_t plates() const;
                std::string shape_signature() const;
                std::int32_t depth_of(const std::string& plate) const;
            private:
                struct Node {
                    std::string plate;
                    std::unique_ptr<Node> early;
                    std::unique_ptr<Node> late;
                    explicit Node(std::string value);
                };
                std::unique_ptr<Node> press_;
                std::size_t plates_ = 0;
                static std::string encode(const Node* node);
            };
            """,
            """
            PrintPlateRegistry::Node::Node(std::string value) : plate(std::move(value)) {}
            bool PrintPlateRegistry::registered(const std::string& plate) const {
                const Node* current = press_.get();
                while (current) {
                    if (plate == current->plate) return true;
                    current = plate < current->plate ? current->early.get() : current->late.get();
                }
                return false;
            }
            std::size_t PrintPlateRegistry::plates() const { return plates_; }
            void PrintPlateRegistry::register_plate(const std::string& plate) {
                if (!press_) {
                    press_ = std::make_unique<Node>(plate);
                    plates_ = 1;
                    return;
                }
                Node* current = press_.get();
                for (;;) {
                    if (plate == current->plate) throw PlateDuplicateError("plate already registered");
                    if (plate < current->plate) {
                        if (!current->early) {
                            current->early = std::make_unique<Node>(plate);
                            ++plates_;
                            return;
                        }
                        current = current->early.get();
                    } else {
                        if (!current->late) {
                            current->late = std::make_unique<Node>(plate);
                            ++plates_;
                            return;
                        }
                        current = current->late.get();
                    }
                }
            }
            std::string PrintPlateRegistry::encode(const Node* node) {
                if (!node) return "";
                return "(" + encode(node->early.get()) + encode(node->late.get()) + ")";
            }
            std::string PrintPlateRegistry::shape_signature() const {
                return encode(press_.get());
            }
            std::int32_t PrintPlateRegistry::depth_of(const std::string& plate) const {
                const Node* current = press_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (plate == current->plate) return depth;
                    ++depth;
                    current = plate < current->plate ? current->early.get() : current->late.get();
                }
                throw PlateAbsentError("plate is not registered");
            }
            """,
            """
            PrintPlateRegistry::Node::Node(std::string value) : plate(std::move(value)) {}
            bool PrintPlateRegistry::registered(const std::string& plate) const {
                const Node* current = press_.get();
                while (current) {
                    if (plate == current->plate) return true;
                    current = current->early.get();
                }
                return false;
            }
            std::size_t PrintPlateRegistry::plates() const { return plates_; }
            void PrintPlateRegistry::register_plate(const std::string& plate) {
                if (registered(plate)) throw PlateDuplicateError("plate already registered");
                if (!press_) {
                    press_ = std::make_unique<Node>(plate);
                    plates_ = 1;
                    return;
                }
                Node* current = press_.get();
                while (current->early) current = current->early.get();
                current->early = std::make_unique<Node>(plate);
                ++plates_;
            }
            std::string PrintPlateRegistry::shape_signature() const {
                std::string out;
                std::size_t depth = 0;
                const Node* current = press_.get();
                while (current) {
                    out += "(";
                    ++depth;
                    current = current->early.get();
                }
                for (std::size_t i = 0; i < depth; ++i) out += ")";
                return out;
            }
            std::int32_t PrintPlateRegistry::depth_of(const std::string& plate) const {
                const Node* current = press_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (plate == current->plate) return depth;
                    ++depth;
                    current = current->early.get();
                }
                throw PlateAbsentError("plate is not registered");
            }
            """,
            """
            PrintPlateRegistry registry;
            registry.register_plate("P-42");
            registry.register_plate("P-17");
            registry.register_plate("P-68");
            registry.register_plate("P-09");
            registry.register_plate("P-25");
            registry.register_plate("P-54");
            registry.register_plate("P-71");
            registry.register_plate("P-33");
            if (!registry.registered("P-33") || registry.registered("P-99")) return 1;
            if (registry.plates() != 8U) return 2;
            return 0;
            """,
            """
            PrintPlateRegistry registry;
            bool threw = false;
            try { registry.depth_of("P-42"); } catch (const PlateAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (registry.shape_signature() != "") return 2;
            registry.register_plate("P-42");
            registry.register_plate("P-17");
            registry.register_plate("P-68");
            registry.register_plate("P-09");
            registry.register_plate("P-25");
            registry.register_plate("P-54");
            registry.register_plate("P-71");
            registry.register_plate("P-33");
            threw = false;
            try { registry.register_plate("P-25"); } catch (const PlateDuplicateError&) { threw = true; }
            if (!threw) return 3;
            if (registry.plates() != 8U) return 4;
            if (registry.shape_signature() != "((()(()))(()()))") return 5;
            if (registry.depth_of("P-33") != 3) return 6;
            if (registry.depth_of("P-42") != 0) return 7;
            threw = false;
            try { registry.depth_of("P-99"); } catch (const PlateAbsentError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "string-keyed linked plates with a recursive parenthesized shape signature",
            "an ordered container, a sorted std::vector, or a single-sided early chain that ignores ordering decisions as the core store",
            "exact nested signatures after P-42,P-17,P-68,P-09,P-25,P-54,P-71,P-33 plus depths and duplicate/absent channels",
            "recursive shape encoding as a structural observable",
            "traversal-rendering ordered tree with exact string output",
        ),
        c(
            "f26bst-aviary-perch-plan",
            "Aviary perch plan",
            "aviary_perch",
            """
            class PerchAbsentError : public std::domain_error {
            public:
                explicit PerchAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class AviaryPerchPlan {
            public:
                void perch(std::int32_t perch_no);
                bool perched(std::int32_t perch_no) const;
                std::size_t perches() const;
                std::string zigzag_plan() const;
                std::int32_t depth_of(std::int32_t perch_no) const;
            };
            """,
            """
            class PerchAbsentError : public std::domain_error {
            public:
                explicit PerchAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class AviaryPerchPlan {
            public:
                void perch(std::int32_t perch_no);
                bool perched(std::int32_t perch_no) const;
                std::size_t perches() const;
                std::string zigzag_plan() const;
                std::int32_t depth_of(std::int32_t perch_no) const;
            private:
                struct Node {
                    std::int32_t perch_no;
                    std::unique_ptr<Node> shady;
                    std::unique_ptr<Node> sunny;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> aviary_;
                std::size_t perches_ = 0;
            };
            """,
            """
            AviaryPerchPlan::Node::Node(std::int32_t value) : perch_no(value) {}
            bool AviaryPerchPlan::perched(std::int32_t perch_no) const {
                const Node* current = aviary_.get();
                while (current) {
                    if (perch_no == current->perch_no) return true;
                    current = perch_no < current->perch_no ? current->shady.get() : current->sunny.get();
                }
                return false;
            }
            std::size_t AviaryPerchPlan::perches() const { return perches_; }
            void AviaryPerchPlan::perch(std::int32_t perch_no) {
                if (!aviary_) {
                    aviary_ = std::make_unique<Node>(perch_no);
                    perches_ = 1;
                    return;
                }
                Node* current = aviary_.get();
                for (;;) {
                    if (perch_no < current->perch_no) {
                        if (!current->shady) {
                            current->shady = std::make_unique<Node>(perch_no);
                            ++perches_;
                            return;
                        }
                        current = current->shady.get();
                    } else {
                        if (!current->sunny) {
                            current->sunny = std::make_unique<Node>(perch_no);
                            ++perches_;
                            return;
                        }
                        current = current->sunny.get();
                    }
                }
            }
            std::string AviaryPerchPlan::zigzag_plan() const {
                if (!aviary_) return "";
                std::string out;
                std::deque<const Node*> wave;
                wave.push_back(aviary_.get());
                bool left_to_right = true;
                bool first_level = true;
                while (!wave.empty()) {
                    if (!first_level) out += "|";
                    first_level = false;
                    std::size_t width = wave.size();
                    std::vector<std::int32_t> level_keys;
                    std::vector<const Node*> next;
                    for (std::size_t i = 0; i < width; ++i) {
                        const Node* node = wave.front();
                        wave.pop_front();
                        level_keys.push_back(node->perch_no);
                        if (node->shady) next.push_back(node->shady.get());
                        if (node->sunny) next.push_back(node->sunny.get());
                    }
                    if (!left_to_right) std::reverse(level_keys.begin(), level_keys.end());
                    for (std::size_t i = 0; i < level_keys.size(); ++i) {
                        if (i) out += ",";
                        out += std::to_string(level_keys[i]);
                    }
                    left_to_right = !left_to_right;
                    for (const Node* node : next) wave.push_back(node);
                }
                return out;
            }
            std::int32_t AviaryPerchPlan::depth_of(std::int32_t perch_no) const {
                const Node* current = aviary_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (perch_no == current->perch_no) return depth;
                    ++depth;
                    current = perch_no < current->perch_no ? current->shady.get() : current->sunny.get();
                }
                throw PerchAbsentError("perch is not planned");
            }
            """,
            """
            AviaryPerchPlan::Node::Node(std::int32_t value) : perch_no(value) {}
            bool AviaryPerchPlan::perched(std::int32_t perch_no) const {
                const Node* current = aviary_.get();
                while (current) {
                    if (perch_no == current->perch_no) return true;
                    current = current->shady.get();
                }
                return false;
            }
            std::size_t AviaryPerchPlan::perches() const { return perches_; }
            void AviaryPerchPlan::perch(std::int32_t perch_no) {
                if (!aviary_) {
                    aviary_ = std::make_unique<Node>(perch_no);
                    perches_ = 1;
                    return;
                }
                Node* current = aviary_.get();
                while (current->shady) current = current->shady.get();
                current->shady = std::make_unique<Node>(perch_no);
                ++perches_;
            }
            std::string AviaryPerchPlan::zigzag_plan() const {
                std::string out;
                bool first = true;
                const Node* current = aviary_.get();
                while (current) {
                    if (!first) out += "|";
                    first = false;
                    out += std::to_string(current->perch_no);
                    current = current->shady.get();
                }
                return out;
            }
            std::int32_t AviaryPerchPlan::depth_of(std::int32_t perch_no) const {
                const Node* current = aviary_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (perch_no == current->perch_no) return depth;
                    ++depth;
                    current = current->shady.get();
                }
                throw PerchAbsentError("perch is not planned");
            }
            """,
            """
            AviaryPerchPlan plan;
            plan.perch(42);
            plan.perch(17);
            plan.perch(68);
            plan.perch(9);
            plan.perch(25);
            plan.perch(54);
            plan.perch(71);
            plan.perch(25);
            if (!plan.perched(25) || plan.perched(100)) return 1;
            if (plan.perches() != 8U) return 2;
            return 0;
            """,
            """
            AviaryPerchPlan plan;
            bool threw = false;
            try { plan.depth_of(42); } catch (const PerchAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (plan.zigzag_plan() != "") return 2;
            plan.perch(42);
            plan.perch(17);
            plan.perch(68);
            plan.perch(9);
            plan.perch(25);
            plan.perch(54);
            plan.perch(71);
            plan.perch(25);
            if (plan.perches() != 8U) return 3;
            if (plan.zigzag_plan() != "42|68,17|9,25,54,71|25") return 4;
            if (plan.depth_of(25) != 2) return 5;
            if (plan.depth_of(9) != 2) return 6;
            if (plan.depth_of(42) != 0) return 7;
            threw = false;
            try { plan.depth_of(100); } catch (const PerchAbsentError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "zigzag breadth-first rendering over linked perches with duplicates placed right",
            "an ordered container, a sorted std::vector, or a single-sided shady chain that ignores ordering decisions as the core store",
            "exact zigzag strings after 42,17,68,9,25,54,71,25, the duplicate at depth three, and total count eight",
            "alternating-direction level rendering with duplicates",
            "traversal-rendering ordered tree with exact string output",
        ),
        c(
            "f26bst-ballot-tally-board",
            "Ballot tally board",
            "ballot_tally",
            """
            class BallotTallyBoard {
            public:
                void cast(std::int32_t candidate);
                bool retract(std::int32_t candidate);
                std::int32_t votes_for(std::int32_t candidate) const;
                std::size_t candidates() const;
                std::size_t ballots() const;
                std::int32_t depth_of(std::int32_t candidate) const;
            };
            """,
            """
            class BallotTallyBoard {
            public:
                void cast(std::int32_t candidate);
                bool retract(std::int32_t candidate);
                std::int32_t votes_for(std::int32_t candidate) const;
                std::size_t candidates() const;
                std::size_t ballots() const;
                std::int32_t depth_of(std::int32_t candidate) const;
            private:
                struct Node {
                    std::int32_t candidate;
                    std::int32_t votes;
                    std::unique_ptr<Node> minor;
                    std::unique_ptr<Node> major;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> board_;
                std::size_t candidates_ = 0;
                std::size_t ballots_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t candidate);
            };
            """,
            """
            BallotTallyBoard::Node::Node(std::int32_t value) : candidate(value), votes(1) {}
            void BallotTallyBoard::cast(std::int32_t candidate) {
                ++ballots_;
                if (!board_) {
                    board_ = std::make_unique<Node>(candidate);
                    candidates_ = 1;
                    return;
                }
                Node* current = board_.get();
                for (;;) {
                    if (candidate == current->candidate) {
                        ++current->votes;
                        return;
                    }
                    if (candidate < current->candidate) {
                        if (!current->minor) {
                            current->minor = std::make_unique<Node>(candidate);
                            ++candidates_;
                            return;
                        }
                        current = current->minor.get();
                    } else {
                        if (!current->major) {
                            current->major = std::make_unique<Node>(candidate);
                            ++candidates_;
                            return;
                        }
                        current = current->major.get();
                    }
                }
            }
            std::unique_ptr<BallotTallyBoard::Node> BallotTallyBoard::detach(std::unique_ptr<Node> node, std::int32_t candidate) {
                if (!node) return nullptr;
                if (candidate < node->candidate) {
                    node->minor = detach(std::move(node->minor), candidate);
                    return node;
                }
                if (node->candidate < candidate) {
                    node->major = detach(std::move(node->major), candidate);
                    return node;
                }
                if (!node->minor) return std::move(node->major);
                if (!node->major) return std::move(node->minor);
                Node* successor = node->major.get();
                while (successor->minor) successor = successor->minor.get();
                node->candidate = successor->candidate;
                node->votes = successor->votes;
                node->major = detach(std::move(node->major), successor->candidate);
                return node;
            }
            bool BallotTallyBoard::retract(std::int32_t candidate) {
                Node* current = board_.get();
                while (current) {
                    if (candidate == current->candidate) break;
                    current = candidate < current->candidate ? current->minor.get() : current->major.get();
                }
                if (!current) return false;
                --ballots_;
                if (current->votes > 1) {
                    --current->votes;
                    return true;
                }
                board_ = detach(std::move(board_), candidate);
                --candidates_;
                return true;
            }
            std::int32_t BallotTallyBoard::votes_for(std::int32_t candidate) const {
                const Node* current = board_.get();
                while (current) {
                    if (candidate == current->candidate) return current->votes;
                    current = candidate < current->candidate ? current->minor.get() : current->major.get();
                }
                return 0;
            }
            std::size_t BallotTallyBoard::candidates() const { return candidates_; }
            std::size_t BallotTallyBoard::ballots() const { return ballots_; }
            std::int32_t BallotTallyBoard::depth_of(std::int32_t candidate) const {
                const Node* current = board_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (candidate == current->candidate) return depth;
                    ++depth;
                    current = candidate < current->candidate ? current->minor.get() : current->major.get();
                }
                return -1;
            }
            """,
            """
            BallotTallyBoard::Node::Node(std::int32_t value) : candidate(value), votes(1) {}
            void BallotTallyBoard::cast(std::int32_t candidate) {
                ++ballots_;
                if (!board_) {
                    board_ = std::make_unique<Node>(candidate);
                    candidates_ = 1;
                    return;
                }
                Node* current = board_.get();
                for (;;) {
                    if (candidate == current->candidate) {
                        ++current->votes;
                        return;
                    }
                    if (!current->major) {
                        current->major = std::make_unique<Node>(candidate);
                        ++candidates_;
                        return;
                    }
                    current = current->major.get();
                }
            }
            bool BallotTallyBoard::retract(std::int32_t candidate) {
                if (!board_) return false;
                if (board_->candidate == candidate) {
                    --ballots_;
                    if (board_->votes > 1) {
                        --board_->votes;
                        return true;
                    }
                    board_ = std::move(board_->major);
                    --candidates_;
                    return true;
                }
                Node* parent = board_.get();
                while (parent->major && parent->major->candidate != candidate) parent = parent->major.get();
                if (!parent->major) return false;
                --ballots_;
                if (parent->major->votes > 1) {
                    --parent->major->votes;
                    return true;
                }
                parent->major = std::move(parent->major->major);
                --candidates_;
                return true;
            }
            std::int32_t BallotTallyBoard::votes_for(std::int32_t candidate) const {
                const Node* current = board_.get();
                while (current) {
                    if (candidate == current->candidate) return current->votes;
                    current = current->major.get();
                }
                return 0;
            }
            std::size_t BallotTallyBoard::candidates() const { return candidates_; }
            std::size_t BallotTallyBoard::ballots() const { return ballots_; }
            std::int32_t BallotTallyBoard::depth_of(std::int32_t candidate) const {
                const Node* current = board_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (candidate == current->candidate) return depth;
                    ++depth;
                    current = current->major.get();
                }
                return -1;
            }
            """,
            """
            BallotTallyBoard board;
            board.cast(12);
            board.cast(6);
            board.cast(6);
            if (board.votes_for(6) != 2) return 1;
            if (board.candidates() != 2U) return 2;
            if (board.ballots() != 3U) return 3;
            if (!board.retract(6)) return 4;
            if (board.votes_for(6) != 1) return 5;
            if (board.ballots() != 2U) return 6;
            return 0;
            """,
            """
            BallotTallyBoard board;
            board.cast(12);
            board.cast(6);
            board.cast(18);
            board.cast(3);
            board.cast(9);
            board.cast(15);
            board.cast(21);
            board.cast(6);
            board.cast(12);
            board.cast(6);
            if (board.votes_for(6) != 3) return 1;
            if (board.votes_for(12) != 2) return 2;
            if (board.votes_for(21) != 1) return 3;
            if (board.candidates() != 7U) return 4;
            if (board.ballots() != 10U) return 5;
            if (board.depth_of(6) != 1) return 6;
            if (board.depth_of(9) != 2) return 7;
            if (board.depth_of(12) != 0) return 8;
            if (board.depth_of(99) != -1) return 9;
            if (board.votes_for(99) != 0) return 10;
            if (board.retract(99)) return 11;
            if (!board.retract(6)) return 12;
            if (!board.retract(6)) return 13;
            if (board.candidates() != 7U) return 14;
            if (!board.retract(6)) return 15;
            if (board.candidates() != 6U) return 16;
            if (board.votes_for(6) != 0) return 17;
            if (board.depth_of(6) != -1) return 18;
            if (board.ballots() != 7U) return 19;
            if (board.retract(6)) return 20;
            return 0;
            """,
            "per-node multiplicity counters over insertion-ordered linked candidates",
            "an ordered container, a sorted std::vector, or a single-sided major chain that ignores ordering decisions as the core store",
            "tallies, distinct and total counts, and exact depths after 12,6,18,3,9,15,21,6,12,6, retraction to detachment, and absent results",
            "counted duplicates as an explicit policy",
            "counted-duplicate (multiplicity) ordered tree",
        ),
        c(
            "f26bst-pantry-jar-counts",
            "Pantry jar counts",
            "pantry_jar",
            """
            class PantryJarCounts {
            public:
                void stock(std::int32_t jar);
                bool use_one(std::int32_t jar);
                std::int32_t jars_of(std::int32_t jar) const;
                std::size_t kinds() const;
                std::size_t total_jars() const;
                std::int32_t depth_of(std::int32_t jar) const;
            };
            """,
            """
            class PantryJarCounts {
            public:
                void stock(std::int32_t jar);
                bool use_one(std::int32_t jar);
                std::int32_t jars_of(std::int32_t jar) const;
                std::size_t kinds() const;
                std::size_t total_jars() const;
                std::int32_t depth_of(std::int32_t jar) const;
            private:
                struct Node {
                    std::int32_t jar;
                    std::int32_t bundles;
                    std::unique_ptr<Node> few;
                    std::unique_ptr<Node> many;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> pantry_;
                std::size_t kinds_ = 0;
                std::size_t total_jars_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t jar);
            };
            """,
            """
            PantryJarCounts::Node::Node(std::int32_t value) : jar(value), bundles(1) {}
            void PantryJarCounts::stock(std::int32_t jar) {
                ++total_jars_;
                if (!pantry_) {
                    pantry_ = std::make_unique<Node>(jar);
                    kinds_ = 1;
                    return;
                }
                Node* current = pantry_.get();
                for (;;) {
                    if (jar == current->jar) {
                        ++current->bundles;
                        return;
                    }
                    if (jar < current->jar) {
                        if (!current->few) {
                            current->few = std::make_unique<Node>(jar);
                            ++kinds_;
                            return;
                        }
                        current = current->few.get();
                    } else {
                        if (!current->many) {
                            current->many = std::make_unique<Node>(jar);
                            ++kinds_;
                            return;
                        }
                        current = current->many.get();
                    }
                }
            }
            std::unique_ptr<PantryJarCounts::Node> PantryJarCounts::detach(std::unique_ptr<Node> node, std::int32_t jar) {
                if (!node) return nullptr;
                if (jar < node->jar) {
                    node->few = detach(std::move(node->few), jar);
                    return node;
                }
                if (node->jar < jar) {
                    node->many = detach(std::move(node->many), jar);
                    return node;
                }
                if (!node->few) return std::move(node->many);
                if (!node->many) return std::move(node->few);
                Node* successor = node->many.get();
                while (successor->few) successor = successor->few.get();
                node->jar = successor->jar;
                node->bundles = successor->bundles;
                node->many = detach(std::move(node->many), successor->jar);
                return node;
            }
            bool PantryJarCounts::use_one(std::int32_t jar) {
                Node* current = pantry_.get();
                while (current) {
                    if (jar == current->jar) break;
                    current = jar < current->jar ? current->few.get() : current->many.get();
                }
                if (!current) return false;
                --total_jars_;
                if (current->bundles > 1) {
                    --current->bundles;
                    return true;
                }
                pantry_ = detach(std::move(pantry_), jar);
                --kinds_;
                return true;
            }
            std::int32_t PantryJarCounts::jars_of(std::int32_t jar) const {
                const Node* current = pantry_.get();
                while (current) {
                    if (jar == current->jar) return current->bundles;
                    current = jar < current->jar ? current->few.get() : current->many.get();
                }
                return 0;
            }
            std::size_t PantryJarCounts::kinds() const { return kinds_; }
            std::size_t PantryJarCounts::total_jars() const { return total_jars_; }
            std::int32_t PantryJarCounts::depth_of(std::int32_t jar) const {
                const Node* current = pantry_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (jar == current->jar) return depth;
                    ++depth;
                    current = jar < current->jar ? current->few.get() : current->many.get();
                }
                return -1;
            }
            """,
            """
            PantryJarCounts::Node::Node(std::int32_t value) : jar(value), bundles(1) {}
            void PantryJarCounts::stock(std::int32_t jar) {
                ++total_jars_;
                if (!pantry_) {
                    pantry_ = std::make_unique<Node>(jar);
                    kinds_ = 1;
                    return;
                }
                Node* current = pantry_.get();
                for (;;) {
                    if (jar == current->jar) {
                        ++current->bundles;
                        return;
                    }
                    if (!current->few) {
                        current->few = std::make_unique<Node>(jar);
                        ++kinds_;
                        return;
                    }
                    current = current->few.get();
                }
            }
            bool PantryJarCounts::use_one(std::int32_t jar) {
                if (!pantry_) return false;
                if (pantry_->jar == jar) {
                    --total_jars_;
                    if (pantry_->bundles > 1) {
                        --pantry_->bundles;
                        return true;
                    }
                    pantry_ = std::move(pantry_->few);
                    --kinds_;
                    return true;
                }
                Node* parent = pantry_.get();
                while (parent->few && parent->few->jar != jar) parent = parent->few.get();
                if (!parent->few) return false;
                --total_jars_;
                if (parent->few->bundles > 1) {
                    --parent->few->bundles;
                    return true;
                }
                parent->few = std::move(parent->few->few);
                --kinds_;
                return true;
            }
            std::int32_t PantryJarCounts::jars_of(std::int32_t jar) const {
                const Node* current = pantry_.get();
                while (current) {
                    if (jar == current->jar) return current->bundles;
                    current = current->few.get();
                }
                return 0;
            }
            std::size_t PantryJarCounts::kinds() const { return kinds_; }
            std::size_t PantryJarCounts::total_jars() const { return total_jars_; }
            std::int32_t PantryJarCounts::depth_of(std::int32_t jar) const {
                const Node* current = pantry_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (jar == current->jar) return depth;
                    ++depth;
                    current = current->few.get();
                }
                return -1;
            }
            """,
            """
            PantryJarCounts counts;
            counts.stock(40);
            counts.stock(20);
            counts.stock(20);
            if (counts.jars_of(20) != 2) return 1;
            if (counts.kinds() != 2U) return 2;
            if (counts.total_jars() != 3U) return 3;
            if (!counts.use_one(20)) return 4;
            if (counts.jars_of(20) != 1) return 5;
            if (counts.total_jars() != 2U) return 6;
            return 0;
            """,
            """
            PantryJarCounts counts;
            counts.stock(40);
            counts.stock(20);
            counts.stock(60);
            counts.stock(10);
            counts.stock(30);
            counts.stock(50);
            counts.stock(70);
            counts.stock(20);
            counts.stock(40);
            counts.stock(20);
            if (counts.jars_of(20) != 3) return 1;
            if (counts.jars_of(40) != 2) return 2;
            if (counts.jars_of(70) != 1) return 3;
            if (counts.kinds() != 7U) return 4;
            if (counts.total_jars() != 10U) return 5;
            if (counts.depth_of(20) != 1) return 6;
            if (counts.depth_of(30) != 2) return 7;
            if (counts.depth_of(40) != 0) return 8;
            if (counts.depth_of(99) != -1) return 9;
            if (counts.jars_of(99) != 0) return 10;
            if (counts.use_one(99)) return 11;
            if (!counts.use_one(20)) return 12;
            if (!counts.use_one(20)) return 13;
            if (counts.kinds() != 7U) return 14;
            if (!counts.use_one(20)) return 15;
            if (counts.kinds() != 6U) return 16;
            if (counts.jars_of(20) != 0) return 17;
            if (counts.depth_of(20) != -1) return 18;
            if (counts.total_jars() != 7U) return 19;
            if (counts.use_one(20)) return 20;
            return 0;
            """,
            "per-node jar tallies over insertion-ordered linked storage",
            "an ordered container, a sorted std::vector, or a single-sided few chain that ignores ordering decisions as the core store",
            "tallies and depths after 40,20,60,10,30,50,70,20,40,20, decrement-to-detach, and absent results",
            "counted duplicates in a pantry domain",
            "counted-duplicate (multiplicity) ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-dart-score-board",
            "Dart score board",
            "dart_score",
            """
            class DartScoreBoard {
            public:
                void score(std::int32_t mark);
                bool erase_one(std::int32_t mark);
                std::int32_t hits_on(std::int32_t mark) const;
                std::size_t marks() const;
                std::size_t darts() const;
                std::int32_t depth_of(std::int32_t mark) const;
            };
            """,
            """
            class DartScoreBoard {
            public:
                void score(std::int32_t mark);
                bool erase_one(std::int32_t mark);
                std::int32_t hits_on(std::int32_t mark) const;
                std::size_t marks() const;
                std::size_t darts() const;
                std::int32_t depth_of(std::int32_t mark) const;
            private:
                struct Node {
                    std::int32_t mark;
                    std::int32_t hits;
                    std::unique_ptr<Node> inner_ring;
                    std::unique_ptr<Node> outer_ring;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> board_;
                std::size_t marks_ = 0;
                std::size_t darts_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t mark);
            };
            """,
            """
            DartScoreBoard::Node::Node(std::int32_t value) : mark(value), hits(1) {}
            void DartScoreBoard::score(std::int32_t mark) {
                ++darts_;
                if (!board_) {
                    board_ = std::make_unique<Node>(mark);
                    marks_ = 1;
                    return;
                }
                Node* current = board_.get();
                for (;;) {
                    if (mark == current->mark) {
                        ++current->hits;
                        return;
                    }
                    if (mark < current->mark) {
                        if (!current->inner_ring) {
                            current->inner_ring = std::make_unique<Node>(mark);
                            ++marks_;
                            return;
                        }
                        current = current->inner_ring.get();
                    } else {
                        if (!current->outer_ring) {
                            current->outer_ring = std::make_unique<Node>(mark);
                            ++marks_;
                            return;
                        }
                        current = current->outer_ring.get();
                    }
                }
            }
            std::unique_ptr<DartScoreBoard::Node> DartScoreBoard::detach(std::unique_ptr<Node> node, std::int32_t mark) {
                if (!node) return nullptr;
                if (mark < node->mark) {
                    node->inner_ring = detach(std::move(node->inner_ring), mark);
                    return node;
                }
                if (node->mark < mark) {
                    node->outer_ring = detach(std::move(node->outer_ring), mark);
                    return node;
                }
                if (!node->inner_ring) return std::move(node->outer_ring);
                if (!node->outer_ring) return std::move(node->inner_ring);
                Node* successor = node->outer_ring.get();
                while (successor->inner_ring) successor = successor->inner_ring.get();
                node->mark = successor->mark;
                node->hits = successor->hits;
                node->outer_ring = detach(std::move(node->outer_ring), successor->mark);
                return node;
            }
            bool DartScoreBoard::erase_one(std::int32_t mark) {
                Node* current = board_.get();
                while (current) {
                    if (mark == current->mark) break;
                    current = mark < current->mark ? current->inner_ring.get() : current->outer_ring.get();
                }
                if (!current) return false;
                --darts_;
                if (current->hits > 1) {
                    --current->hits;
                    return true;
                }
                board_ = detach(std::move(board_), mark);
                --marks_;
                return true;
            }
            std::int32_t DartScoreBoard::hits_on(std::int32_t mark) const {
                const Node* current = board_.get();
                while (current) {
                    if (mark == current->mark) return current->hits;
                    current = mark < current->mark ? current->inner_ring.get() : current->outer_ring.get();
                }
                return 0;
            }
            std::size_t DartScoreBoard::marks() const { return marks_; }
            std::size_t DartScoreBoard::darts() const { return darts_; }
            std::int32_t DartScoreBoard::depth_of(std::int32_t mark) const {
                const Node* current = board_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (mark == current->mark) return depth;
                    ++depth;
                    current = mark < current->mark ? current->inner_ring.get() : current->outer_ring.get();
                }
                return -1;
            }
            """,
            """
            DartScoreBoard::Node::Node(std::int32_t value) : mark(value), hits(1) {}
            void DartScoreBoard::score(std::int32_t mark) {
                ++darts_;
                if (!board_) {
                    board_ = std::make_unique<Node>(mark);
                    marks_ = 1;
                    return;
                }
                Node* current = board_.get();
                for (;;) {
                    if (mark == current->mark) {
                        ++current->hits;
                        return;
                    }
                    if (!current->outer_ring) {
                        current->outer_ring = std::make_unique<Node>(mark);
                        ++marks_;
                        return;
                    }
                    current = current->outer_ring.get();
                }
            }
            bool DartScoreBoard::erase_one(std::int32_t mark) {
                if (!board_) return false;
                if (board_->mark == mark) {
                    --darts_;
                    if (board_->hits > 1) {
                        --board_->hits;
                        return true;
                    }
                    board_ = std::move(board_->outer_ring);
                    --marks_;
                    return true;
                }
                Node* parent = board_.get();
                while (parent->outer_ring && parent->outer_ring->mark != mark) parent = parent->outer_ring.get();
                if (!parent->outer_ring) return false;
                --darts_;
                if (parent->outer_ring->hits > 1) {
                    --parent->outer_ring->hits;
                    return true;
                }
                parent->outer_ring = std::move(parent->outer_ring->outer_ring);
                --marks_;
                return true;
            }
            std::int32_t DartScoreBoard::hits_on(std::int32_t mark) const {
                const Node* current = board_.get();
                while (current) {
                    if (mark == current->mark) return current->hits;
                    current = current->outer_ring.get();
                }
                return 0;
            }
            std::size_t DartScoreBoard::marks() const { return marks_; }
            std::size_t DartScoreBoard::darts() const { return darts_; }
            std::int32_t DartScoreBoard::depth_of(std::int32_t mark) const {
                const Node* current = board_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (mark == current->mark) return depth;
                    ++depth;
                    current = current->outer_ring.get();
                }
                return -1;
            }
            """,
            """
            DartScoreBoard board;
            board.score(50);
            board.score(25);
            board.score(25);
            if (board.hits_on(25) != 2) return 1;
            if (board.marks() != 2U) return 2;
            if (board.darts() != 3U) return 3;
            if (!board.erase_one(25)) return 4;
            if (board.hits_on(25) != 1) return 5;
            if (board.darts() != 2U) return 6;
            return 0;
            """,
            """
            DartScoreBoard board;
            board.score(50);
            board.score(25);
            board.score(75);
            board.score(13);
            board.score(38);
            board.score(63);
            board.score(88);
            board.score(25);
            board.score(50);
            board.score(50);
            board.score(88);
            if (board.hits_on(50) != 3) return 1;
            if (board.hits_on(25) != 2) return 2;
            if (board.hits_on(88) != 2) return 3;
            if (board.marks() != 7U) return 4;
            if (board.darts() != 11U) return 5;
            if (board.depth_of(25) != 1) return 6;
            if (board.depth_of(38) != 2) return 7;
            if (board.depth_of(50) != 0) return 8;
            if (board.depth_of(99) != -1) return 9;
            if (board.hits_on(99) != 0) return 10;
            if (board.erase_one(99)) return 11;
            if (!board.erase_one(50)) return 12;
            if (!board.erase_one(50)) return 13;
            if (board.marks() != 7U) return 14;
            if (!board.erase_one(50)) return 15;
            if (board.marks() != 6U) return 16;
            if (board.hits_on(50) != 0) return 17;
            if (board.depth_of(50) != -1) return 18;
            if (board.darts() != 8U) return 19;
            if (board.erase_one(50)) return 20;
            return 0;
            """,
            "per-node hit tallies over insertion-ordered linked marks",
            "an ordered container, a sorted std::vector, or a single-sided outer-ring chain that ignores ordering decisions as the core store",
            "tallies and depths after 50,25,75,13,38,63,88,25,50,50,88, decrement-to-detach, and absent results",
            "counted duplicates with score vocabulary",
            "counted-duplicate (multiplicity) ordered tree",
        ),
        c(
            "f26bst-coffee-bean-batches",
            "Coffee bean batches",
            "coffee_bean",
            """
            class CoffeeBeanBatches {
            public:
                void receive(std::int64_t batch);
                bool scoop(std::int64_t batch);
                std::int32_t bags_of(std::int64_t batch) const;
                std::size_t batches() const;
                std::int64_t total_bags() const;
                std::int32_t depth_of(std::int64_t batch) const;
            };
            """,
            """
            class CoffeeBeanBatches {
            public:
                void receive(std::int64_t batch);
                bool scoop(std::int64_t batch);
                std::int32_t bags_of(std::int64_t batch) const;
                std::size_t batches() const;
                std::int64_t total_bags() const;
                std::int32_t depth_of(std::int64_t batch) const;
            private:
                struct Node {
                    std::int64_t batch;
                    std::int32_t bags;
                    std::unique_ptr<Node> light_roast;
                    std::unique_ptr<Node> dark_roast;
                    explicit Node(std::int64_t value);
                };
                std::unique_ptr<Node> silo_;
                std::size_t batches_ = 0;
                std::int64_t total_bags_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int64_t batch);
            };
            """,
            """
            CoffeeBeanBatches::Node::Node(std::int64_t value) : batch(value), bags(1) {}
            void CoffeeBeanBatches::receive(std::int64_t batch) {
                ++total_bags_;
                if (!silo_) {
                    silo_ = std::make_unique<Node>(batch);
                    batches_ = 1;
                    return;
                }
                Node* current = silo_.get();
                for (;;) {
                    if (batch == current->batch) {
                        ++current->bags;
                        return;
                    }
                    if (batch < current->batch) {
                        if (!current->light_roast) {
                            current->light_roast = std::make_unique<Node>(batch);
                            ++batches_;
                            return;
                        }
                        current = current->light_roast.get();
                    } else {
                        if (!current->dark_roast) {
                            current->dark_roast = std::make_unique<Node>(batch);
                            ++batches_;
                            return;
                        }
                        current = current->dark_roast.get();
                    }
                }
            }
            std::unique_ptr<CoffeeBeanBatches::Node> CoffeeBeanBatches::detach(std::unique_ptr<Node> node, std::int64_t batch) {
                if (!node) return nullptr;
                if (batch < node->batch) {
                    node->light_roast = detach(std::move(node->light_roast), batch);
                    return node;
                }
                if (node->batch < batch) {
                    node->dark_roast = detach(std::move(node->dark_roast), batch);
                    return node;
                }
                if (!node->light_roast) return std::move(node->dark_roast);
                if (!node->dark_roast) return std::move(node->light_roast);
                Node* successor = node->dark_roast.get();
                while (successor->light_roast) successor = successor->light_roast.get();
                node->batch = successor->batch;
                node->bags = successor->bags;
                node->dark_roast = detach(std::move(node->dark_roast), successor->batch);
                return node;
            }
            bool CoffeeBeanBatches::scoop(std::int64_t batch) {
                Node* current = silo_.get();
                while (current) {
                    if (batch == current->batch) break;
                    current = batch < current->batch ? current->light_roast.get() : current->dark_roast.get();
                }
                if (!current) return false;
                --total_bags_;
                if (current->bags > 1) {
                    --current->bags;
                    return true;
                }
                silo_ = detach(std::move(silo_), batch);
                --batches_;
                return true;
            }
            std::int32_t CoffeeBeanBatches::bags_of(std::int64_t batch) const {
                const Node* current = silo_.get();
                while (current) {
                    if (batch == current->batch) return current->bags;
                    current = batch < current->batch ? current->light_roast.get() : current->dark_roast.get();
                }
                return 0;
            }
            std::size_t CoffeeBeanBatches::batches() const { return batches_; }
            std::int64_t CoffeeBeanBatches::total_bags() const { return total_bags_; }
            std::int32_t CoffeeBeanBatches::depth_of(std::int64_t batch) const {
                const Node* current = silo_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (batch == current->batch) return depth;
                    ++depth;
                    current = batch < current->batch ? current->light_roast.get() : current->dark_roast.get();
                }
                return -1;
            }
            """,
            """
            CoffeeBeanBatches::Node::Node(std::int64_t value) : batch(value), bags(1) {}
            void CoffeeBeanBatches::receive(std::int64_t batch) {
                ++total_bags_;
                if (!silo_) {
                    silo_ = std::make_unique<Node>(batch);
                    batches_ = 1;
                    return;
                }
                Node* current = silo_.get();
                for (;;) {
                    if (batch == current->batch) {
                        ++current->bags;
                        return;
                    }
                    if (!current->light_roast) {
                        current->light_roast = std::make_unique<Node>(batch);
                        ++batches_;
                        return;
                    }
                    current = current->light_roast.get();
                }
            }
            bool CoffeeBeanBatches::scoop(std::int64_t batch) {
                if (!silo_) return false;
                if (silo_->batch == batch) {
                    --total_bags_;
                    if (silo_->bags > 1) {
                        --silo_->bags;
                        return true;
                    }
                    silo_ = std::move(silo_->light_roast);
                    --batches_;
                    return true;
                }
                Node* parent = silo_.get();
                while (parent->light_roast && parent->light_roast->batch != batch) parent = parent->light_roast.get();
                if (!parent->light_roast) return false;
                --total_bags_;
                if (parent->light_roast->bags > 1) {
                    --parent->light_roast->bags;
                    return true;
                }
                parent->light_roast = std::move(parent->light_roast->light_roast);
                --batches_;
                return true;
            }
            std::int32_t CoffeeBeanBatches::bags_of(std::int64_t batch) const {
                const Node* current = silo_.get();
                while (current) {
                    if (batch == current->batch) return current->bags;
                    current = current->light_roast.get();
                }
                return 0;
            }
            std::size_t CoffeeBeanBatches::batches() const { return batches_; }
            std::int64_t CoffeeBeanBatches::total_bags() const { return total_bags_; }
            std::int32_t CoffeeBeanBatches::depth_of(std::int64_t batch) const {
                const Node* current = silo_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (batch == current->batch) return depth;
                    ++depth;
                    current = current->light_roast.get();
                }
                return -1;
            }
            """,
            """
            CoffeeBeanBatches batches_obj;
            batches_obj.receive(900);
            batches_obj.receive(450);
            batches_obj.receive(450);
            if (batches_obj.bags_of(450) != 2) return 1;
            if (batches_obj.batches() != 2U) return 2;
            if (batches_obj.total_bags() != 3) return 3;
            if (!batches_obj.scoop(450)) return 4;
            if (batches_obj.bags_of(450) != 1) return 5;
            if (batches_obj.total_bags() != 2) return 6;
            return 0;
            """,
            """
            CoffeeBeanBatches batches_obj;
            batches_obj.receive(900);
            batches_obj.receive(450);
            batches_obj.receive(1350);
            batches_obj.receive(225);
            batches_obj.receive(675);
            batches_obj.receive(1125);
            batches_obj.receive(1575);
            batches_obj.receive(450);
            batches_obj.receive(900);
            if (batches_obj.bags_of(450) != 2) return 1;
            if (batches_obj.bags_of(900) != 2) return 2;
            if (batches_obj.bags_of(1575) != 1) return 3;
            if (batches_obj.batches() != 7U) return 4;
            if (batches_obj.total_bags() != 9) return 5;
            if (batches_obj.depth_of(450) != 1) return 6;
            if (batches_obj.depth_of(675) != 2) return 7;
            if (batches_obj.depth_of(900) != 0) return 8;
            if (batches_obj.depth_of(99) != -1) return 9;
            if (batches_obj.bags_of(99) != 0) return 10;
            if (batches_obj.scoop(99)) return 11;
            if (!batches_obj.scoop(450)) return 12;
            if (batches_obj.batches() != 7U) return 13;
            if (!batches_obj.scoop(450)) return 14;
            if (batches_obj.batches() != 6U) return 15;
            if (batches_obj.bags_of(450) != 0) return 16;
            if (batches_obj.depth_of(450) != -1) return 17;
            if (batches_obj.total_bags() != 7) return 18;
            if (batches_obj.scoop(450)) return 19;
            return 0;
            """,
            "sixty-four-bit batch tallies over insertion-ordered linked storage",
            "an ordered container, a sorted std::vector, or a single-sided light-roast chain that ignores ordering decisions as the core store",
            "tallies and depths after 900,450,1350,225,675,1125,1575,450,900, decrement-to-detach, and absent results",
            "64-bit counted duplicates",
            "counted-duplicate (multiplicity) ordered tree",
        ),
        c(
            "f26bst-turnstile-scan-counts",
            "Turnstile scan counts",
            "turnstile_scan",
            """
            class TurnstileScanCounts {
            public:
                void scan(std::int32_t gate);
                bool void_scan(std::int32_t gate);
                std::int32_t scans_of(std::int32_t gate) const;
                std::size_t gates() const;
                std::size_t scans() const;
                std::int32_t depth_of(std::int32_t gate) const;
            };
            """,
            """
            class TurnstileScanCounts {
            public:
                void scan(std::int32_t gate);
                bool void_scan(std::int32_t gate);
                std::int32_t scans_of(std::int32_t gate) const;
                std::size_t gates() const;
                std::size_t scans() const;
                std::int32_t depth_of(std::int32_t gate) const;
            private:
                struct Node {
                    std::int32_t gate;
                    std::int32_t passages;
                    std::unique_ptr<Node> near_gate;
                    std::unique_ptr<Node> far_gate;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> plaza_;
                std::size_t gates_ = 0;
                std::size_t scans_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t gate);
            };
            """,
            """
            TurnstileScanCounts::Node::Node(std::int32_t value) : gate(value), passages(1) {}
            void TurnstileScanCounts::scan(std::int32_t gate) {
                ++scans_;
                if (!plaza_) {
                    plaza_ = std::make_unique<Node>(gate);
                    gates_ = 1;
                    return;
                }
                Node* current = plaza_.get();
                for (;;) {
                    if (gate == current->gate) {
                        ++current->passages;
                        return;
                    }
                    if (gate < current->gate) {
                        if (!current->near_gate) {
                            current->near_gate = std::make_unique<Node>(gate);
                            ++gates_;
                            return;
                        }
                        current = current->near_gate.get();
                    } else {
                        if (!current->far_gate) {
                            current->far_gate = std::make_unique<Node>(gate);
                            ++gates_;
                            return;
                        }
                        current = current->far_gate.get();
                    }
                }
            }
            std::unique_ptr<TurnstileScanCounts::Node> TurnstileScanCounts::detach(std::unique_ptr<Node> node, std::int32_t gate) {
                if (!node) return nullptr;
                if (gate < node->gate) {
                    node->near_gate = detach(std::move(node->near_gate), gate);
                    return node;
                }
                if (node->gate < gate) {
                    node->far_gate = detach(std::move(node->far_gate), gate);
                    return node;
                }
                if (!node->near_gate) return std::move(node->far_gate);
                if (!node->far_gate) return std::move(node->near_gate);
                Node* successor = node->far_gate.get();
                while (successor->near_gate) successor = successor->near_gate.get();
                node->gate = successor->gate;
                node->passages = successor->passages;
                node->far_gate = detach(std::move(node->far_gate), successor->gate);
                return node;
            }
            bool TurnstileScanCounts::void_scan(std::int32_t gate) {
                Node* current = plaza_.get();
                while (current) {
                    if (gate == current->gate) break;
                    current = gate < current->gate ? current->near_gate.get() : current->far_gate.get();
                }
                if (!current) return false;
                --scans_;
                if (current->passages > 1) {
                    --current->passages;
                    return true;
                }
                plaza_ = detach(std::move(plaza_), gate);
                --gates_;
                return true;
            }
            std::int32_t TurnstileScanCounts::scans_of(std::int32_t gate) const {
                const Node* current = plaza_.get();
                while (current) {
                    if (gate == current->gate) return current->passages;
                    current = gate < current->gate ? current->near_gate.get() : current->far_gate.get();
                }
                return 0;
            }
            std::size_t TurnstileScanCounts::gates() const { return gates_; }
            std::size_t TurnstileScanCounts::scans() const { return scans_; }
            std::int32_t TurnstileScanCounts::depth_of(std::int32_t gate) const {
                const Node* current = plaza_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gate == current->gate) return depth;
                    ++depth;
                    current = gate < current->gate ? current->near_gate.get() : current->far_gate.get();
                }
                return -1;
            }
            """,
            """
            TurnstileScanCounts::Node::Node(std::int32_t value) : gate(value), passages(1) {}
            void TurnstileScanCounts::scan(std::int32_t gate) {
                ++scans_;
                if (!plaza_) {
                    plaza_ = std::make_unique<Node>(gate);
                    gates_ = 1;
                    return;
                }
                Node* current = plaza_.get();
                for (;;) {
                    if (gate == current->gate) {
                        ++current->passages;
                        return;
                    }
                    if (!current->far_gate) {
                        current->far_gate = std::make_unique<Node>(gate);
                        ++gates_;
                        return;
                    }
                    current = current->far_gate.get();
                }
            }
            bool TurnstileScanCounts::void_scan(std::int32_t gate) {
                if (!plaza_) return false;
                if (plaza_->gate == gate) {
                    --scans_;
                    if (plaza_->passages > 1) {
                        --plaza_->passages;
                        return true;
                    }
                    plaza_ = std::move(plaza_->far_gate);
                    --gates_;
                    return true;
                }
                Node* parent = plaza_.get();
                while (parent->far_gate && parent->far_gate->gate != gate) parent = parent->far_gate.get();
                if (!parent->far_gate) return false;
                --scans_;
                if (parent->far_gate->passages > 1) {
                    --parent->far_gate->passages;
                    return true;
                }
                parent->far_gate = std::move(parent->far_gate->far_gate);
                --gates_;
                return true;
            }
            std::int32_t TurnstileScanCounts::scans_of(std::int32_t gate) const {
                const Node* current = plaza_.get();
                while (current) {
                    if (gate == current->gate) return current->passages;
                    current = current->far_gate.get();
                }
                return 0;
            }
            std::size_t TurnstileScanCounts::gates() const { return gates_; }
            std::size_t TurnstileScanCounts::scans() const { return scans_; }
            std::int32_t TurnstileScanCounts::depth_of(std::int32_t gate) const {
                const Node* current = plaza_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gate == current->gate) return depth;
                    ++depth;
                    current = current->far_gate.get();
                }
                return -1;
            }
            """,
            """
            TurnstileScanCounts counts;
            counts.scan(7);
            counts.scan(4);
            counts.scan(4);
            if (counts.scans_of(4) != 2) return 1;
            if (counts.gates() != 2U) return 2;
            if (counts.scans() != 3U) return 3;
            if (!counts.void_scan(4)) return 4;
            if (counts.scans_of(4) != 1) return 5;
            if (counts.scans() != 2U) return 6;
            return 0;
            """,
            """
            TurnstileScanCounts counts;
            counts.scan(7);
            counts.scan(4);
            counts.scan(10);
            counts.scan(2);
            counts.scan(6);
            counts.scan(8);
            counts.scan(12);
            counts.scan(4);
            counts.scan(7);
            counts.scan(4);
            counts.scan(10);
            if (counts.scans_of(4) != 3) return 1;
            if (counts.scans_of(7) != 2) return 2;
            if (counts.scans_of(10) != 2) return 3;
            if (counts.gates() != 7U) return 4;
            if (counts.scans() != 11U) return 5;
            if (counts.depth_of(4) != 1) return 6;
            if (counts.depth_of(6) != 2) return 7;
            if (counts.depth_of(7) != 0) return 8;
            if (counts.depth_of(99) != -1) return 9;
            if (counts.scans_of(99) != 0) return 10;
            if (counts.void_scan(99)) return 11;
            if (!counts.void_scan(4)) return 12;
            if (!counts.void_scan(4)) return 13;
            if (counts.gates() != 7U) return 14;
            if (!counts.void_scan(4)) return 15;
            if (counts.gates() != 6U) return 16;
            if (counts.scans_of(4) != 0) return 17;
            if (counts.depth_of(4) != -1) return 18;
            if (counts.scans() != 8U) return 19;
            if (counts.void_scan(4)) return 20;
            return 0;
            """,
            "per-node scan tallies over insertion-ordered linked gates",
            "an ordered container, a sorted std::vector, or a single-sided far-gate chain that ignores ordering decisions as the core store",
            "tallies and depths after 7,4,10,2,6,8,12,4,7,4,10, decrement-to-detach, and absent results",
            "counted duplicates with small dense keys",
            "counted-duplicate (multiplicity) ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-key-tag-counts",
            "Key tag counts",
            "key_tag",
            """
            class KeyTagCounts {
            public:
                void attach(std::int32_t tag);
                bool detach_one(std::int32_t tag);
                std::int32_t tags_of(std::int32_t tag) const;
                std::size_t kinds() const;
                std::size_t tagged() const;
                std::int32_t depth_of(std::int32_t tag) const;
            };
            """,
            """
            class KeyTagCounts {
            public:
                void attach(std::int32_t tag);
                bool detach_one(std::int32_t tag);
                std::int32_t tags_of(std::int32_t tag) const;
                std::size_t kinds() const;
                std::size_t tagged() const;
                std::int32_t depth_of(std::int32_t tag) const;
            private:
                struct Node {
                    std::int32_t tag;
                    std::int32_t clipped;
                    std::unique_ptr<Node> short_tag;
                    std::unique_ptr<Node> long_tag;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> rack_;
                std::size_t kinds_ = 0;
                std::size_t tagged_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t tag);
            };
            """,
            """
            KeyTagCounts::Node::Node(std::int32_t value) : tag(value), clipped(1) {}
            void KeyTagCounts::attach(std::int32_t tag) {
                ++tagged_;
                if (!rack_) {
                    rack_ = std::make_unique<Node>(tag);
                    kinds_ = 1;
                    return;
                }
                Node* current = rack_.get();
                for (;;) {
                    if (tag == current->tag) {
                        ++current->clipped;
                        return;
                    }
                    if (tag < current->tag) {
                        if (!current->short_tag) {
                            current->short_tag = std::make_unique<Node>(tag);
                            ++kinds_;
                            return;
                        }
                        current = current->short_tag.get();
                    } else {
                        if (!current->long_tag) {
                            current->long_tag = std::make_unique<Node>(tag);
                            ++kinds_;
                            return;
                        }
                        current = current->long_tag.get();
                    }
                }
            }
            std::unique_ptr<KeyTagCounts::Node> KeyTagCounts::detach(std::unique_ptr<Node> node, std::int32_t tag) {
                if (!node) return nullptr;
                if (tag < node->tag) {
                    node->short_tag = detach(std::move(node->short_tag), tag);
                    return node;
                }
                if (node->tag < tag) {
                    node->long_tag = detach(std::move(node->long_tag), tag);
                    return node;
                }
                if (!node->short_tag) return std::move(node->long_tag);
                if (!node->long_tag) return std::move(node->short_tag);
                Node* successor = node->long_tag.get();
                while (successor->short_tag) successor = successor->short_tag.get();
                node->tag = successor->tag;
                node->clipped = successor->clipped;
                node->long_tag = detach(std::move(node->long_tag), successor->tag);
                return node;
            }
            bool KeyTagCounts::detach_one(std::int32_t tag) {
                Node* current = rack_.get();
                while (current) {
                    if (tag == current->tag) break;
                    current = tag < current->tag ? current->short_tag.get() : current->long_tag.get();
                }
                if (!current) return false;
                --tagged_;
                if (current->clipped > 1) {
                    --current->clipped;
                    return true;
                }
                rack_ = detach(std::move(rack_), tag);
                --kinds_;
                return true;
            }
            std::int32_t KeyTagCounts::tags_of(std::int32_t tag) const {
                const Node* current = rack_.get();
                while (current) {
                    if (tag == current->tag) return current->clipped;
                    current = tag < current->tag ? current->short_tag.get() : current->long_tag.get();
                }
                return 0;
            }
            std::size_t KeyTagCounts::kinds() const { return kinds_; }
            std::size_t KeyTagCounts::tagged() const { return tagged_; }
            std::int32_t KeyTagCounts::depth_of(std::int32_t tag) const {
                const Node* current = rack_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (tag == current->tag) return depth;
                    ++depth;
                    current = tag < current->tag ? current->short_tag.get() : current->long_tag.get();
                }
                return -1;
            }
            """,
            """
            KeyTagCounts::Node::Node(std::int32_t value) : tag(value), clipped(1) {}
            void KeyTagCounts::attach(std::int32_t tag) {
                ++tagged_;
                if (!rack_) {
                    rack_ = std::make_unique<Node>(tag);
                    kinds_ = 1;
                    return;
                }
                Node* current = rack_.get();
                for (;;) {
                    if (tag == current->tag) {
                        ++current->clipped;
                        return;
                    }
                    if (!current->short_tag) {
                        current->short_tag = std::make_unique<Node>(tag);
                        ++kinds_;
                        return;
                    }
                    current = current->short_tag.get();
                }
            }
            bool KeyTagCounts::detach_one(std::int32_t tag) {
                if (!rack_) return false;
                if (rack_->tag == tag) {
                    --tagged_;
                    if (rack_->clipped > 1) {
                        --rack_->clipped;
                        return true;
                    }
                    rack_ = std::move(rack_->short_tag);
                    --kinds_;
                    return true;
                }
                Node* parent = rack_.get();
                while (parent->short_tag && parent->short_tag->tag != tag) parent = parent->short_tag.get();
                if (!parent->short_tag) return false;
                --tagged_;
                if (parent->short_tag->clipped > 1) {
                    --parent->short_tag->clipped;
                    return true;
                }
                parent->short_tag = std::move(parent->short_tag->short_tag);
                --kinds_;
                return true;
            }
            std::int32_t KeyTagCounts::tags_of(std::int32_t tag) const {
                const Node* current = rack_.get();
                while (current) {
                    if (tag == current->tag) return current->clipped;
                    current = current->short_tag.get();
                }
                return 0;
            }
            std::size_t KeyTagCounts::kinds() const { return kinds_; }
            std::size_t KeyTagCounts::tagged() const { return tagged_; }
            std::int32_t KeyTagCounts::depth_of(std::int32_t tag) const {
                const Node* current = rack_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (tag == current->tag) return depth;
                    ++depth;
                    current = current->short_tag.get();
                }
                return -1;
            }
            """,
            """
            KeyTagCounts counts;
            counts.attach(33);
            counts.attach(17);
            counts.attach(17);
            if (counts.tags_of(17) != 2) return 1;
            if (counts.kinds() != 2U) return 2;
            if (counts.tagged() != 3U) return 3;
            if (!counts.detach_one(17)) return 4;
            if (counts.tags_of(17) != 1) return 5;
            if (counts.tagged() != 2U) return 6;
            return 0;
            """,
            """
            KeyTagCounts counts;
            counts.attach(33);
            counts.attach(17);
            counts.attach(49);
            counts.attach(9);
            counts.attach(25);
            counts.attach(41);
            counts.attach(57);
            counts.attach(17);
            counts.attach(33);
            counts.attach(17);
            if (counts.tags_of(17) != 3) return 1;
            if (counts.tags_of(33) != 2) return 2;
            if (counts.tags_of(57) != 1) return 3;
            if (counts.kinds() != 7U) return 4;
            if (counts.tagged() != 10U) return 5;
            if (counts.depth_of(17) != 1) return 6;
            if (counts.depth_of(25) != 2) return 7;
            if (counts.depth_of(33) != 0) return 8;
            if (counts.depth_of(99) != -1) return 9;
            if (counts.tags_of(99) != 0) return 10;
            if (counts.detach_one(99)) return 11;
            if (!counts.detach_one(17)) return 12;
            if (!counts.detach_one(17)) return 13;
            if (counts.kinds() != 7U) return 14;
            if (!counts.detach_one(17)) return 15;
            if (counts.kinds() != 6U) return 16;
            if (counts.tags_of(17) != 0) return 17;
            if (counts.depth_of(17) != -1) return 18;
            if (counts.tagged() != 7U) return 19;
            if (counts.detach_one(17)) return 20;
            return 0;
            """,
            "per-node tag tallies over insertion-ordered linked hooks",
            "an ordered container, a sorted std::vector, or a single-sided short-tag chain that ignores ordering decisions as the core store",
            "tallies and depths after 33,17,49,9,25,41,57,17,33,17, decrement-to-detach, and absent results",
            "counted duplicates with hook vocabulary",
            "counted-duplicate (multiplicity) ordered tree",
        ),
        c(
            "f26bst-rain-gauge-buckets",
            "Rain gauge buckets",
            "rain_gauge",
            """
            class RainGaugeBuckets {
            public:
                void tip(std::int32_t gauge);
                bool drain_one(std::int32_t gauge);
                std::int32_t tips_of(std::int32_t gauge) const;
                std::size_t gauges() const;
                std::size_t tips() const;
                std::int32_t depth_of(std::int32_t gauge) const;
            };
            """,
            """
            class RainGaugeBuckets {
            public:
                void tip(std::int32_t gauge);
                bool drain_one(std::int32_t gauge);
                std::int32_t tips_of(std::int32_t gauge) const;
                std::size_t gauges() const;
                std::size_t tips() const;
                std::int32_t depth_of(std::int32_t gauge) const;
            private:
                struct Node {
                    std::int32_t gauge;
                    std::int32_t clicks;
                    std::unique_ptr<Node> dry_gauge;
                    std::unique_ptr<Node> wet_gauge;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> field_;
                std::size_t gauges_ = 0;
                std::size_t tips_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t gauge);
            };
            """,
            """
            RainGaugeBuckets::Node::Node(std::int32_t value) : gauge(value), clicks(1) {}
            void RainGaugeBuckets::tip(std::int32_t gauge) {
                ++tips_;
                if (!field_) {
                    field_ = std::make_unique<Node>(gauge);
                    gauges_ = 1;
                    return;
                }
                Node* current = field_.get();
                for (;;) {
                    if (gauge == current->gauge) {
                        ++current->clicks;
                        return;
                    }
                    if (gauge < current->gauge) {
                        if (!current->dry_gauge) {
                            current->dry_gauge = std::make_unique<Node>(gauge);
                            ++gauges_;
                            return;
                        }
                        current = current->dry_gauge.get();
                    } else {
                        if (!current->wet_gauge) {
                            current->wet_gauge = std::make_unique<Node>(gauge);
                            ++gauges_;
                            return;
                        }
                        current = current->wet_gauge.get();
                    }
                }
            }
            std::unique_ptr<RainGaugeBuckets::Node> RainGaugeBuckets::detach(std::unique_ptr<Node> node, std::int32_t gauge) {
                if (!node) return nullptr;
                if (gauge < node->gauge) {
                    node->dry_gauge = detach(std::move(node->dry_gauge), gauge);
                    return node;
                }
                if (node->gauge < gauge) {
                    node->wet_gauge = detach(std::move(node->wet_gauge), gauge);
                    return node;
                }
                if (!node->dry_gauge) return std::move(node->wet_gauge);
                if (!node->wet_gauge) return std::move(node->dry_gauge);
                Node* successor = node->wet_gauge.get();
                while (successor->dry_gauge) successor = successor->dry_gauge.get();
                node->gauge = successor->gauge;
                node->clicks = successor->clicks;
                node->wet_gauge = detach(std::move(node->wet_gauge), successor->gauge);
                return node;
            }
            bool RainGaugeBuckets::drain_one(std::int32_t gauge) {
                Node* current = field_.get();
                while (current) {
                    if (gauge == current->gauge) break;
                    current = gauge < current->gauge ? current->dry_gauge.get() : current->wet_gauge.get();
                }
                if (!current) return false;
                --tips_;
                if (current->clicks > 1) {
                    --current->clicks;
                    return true;
                }
                field_ = detach(std::move(field_), gauge);
                --gauges_;
                return true;
            }
            std::int32_t RainGaugeBuckets::tips_of(std::int32_t gauge) const {
                const Node* current = field_.get();
                while (current) {
                    if (gauge == current->gauge) return current->clicks;
                    current = gauge < current->gauge ? current->dry_gauge.get() : current->wet_gauge.get();
                }
                return 0;
            }
            std::size_t RainGaugeBuckets::gauges() const { return gauges_; }
            std::size_t RainGaugeBuckets::tips() const { return tips_; }
            std::int32_t RainGaugeBuckets::depth_of(std::int32_t gauge) const {
                const Node* current = field_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gauge == current->gauge) return depth;
                    ++depth;
                    current = gauge < current->gauge ? current->dry_gauge.get() : current->wet_gauge.get();
                }
                return -1;
            }
            """,
            """
            RainGaugeBuckets::Node::Node(std::int32_t value) : gauge(value), clicks(1) {}
            void RainGaugeBuckets::tip(std::int32_t gauge) {
                ++tips_;
                if (!field_) {
                    field_ = std::make_unique<Node>(gauge);
                    gauges_ = 1;
                    return;
                }
                Node* current = field_.get();
                for (;;) {
                    if (gauge == current->gauge) {
                        ++current->clicks;
                        return;
                    }
                    if (!current->wet_gauge) {
                        current->wet_gauge = std::make_unique<Node>(gauge);
                        ++gauges_;
                        return;
                    }
                    current = current->wet_gauge.get();
                }
            }
            bool RainGaugeBuckets::drain_one(std::int32_t gauge) {
                if (!field_) return false;
                if (field_->gauge == gauge) {
                    --tips_;
                    if (field_->clicks > 1) {
                        --field_->clicks;
                        return true;
                    }
                    field_ = std::move(field_->wet_gauge);
                    --gauges_;
                    return true;
                }
                Node* parent = field_.get();
                while (parent->wet_gauge && parent->wet_gauge->gauge != gauge) parent = parent->wet_gauge.get();
                if (!parent->wet_gauge) return false;
                --tips_;
                if (parent->wet_gauge->clicks > 1) {
                    --parent->wet_gauge->clicks;
                    return true;
                }
                parent->wet_gauge = std::move(parent->wet_gauge->wet_gauge);
                --gauges_;
                return true;
            }
            std::int32_t RainGaugeBuckets::tips_of(std::int32_t gauge) const {
                const Node* current = field_.get();
                while (current) {
                    if (gauge == current->gauge) return current->clicks;
                    current = current->wet_gauge.get();
                }
                return 0;
            }
            std::size_t RainGaugeBuckets::gauges() const { return gauges_; }
            std::size_t RainGaugeBuckets::tips() const { return tips_; }
            std::int32_t RainGaugeBuckets::depth_of(std::int32_t gauge) const {
                const Node* current = field_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gauge == current->gauge) return depth;
                    ++depth;
                    current = current->wet_gauge.get();
                }
                return -1;
            }
            """,
            """
            RainGaugeBuckets buckets;
            buckets.tip(90);
            buckets.tip(45);
            buckets.tip(45);
            if (buckets.tips_of(45) != 2) return 1;
            if (buckets.gauges() != 2U) return 2;
            if (buckets.tips() != 3U) return 3;
            if (!buckets.drain_one(45)) return 4;
            if (buckets.tips_of(45) != 1) return 5;
            if (buckets.tips() != 2U) return 6;
            return 0;
            """,
            """
            RainGaugeBuckets buckets;
            buckets.tip(90);
            buckets.tip(45);
            buckets.tip(135);
            buckets.tip(23);
            buckets.tip(68);
            buckets.tip(113);
            buckets.tip(158);
            buckets.tip(45);
            buckets.tip(90);
            buckets.tip(45);
            buckets.tip(135);
            if (buckets.tips_of(45) != 3) return 1;
            if (buckets.tips_of(90) != 2) return 2;
            if (buckets.tips_of(135) != 2) return 3;
            if (buckets.gauges() != 7U) return 4;
            if (buckets.tips() != 11U) return 5;
            if (buckets.depth_of(45) != 1) return 6;
            if (buckets.depth_of(68) != 2) return 7;
            if (buckets.depth_of(90) != 0) return 8;
            if (buckets.depth_of(99) != -1) return 9;
            if (buckets.tips_of(99) != 0) return 10;
            if (buckets.drain_one(99)) return 11;
            if (!buckets.drain_one(45)) return 12;
            if (!buckets.drain_one(45)) return 13;
            if (buckets.gauges() != 7U) return 14;
            if (!buckets.drain_one(45)) return 15;
            if (buckets.gauges() != 6U) return 16;
            if (buckets.tips_of(45) != 0) return 17;
            if (buckets.depth_of(45) != -1) return 18;
            if (buckets.tips() != 8U) return 19;
            if (buckets.drain_one(45)) return 20;
            return 0;
            """,
            "per-node tip tallies over insertion-ordered linked gauges",
            "an ordered container, a sorted std::vector, or a single-sided wet-gauge chain that ignores ordering decisions as the core store",
            "tallies and depths after 90,45,135,23,68,113,158,45,90,45,135, decrement-to-detach, and absent results",
            "counted duplicates with gauge vocabulary",
            "counted-duplicate (multiplicity) ordered tree",
        ),
        c(
            "f26bst-coin-roll-counts",
            "Coin roll counts",
            "coin_roll",
            """
            class CoinRollCounts {
            public:
                void roll(std::int32_t wrapper);
                bool spend_one(std::int32_t wrapper);
                std::int32_t rolls_of(std::int32_t wrapper) const;
                std::size_t wrappers() const;
                std::size_t coins_total() const;
                std::int32_t depth_of(std::int32_t wrapper) const;
            };
            """,
            """
            class CoinRollCounts {
            public:
                void roll(std::int32_t wrapper);
                bool spend_one(std::int32_t wrapper);
                std::int32_t rolls_of(std::int32_t wrapper) const;
                std::size_t wrappers() const;
                std::size_t coins_total() const;
                std::int32_t depth_of(std::int32_t wrapper) const;
            private:
                struct Node {
                    std::int32_t wrapper;
                    std::int32_t rolls;
                    std::unique_ptr<Node> small_roll;
                    std::unique_ptr<Node> large_roll;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> drawer_;
                std::size_t wrappers_ = 0;
                std::size_t coins_total_ = 0;
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t wrapper);
            };
            """,
            """
            CoinRollCounts::Node::Node(std::int32_t value) : wrapper(value), rolls(1) {}
            void CoinRollCounts::roll(std::int32_t wrapper) {
                ++coins_total_;
                if (!drawer_) {
                    drawer_ = std::make_unique<Node>(wrapper);
                    wrappers_ = 1;
                    return;
                }
                Node* current = drawer_.get();
                for (;;) {
                    if (wrapper == current->wrapper) {
                        ++current->rolls;
                        return;
                    }
                    if (wrapper < current->wrapper) {
                        if (!current->small_roll) {
                            current->small_roll = std::make_unique<Node>(wrapper);
                            ++wrappers_;
                            return;
                        }
                        current = current->small_roll.get();
                    } else {
                        if (!current->large_roll) {
                            current->large_roll = std::make_unique<Node>(wrapper);
                            ++wrappers_;
                            return;
                        }
                        current = current->large_roll.get();
                    }
                }
            }
            std::unique_ptr<CoinRollCounts::Node> CoinRollCounts::detach(std::unique_ptr<Node> node, std::int32_t wrapper) {
                if (!node) return nullptr;
                if (wrapper < node->wrapper) {
                    node->small_roll = detach(std::move(node->small_roll), wrapper);
                    return node;
                }
                if (node->wrapper < wrapper) {
                    node->large_roll = detach(std::move(node->large_roll), wrapper);
                    return node;
                }
                if (!node->small_roll) return std::move(node->large_roll);
                if (!node->large_roll) return std::move(node->small_roll);
                Node* successor = node->large_roll.get();
                while (successor->small_roll) successor = successor->small_roll.get();
                node->wrapper = successor->wrapper;
                node->rolls = successor->rolls;
                node->large_roll = detach(std::move(node->large_roll), successor->wrapper);
                return node;
            }
            bool CoinRollCounts::spend_one(std::int32_t wrapper) {
                Node* current = drawer_.get();
                while (current) {
                    if (wrapper == current->wrapper) break;
                    current = wrapper < current->wrapper ? current->small_roll.get() : current->large_roll.get();
                }
                if (!current) return false;
                --coins_total_;
                if (current->rolls > 1) {
                    --current->rolls;
                    return true;
                }
                drawer_ = detach(std::move(drawer_), wrapper);
                --wrappers_;
                return true;
            }
            std::int32_t CoinRollCounts::rolls_of(std::int32_t wrapper) const {
                const Node* current = drawer_.get();
                while (current) {
                    if (wrapper == current->wrapper) return current->rolls;
                    current = wrapper < current->wrapper ? current->small_roll.get() : current->large_roll.get();
                }
                return 0;
            }
            std::size_t CoinRollCounts::wrappers() const { return wrappers_; }
            std::size_t CoinRollCounts::coins_total() const { return coins_total_; }
            std::int32_t CoinRollCounts::depth_of(std::int32_t wrapper) const {
                const Node* current = drawer_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (wrapper == current->wrapper) return depth;
                    ++depth;
                    current = wrapper < current->wrapper ? current->small_roll.get() : current->large_roll.get();
                }
                return -1;
            }
            """,
            """
            CoinRollCounts::Node::Node(std::int32_t value) : wrapper(value), rolls(1) {}
            void CoinRollCounts::roll(std::int32_t wrapper) {
                ++coins_total_;
                if (!drawer_) {
                    drawer_ = std::make_unique<Node>(wrapper);
                    wrappers_ = 1;
                    return;
                }
                Node* current = drawer_.get();
                for (;;) {
                    if (wrapper == current->wrapper) {
                        ++current->rolls;
                        return;
                    }
                    if (!current->small_roll) {
                        current->small_roll = std::make_unique<Node>(wrapper);
                        ++wrappers_;
                        return;
                    }
                    current = current->small_roll.get();
                }
            }
            bool CoinRollCounts::spend_one(std::int32_t wrapper) {
                if (!drawer_) return false;
                if (drawer_->wrapper == wrapper) {
                    --coins_total_;
                    if (drawer_->rolls > 1) {
                        --drawer_->rolls;
                        return true;
                    }
                    drawer_ = std::move(drawer_->small_roll);
                    --wrappers_;
                    return true;
                }
                Node* parent = drawer_.get();
                while (parent->small_roll && parent->small_roll->wrapper != wrapper) parent = parent->small_roll.get();
                if (!parent->small_roll) return false;
                --coins_total_;
                if (parent->small_roll->rolls > 1) {
                    --parent->small_roll->rolls;
                    return true;
                }
                parent->small_roll = std::move(parent->small_roll->small_roll);
                --wrappers_;
                return true;
            }
            std::int32_t CoinRollCounts::rolls_of(std::int32_t wrapper) const {
                const Node* current = drawer_.get();
                while (current) {
                    if (wrapper == current->wrapper) return current->rolls;
                    current = current->small_roll.get();
                }
                return 0;
            }
            std::size_t CoinRollCounts::wrappers() const { return wrappers_; }
            std::size_t CoinRollCounts::coins_total() const { return coins_total_; }
            std::int32_t CoinRollCounts::depth_of(std::int32_t wrapper) const {
                const Node* current = drawer_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (wrapper == current->wrapper) return depth;
                    ++depth;
                    current = current->small_roll.get();
                }
                return -1;
            }
            """,
            """
            CoinRollCounts counts;
            counts.roll(21);
            counts.roll(11);
            counts.roll(11);
            if (counts.rolls_of(11) != 2) return 1;
            if (counts.wrappers() != 2U) return 2;
            if (counts.coins_total() != 3U) return 3;
            if (!counts.spend_one(11)) return 4;
            if (counts.rolls_of(11) != 1) return 5;
            if (counts.coins_total() != 2U) return 6;
            return 0;
            """,
            """
            CoinRollCounts counts;
            counts.roll(21);
            counts.roll(11);
            counts.roll(31);
            counts.roll(6);
            counts.roll(16);
            counts.roll(26);
            counts.roll(36);
            counts.roll(11);
            counts.roll(21);
            counts.roll(11);
            counts.roll(31);
            counts.roll(36);
            if (counts.rolls_of(11) != 3) return 1;
            if (counts.rolls_of(21) != 2) return 2;
            if (counts.rolls_of(36) != 2) return 3;
            if (counts.wrappers() != 7U) return 4;
            if (counts.coins_total() != 12U) return 5;
            if (counts.depth_of(11) != 1) return 6;
            if (counts.depth_of(16) != 2) return 7;
            if (counts.depth_of(21) != 0) return 8;
            if (counts.depth_of(99) != -1) return 9;
            if (counts.rolls_of(99) != 0) return 10;
            if (counts.spend_one(99)) return 11;
            if (!counts.spend_one(11)) return 12;
            if (!counts.spend_one(11)) return 13;
            if (counts.wrappers() != 7U) return 14;
            if (!counts.spend_one(11)) return 15;
            if (counts.wrappers() != 6U) return 16;
            if (counts.rolls_of(11) != 0) return 17;
            if (counts.depth_of(11) != -1) return 18;
            if (counts.coins_total() != 9U) return 19;
            if (counts.spend_one(11)) return 20;
            return 0;
            """,
            "per-node roll tallies over insertion-ordered linked wrappers",
            "an ordered container, a sorted std::vector, or a single-sided small-roll chain that ignores ordering decisions as the core store",
            "tallies and depths after 21,11,31,6,16,26,36,11,21,11,31,36, decrement-to-detach, and absent results",
            "counted duplicates with twelve-key sequences",
            "counted-duplicate (multiplicity) ordered tree",
        ),
        c(
            "f26bst-ferry-lane-log",
            "Ferry lane log",
            "ferry_lane",
            """
            class LaneDuplicateError : public std::logic_error {
            public:
                explicit LaneDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class LaneAbsentError : public std::runtime_error {
            public:
                explicit LaneAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class FerryLaneLog {
            public:
                void open_lane(const std::string& lane);
                void close_lane(const std::string& lane);
                bool opened(const std::string& lane) const;
                std::size_t lanes() const;
                std::vector<std::string> log() const;
            };
            """,
            """
            class LaneDuplicateError : public std::logic_error {
            public:
                explicit LaneDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class LaneAbsentError : public std::runtime_error {
            public:
                explicit LaneAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class FerryLaneLog {
            public:
                void open_lane(const std::string& lane);
                void close_lane(const std::string& lane);
                bool opened(const std::string& lane) const;
                std::size_t lanes() const;
                std::vector<std::string> log() const;
            private:
                struct Node {
                    std::string lane;
                    std::unique_ptr<Node> upstream;
                    std::unique_ptr<Node> downstream;
                    explicit Node(std::string value);
                };
                std::unique_ptr<Node> harbor_;
                std::size_t lanes_ = 0;
                std::vector<std::string> journal_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, const std::string& lane, std::string& entry);
            };
            """,
            """
            FerryLaneLog::Node::Node(std::string value) : lane(std::move(value)) {}
            bool FerryLaneLog::opened(const std::string& lane) const {
                const Node* current = harbor_.get();
                while (current) {
                    if (lane == current->lane) return true;
                    current = lane < current->lane ? current->upstream.get() : current->downstream.get();
                }
                return false;
            }
            std::size_t FerryLaneLog::lanes() const { return lanes_; }
            std::vector<std::string> FerryLaneLog::log() const { return journal_; }
            void FerryLaneLog::open_lane(const std::string& lane) {
                if (opened(lane)) throw LaneDuplicateError("lane already open");
                if (!harbor_) {
                    journal_.push_back("open-root:" + lane);
                    harbor_ = std::make_unique<Node>(lane);
                    lanes_ = 1;
                    return;
                }
                Node* current = harbor_.get();
                for (;;) {
                    if (lane < current->lane) {
                        journal_.push_back("pass-left:" + current->lane);
                        if (!current->upstream) {
                            journal_.push_back("open-left:" + lane);
                            current->upstream = std::make_unique<Node>(lane);
                            ++lanes_;
                            return;
                        }
                        current = current->upstream.get();
                    } else {
                        journal_.push_back("pass-right:" + current->lane);
                        if (!current->downstream) {
                            journal_.push_back("open-right:" + lane);
                            current->downstream = std::make_unique<Node>(lane);
                            ++lanes_;
                            return;
                        }
                        current = current->downstream.get();
                    }
                }
            }
            std::unique_ptr<FerryLaneLog::Node> FerryLaneLog::unlink(std::unique_ptr<Node> node, const std::string& lane, std::string& entry) {
                if (!node) return nullptr;
                if (lane < node->lane) {
                    node->upstream = unlink(std::move(node->upstream), lane, entry);
                    return node;
                }
                if (node->lane < lane) {
                    node->downstream = unlink(std::move(node->downstream), lane, entry);
                    return node;
                }
                if (node->upstream && node->downstream) {
                    Node* successor = node->downstream.get();
                    while (successor->upstream) successor = successor->upstream.get();
                    entry = "successor:" + successor->lane;
                    node->lane = successor->lane;
                    std::string ignored;
                    node->downstream = unlink(std::move(node->downstream), successor->lane, ignored);
                    return node;
                }
                entry = (node->upstream || node->downstream) ? ("bypass:" + lane) : ("prune:" + lane);
                return node->upstream ? std::move(node->upstream) : std::move(node->downstream);
            }
            void FerryLaneLog::close_lane(const std::string& lane) {
                std::string entry;
                harbor_ = unlink(std::move(harbor_), lane, entry);
                if (entry.empty()) throw LaneAbsentError("lane is not open");
                journal_.push_back(entry);
                --lanes_;
            }
            """,
            """
            FerryLaneLog::Node::Node(std::string value) : lane(std::move(value)) {}
            bool FerryLaneLog::opened(const std::string& lane) const {
                const Node* current = harbor_.get();
                while (current) {
                    if (lane == current->lane) return true;
                    current = current->downstream.get();
                }
                return false;
            }
            std::size_t FerryLaneLog::lanes() const { return lanes_; }
            std::vector<std::string> FerryLaneLog::log() const { return journal_; }
            void FerryLaneLog::open_lane(const std::string& lane) {
                if (opened(lane)) throw LaneDuplicateError("lane already open");
                if (!harbor_) {
                    journal_.push_back("open-root:" + lane);
                    harbor_ = std::make_unique<Node>(lane);
                    lanes_ = 1;
                    return;
                }
                Node* current = harbor_.get();
                for (;;) {
                    journal_.push_back("pass-right:" + current->lane);
                    if (!current->downstream) {
                        journal_.push_back("open-right:" + lane);
                        current->downstream = std::make_unique<Node>(lane);
                        ++lanes_;
                        return;
                    }
                    current = current->downstream.get();
                }
            }
            void FerryLaneLog::close_lane(const std::string& lane) {
                if (!harbor_) throw LaneAbsentError("lane is not open");
                if (harbor_->lane == lane) {
                    journal_.push_back("bypass:" + lane);
                    harbor_ = std::move(harbor_->downstream);
                    --lanes_;
                    return;
                }
                Node* parent = harbor_.get();
                while (parent->downstream && parent->downstream->lane != lane) parent = parent->downstream.get();
                if (!parent->downstream) throw LaneAbsentError("lane is not open");
                journal_.push_back("bypass:" + lane);
                parent->downstream = std::move(parent->downstream->downstream);
                --lanes_;
            }
            """,
            """
            FerryLaneLog log_obj;
            log_obj.open_lane("L03");
            log_obj.open_lane("L01");
            log_obj.open_lane("L05");
            if (!log_obj.opened("L01") || log_obj.opened("L99")) return 1;
            if (log_obj.lanes() != 3U) return 2;
            log_obj.close_lane("L01");
            if (log_obj.opened("L01")) return 3;
            if (log_obj.lanes() != 2U) return 4;
            return 0;
            """,
            """
            FerryLaneLog log_obj;
            log_obj.open_lane("L03");
            log_obj.open_lane("L01");
            log_obj.open_lane("L05");
            log_obj.open_lane("L00");
            log_obj.open_lane("L02");
            log_obj.open_lane("L04");
            log_obj.open_lane("L06");
            if (log_obj.lanes() != 7U) return 1;
            bool threw = false;
            try { log_obj.open_lane("L04"); } catch (const LaneDuplicateError&) { threw = true; }
            if (!threw) return 2;
            log_obj.close_lane("L01");
            log_obj.close_lane("L03");
            log_obj.close_lane("L00");
            threw = false;
            try { log_obj.close_lane("L99"); } catch (const LaneAbsentError&) { threw = true; }
            if (!threw) return 3;
            log_obj.close_lane("L05");
            std::vector<std::string> expected = {
                "open-root:L03",
                "pass-left:L03", "open-left:L01",
                "pass-right:L03", "open-right:L05",
                "pass-left:L03", "pass-left:L01", "open-left:L00",
                "pass-left:L03", "pass-right:L01", "open-right:L02",
                "pass-right:L03", "pass-left:L05", "open-left:L04",
                "pass-right:L03", "pass-right:L05", "open-right:L06",
                "successor:L02",
                "successor:L04",
                "prune:L00",
                "bypass:L05",
            };
            if (log_obj.log() != expected) return 4;
            if (log_obj.lanes() != 3U) return 5;
            if (!log_obj.opened("L02") || log_obj.opened("L01")) return 6;
            if (!log_obj.opened("L06") || log_obj.opened("L05")) return 7;
            return 0;
            """,
            "linked lanes recording exact descent turns and removal kinds in a deterministic journal",
            "an ordered container, a sorted std::vector, or a single-sided downstream chain that ignores ordering decisions as the core store",
            "exact journal entry sequences after L03,L01,L05,L00,L02,L04,L06 opens and mixed closes, with rejected calls appending nothing",
            "deterministic mutation traces over owned nodes",
            "mutation-trace journaling ordered tree",
        ),
        c(
            "f26bst-elevator-stop-tree",
            "Elevator stop tree",
            "elevator_stop",
            """
            class StopDuplicateError : public std::runtime_error {
            public:
                explicit StopDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class StopAbsentError : public std::logic_error {
            public:
                explicit StopAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class ElevatorStopTree {
            public:
                void add_stop(std::int32_t floor_no);
                void skip_stop(std::int32_t floor_no);
                bool serves(std::int32_t floor_no) const;
                std::size_t stops() const;
                std::vector<std::string> journey_log() const;
            };
            """,
            """
            class StopDuplicateError : public std::runtime_error {
            public:
                explicit StopDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class StopAbsentError : public std::logic_error {
            public:
                explicit StopAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class ElevatorStopTree {
            public:
                void add_stop(std::int32_t floor_no);
                void skip_stop(std::int32_t floor_no);
                bool serves(std::int32_t floor_no) const;
                std::size_t stops() const;
                std::vector<std::string> journey_log() const;
            private:
                struct Node {
                    std::int32_t floor_no;
                    std::unique_ptr<Node> below;
                    std::unique_ptr<Node> above;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> shaft_;
                std::size_t stops_ = 0;
                std::vector<std::string> journal_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t floor_no, std::string& entry);
            };
            """,
            """
            ElevatorStopTree::Node::Node(std::int32_t value) : floor_no(value) {}
            bool ElevatorStopTree::serves(std::int32_t floor_no) const {
                const Node* current = shaft_.get();
                while (current) {
                    if (floor_no == current->floor_no) return true;
                    current = floor_no < current->floor_no ? current->below.get() : current->above.get();
                }
                return false;
            }
            std::size_t ElevatorStopTree::stops() const { return stops_; }
            std::vector<std::string> ElevatorStopTree::journey_log() const { return journal_; }
            void ElevatorStopTree::add_stop(std::int32_t floor_no) {
                if (serves(floor_no)) throw StopDuplicateError("floor already served");
                if (!shaft_) {
                    journal_.push_back("root:" + std::to_string(floor_no));
                    shaft_ = std::make_unique<Node>(floor_no);
                    stops_ = 1;
                    return;
                }
                Node* current = shaft_.get();
                for (;;) {
                    if (floor_no < current->floor_no) {
                        journal_.push_back("descend-down:" + std::to_string(current->floor_no));
                        if (!current->below) {
                            journal_.push_back("attach-down:" + std::to_string(floor_no));
                            current->below = std::make_unique<Node>(floor_no);
                            ++stops_;
                            return;
                        }
                        current = current->below.get();
                    } else {
                        journal_.push_back("descend-up:" + std::to_string(current->floor_no));
                        if (!current->above) {
                            journal_.push_back("attach-up:" + std::to_string(floor_no));
                            current->above = std::make_unique<Node>(floor_no);
                            ++stops_;
                            return;
                        }
                        current = current->above.get();
                    }
                }
            }
            std::unique_ptr<ElevatorStopTree::Node> ElevatorStopTree::unlink(std::unique_ptr<Node> node, std::int32_t floor_no, std::string& entry) {
                if (!node) return nullptr;
                if (floor_no < node->floor_no) {
                    node->below = unlink(std::move(node->below), floor_no, entry);
                    return node;
                }
                if (node->floor_no < floor_no) {
                    node->above = unlink(std::move(node->above), floor_no, entry);
                    return node;
                }
                if (node->below && node->above) {
                    Node* successor = node->above.get();
                    while (successor->below) successor = successor->below.get();
                    entry = "successor:" + std::to_string(successor->floor_no);
                    node->floor_no = successor->floor_no;
                    std::string ignored;
                    node->above = unlink(std::move(node->above), successor->floor_no, ignored);
                    return node;
                }
                entry = (node->below || node->above) ? ("bypass:" + std::to_string(floor_no)) : ("prune:" + std::to_string(floor_no));
                return node->below ? std::move(node->below) : std::move(node->above);
            }
            void ElevatorStopTree::skip_stop(std::int32_t floor_no) {
                std::string entry;
                shaft_ = unlink(std::move(shaft_), floor_no, entry);
                if (entry.empty()) throw StopAbsentError("floor is not served");
                journal_.push_back(entry);
                --stops_;
            }
            """,
            """
            ElevatorStopTree::Node::Node(std::int32_t value) : floor_no(value) {}
            bool ElevatorStopTree::serves(std::int32_t floor_no) const {
                const Node* current = shaft_.get();
                while (current) {
                    if (floor_no == current->floor_no) return true;
                    current = current->below.get();
                }
                return false;
            }
            std::size_t ElevatorStopTree::stops() const { return stops_; }
            std::vector<std::string> ElevatorStopTree::journey_log() const { return journal_; }
            void ElevatorStopTree::add_stop(std::int32_t floor_no) {
                if (serves(floor_no)) throw StopDuplicateError("floor already served");
                if (!shaft_) {
                    journal_.push_back("root:" + std::to_string(floor_no));
                    shaft_ = std::make_unique<Node>(floor_no);
                    stops_ = 1;
                    return;
                }
                Node* current = shaft_.get();
                for (;;) {
                    journal_.push_back("descend-down:" + std::to_string(current->floor_no));
                    if (!current->below) {
                        journal_.push_back("attach-down:" + std::to_string(floor_no));
                        current->below = std::make_unique<Node>(floor_no);
                        ++stops_;
                        return;
                    }
                    current = current->below.get();
                }
            }
            void ElevatorStopTree::skip_stop(std::int32_t floor_no) {
                if (!shaft_) throw StopAbsentError("floor is not served");
                if (shaft_->floor_no == floor_no) {
                    journal_.push_back("bypass:" + std::to_string(floor_no));
                    shaft_ = std::move(shaft_->below);
                    --stops_;
                    return;
                }
                Node* parent = shaft_.get();
                while (parent->below && parent->below->floor_no != floor_no) parent = parent->below.get();
                if (!parent->below) throw StopAbsentError("floor is not served");
                journal_.push_back("bypass:" + std::to_string(floor_no));
                parent->below = std::move(parent->below->below);
                --stops_;
            }
            """,
            """
            ElevatorStopTree tree;
            tree.add_stop(12);
            tree.add_stop(6);
            tree.add_stop(18);
            if (!tree.serves(6) || tree.serves(99)) return 1;
            if (tree.stops() != 3U) return 2;
            tree.skip_stop(6);
            if (tree.serves(6)) return 3;
            if (tree.stops() != 2U) return 4;
            return 0;
            """,
            """
            ElevatorStopTree tree;
            tree.add_stop(12);
            tree.add_stop(6);
            tree.add_stop(18);
            tree.add_stop(3);
            tree.add_stop(9);
            tree.add_stop(15);
            tree.add_stop(21);
            tree.add_stop(8);
            if (tree.stops() != 8U) return 1;
            bool threw = false;
            try { tree.add_stop(15); } catch (const StopDuplicateError&) { threw = true; }
            if (!threw) return 2;
            tree.skip_stop(6);
            tree.skip_stop(12);
            tree.skip_stop(3);
            tree.skip_stop(9);
            threw = false;
            try { tree.skip_stop(99); } catch (const StopAbsentError&) { threw = true; }
            if (!threw) return 3;
            tree.skip_stop(18);
            std::vector<std::string> expected = {
                "root:12",
                "descend-down:12", "attach-down:6",
                "descend-up:12", "attach-up:18",
                "descend-down:12", "descend-down:6", "attach-down:3",
                "descend-down:12", "descend-up:6", "attach-up:9",
                "descend-up:12", "descend-down:18", "attach-down:15",
                "descend-up:12", "descend-up:18", "attach-up:21",
                "descend-down:12", "descend-up:6", "descend-down:9", "attach-down:8",
                "successor:8",
                "successor:15",
                "prune:3",
                "prune:9",
                "bypass:18",
            };
            if (tree.journey_log() != expected) return 4;
            if (tree.stops() != 3U) return 5;
            if (!tree.serves(8) || tree.serves(6)) return 6;
            if (!tree.serves(21) || tree.serves(12)) return 7;
            return 0;
            """,
            "linked floors with up/down journey traces and successor-side skips",
            "an ordered container, a sorted std::vector, or a single-sided below chain that ignores ordering decisions as the core store",
            "exact journey entries after 12,6,18,3,9,15,21,8 adds and mixed skips, with rejected calls appending nothing",
            "vertical-domain trace vocabulary",
            "mutation-trace journaling ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-maze-junction-map",
            "Maze junction map",
            "maze_junction",
            """
            class JunctionDuplicateError : public std::invalid_argument {
            public:
                explicit JunctionDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class JunctionAbsentError : public std::out_of_range {
            public:
                explicit JunctionAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class MazeJunctionMap {
            public:
                void carve(const std::string& junction);
                void fill(const std::string& junction);
                bool carved(const std::string& junction) const;
                std::size_t junctions() const;
                std::string carve_trail() const;
            };
            """,
            """
            class JunctionDuplicateError : public std::invalid_argument {
            public:
                explicit JunctionDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class JunctionAbsentError : public std::out_of_range {
            public:
                explicit JunctionAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class MazeJunctionMap {
            public:
                void carve(const std::string& junction);
                void fill(const std::string& junction);
                bool carved(const std::string& junction) const;
                std::size_t junctions() const;
                std::string carve_trail() const;
            private:
                struct Node {
                    std::string junction;
                    std::unique_ptr<Node> earlier;
                    std::unique_ptr<Node> later;
                    explicit Node(std::string value);
                };
                std::unique_ptr<Node> maze_;
                std::size_t junctions_ = 0;
                std::vector<std::string> trail_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, const std::string& junction, std::string& entry);
            };
            """,
            """
            MazeJunctionMap::Node::Node(std::string value) : junction(std::move(value)) {}
            bool MazeJunctionMap::carved(const std::string& junction) const {
                const Node* current = maze_.get();
                while (current) {
                    if (junction == current->junction) return true;
                    current = junction < current->junction ? current->earlier.get() : current->later.get();
                }
                return false;
            }
            std::size_t MazeJunctionMap::junctions() const { return junctions_; }
            std::string MazeJunctionMap::carve_trail() const {
                std::string out;
                for (std::size_t i = 0; i < trail_.size(); ++i) {
                    if (i) out += ";";
                    out += trail_[i];
                }
                return out;
            }
            void MazeJunctionMap::carve(const std::string& junction) {
                if (carved(junction)) throw JunctionDuplicateError("junction already carved");
                if (!maze_) {
                    trail_.push_back("root(" + junction + ")");
                    maze_ = std::make_unique<Node>(junction);
                    junctions_ = 1;
                    return;
                }
                Node* current = maze_.get();
                for (;;) {
                    if (junction < current->junction) {
                        trail_.push_back("L(" + current->junction + ")");
                        if (!current->earlier) {
                            trail_.push_back("add-L(" + junction + ")");
                            current->earlier = std::make_unique<Node>(junction);
                            ++junctions_;
                            return;
                        }
                        current = current->earlier.get();
                    } else {
                        trail_.push_back("R(" + current->junction + ")");
                        if (!current->later) {
                            trail_.push_back("add-R(" + junction + ")");
                            current->later = std::make_unique<Node>(junction);
                            ++junctions_;
                            return;
                        }
                        current = current->later.get();
                    }
                }
            }
            std::unique_ptr<MazeJunctionMap::Node> MazeJunctionMap::unlink(std::unique_ptr<Node> node, const std::string& junction, std::string& entry) {
                if (!node) return nullptr;
                if (junction < node->junction) {
                    node->earlier = unlink(std::move(node->earlier), junction, entry);
                    return node;
                }
                if (node->junction < junction) {
                    node->later = unlink(std::move(node->later), junction, entry);
                    return node;
                }
                if (node->earlier && node->later) {
                    Node* successor = node->later.get();
                    while (successor->earlier) successor = successor->earlier.get();
                    entry = "swap(" + successor->junction + ")";
                    node->junction = successor->junction;
                    std::string ignored;
                    node->later = unlink(std::move(node->later), successor->junction, ignored);
                    return node;
                }
                entry = (node->earlier || node->later) ? ("skip(" + junction + ")") : ("cut(" + junction + ")");
                return node->earlier ? std::move(node->earlier) : std::move(node->later);
            }
            void MazeJunctionMap::fill(const std::string& junction) {
                std::string entry;
                maze_ = unlink(std::move(maze_), junction, entry);
                if (entry.empty()) throw JunctionAbsentError("junction is not carved");
                trail_.push_back(entry);
                --junctions_;
            }
            """,
            """
            MazeJunctionMap::Node::Node(std::string value) : junction(std::move(value)) {}
            bool MazeJunctionMap::carved(const std::string& junction) const {
                const Node* current = maze_.get();
                while (current) {
                    if (junction == current->junction) return true;
                    current = current->later.get();
                }
                return false;
            }
            std::size_t MazeJunctionMap::junctions() const { return junctions_; }
            std::string MazeJunctionMap::carve_trail() const {
                std::string out;
                for (std::size_t i = 0; i < trail_.size(); ++i) {
                    if (i) out += ";";
                    out += trail_[i];
                }
                return out;
            }
            void MazeJunctionMap::carve(const std::string& junction) {
                if (carved(junction)) throw JunctionDuplicateError("junction already carved");
                if (!maze_) {
                    trail_.push_back("root(" + junction + ")");
                    maze_ = std::make_unique<Node>(junction);
                    junctions_ = 1;
                    return;
                }
                Node* current = maze_.get();
                for (;;) {
                    trail_.push_back("R(" + current->junction + ")");
                    if (!current->later) {
                        trail_.push_back("add-R(" + junction + ")");
                        current->later = std::make_unique<Node>(junction);
                        ++junctions_;
                        return;
                    }
                    current = current->later.get();
                }
            }
            void MazeJunctionMap::fill(const std::string& junction) {
                if (!maze_) throw JunctionAbsentError("junction is not carved");
                if (maze_->junction == junction) {
                    trail_.push_back("skip(" + junction + ")");
                    maze_ = std::move(maze_->later);
                    --junctions_;
                    return;
                }
                Node* parent = maze_.get();
                while (parent->later && parent->later->junction != junction) parent = parent->later.get();
                if (!parent->later) throw JunctionAbsentError("junction is not carved");
                trail_.push_back("skip(" + junction + ")");
                parent->later = std::move(parent->later->later);
                --junctions_;
            }
            """,
            """
            MazeJunctionMap map;
            map.carve("J7");
            map.carve("J3");
            map.carve("J9");
            if (!map.carved("J3") || map.carved("ZZ")) return 1;
            if (map.junctions() != 3U) return 2;
            map.fill("J3");
            if (map.carved("J3")) return 3;
            if (map.junctions() != 2U) return 4;
            return 0;
            """,
            """
            MazeJunctionMap map;
            map.carve("J7");
            map.carve("J3");
            map.carve("J9");
            map.carve("J1");
            map.carve("J5");
            map.carve("J8");
            map.carve("JB");
            map.carve("J4");
            if (map.junctions() != 8U) return 1;
            bool threw = false;
            try { map.carve("J5"); } catch (const JunctionDuplicateError&) { threw = true; }
            if (!threw) return 2;
            map.fill("J3");
            map.fill("J7");
            map.fill("J1");
            threw = false;
            try { map.fill("ZZ"); } catch (const JunctionAbsentError&) { threw = true; }
            if (!threw) return 3;
            map.fill("J9");
            const std::string expected =
                "root(J7);L(J7);add-L(J3);R(J7);add-R(J9);"
                "L(J7);L(J3);add-L(J1);L(J7);R(J3);add-R(J5);"
                "R(J7);L(J9);add-L(J8);R(J7);R(J9);add-R(JB);"
                "L(J7);R(J3);L(J5);add-L(J4);"
                "swap(J4);swap(J8);cut(J1);skip(J9)";
            if (map.carve_trail() != expected) return 4;
            if (map.junctions() != 4U) return 5;
            if (!map.carved("J4") || map.carved("J3")) return 6;
            if (!map.carved("JB") || map.carved("J7")) return 7;
            return 0;
            """,
            "single-string trail rendering over lexicographically linked junctions",
            "an ordered container, a sorted std::vector, or a single-sided later chain that ignores ordering decisions as the core store",
            "the exact trail string after J7,J3,J9,J1,J5,J8,JB,J4 carves and mixed fills, with rejected calls appending nothing",
            "compact single-string trace rendering",
            "mutation-trace journaling ordered tree",
        ),
        c(
            "f26bst-server-rack-index",
            "Server rack index",
            "server_rack",
            """
            class RackDuplicateError : public std::logic_error {
            public:
                explicit RackDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class RackAbsentError : public std::domain_error {
            public:
                explicit RackAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class ServerRackIndex {
            public:
                void mount(std::int32_t unit);
                void unmount(std::int32_t unit);
                bool mounted(std::int32_t unit) const;
                std::size_t units() const;
                std::vector<std::string> mount_log() const;
                std::int32_t depth_of(std::int32_t unit) const;
            };
            """,
            """
            class RackDuplicateError : public std::logic_error {
            public:
                explicit RackDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class RackAbsentError : public std::domain_error {
            public:
                explicit RackAbsentError(const std::string& message) : std::domain_error(message) {}
            };
            class ServerRackIndex {
            public:
                void mount(std::int32_t unit);
                void unmount(std::int32_t unit);
                bool mounted(std::int32_t unit) const;
                std::size_t units() const;
                std::vector<std::string> mount_log() const;
                std::int32_t depth_of(std::int32_t unit) const;
            private:
                struct Node {
                    std::int32_t unit;
                    std::unique_ptr<Node> bottom_unit;
                    std::unique_ptr<Node> top_unit;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> frame_;
                std::size_t units_ = 0;
                std::vector<std::string> journal_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t unit, std::string& entry);
            };
            """,
            """
            ServerRackIndex::Node::Node(std::int32_t value) : unit(value) {}
            bool ServerRackIndex::mounted(std::int32_t unit) const {
                const Node* current = frame_.get();
                while (current) {
                    if (unit == current->unit) return true;
                    current = unit < current->unit ? current->bottom_unit.get() : current->top_unit.get();
                }
                return false;
            }
            std::size_t ServerRackIndex::units() const { return units_; }
            std::vector<std::string> ServerRackIndex::mount_log() const { return journal_; }
            void ServerRackIndex::mount(std::int32_t unit) {
                if (mounted(unit)) throw RackDuplicateError("unit already mounted");
                if (!frame_) {
                    journal_.push_back("root:" + std::to_string(unit));
                    frame_ = std::make_unique<Node>(unit);
                    units_ = 1;
                    return;
                }
                Node* current = frame_.get();
                std::int32_t depth = 0;
                for (;;) {
                    ++depth;
                    if (unit < current->unit) {
                        if (!current->bottom_unit) {
                            journal_.push_back("attach-left:" + std::to_string(unit) + "@d" + std::to_string(depth));
                            current->bottom_unit = std::make_unique<Node>(unit);
                            ++units_;
                            return;
                        }
                        current = current->bottom_unit.get();
                    } else {
                        if (!current->top_unit) {
                            journal_.push_back("attach-right:" + std::to_string(unit) + "@d" + std::to_string(depth));
                            current->top_unit = std::make_unique<Node>(unit);
                            ++units_;
                            return;
                        }
                        current = current->top_unit.get();
                    }
                }
            }
            std::unique_ptr<ServerRackIndex::Node> ServerRackIndex::unlink(std::unique_ptr<Node> node, std::int32_t unit, std::string& entry) {
                if (!node) return nullptr;
                if (unit < node->unit) {
                    node->bottom_unit = unlink(std::move(node->bottom_unit), unit, entry);
                    return node;
                }
                if (node->unit < unit) {
                    node->top_unit = unlink(std::move(node->top_unit), unit, entry);
                    return node;
                }
                if (node->bottom_unit && node->top_unit) {
                    Node* successor = node->top_unit.get();
                    while (successor->bottom_unit) successor = successor->bottom_unit.get();
                    entry = "successor:" + std::to_string(successor->unit);
                    node->unit = successor->unit;
                    std::string ignored;
                    node->top_unit = unlink(std::move(node->top_unit), successor->unit, ignored);
                    return node;
                }
                entry = (node->bottom_unit || node->top_unit) ? ("bypass:" + std::to_string(unit)) : ("prune:" + std::to_string(unit));
                return node->bottom_unit ? std::move(node->bottom_unit) : std::move(node->top_unit);
            }
            void ServerRackIndex::unmount(std::int32_t unit) {
                std::string entry;
                frame_ = unlink(std::move(frame_), unit, entry);
                if (entry.empty()) throw RackAbsentError("unit is not mounted");
                journal_.push_back(entry);
                --units_;
            }
            std::int32_t ServerRackIndex::depth_of(std::int32_t unit) const {
                const Node* current = frame_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (unit == current->unit) return depth;
                    ++depth;
                    current = unit < current->unit ? current->bottom_unit.get() : current->top_unit.get();
                }
                throw RackAbsentError("unit is not mounted");
            }
            """,
            """
            ServerRackIndex::Node::Node(std::int32_t value) : unit(value) {}
            bool ServerRackIndex::mounted(std::int32_t unit) const {
                const Node* current = frame_.get();
                while (current) {
                    if (unit == current->unit) return true;
                    current = current->bottom_unit.get();
                }
                return false;
            }
            std::size_t ServerRackIndex::units() const { return units_; }
            std::vector<std::string> ServerRackIndex::mount_log() const { return journal_; }
            void ServerRackIndex::mount(std::int32_t unit) {
                if (mounted(unit)) throw RackDuplicateError("unit already mounted");
                if (!frame_) {
                    journal_.push_back("root:" + std::to_string(unit));
                    frame_ = std::make_unique<Node>(unit);
                    units_ = 1;
                    return;
                }
                Node* current = frame_.get();
                std::int32_t depth = 0;
                for (;;) {
                    ++depth;
                    if (!current->bottom_unit) {
                        journal_.push_back("attach-left:" + std::to_string(unit) + "@d" + std::to_string(depth));
                        current->bottom_unit = std::make_unique<Node>(unit);
                        ++units_;
                        return;
                    }
                    current = current->bottom_unit.get();
                }
            }
            void ServerRackIndex::unmount(std::int32_t unit) {
                if (!frame_) throw RackAbsentError("unit is not mounted");
                if (frame_->unit == unit) {
                    journal_.push_back("bypass:" + std::to_string(unit));
                    frame_ = std::move(frame_->bottom_unit);
                    --units_;
                    return;
                }
                Node* parent = frame_.get();
                while (parent->bottom_unit && parent->bottom_unit->unit != unit) parent = parent->bottom_unit.get();
                if (!parent->bottom_unit) throw RackAbsentError("unit is not mounted");
                journal_.push_back("bypass:" + std::to_string(unit));
                parent->bottom_unit = std::move(parent->bottom_unit->bottom_unit);
                --units_;
            }
            std::int32_t ServerRackIndex::depth_of(std::int32_t unit) const {
                const Node* current = frame_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (unit == current->unit) return depth;
                    ++depth;
                    current = current->bottom_unit.get();
                }
                throw RackAbsentError("unit is not mounted");
            }
            """,
            """
            ServerRackIndex index;
            index.mount(42);
            index.mount(17);
            index.mount(68);
            if (!index.mounted(17) || index.mounted(99)) return 1;
            if (index.units() != 3U) return 2;
            index.unmount(17);
            if (index.mounted(17)) return 3;
            if (index.units() != 2U) return 4;
            return 0;
            """,
            """
            ServerRackIndex index;
            index.mount(42);
            index.mount(17);
            index.mount(68);
            index.mount(9);
            index.mount(25);
            index.mount(54);
            index.mount(71);
            index.mount(35);
            if (index.units() != 8U) return 1;
            bool threw = false;
            try { index.mount(54); } catch (const RackDuplicateError&) { threw = true; }
            if (!threw) return 2;
            index.unmount(17);
            index.unmount(42);
            index.unmount(9);
            threw = false;
            try { index.unmount(999); } catch (const RackAbsentError&) { threw = true; }
            if (!threw) return 3;
            index.unmount(25);
            std::vector<std::string> expected = {
                "root:42",
                "attach-left:17@d1",
                "attach-right:68@d1",
                "attach-left:9@d2",
                "attach-right:25@d2",
                "attach-left:54@d2",
                "attach-right:71@d2",
                "attach-right:35@d3",
                "successor:25",
                "successor:54",
                "prune:9",
                "bypass:25",
            };
            if (index.mount_log() != expected) return 4;
            if (index.units() != 4U) return 5;
            if (index.depth_of(35) != 1) return 6;
            if (index.depth_of(54) != 0) return 7;
            if (index.depth_of(71) != 2) return 8;
            threw = false;
            try { index.depth_of(17); } catch (const RackAbsentError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "depth-annotated mount traces over insertion-ordered linked units",
            "an ordered container, a sorted std::vector, or a single-sided bottom-unit chain that ignores ordering decisions as the core store",
            "exact log entries and depths after 42,17,68,9,25,54,71,35 mounts and mixed unmounts, with rejected calls appending nothing",
            "traces coupled with structural depth annotations",
            "mutation-trace journaling ordered tree",
        ),
        c(
            "f26bst-greenhouse-row-journal",
            "Greenhouse row journal",
            "greenhouse_row",
            """
            class RowSownError : public std::runtime_error {
            public:
                explicit RowSownError(const std::string& message) : std::runtime_error(message) {}
            };
            class RowMissingError : public std::logic_error {
            public:
                explicit RowMissingError(const std::string& message) : std::logic_error(message) {}
            };
            class GreenhouseRowJournal {
            public:
                void sow(std::int32_t row);
                void pull(std::int32_t row);
                bool sown(std::int32_t row) const;
                std::size_t rows() const;
                std::vector<std::string> journal() const;
            };
            """,
            """
            class RowSownError : public std::runtime_error {
            public:
                explicit RowSownError(const std::string& message) : std::runtime_error(message) {}
            };
            class RowMissingError : public std::logic_error {
            public:
                explicit RowMissingError(const std::string& message) : std::logic_error(message) {}
            };
            class GreenhouseRowJournal {
            public:
                void sow(std::int32_t row);
                void pull(std::int32_t row);
                bool sown(std::int32_t row) const;
                std::size_t rows() const;
                std::vector<std::string> journal() const;
            private:
                struct Node {
                    std::int32_t row;
                    std::unique_ptr<Node> early_row;
                    std::unique_ptr<Node> late_row;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> bed_;
                std::size_t rows_ = 0;
                std::vector<std::string> journal_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t row, std::string& entry);
            };
            """,
            """
            GreenhouseRowJournal::Node::Node(std::int32_t value) : row(value) {}
            bool GreenhouseRowJournal::sown(std::int32_t row) const {
                const Node* current = bed_.get();
                while (current) {
                    if (row == current->row) return true;
                    current = row < current->row ? current->early_row.get() : current->late_row.get();
                }
                return false;
            }
            std::size_t GreenhouseRowJournal::rows() const { return rows_; }
            std::vector<std::string> GreenhouseRowJournal::journal() const { return journal_; }
            void GreenhouseRowJournal::sow(std::int32_t row) {
                if (sown(row)) throw RowSownError("row already sown");
                if (!bed_) {
                    journal_.push_back("root:" + std::to_string(row));
                    bed_ = std::make_unique<Node>(row);
                    rows_ = 1;
                    return;
                }
                Node* current = bed_.get();
                for (;;) {
                    if (row < current->row) {
                        journal_.push_back("left-of:" + std::to_string(current->row));
                        if (!current->early_row) {
                            journal_.push_back("bed-left:" + std::to_string(row));
                            current->early_row = std::make_unique<Node>(row);
                            ++rows_;
                            return;
                        }
                        current = current->early_row.get();
                    } else {
                        journal_.push_back("right-of:" + std::to_string(current->row));
                        if (!current->late_row) {
                            journal_.push_back("bed-right:" + std::to_string(row));
                            current->late_row = std::make_unique<Node>(row);
                            ++rows_;
                            return;
                        }
                        current = current->late_row.get();
                    }
                }
            }
            std::unique_ptr<GreenhouseRowJournal::Node> GreenhouseRowJournal::unlink(std::unique_ptr<Node> node, std::int32_t row, std::string& entry) {
                if (!node) return nullptr;
                if (row < node->row) {
                    node->early_row = unlink(std::move(node->early_row), row, entry);
                    return node;
                }
                if (node->row < row) {
                    node->late_row = unlink(std::move(node->late_row), row, entry);
                    return node;
                }
                if (node->early_row && node->late_row) {
                    Node* successor = node->late_row.get();
                    while (successor->early_row) successor = successor->early_row.get();
                    entry = "relay:" + std::to_string(successor->row);
                    node->row = successor->row;
                    std::string ignored;
                    node->late_row = unlink(std::move(node->late_row), successor->row, ignored);
                    return node;
                }
                entry = (node->early_row || node->late_row) ? ("bridge:" + std::to_string(row)) : ("rake:" + std::to_string(row));
                return node->early_row ? std::move(node->early_row) : std::move(node->late_row);
            }
            void GreenhouseRowJournal::pull(std::int32_t row) {
                std::string entry;
                bed_ = unlink(std::move(bed_), row, entry);
                if (entry.empty()) throw RowMissingError("row is not sown");
                journal_.push_back(entry);
                --rows_;
            }
            """,
            """
            GreenhouseRowJournal::Node::Node(std::int32_t value) : row(value) {}
            bool GreenhouseRowJournal::sown(std::int32_t row) const {
                const Node* current = bed_.get();
                while (current) {
                    if (row == current->row) return true;
                    current = current->late_row.get();
                }
                return false;
            }
            std::size_t GreenhouseRowJournal::rows() const { return rows_; }
            std::vector<std::string> GreenhouseRowJournal::journal() const { return journal_; }
            void GreenhouseRowJournal::sow(std::int32_t row) {
                if (sown(row)) throw RowSownError("row already sown");
                if (!bed_) {
                    journal_.push_back("root:" + std::to_string(row));
                    bed_ = std::make_unique<Node>(row);
                    rows_ = 1;
                    return;
                }
                Node* current = bed_.get();
                for (;;) {
                    journal_.push_back("right-of:" + std::to_string(current->row));
                    if (!current->late_row) {
                        journal_.push_back("bed-right:" + std::to_string(row));
                        current->late_row = std::make_unique<Node>(row);
                        ++rows_;
                        return;
                    }
                    current = current->late_row.get();
                }
            }
            void GreenhouseRowJournal::pull(std::int32_t row) {
                if (!bed_) throw RowMissingError("row is not sown");
                if (bed_->row == row) {
                    journal_.push_back("bridge:" + std::to_string(row));
                    bed_ = std::move(bed_->late_row);
                    --rows_;
                    return;
                }
                Node* parent = bed_.get();
                while (parent->late_row && parent->late_row->row != row) parent = parent->late_row.get();
                if (!parent->late_row) throw RowMissingError("row is not sown");
                journal_.push_back("bridge:" + std::to_string(row));
                parent->late_row = std::move(parent->late_row->late_row);
                --rows_;
            }
            """,
            """
            GreenhouseRowJournal journal_obj;
            journal_obj.sow(24);
            journal_obj.sow(12);
            journal_obj.sow(36);
            if (!journal_obj.sown(12) || journal_obj.sown(99)) return 1;
            if (journal_obj.rows() != 3U) return 2;
            journal_obj.pull(12);
            if (journal_obj.sown(12)) return 3;
            if (journal_obj.rows() != 2U) return 4;
            return 0;
            """,
            """
            GreenhouseRowJournal journal_obj;
            journal_obj.sow(24);
            journal_obj.sow(12);
            journal_obj.sow(36);
            journal_obj.sow(6);
            journal_obj.sow(18);
            journal_obj.sow(30);
            journal_obj.sow(42);
            journal_obj.sow(15);
            if (journal_obj.rows() != 8U) return 1;
            bool threw = false;
            try { journal_obj.sow(18); } catch (const RowSownError&) { threw = true; }
            if (!threw) return 2;
            journal_obj.pull(12);
            journal_obj.pull(24);
            journal_obj.pull(6);
            threw = false;
            try { journal_obj.pull(99); } catch (const RowMissingError&) { threw = true; }
            if (!threw) return 3;
            journal_obj.pull(36);
            std::vector<std::string> expected = {
                "root:24",
                "left-of:24", "bed-left:12",
                "right-of:24", "bed-right:36",
                "left-of:24", "left-of:12", "bed-left:6",
                "left-of:24", "right-of:12", "bed-right:18",
                "right-of:24", "left-of:36", "bed-left:30",
                "right-of:24", "right-of:36", "bed-right:42",
                "left-of:24", "right-of:12", "left-of:18", "bed-left:15",
                "relay:15",
                "relay:30",
                "rake:6",
                "bridge:36",
            };
            if (journal_obj.journal() != expected) return 4;
            if (journal_obj.rows() != 4U) return 5;
            if (!journal_obj.sown(15) || journal_obj.sown(12)) return 6;
            if (!journal_obj.sown(42) || journal_obj.sown(24)) return 7;
            return 0;
            """,
            "horticultural trace vocabulary over insertion-ordered linked rows",
            "an ordered container, a sorted std::vector, or a single-sided late-row chain that ignores ordering decisions as the core store",
            "exact journal entries after 24,12,36,6,18,30,42,15 sowing and mixed pulls, with rejected calls appending nothing",
            "a third trace grammar with removal verbs",
            "mutation-trace journaling ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-hangar-bay-line",
            "Hangar bay line",
            "hangar_bay",
            """
            class BayParkedError : public std::invalid_argument {
            public:
                explicit BayParkedError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BayMissingError : public std::out_of_range {
            public:
                explicit BayMissingError(const std::string& message) : std::out_of_range(message) {}
            };
            class HangarBayLine {
            public:
                void park(std::int32_t bay);
                void tow(std::int32_t bay);
                bool parked(std::int32_t bay) const;
                std::size_t bays() const;
                std::vector<std::string> tow_log() const;
                std::int32_t depth_of(std::int32_t bay) const;
            };
            """,
            """
            class BayParkedError : public std::invalid_argument {
            public:
                explicit BayParkedError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BayMissingError : public std::out_of_range {
            public:
                explicit BayMissingError(const std::string& message) : std::out_of_range(message) {}
            };
            class HangarBayLine {
            public:
                void park(std::int32_t bay);
                void tow(std::int32_t bay);
                bool parked(std::int32_t bay) const;
                std::size_t bays() const;
                std::vector<std::string> tow_log() const;
                std::int32_t depth_of(std::int32_t bay) const;
            private:
                struct Node {
                    std::int32_t bay;
                    std::unique_ptr<Node> port_bay;
                    std::unique_ptr<Node> starboard_bay;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> apron_;
                std::size_t bays_ = 0;
                std::vector<std::string> journal_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t bay, std::string& entry);
            };
            """,
            """
            HangarBayLine::Node::Node(std::int32_t value) : bay(value) {}
            bool HangarBayLine::parked(std::int32_t bay) const {
                const Node* current = apron_.get();
                while (current) {
                    if (bay == current->bay) return true;
                    current = bay < current->bay ? current->port_bay.get() : current->starboard_bay.get();
                }
                return false;
            }
            std::size_t HangarBayLine::bays() const { return bays_; }
            std::vector<std::string> HangarBayLine::tow_log() const { return journal_; }
            void HangarBayLine::park(std::int32_t bay) {
                if (parked(bay)) throw BayParkedError("bay already parked");
                if (!apron_) {
                    journal_.push_back("anchor:" + std::to_string(bay));
                    apron_ = std::make_unique<Node>(bay);
                    bays_ = 1;
                    return;
                }
                Node* current = apron_.get();
                for (;;) {
                    if (bay < current->bay) {
                        journal_.push_back("turn-port:" + std::to_string(current->bay));
                        if (!current->port_bay) {
                            journal_.push_back("slot-port:" + std::to_string(bay));
                            current->port_bay = std::make_unique<Node>(bay);
                            ++bays_;
                            return;
                        }
                        current = current->port_bay.get();
                    } else {
                        journal_.push_back("turn-starboard:" + std::to_string(current->bay));
                        if (!current->starboard_bay) {
                            journal_.push_back("slot-starboard:" + std::to_string(bay));
                            current->starboard_bay = std::make_unique<Node>(bay);
                            ++bays_;
                            return;
                        }
                        current = current->starboard_bay.get();
                    }
                }
            }
            std::unique_ptr<HangarBayLine::Node> HangarBayLine::unlink(std::unique_ptr<Node> node, std::int32_t bay, std::string& entry) {
                if (!node) return nullptr;
                if (bay < node->bay) {
                    node->port_bay = unlink(std::move(node->port_bay), bay, entry);
                    return node;
                }
                if (node->bay < bay) {
                    node->starboard_bay = unlink(std::move(node->starboard_bay), bay, entry);
                    return node;
                }
                if (node->port_bay && node->starboard_bay) {
                    Node* successor = node->starboard_bay.get();
                    while (successor->port_bay) successor = successor->port_bay.get();
                    entry = "relief:" + std::to_string(successor->bay);
                    node->bay = successor->bay;
                    std::string ignored;
                    node->starboard_bay = unlink(std::move(node->starboard_bay), successor->bay, ignored);
                    return node;
                }
                entry = (node->port_bay || node->starboard_bay) ? ("shunt:" + std::to_string(bay)) : ("winch:" + std::to_string(bay));
                return node->port_bay ? std::move(node->port_bay) : std::move(node->starboard_bay);
            }
            void HangarBayLine::tow(std::int32_t bay) {
                std::string entry;
                apron_ = unlink(std::move(apron_), bay, entry);
                if (entry.empty()) throw BayMissingError("bay is not parked");
                journal_.push_back(entry);
                --bays_;
            }
            std::int32_t HangarBayLine::depth_of(std::int32_t bay) const {
                const Node* current = apron_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bay == current->bay) return depth;
                    ++depth;
                    current = bay < current->bay ? current->port_bay.get() : current->starboard_bay.get();
                }
                throw BayMissingError("bay is not parked");
            }
            """,
            """
            HangarBayLine::Node::Node(std::int32_t value) : bay(value) {}
            bool HangarBayLine::parked(std::int32_t bay) const {
                const Node* current = apron_.get();
                while (current) {
                    if (bay == current->bay) return true;
                    current = current->port_bay.get();
                }
                return false;
            }
            std::size_t HangarBayLine::bays() const { return bays_; }
            std::vector<std::string> HangarBayLine::tow_log() const { return journal_; }
            void HangarBayLine::park(std::int32_t bay) {
                if (parked(bay)) throw BayParkedError("bay already parked");
                if (!apron_) {
                    journal_.push_back("anchor:" + std::to_string(bay));
                    apron_ = std::make_unique<Node>(bay);
                    bays_ = 1;
                    return;
                }
                Node* current = apron_.get();
                for (;;) {
                    journal_.push_back("turn-port:" + std::to_string(current->bay));
                    if (!current->port_bay) {
                        journal_.push_back("slot-port:" + std::to_string(bay));
                        current->port_bay = std::make_unique<Node>(bay);
                        ++bays_;
                        return;
                    }
                    current = current->port_bay.get();
                }
            }
            void HangarBayLine::tow(std::int32_t bay) {
                if (!apron_) throw BayMissingError("bay is not parked");
                if (apron_->bay == bay) {
                    journal_.push_back("shunt:" + std::to_string(bay));
                    apron_ = std::move(apron_->port_bay);
                    --bays_;
                    return;
                }
                Node* parent = apron_.get();
                while (parent->port_bay && parent->port_bay->bay != bay) parent = parent->port_bay.get();
                if (!parent->port_bay) throw BayMissingError("bay is not parked");
                journal_.push_back("shunt:" + std::to_string(bay));
                parent->port_bay = std::move(parent->port_bay->port_bay);
                --bays_;
            }
            std::int32_t HangarBayLine::depth_of(std::int32_t bay) const {
                const Node* current = apron_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (bay == current->bay) return depth;
                    ++depth;
                    current = current->port_bay.get();
                }
                throw BayMissingError("bay is not parked");
            }
            """,
            """
            HangarBayLine line;
            line.park(60);
            line.park(30);
            line.park(90);
            if (!line.parked(30) || line.parked(999)) return 1;
            if (line.bays() != 3U) return 2;
            line.tow(30);
            if (line.parked(30)) return 3;
            if (line.bays() != 2U) return 4;
            return 0;
            """,
            """
            HangarBayLine line;
            line.park(60);
            line.park(30);
            line.park(90);
            line.park(15);
            line.park(45);
            line.park(75);
            line.park(105);
            line.park(38);
            if (line.bays() != 8U) return 1;
            bool threw = false;
            try { line.park(45); } catch (const BayParkedError&) { threw = true; }
            if (!threw) return 2;
            line.tow(30);
            line.tow(60);
            line.tow(15);
            threw = false;
            try { line.tow(999); } catch (const BayMissingError&) { threw = true; }
            if (!threw) return 3;
            line.tow(90);
            std::vector<std::string> expected = {
                "anchor:60",
                "turn-port:60", "slot-port:30",
                "turn-starboard:60", "slot-starboard:90",
                "turn-port:60", "turn-port:30", "slot-port:15",
                "turn-port:60", "turn-starboard:30", "slot-starboard:45",
                "turn-starboard:60", "turn-port:90", "slot-port:75",
                "turn-starboard:60", "turn-starboard:90", "slot-starboard:105",
                "turn-port:60", "turn-starboard:30", "turn-port:45", "slot-port:38",
                "relief:38",
                "relief:75",
                "winch:15",
                "shunt:90",
            };
            if (line.tow_log() != expected) return 4;
            if (line.bays() != 4U) return 5;
            if (line.depth_of(45) != 2) return 6;
            if (line.depth_of(75) != 0) return 7;
            threw = false;
            try { line.depth_of(30); } catch (const BayMissingError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "aviation trace vocabulary over insertion-ordered linked bays",
            "an ordered container, a sorted std::vector, or a single-sided port-bay chain that ignores ordering decisions as the core store",
            "exact tow-log entries after 60,30,90,15,45,75,105,38 parks and mixed tows, with rejected calls appending nothing",
            "nautical-aviation trace vocabulary with depths",
            "mutation-trace journaling ordered tree",
        ),
        c(
            "f26bst-gallery-hang-route",
            "Gallery hang route",
            "gallery_hang",
            """
            class PieceHungError : public std::logic_error {
            public:
                explicit PieceHungError(const std::string& message) : std::logic_error(message) {}
            };
            class PieceMissingError : public std::runtime_error {
            public:
                explicit PieceMissingError(const std::string& message) : std::runtime_error(message) {}
            };
            class GalleryHangRoute {
            public:
                void hang(const std::string& piece);
                void lift(const std::string& piece);
                bool hung(const std::string& piece) const;
                std::size_t pieces() const;
                std::string hang_route() const;
                std::int32_t depth_of(const std::string& piece) const;
            };
            """,
            """
            class PieceHungError : public std::logic_error {
            public:
                explicit PieceHungError(const std::string& message) : std::logic_error(message) {}
            };
            class PieceMissingError : public std::runtime_error {
            public:
                explicit PieceMissingError(const std::string& message) : std::runtime_error(message) {}
            };
            class GalleryHangRoute {
            public:
                void hang(const std::string& piece);
                void lift(const std::string& piece);
                bool hung(const std::string& piece) const;
                std::size_t pieces() const;
                std::string hang_route() const;
                std::int32_t depth_of(const std::string& piece) const;
            private:
                struct Node {
                    std::string piece;
                    std::unique_ptr<Node> small_piece;
                    std::unique_ptr<Node> large_piece;
                    explicit Node(std::string value);
                };
                std::unique_ptr<Node> wall_;
                std::size_t pieces_ = 0;
                std::vector<std::string> route_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, const std::string& piece, std::string& entry);
            };
            """,
            """
            GalleryHangRoute::Node::Node(std::string value) : piece(std::move(value)) {}
            bool GalleryHangRoute::hung(const std::string& piece) const {
                const Node* current = wall_.get();
                while (current) {
                    if (piece == current->piece) return true;
                    current = piece < current->piece ? current->small_piece.get() : current->large_piece.get();
                }
                return false;
            }
            std::size_t GalleryHangRoute::pieces() const { return pieces_; }
            std::string GalleryHangRoute::hang_route() const {
                std::string out;
                for (std::size_t i = 0; i < route_.size(); ++i) {
                    if (i) out += " -> ";
                    out += route_[i];
                }
                return out;
            }
            void GalleryHangRoute::hang(const std::string& piece) {
                if (hung(piece)) throw PieceHungError("piece already hung");
                if (!wall_) {
                    route_.push_back("root=" + piece);
                    wall_ = std::make_unique<Node>(piece);
                    pieces_ = 1;
                    return;
                }
                Node* current = wall_.get();
                for (;;) {
                    if (piece < current->piece) {
                        route_.push_back("left-of=" + current->piece);
                        if (!current->small_piece) {
                            route_.push_back("hook-left=" + piece);
                            current->small_piece = std::make_unique<Node>(piece);
                            ++pieces_;
                            return;
                        }
                        current = current->small_piece.get();
                    } else {
                        route_.push_back("right-of=" + current->piece);
                        if (!current->large_piece) {
                            route_.push_back("hook-right=" + piece);
                            current->large_piece = std::make_unique<Node>(piece);
                            ++pieces_;
                            return;
                        }
                        current = current->large_piece.get();
                    }
                }
            }
            std::unique_ptr<GalleryHangRoute::Node> GalleryHangRoute::unlink(std::unique_ptr<Node> node, const std::string& piece, std::string& entry) {
                if (!node) return nullptr;
                if (piece < node->piece) {
                    node->small_piece = unlink(std::move(node->small_piece), piece, entry);
                    return node;
                }
                if (node->piece < piece) {
                    node->large_piece = unlink(std::move(node->large_piece), piece, entry);
                    return node;
                }
                if (node->small_piece && node->large_piece) {
                    Node* successor = node->large_piece.get();
                    while (successor->small_piece) successor = successor->small_piece.get();
                    entry = "relay=" + successor->piece;
                    node->piece = successor->piece;
                    std::string ignored;
                    node->large_piece = unlink(std::move(node->large_piece), successor->piece, ignored);
                    return node;
                }
                entry = (node->small_piece || node->large_piece) ? ("swing=" + piece) : ("unhook=" + piece);
                return node->small_piece ? std::move(node->small_piece) : std::move(node->large_piece);
            }
            void GalleryHangRoute::lift(const std::string& piece) {
                std::string entry;
                wall_ = unlink(std::move(wall_), piece, entry);
                if (entry.empty()) throw PieceMissingError("piece is not hung");
                route_.push_back(entry);
                --pieces_;
            }
            std::int32_t GalleryHangRoute::depth_of(const std::string& piece) const {
                const Node* current = wall_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (piece == current->piece) return depth;
                    ++depth;
                    current = piece < current->piece ? current->small_piece.get() : current->large_piece.get();
                }
                throw PieceMissingError("piece is not hung");
            }
            """,
            """
            GalleryHangRoute::Node::Node(std::string value) : piece(std::move(value)) {}
            bool GalleryHangRoute::hung(const std::string& piece) const {
                const Node* current = wall_.get();
                while (current) {
                    if (piece == current->piece) return true;
                    current = current->large_piece.get();
                }
                return false;
            }
            std::size_t GalleryHangRoute::pieces() const { return pieces_; }
            std::string GalleryHangRoute::hang_route() const {
                std::string out;
                for (std::size_t i = 0; i < route_.size(); ++i) {
                    if (i) out += " -> ";
                    out += route_[i];
                }
                return out;
            }
            void GalleryHangRoute::hang(const std::string& piece) {
                if (hung(piece)) throw PieceHungError("piece already hung");
                if (!wall_) {
                    route_.push_back("root=" + piece);
                    wall_ = std::make_unique<Node>(piece);
                    pieces_ = 1;
                    return;
                }
                Node* current = wall_.get();
                for (;;) {
                    route_.push_back("right-of=" + current->piece);
                    if (!current->large_piece) {
                        route_.push_back("hook-right=" + piece);
                        current->large_piece = std::make_unique<Node>(piece);
                        ++pieces_;
                        return;
                    }
                    current = current->large_piece.get();
                }
            }
            void GalleryHangRoute::lift(const std::string& piece) {
                if (!wall_) throw PieceMissingError("piece is not hung");
                if (wall_->piece == piece) {
                    route_.push_back("swing=" + piece);
                    wall_ = std::move(wall_->large_piece);
                    --pieces_;
                    return;
                }
                Node* parent = wall_.get();
                while (parent->large_piece && parent->large_piece->piece != piece) parent = parent->large_piece.get();
                if (!parent->large_piece) throw PieceMissingError("piece is not hung");
                route_.push_back("swing=" + piece);
                parent->large_piece = std::move(parent->large_piece->large_piece);
                --pieces_;
            }
            std::int32_t GalleryHangRoute::depth_of(const std::string& piece) const {
                const Node* current = wall_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (piece == current->piece) return depth;
                    ++depth;
                    current = current->large_piece.get();
                }
                throw PieceMissingError("piece is not hung");
            }
            """,
            """
            GalleryHangRoute route_obj;
            route_obj.hang("E05");
            route_obj.hang("E02");
            route_obj.hang("E08");
            if (!route_obj.hung("E02") || route_obj.hung("E99")) return 1;
            if (route_obj.pieces() != 3U) return 2;
            route_obj.lift("E02");
            if (route_obj.hung("E02")) return 3;
            if (route_obj.pieces() != 2U) return 4;
            return 0;
            """,
            """
            GalleryHangRoute route_obj;
            route_obj.hang("E05");
            route_obj.hang("E02");
            route_obj.hang("E08");
            route_obj.hang("E01");
            route_obj.hang("E04");
            route_obj.hang("E07");
            route_obj.hang("E09");
            route_obj.hang("E03");
            if (route_obj.pieces() != 8U) return 1;
            bool threw = false;
            try { route_obj.hang("E04"); } catch (const PieceHungError&) { threw = true; }
            if (!threw) return 2;
            route_obj.lift("E02");
            route_obj.lift("E05");
            route_obj.lift("E01");
            threw = false;
            try { route_obj.lift("E99"); } catch (const PieceMissingError&) { threw = true; }
            if (!threw) return 3;
            route_obj.lift("E08");
            const std::string expected =
                "root=E05 -> left-of=E05 -> hook-left=E02 -> right-of=E05 -> hook-right=E08 -> "
                "left-of=E05 -> left-of=E02 -> hook-left=E01 -> left-of=E05 -> right-of=E02 -> hook-right=E04 -> "
                "right-of=E05 -> left-of=E08 -> hook-left=E07 -> right-of=E05 -> right-of=E08 -> hook-right=E09 -> "
                "left-of=E05 -> right-of=E02 -> left-of=E04 -> hook-left=E03 -> "
                "relay=E03 -> relay=E07 -> unhook=E01 -> swing=E08";
            if (route_obj.hang_route() != expected) return 4;
            if (route_obj.pieces() != 4U) return 5;
            if (route_obj.depth_of("E04") != 2) return 6;
            if (route_obj.depth_of("E07") != 0) return 7;
            threw = false;
            try { route_obj.depth_of("E02"); } catch (const PieceMissingError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "gallery trace grammar over string-keyed linked pieces",
            "an ordered container, a sorted std::vector, or a single-sided large-piece chain that ignores ordering decisions as the core store",
            "the exact route string after E05,E02,E08,E01,E04,E07,E09,E03 hangs and mixed lifts, with rejected calls appending nothing",
            "equative trace rendering over string keys",
            "mutation-trace journaling ordered tree",
        ),
        c(
            "f26bst-canyon-camp-sites",
            "Canyon camp sites",
            "canyon_camp",
            """
            class SitePitchedError : public std::domain_error {
            public:
                explicit SitePitchedError(const std::string& message) : std::domain_error(message) {}
            };
            class SiteMissingError : public std::logic_error {
            public:
                explicit SiteMissingError(const std::string& message) : std::logic_error(message) {}
            };
            class CanyonCampSites {
            public:
                void pitch(std::int64_t site);
                void strike(std::int64_t site);
                bool pitched(std::int64_t site) const;
                std::size_t sites() const;
                std::vector<std::string> pitch_trail() const;
            };
            """,
            """
            class SitePitchedError : public std::domain_error {
            public:
                explicit SitePitchedError(const std::string& message) : std::domain_error(message) {}
            };
            class SiteMissingError : public std::logic_error {
            public:
                explicit SiteMissingError(const std::string& message) : std::logic_error(message) {}
            };
            class CanyonCampSites {
            public:
                void pitch(std::int64_t site);
                void strike(std::int64_t site);
                bool pitched(std::int64_t site) const;
                std::size_t sites() const;
                std::vector<std::string> pitch_trail() const;
            private:
                struct Node {
                    std::int64_t site;
                    std::unique_ptr<Node> down_camp;
                    std::unique_ptr<Node> up_camp;
                    explicit Node(std::int64_t value);
                };
                std::unique_ptr<Node> ridge_;
                std::size_t sites_ = 0;
                std::vector<std::string> journal_;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int64_t site, std::string& entry);
            };
            """,
            """
            CanyonCampSites::Node::Node(std::int64_t value) : site(value) {}
            bool CanyonCampSites::pitched(std::int64_t site) const {
                const Node* current = ridge_.get();
                while (current) {
                    if (site == current->site) return true;
                    current = site < current->site ? current->down_camp.get() : current->up_camp.get();
                }
                return false;
            }
            std::size_t CanyonCampSites::sites() const { return sites_; }
            std::vector<std::string> CanyonCampSites::pitch_trail() const { return journal_; }
            void CanyonCampSites::pitch(std::int64_t site) {
                if (pitched(site)) throw SitePitchedError("site already pitched");
                if (!ridge_) {
                    journal_.push_back("base:" + std::to_string(site));
                    ridge_ = std::make_unique<Node>(site);
                    sites_ = 1;
                    return;
                }
                Node* current = ridge_.get();
                for (;;) {
                    if (site < current->site) {
                        journal_.push_back("drop:" + std::to_string(current->site));
                        if (!current->down_camp) {
                            journal_.push_back("camp-low:" + std::to_string(site));
                            current->down_camp = std::make_unique<Node>(site);
                            ++sites_;
                            return;
                        }
                        current = current->down_camp.get();
                    } else {
                        journal_.push_back("rise:" + std::to_string(current->site));
                        if (!current->up_camp) {
                            journal_.push_back("camp-high:" + std::to_string(site));
                            current->up_camp = std::make_unique<Node>(site);
                            ++sites_;
                            return;
                        }
                        current = current->up_camp.get();
                    }
                }
            }
            std::unique_ptr<CanyonCampSites::Node> CanyonCampSites::unlink(std::unique_ptr<Node> node, std::int64_t site, std::string& entry) {
                if (!node) return nullptr;
                if (site < node->site) {
                    node->down_camp = unlink(std::move(node->down_camp), site, entry);
                    return node;
                }
                if (node->site < site) {
                    node->up_camp = unlink(std::move(node->up_camp), site, entry);
                    return node;
                }
                if (node->down_camp && node->up_camp) {
                    Node* successor = node->up_camp.get();
                    while (successor->down_camp) successor = successor->down_camp.get();
                    entry = "relay:" + std::to_string(successor->site);
                    node->site = successor->site;
                    std::string ignored;
                    node->up_camp = unlink(std::move(node->up_camp), successor->site, ignored);
                    return node;
                }
                entry = (node->down_camp || node->up_camp) ? ("span:" + std::to_string(site)) : ("fold:" + std::to_string(site));
                return node->down_camp ? std::move(node->down_camp) : std::move(node->up_camp);
            }
            void CanyonCampSites::strike(std::int64_t site) {
                std::string entry;
                ridge_ = unlink(std::move(ridge_), site, entry);
                if (entry.empty()) throw SiteMissingError("site is not pitched");
                journal_.push_back(entry);
                --sites_;
            }
            """,
            """
            CanyonCampSites::Node::Node(std::int64_t value) : site(value) {}
            bool CanyonCampSites::pitched(std::int64_t site) const {
                const Node* current = ridge_.get();
                while (current) {
                    if (site == current->site) return true;
                    current = current->down_camp.get();
                }
                return false;
            }
            std::size_t CanyonCampSites::sites() const { return sites_; }
            std::vector<std::string> CanyonCampSites::pitch_trail() const { return journal_; }
            void CanyonCampSites::pitch(std::int64_t site) {
                if (pitched(site)) throw SitePitchedError("site already pitched");
                if (!ridge_) {
                    journal_.push_back("base:" + std::to_string(site));
                    ridge_ = std::make_unique<Node>(site);
                    sites_ = 1;
                    return;
                }
                Node* current = ridge_.get();
                for (;;) {
                    journal_.push_back("drop:" + std::to_string(current->site));
                    if (!current->down_camp) {
                        journal_.push_back("camp-low:" + std::to_string(site));
                        current->down_camp = std::make_unique<Node>(site);
                        ++sites_;
                        return;
                    }
                    current = current->down_camp.get();
                }
            }
            void CanyonCampSites::strike(std::int64_t site) {
                if (!ridge_) throw SiteMissingError("site is not pitched");
                if (ridge_->site == site) {
                    journal_.push_back("span:" + std::to_string(site));
                    ridge_ = std::move(ridge_->down_camp);
                    --sites_;
                    return;
                }
                Node* parent = ridge_.get();
                while (parent->down_camp && parent->down_camp->site != site) parent = parent->down_camp.get();
                if (!parent->down_camp) throw SiteMissingError("site is not pitched");
                journal_.push_back("span:" + std::to_string(site));
                parent->down_camp = std::move(parent->down_camp->down_camp);
                --sites_;
            }
            """,
            """
            CanyonCampSites camps;
            camps.pitch(2400);
            camps.pitch(1200);
            camps.pitch(3600);
            if (!camps.pitched(1200) || camps.pitched(9999)) return 1;
            if (camps.sites() != 3U) return 2;
            camps.strike(1200);
            if (camps.pitched(1200)) return 3;
            if (camps.sites() != 2U) return 4;
            return 0;
            """,
            """
            CanyonCampSites camps;
            camps.pitch(2400);
            camps.pitch(1200);
            camps.pitch(3600);
            camps.pitch(600);
            camps.pitch(1800);
            camps.pitch(3000);
            camps.pitch(4200);
            camps.pitch(1500);
            if (camps.sites() != 8U) return 1;
            bool threw = false;
            try { camps.pitch(1800); } catch (const SitePitchedError&) { threw = true; }
            if (!threw) return 2;
            camps.strike(1200);
            camps.strike(2400);
            camps.strike(600);
            threw = false;
            try { camps.strike(9999); } catch (const SiteMissingError&) { threw = true; }
            if (!threw) return 3;
            camps.strike(3600);
            std::vector<std::string> expected = {
                "base:2400",
                "drop:2400", "camp-low:1200",
                "rise:2400", "camp-high:3600",
                "drop:2400", "drop:1200", "camp-low:600",
                "drop:2400", "rise:1200", "camp-high:1800",
                "rise:2400", "drop:3600", "camp-low:3000",
                "rise:2400", "rise:3600", "camp-high:4200",
                "drop:2400", "rise:1200", "drop:1800", "camp-low:1500",
                "relay:1500",
                "relay:3000",
                "fold:600",
                "span:3600",
            };
            if (camps.pitch_trail() != expected) return 4;
            if (camps.sites() != 4U) return 5;
            if (!camps.pitched(1500) || camps.pitched(1200)) return 6;
            if (!camps.pitched(4200) || camps.pitched(2400)) return 7;
            return 0;
            """,
            "sixty-four-bit elevation traces over insertion-ordered linked camps",
            "an ordered container, a sorted std::vector, or a single-sided down-camp chain that ignores ordering decisions as the core store",
            "exact trail entries after 2400,1200,3600,600,1800,3000,4200,1500 pitches and mixed strikes, with rejected calls appending nothing",
            "64-bit trace journaling",
            "mutation-trace journaling ordered tree",
        ),
        c(
            "f26bst-lighthouse-beam-index",
            "Lighthouse beam index",
            "lighthouse_beam",
            """
            class BeamDuplicateError : public std::logic_error {
            public:
                explicit BeamDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class BeamAbsentError : public std::runtime_error {
            public:
                explicit BeamAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class LighthouseBeamIndex {
            public:
                void index_beam(std::int32_t beam);
                bool indexed(std::int32_t beam) const;
                std::size_t beams() const;
                std::optional<std::int32_t> parent_of(std::int32_t beam) const;
                std::string sweep_path(std::int32_t beam) const;
                std::optional<std::int32_t> dimmest() const;
                std::optional<std::int32_t> brightest() const;
            };
            """,
            """
            class BeamDuplicateError : public std::logic_error {
            public:
                explicit BeamDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class BeamAbsentError : public std::runtime_error {
            public:
                explicit BeamAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class LighthouseBeamIndex {
            public:
                void index_beam(std::int32_t beam);
                bool indexed(std::int32_t beam) const;
                std::size_t beams() const;
                std::optional<std::int32_t> parent_of(std::int32_t beam) const;
                std::string sweep_path(std::int32_t beam) const;
                std::optional<std::int32_t> dimmest() const;
                std::optional<std::int32_t> brightest() const;
            private:
                struct Node {
                    std::int32_t beam;
                    std::unique_ptr<Node> dim_beam;
                    std::unique_ptr<Node> bright_beam;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> tower_;
                std::size_t beams_ = 0;
            };
            """,
            """
            LighthouseBeamIndex::Node::Node(std::int32_t value) : beam(value) {}
            bool LighthouseBeamIndex::indexed(std::int32_t beam) const {
                const Node* current = tower_.get();
                while (current) {
                    if (beam == current->beam) return true;
                    current = beam < current->beam ? current->dim_beam.get() : current->bright_beam.get();
                }
                return false;
            }
            std::size_t LighthouseBeamIndex::beams() const { return beams_; }
            void LighthouseBeamIndex::index_beam(std::int32_t beam) {
                if (!tower_) {
                    tower_ = std::make_unique<Node>(beam);
                    beams_ = 1;
                    return;
                }
                Node* current = tower_.get();
                for (;;) {
                    if (beam == current->beam) throw BeamDuplicateError("beam already indexed");
                    if (beam < current->beam) {
                        if (!current->dim_beam) {
                            current->dim_beam = std::make_unique<Node>(beam);
                            ++beams_;
                            return;
                        }
                        current = current->dim_beam.get();
                    } else {
                        if (!current->bright_beam) {
                            current->bright_beam = std::make_unique<Node>(beam);
                            ++beams_;
                            return;
                        }
                        current = current->bright_beam.get();
                    }
                }
            }
            std::optional<std::int32_t> LighthouseBeamIndex::parent_of(std::int32_t beam) const {
                const Node* current = tower_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (beam == current->beam) {
                        if (!parent) return std::nullopt;
                        return parent->beam;
                    }
                    parent = current;
                    current = beam < current->beam ? current->dim_beam.get() : current->bright_beam.get();
                }
                return std::nullopt;
            }
            std::string LighthouseBeamIndex::sweep_path(std::int32_t beam) const {
                const Node* current = tower_.get();
                std::string path = "root";
                while (current) {
                    if (beam == current->beam) return path;
                    if (beam < current->beam) {
                        path += "<l";
                        current = current->dim_beam.get();
                    } else {
                        path += "<r";
                        current = current->bright_beam.get();
                    }
                }
                throw BeamAbsentError("beam is not indexed");
            }
            std::optional<std::int32_t> LighthouseBeamIndex::dimmest() const {
                if (!tower_) return std::nullopt;
                const Node* current = tower_.get();
                while (current->dim_beam) current = current->dim_beam.get();
                return current->beam;
            }
            std::optional<std::int32_t> LighthouseBeamIndex::brightest() const {
                if (!tower_) return std::nullopt;
                const Node* current = tower_.get();
                while (current->bright_beam) current = current->bright_beam.get();
                return current->beam;
            }
            """,
            """
            LighthouseBeamIndex::Node::Node(std::int32_t value) : beam(value) {}
            bool LighthouseBeamIndex::indexed(std::int32_t beam) const {
                const Node* current = tower_.get();
                while (current) {
                    if (beam == current->beam) return true;
                    current = current->bright_beam.get();
                }
                return false;
            }
            std::size_t LighthouseBeamIndex::beams() const { return beams_; }
            void LighthouseBeamIndex::index_beam(std::int32_t beam) {
                if (indexed(beam)) throw BeamDuplicateError("beam already indexed");
                if (!tower_) {
                    tower_ = std::make_unique<Node>(beam);
                    beams_ = 1;
                    return;
                }
                Node* current = tower_.get();
                while (current->bright_beam) current = current->bright_beam.get();
                current->bright_beam = std::make_unique<Node>(beam);
                ++beams_;
            }
            std::optional<std::int32_t> LighthouseBeamIndex::parent_of(std::int32_t beam) const {
                const Node* current = tower_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (beam == current->beam) {
                        if (!parent) return std::nullopt;
                        return parent->beam;
                    }
                    parent = current;
                    current = current->bright_beam.get();
                }
                return std::nullopt;
            }
            std::string LighthouseBeamIndex::sweep_path(std::int32_t beam) const {
                const Node* current = tower_.get();
                std::string path = "root";
                while (current) {
                    if (beam == current->beam) return path;
                    path += "<r";
                    current = current->bright_beam.get();
                }
                throw BeamAbsentError("beam is not indexed");
            }
            std::optional<std::int32_t> LighthouseBeamIndex::dimmest() const {
                if (!tower_) return std::nullopt;
                const Node* current = tower_.get();
                while (current->bright_beam) current = current->bright_beam.get();
                return current->beam;
            }
            std::optional<std::int32_t> LighthouseBeamIndex::brightest() const {
                if (!tower_) return std::nullopt;
                return tower_->beam;
            }
            """,
            """
            LighthouseBeamIndex index;
            index.index_beam(270);
            index.index_beam(135);
            index.index_beam(405);
            index.index_beam(68);
            index.index_beam(203);
            index.index_beam(338);
            index.index_beam(473);
            index.index_beam(169);
            if (!index.indexed(169) || index.indexed(999)) return 1;
            if (index.beams() != 8U) return 2;
            return 0;
            """,
            """
            LighthouseBeamIndex index;
            bool threw = false;
            try { index.sweep_path(270); } catch (const BeamAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (index.dimmest().has_value()) return 2;
            if (index.brightest().has_value()) return 3;
            index.index_beam(270);
            index.index_beam(135);
            index.index_beam(405);
            index.index_beam(68);
            index.index_beam(203);
            index.index_beam(338);
            index.index_beam(473);
            index.index_beam(169);
            threw = false;
            try { index.index_beam(203); } catch (const BeamDuplicateError&) { threw = true; }
            if (!threw) return 4;
            if (index.beams() != 8U) return 5;
            if (index.sweep_path(169) != "root<l<r<l") return 6;
            if (index.sweep_path(338) != "root<r<l") return 7;
            if (index.sweep_path(270) != "root") return 8;
            if (index.parent_of(169) != 203) return 9;
            if (index.parent_of(270).has_value()) return 10;
            if (index.dimmest() != 68) return 11;
            if (index.brightest() != 473) return 12;
            threw = false;
            try { index.sweep_path(999); } catch (const BeamAbsentError&) { threw = true; }
            if (!threw) return 13;
            return 0;
            """,
            "iteratively built linked beams with parent and endpoint navigation",
            "an ordered container, a sorted std::vector, or a single-sided bright-beam chain that ignores ordering decisions as the core store",
            "exact sweep paths, parents, and endpoints after 270,135,405,68,203,338,473,169, with duplicate/absent channels",
            "endpoint navigation added to structural queries",
            "navigation, successor, prune, two-phase, or rank ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-dock-crane-queue",
            "Dock crane queue",
            "dock_crane",
            """
            class CraneDuplicateError : public std::runtime_error {
            public:
                explicit CraneDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class CraneAbsentError : public std::logic_error {
            public:
                explicit CraneAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class DockCraneQueue {
            public:
                void queue_crane(std::int32_t crane);
                void dequeue_crane(std::int32_t crane);
                bool queued(std::int32_t crane) const;
                std::size_t cranes() const;
                std::optional<std::int32_t> next_heavier(std::int32_t crane) const;
                std::optional<std::int32_t> prev_lighter(std::int32_t crane) const;
                std::int32_t depth_of(std::int32_t crane) const;
            };
            """,
            """
            class CraneDuplicateError : public std::runtime_error {
            public:
                explicit CraneDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class CraneAbsentError : public std::logic_error {
            public:
                explicit CraneAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class DockCraneQueue {
            public:
                void queue_crane(std::int32_t crane);
                void dequeue_crane(std::int32_t crane);
                bool queued(std::int32_t crane) const;
                std::size_t cranes() const;
                std::optional<std::int32_t> next_heavier(std::int32_t crane) const;
                std::optional<std::int32_t> prev_lighter(std::int32_t crane) const;
                std::int32_t depth_of(std::int32_t crane) const;
            private:
                struct Node {
                    std::int32_t crane;
                    std::unique_ptr<Node> light_crane;
                    std::unique_ptr<Node> heavy_crane;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> dockside_;
                std::size_t cranes_ = 0;
                static std::unique_ptr<Node> attach(std::unique_ptr<Node> node, std::int32_t crane, bool& linked);
                static std::unique_ptr<Node> detach(std::unique_ptr<Node> node, std::int32_t crane, bool& removed);
            };
            """,
            """
            DockCraneQueue::Node::Node(std::int32_t value) : crane(value) {}
            bool DockCraneQueue::queued(std::int32_t crane) const {
                const Node* current = dockside_.get();
                while (current) {
                    if (crane == current->crane) return true;
                    current = crane < current->crane ? current->light_crane.get() : current->heavy_crane.get();
                }
                return false;
            }
            std::size_t DockCraneQueue::cranes() const { return cranes_; }
            std::unique_ptr<DockCraneQueue::Node> DockCraneQueue::attach(std::unique_ptr<Node> node, std::int32_t crane, bool& linked) {
                if (!node) {
                    linked = true;
                    return std::make_unique<Node>(crane);
                }
                if (crane == node->crane) return node;
                if (crane < node->crane) {
                    node->light_crane = attach(std::move(node->light_crane), crane, linked);
                } else {
                    node->heavy_crane = attach(std::move(node->heavy_crane), crane, linked);
                }
                return node;
            }
            void DockCraneQueue::queue_crane(std::int32_t crane) {
                bool linked = false;
                dockside_ = attach(std::move(dockside_), crane, linked);
                if (!linked) throw CraneDuplicateError("crane already queued");
                ++cranes_;
            }
            std::unique_ptr<DockCraneQueue::Node> DockCraneQueue::detach(std::unique_ptr<Node> node, std::int32_t crane, bool& removed) {
                if (!node) return nullptr;
                if (crane < node->crane) {
                    node->light_crane = detach(std::move(node->light_crane), crane, removed);
                    return node;
                }
                if (node->crane < crane) {
                    node->heavy_crane = detach(std::move(node->heavy_crane), crane, removed);
                    return node;
                }
                removed = true;
                if (!node->light_crane) return std::move(node->heavy_crane);
                if (!node->heavy_crane) return std::move(node->light_crane);
                Node* successor = node->heavy_crane.get();
                while (successor->light_crane) successor = successor->light_crane.get();
                node->crane = successor->crane;
                bool ignored = false;
                node->heavy_crane = detach(std::move(node->heavy_crane), successor->crane, ignored);
                return node;
            }
            void DockCraneQueue::dequeue_crane(std::int32_t crane) {
                bool removed = false;
                dockside_ = detach(std::move(dockside_), crane, removed);
                if (!removed) throw CraneAbsentError("crane is not queued");
                --cranes_;
            }
            std::optional<std::int32_t> DockCraneQueue::next_heavier(std::int32_t crane) const {
                if (!queued(crane)) return std::nullopt;
                const Node* current = dockside_.get();
                const Node* candidate = nullptr;
                while (current) {
                    if (crane < current->crane) {
                        candidate = current;
                        current = current->light_crane.get();
                    } else {
                        current = current->heavy_crane.get();
                    }
                }
                if (!candidate) return std::nullopt;
                return candidate->crane;
            }
            std::optional<std::int32_t> DockCraneQueue::prev_lighter(std::int32_t crane) const {
                if (!queued(crane)) return std::nullopt;
                const Node* current = dockside_.get();
                const Node* candidate = nullptr;
                while (current) {
                    if (current->crane < crane) {
                        candidate = current;
                        current = current->heavy_crane.get();
                    } else {
                        current = current->light_crane.get();
                    }
                }
                if (!candidate) return std::nullopt;
                return candidate->crane;
            }
            std::int32_t DockCraneQueue::depth_of(std::int32_t crane) const {
                const Node* current = dockside_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (crane == current->crane) return depth;
                    ++depth;
                    current = crane < current->crane ? current->light_crane.get() : current->heavy_crane.get();
                }
                throw CraneAbsentError("crane is not queued");
            }
            """,
            """
            DockCraneQueue::Node::Node(std::int32_t value) : crane(value) {}
            bool DockCraneQueue::queued(std::int32_t crane) const {
                const Node* current = dockside_.get();
                while (current) {
                    if (crane == current->crane) return true;
                    current = current->light_crane.get();
                }
                return false;
            }
            std::size_t DockCraneQueue::cranes() const { return cranes_; }
            void DockCraneQueue::queue_crane(std::int32_t crane) {
                if (queued(crane)) throw CraneDuplicateError("crane already queued");
                if (!dockside_) {
                    dockside_ = std::make_unique<Node>(crane);
                    cranes_ = 1;
                    return;
                }
                Node* current = dockside_.get();
                while (current->light_crane) current = current->light_crane.get();
                current->light_crane = std::make_unique<Node>(crane);
                ++cranes_;
            }
            void DockCraneQueue::dequeue_crane(std::int32_t crane) {
                if (!dockside_) throw CraneAbsentError("crane is not queued");
                if (dockside_->crane == crane) {
                    dockside_ = std::move(dockside_->light_crane);
                    --cranes_;
                    return;
                }
                Node* parent = dockside_.get();
                while (parent->light_crane && parent->light_crane->crane != crane) parent = parent->light_crane.get();
                if (!parent->light_crane) throw CraneAbsentError("crane is not queued");
                parent->light_crane = std::move(parent->light_crane->light_crane);
                --cranes_;
            }
            std::optional<std::int32_t> DockCraneQueue::next_heavier(std::int32_t crane) const {
                if (!queued(crane)) return std::nullopt;
                const Node* current = dockside_.get();
                const Node* best = nullptr;
                while (current) {
                    if (current->crane > crane && (!best || current->crane < best->crane)) best = current;
                    current = current->light_crane.get();
                }
                if (!best) return std::nullopt;
                return best->crane;
            }
            std::optional<std::int32_t> DockCraneQueue::prev_lighter(std::int32_t crane) const {
                if (!queued(crane)) return std::nullopt;
                const Node* current = dockside_.get();
                const Node* best = nullptr;
                while (current) {
                    if (current->crane < crane && (!best || current->crane > best->crane)) best = current;
                    current = current->light_crane.get();
                }
                if (!best) return std::nullopt;
                return best->crane;
            }
            std::int32_t DockCraneQueue::depth_of(std::int32_t crane) const {
                const Node* current = dockside_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (crane == current->crane) return depth;
                    ++depth;
                    current = current->light_crane.get();
                }
                throw CraneAbsentError("crane is not queued");
            }
            """,
            """
            DockCraneQueue queue;
            queue.queue_crane(56);
            queue.queue_crane(28);
            queue.queue_crane(84);
            if (!queue.queued(28) || queue.queued(999)) return 1;
            if (queue.cranes() != 3U) return 2;
            queue.dequeue_crane(28);
            if (queue.queued(28)) return 3;
            if (queue.cranes() != 2U) return 4;
            return 0;
            """,
            """
            DockCraneQueue queue;
            bool threw = false;
            try { queue.depth_of(56); } catch (const CraneAbsentError&) { threw = true; }
            if (!threw) return 1;
            queue.queue_crane(56);
            queue.queue_crane(28);
            queue.queue_crane(84);
            queue.queue_crane(14);
            queue.queue_crane(42);
            queue.queue_crane(70);
            queue.queue_crane(98);
            queue.queue_crane(35);
            threw = false;
            try { queue.queue_crane(42); } catch (const CraneDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (queue.cranes() != 8U) return 3;
            if (queue.next_heavier(35) != 42) return 4;
            if (queue.prev_lighter(35) != 28) return 5;
            if (queue.next_heavier(98).has_value()) return 6;
            if (queue.prev_lighter(14).has_value()) return 7;
            if (queue.next_heavier(999).has_value()) return 8;
            if (queue.depth_of(35) != 3) return 9;
            if (queue.depth_of(56) != 0) return 10;
            queue.dequeue_crane(28);
            if (queue.next_heavier(14) != 35) return 11;
            if (queue.prev_lighter(35) != 14) return 12;
            if (queue.depth_of(35) != 1) return 13;
            if (queue.depth_of(14) != 2) return 14;
            threw = false;
            try { queue.dequeue_crane(28); } catch (const CraneAbsentError&) { threw = true; }
            if (!threw) return 15;
            if (queue.cranes() != 7U) return 16;
            return 0;
            """,
            "recursively maintained linked cranes with in-order successor and predecessor queries",
            "an ordered container, a sorted std::vector, or a single-sided light-crane chain that ignores ordering decisions as the core store",
            "exact successors, predecessors, and depths after 56,28,84,14,42,70,98,35, recursive successor-side dequeue of 28, and nullopt edges",
            "recursive structure paired with neighbor queries",
            "navigation, successor, prune, two-phase, or rank ordered tree",
        ),
        c(
            "f26bst-bazaar-stall-rows",
            "Bazaar stall rows",
            "bazaar_stall",
            """
            class StallDuplicateError : public std::logic_error {
            public:
                explicit StallDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class StallPendingError : public std::runtime_error {
            public:
                explicit StallPendingError(const std::string& message) : std::runtime_error(message) {}
            };
            class StallEmptyError : public std::domain_error {
            public:
                explicit StallEmptyError(const std::string& message) : std::domain_error(message) {}
            };
            class StallAbsentError : public std::out_of_range {
            public:
                explicit StallAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class BazaarStallRows {
            public:
                void stage(std::int32_t stall);
                void commit();
                void abort();
                bool erected(std::int32_t stall) const;
                std::size_t stalls() const;
                bool staging() const;
                std::int32_t depth_of(std::int32_t stall) const;
            };
            """,
            """
            class StallDuplicateError : public std::logic_error {
            public:
                explicit StallDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class StallPendingError : public std::runtime_error {
            public:
                explicit StallPendingError(const std::string& message) : std::runtime_error(message) {}
            };
            class StallEmptyError : public std::domain_error {
            public:
                explicit StallEmptyError(const std::string& message) : std::domain_error(message) {}
            };
            class StallAbsentError : public std::out_of_range {
            public:
                explicit StallAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class BazaarStallRows {
            public:
                void stage(std::int32_t stall);
                void commit();
                void abort();
                bool erected(std::int32_t stall) const;
                std::size_t stalls() const;
                bool staging() const;
                std::int32_t depth_of(std::int32_t stall) const;
            private:
                struct Node {
                    std::int32_t stall;
                    std::unique_ptr<Node> near_stall;
                    std::unique_ptr<Node> far_stall;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> square_;
                std::size_t stalls_ = 0;
                std::optional<std::int32_t> pending_;
            };
            """,
            """
            BazaarStallRows::Node::Node(std::int32_t value) : stall(value) {}
            bool BazaarStallRows::erected(std::int32_t stall) const {
                const Node* current = square_.get();
                while (current) {
                    if (stall == current->stall) return true;
                    current = stall < current->stall ? current->near_stall.get() : current->far_stall.get();
                }
                return false;
            }
            std::size_t BazaarStallRows::stalls() const { return stalls_; }
            bool BazaarStallRows::staging() const { return pending_.has_value(); }
            void BazaarStallRows::stage(std::int32_t stall) {
                if (pending_) throw StallPendingError("a stall is already staged");
                if (erected(stall)) throw StallDuplicateError("stall already erected");
                pending_ = stall;
            }
            void BazaarStallRows::commit() {
                if (!pending_) throw StallEmptyError("no staged stall");
                const std::int32_t stall = *pending_;
                pending_.reset();
                if (!square_) {
                    square_ = std::make_unique<Node>(stall);
                    stalls_ = 1;
                    return;
                }
                Node* current = square_.get();
                for (;;) {
                    if (stall < current->stall) {
                        if (!current->near_stall) {
                            current->near_stall = std::make_unique<Node>(stall);
                            ++stalls_;
                            return;
                        }
                        current = current->near_stall.get();
                    } else {
                        if (!current->far_stall) {
                            current->far_stall = std::make_unique<Node>(stall);
                            ++stalls_;
                            return;
                        }
                        current = current->far_stall.get();
                    }
                }
            }
            void BazaarStallRows::abort() {
                if (!pending_) throw StallEmptyError("no staged stall");
                pending_.reset();
            }
            std::int32_t BazaarStallRows::depth_of(std::int32_t stall) const {
                const Node* current = square_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (stall == current->stall) return depth;
                    ++depth;
                    current = stall < current->stall ? current->near_stall.get() : current->far_stall.get();
                }
                throw StallAbsentError("stall is not erected");
            }
            """,
            """
            BazaarStallRows::Node::Node(std::int32_t value) : stall(value) {}
            bool BazaarStallRows::erected(std::int32_t stall) const {
                const Node* current = square_.get();
                while (current) {
                    if (stall == current->stall) return true;
                    current = current->far_stall.get();
                }
                return false;
            }
            std::size_t BazaarStallRows::stalls() const { return stalls_; }
            bool BazaarStallRows::staging() const { return pending_.has_value(); }
            void BazaarStallRows::stage(std::int32_t stall) {
                if (pending_) throw StallPendingError("a stall is already staged");
                if (erected(stall)) throw StallDuplicateError("stall already erected");
                pending_ = stall;
                if (!square_) {
                    square_ = std::make_unique<Node>(stall);
                    stalls_ = 1;
                    return;
                }
                Node* current = square_.get();
                while (current->far_stall) current = current->far_stall.get();
                current->far_stall = std::make_unique<Node>(stall);
                ++stalls_;
            }
            void BazaarStallRows::commit() {
                if (!pending_) throw StallEmptyError("no staged stall");
                pending_.reset();
            }
            void BazaarStallRows::abort() {
                if (!pending_) throw StallEmptyError("no staged stall");
                const std::int32_t stall = *pending_;
                pending_.reset();
                if (!square_) return;
                if (square_->stall == stall) {
                    square_ = std::move(square_->far_stall);
                    --stalls_;
                    return;
                }
                Node* parent = square_.get();
                while (parent->far_stall && parent->far_stall->stall != stall) parent = parent->far_stall.get();
                if (parent->far_stall) {
                    parent->far_stall = std::move(parent->far_stall->far_stall);
                    --stalls_;
                }
            }
            std::int32_t BazaarStallRows::depth_of(std::int32_t stall) const {
                const Node* current = square_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (stall == current->stall) return depth;
                    ++depth;
                    current = current->far_stall.get();
                }
                throw StallAbsentError("stall is not erected");
            }
            """,
            """
            BazaarStallRows rows;
            rows.stage(48);
            rows.commit();
            rows.stage(24);
            rows.commit();
            if (!rows.erected(24) || rows.erected(99)) return 1;
            if (rows.stalls() != 2U) return 2;
            rows.stage(72);
            rows.abort();
            if (rows.erected(72)) return 3;
            if (rows.stalls() != 2U) return 4;
            return 0;
            """,
            """
            BazaarStallRows rows;
            bool threw = false;
            try { rows.commit(); } catch (const StallEmptyError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { rows.abort(); } catch (const StallEmptyError&) { threw = true; }
            if (!threw) return 2;
            rows.stage(48);
            if (rows.erected(48)) return 3;
            if (!rows.staging()) return 4;
            if (rows.stalls() != 0U) return 5;
            threw = false;
            try { rows.stage(24); } catch (const StallPendingError&) { threw = true; }
            if (!threw) return 6;
            rows.commit();
            if (!rows.erected(48)) return 7;
            if (rows.stalls() != 1U) return 8;
            if (rows.staging()) return 9;
            rows.stage(24);
            rows.commit();
            rows.stage(72);
            rows.commit();
            rows.stage(12);
            rows.commit();
            rows.stage(36);
            rows.commit();
            rows.stage(60);
            rows.commit();
            rows.stage(84);
            rows.commit();
            threw = false;
            try { rows.stage(36); } catch (const StallDuplicateError&) { threw = true; }
            if (!threw) return 10;
            rows.stage(30);
            rows.abort();
            if (rows.erected(30)) return 11;
            if (rows.stalls() != 7U) return 12;
            if (rows.depth_of(36) != 2) return 13;
            if (rows.depth_of(48) != 0) return 14;
            if (rows.depth_of(12) != 2) return 15;
            threw = false;
            try { rows.depth_of(30); } catch (const StallAbsentError&) { threw = true; }
            if (!threw) return 16;
            return 0;
            """,
            "transactional stage, commit, and abort insertion over owned linked stalls",
            "an ordered container, a sorted std::vector, or a single-sided far-stall chain that ignores ordering decisions as the core store",
            "staged stalls not yet erected, exact depths after committed sequences, pending and empty channels, and abort semantics",
            "two-phase mutation over owned nodes",
            "navigation, successor, prune, two-phase, or rank ordered tree",
        ),
        c(
            "f26bst-ranch-paddock-gates",
            "Ranch paddock gates",
            "ranch_paddock",
            """
            class GateDuplicateError : public std::logic_error {
            public:
                explicit GateDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class GateAbsentError : public std::runtime_error {
            public:
                explicit GateAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class RanchPaddockGates {
            public:
                void fence(std::int32_t gate);
                std::size_t clear_below(std::int32_t gate);
                bool fenced(std::int32_t gate) const;
                std::size_t gates() const;
                std::int32_t depth_of(std::int32_t gate) const;
            };
            """,
            """
            class GateDuplicateError : public std::logic_error {
            public:
                explicit GateDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class GateAbsentError : public std::runtime_error {
            public:
                explicit GateAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class RanchPaddockGates {
            public:
                void fence(std::int32_t gate);
                std::size_t clear_below(std::int32_t gate);
                bool fenced(std::int32_t gate) const;
                std::size_t gates() const;
                std::int32_t depth_of(std::int32_t gate) const;
            private:
                struct Node {
                    std::int32_t gate;
                    std::unique_ptr<Node> inner_gate;
                    std::unique_ptr<Node> outer_gate;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> range_;
                std::size_t fenced_ = 0;
                static std::size_t measure(const Node* node);
            };
            """,
            """
            RanchPaddockGates::Node::Node(std::int32_t value) : gate(value) {}
            bool RanchPaddockGates::fenced(std::int32_t gate) const {
                const Node* current = range_.get();
                while (current) {
                    if (gate == current->gate) return true;
                    current = gate < current->gate ? current->inner_gate.get() : current->outer_gate.get();
                }
                return false;
            }
            std::size_t RanchPaddockGates::gates() const { return fenced_; }
            std::size_t RanchPaddockGates::measure(const Node* node) {
                if (!node) return 0;
                return 1 + measure(node->inner_gate.get()) + measure(node->outer_gate.get());
            }
            void RanchPaddockGates::fence(std::int32_t gate) {
                if (!range_) {
                    range_ = std::make_unique<Node>(gate);
                    fenced_ = 1;
                    return;
                }
                Node* current = range_.get();
                for (;;) {
                    if (gate == current->gate) throw GateDuplicateError("gate already fenced");
                    if (gate < current->gate) {
                        if (!current->inner_gate) {
                            current->inner_gate = std::make_unique<Node>(gate);
                            ++fenced_;
                            return;
                        }
                        current = current->inner_gate.get();
                    } else {
                        if (!current->outer_gate) {
                            current->outer_gate = std::make_unique<Node>(gate);
                            ++fenced_;
                            return;
                        }
                        current = current->outer_gate.get();
                    }
                }
            }
            std::size_t RanchPaddockGates::clear_below(std::int32_t gate) {
                if (!range_) throw GateAbsentError("gate is not fenced");
                if (range_->gate == gate) {
                    const std::size_t removed = measure(range_.get());
                    range_.reset();
                    fenced_ -= removed;
                    return removed;
                }
                Node* parent = range_.get();
                for (;;) {
                    const bool go_inner = gate < parent->gate;
                    Node* next = go_inner ? parent->inner_gate.get() : parent->outer_gate.get();
                    if (!next) throw GateAbsentError("gate is not fenced");
                    if (next->gate == gate) {
                        const std::size_t removed = measure(next);
                        if (go_inner) {
                            parent->inner_gate.reset();
                        } else {
                            parent->outer_gate.reset();
                        }
                        fenced_ -= removed;
                        return removed;
                    }
                    parent = next;
                }
            }
            std::int32_t RanchPaddockGates::depth_of(std::int32_t gate) const {
                const Node* current = range_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gate == current->gate) return depth;
                    ++depth;
                    current = gate < current->gate ? current->inner_gate.get() : current->outer_gate.get();
                }
                throw GateAbsentError("gate is not fenced");
            }
            """,
            """
            RanchPaddockGates::Node::Node(std::int32_t value) : gate(value) {}
            bool RanchPaddockGates::fenced(std::int32_t gate) const {
                const Node* current = range_.get();
                while (current) {
                    if (gate == current->gate) return true;
                    current = current->inner_gate.get();
                }
                return false;
            }
            std::size_t RanchPaddockGates::gates() const { return fenced_; }
            void RanchPaddockGates::fence(std::int32_t gate) {
                if (fenced(gate)) throw GateDuplicateError("gate already fenced");
                if (!range_) {
                    range_ = std::make_unique<Node>(gate);
                    fenced_ = 1;
                    return;
                }
                Node* current = range_.get();
                while (current->inner_gate) current = current->inner_gate.get();
                current->inner_gate = std::make_unique<Node>(gate);
                ++fenced_;
            }
            std::size_t RanchPaddockGates::clear_below(std::int32_t gate) {
                if (!range_) throw GateAbsentError("gate is not fenced");
                if (range_->gate == gate) {
                    range_ = std::move(range_->inner_gate);
                    --fenced_;
                    return 1;
                }
                Node* parent = range_.get();
                while (parent->inner_gate && parent->inner_gate->gate != gate) parent = parent->inner_gate.get();
                if (!parent->inner_gate) throw GateAbsentError("gate is not fenced");
                parent->inner_gate = std::move(parent->inner_gate->inner_gate);
                --fenced_;
                return 1;
            }
            std::int32_t RanchPaddockGates::depth_of(std::int32_t gate) const {
                const Node* current = range_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (gate == current->gate) return depth;
                    ++depth;
                    current = current->inner_gate.get();
                }
                throw GateAbsentError("gate is not fenced");
            }
            """,
            """
            RanchPaddockGates ranch;
            ranch.fence(80);
            ranch.fence(40);
            ranch.fence(120);
            ranch.fence(20);
            ranch.fence(60);
            if (!ranch.fenced(60) || ranch.fenced(999)) return 1;
            if (ranch.gates() != 5U) return 2;
            if (ranch.clear_below(20) != 1U) return 3;
            if (ranch.gates() != 4U) return 4;
            if (ranch.fenced(20)) return 5;
            return 0;
            """,
            """
            RanchPaddockGates ranch;
            ranch.fence(80);
            ranch.fence(40);
            ranch.fence(120);
            ranch.fence(20);
            ranch.fence(60);
            ranch.fence(100);
            ranch.fence(140);
            ranch.fence(50);
            ranch.fence(70);
            ranch.fence(110);
            bool threw = false;
            try { ranch.fence(60); } catch (const GateDuplicateError&) { threw = true; }
            if (!threw) return 1;
            if (ranch.gates() != 10U) return 2;
            if (ranch.depth_of(110) != 3) return 3;
            if (ranch.clear_below(40) != 5U) return 4;
            if (ranch.gates() != 5U) return 5;
            if (ranch.fenced(40) || ranch.fenced(60)) return 6;
            threw = false;
            try { ranch.depth_of(50); } catch (const GateAbsentError&) { threw = true; }
            if (!threw) return 7;
            if (ranch.depth_of(110) != 3) return 8;
            if (ranch.depth_of(120) != 1) return 9;
            threw = false;
            try { ranch.clear_below(40); } catch (const GateAbsentError&) { threw = true; }
            if (!threw) return 10;
            if (ranch.clear_below(80) != 5U) return 11;
            if (ranch.gates() != 0U) return 12;
            threw = false;
            try { ranch.depth_of(80); } catch (const GateAbsentError&) { threw = true; }
            if (!threw) return 13;
            return 0;
            """,
            "whole-subtree removal with exact node accounting over owned linked gates",
            "an ordered container, a sorted std::vector, or a single-sided inner-gate chain that ignores ordering decisions as the core store",
            "clear_below removing exactly five nodes, surviving depths, single-node erasure distinguished from subtree erasure, and absent channels",
            "subtree identity versus sorted content",
            "navigation, successor, prune, two-phase, or rank ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-studio-take-catalog",
            "Studio take catalog",
            "studio_take",
            """
            class TakeDuplicateError : public std::invalid_argument {
            public:
                explicit TakeDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TakeAbsentError : public std::out_of_range {
            public:
                explicit TakeAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class StudioTakeCatalog {
            public:
                void slate(std::int32_t take);
                bool slated(std::int32_t take) const;
                std::size_t takes() const;
                std::optional<std::int32_t> floor_of(std::int32_t mark) const;
                std::optional<std::int32_t> ceiling_of(std::int32_t mark) const;
                std::optional<std::int32_t> parent_of(std::int32_t take) const;
                std::int32_t depth_of(std::int32_t take) const;
            };
            """,
            """
            class TakeDuplicateError : public std::invalid_argument {
            public:
                explicit TakeDuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TakeAbsentError : public std::out_of_range {
            public:
                explicit TakeAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class StudioTakeCatalog {
            public:
                void slate(std::int32_t take);
                bool slated(std::int32_t take) const;
                std::size_t takes() const;
                std::optional<std::int32_t> floor_of(std::int32_t mark) const;
                std::optional<std::int32_t> ceiling_of(std::int32_t mark) const;
                std::optional<std::int32_t> parent_of(std::int32_t take) const;
                std::int32_t depth_of(std::int32_t take) const;
            private:
                struct Node {
                    std::int32_t take;
                    std::unique_ptr<Node> early_take;
                    std::unique_ptr<Node> late_take;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> reel_;
                std::size_t takes_ = 0;
            };
            """,
            """
            StudioTakeCatalog::Node::Node(std::int32_t value) : take(value) {}
            bool StudioTakeCatalog::slated(std::int32_t take) const {
                const Node* current = reel_.get();
                while (current) {
                    if (take == current->take) return true;
                    current = take < current->take ? current->early_take.get() : current->late_take.get();
                }
                return false;
            }
            std::size_t StudioTakeCatalog::takes() const { return takes_; }
            void StudioTakeCatalog::slate(std::int32_t take) {
                if (!reel_) {
                    reel_ = std::make_unique<Node>(take);
                    takes_ = 1;
                    return;
                }
                Node* current = reel_.get();
                for (;;) {
                    if (take == current->take) throw TakeDuplicateError("take already slated");
                    if (take < current->take) {
                        if (!current->early_take) {
                            current->early_take = std::make_unique<Node>(take);
                            ++takes_;
                            return;
                        }
                        current = current->early_take.get();
                    } else {
                        if (!current->late_take) {
                            current->late_take = std::make_unique<Node>(take);
                            ++takes_;
                            return;
                        }
                        current = current->late_take.get();
                    }
                }
            }
            std::optional<std::int32_t> StudioTakeCatalog::floor_of(std::int32_t mark) const {
                const Node* current = reel_.get();
                const Node* best = nullptr;
                while (current) {
                    if (current->take <= mark) {
                        best = current;
                        current = current->late_take.get();
                    } else {
                        current = current->early_take.get();
                    }
                }
                if (!best) return std::nullopt;
                return best->take;
            }
            std::optional<std::int32_t> StudioTakeCatalog::ceiling_of(std::int32_t mark) const {
                const Node* current = reel_.get();
                const Node* best = nullptr;
                while (current) {
                    if (current->take >= mark) {
                        best = current;
                        current = current->early_take.get();
                    } else {
                        current = current->late_take.get();
                    }
                }
                if (!best) return std::nullopt;
                return best->take;
            }
            std::optional<std::int32_t> StudioTakeCatalog::parent_of(std::int32_t take) const {
                const Node* current = reel_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (take == current->take) {
                        if (!parent) return std::nullopt;
                        return parent->take;
                    }
                    parent = current;
                    current = take < current->take ? current->early_take.get() : current->late_take.get();
                }
                throw TakeAbsentError("take is not slated");
            }
            std::int32_t StudioTakeCatalog::depth_of(std::int32_t take) const {
                const Node* current = reel_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (take == current->take) return depth;
                    ++depth;
                    current = take < current->take ? current->early_take.get() : current->late_take.get();
                }
                throw TakeAbsentError("take is not slated");
            }
            """,
            """
            StudioTakeCatalog::Node::Node(std::int32_t value) : take(value) {}
            bool StudioTakeCatalog::slated(std::int32_t take) const {
                const Node* current = reel_.get();
                while (current) {
                    if (take == current->take) return true;
                    current = current->early_take.get();
                }
                return false;
            }
            std::size_t StudioTakeCatalog::takes() const { return takes_; }
            void StudioTakeCatalog::slate(std::int32_t take) {
                if (slated(take)) throw TakeDuplicateError("take already slated");
                if (!reel_) {
                    reel_ = std::make_unique<Node>(take);
                    takes_ = 1;
                    return;
                }
                Node* current = reel_.get();
                while (current->early_take) current = current->early_take.get();
                current->early_take = std::make_unique<Node>(take);
                ++takes_;
            }
            std::optional<std::int32_t> StudioTakeCatalog::floor_of(std::int32_t mark) const {
                const Node* current = reel_.get();
                const Node* best = nullptr;
                while (current) {
                    if (current->take <= mark && (!best || current->take > best->take)) best = current;
                    current = current->early_take.get();
                }
                if (!best) return std::nullopt;
                return best->take;
            }
            std::optional<std::int32_t> StudioTakeCatalog::ceiling_of(std::int32_t mark) const {
                const Node* current = reel_.get();
                const Node* best = nullptr;
                while (current) {
                    if (current->take >= mark && (!best || current->take < best->take)) best = current;
                    current = current->early_take.get();
                }
                if (!best) return std::nullopt;
                return best->take;
            }
            std::optional<std::int32_t> StudioTakeCatalog::parent_of(std::int32_t take) const {
                const Node* current = reel_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (take == current->take) {
                        if (!parent) return std::nullopt;
                        return parent->take;
                    }
                    parent = current;
                    current = current->early_take.get();
                }
                throw TakeAbsentError("take is not slated");
            }
            std::int32_t StudioTakeCatalog::depth_of(std::int32_t take) const {
                const Node* current = reel_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (take == current->take) return depth;
                    ++depth;
                    current = current->early_take.get();
                }
                throw TakeAbsentError("take is not slated");
            }
            """,
            """
            StudioTakeCatalog catalog;
            catalog.slate(130);
            catalog.slate(65);
            catalog.slate(195);
            if (!catalog.slated(65) || catalog.slated(999)) return 1;
            if (catalog.takes() != 3U) return 2;
            return 0;
            """,
            """
            StudioTakeCatalog catalog;
            bool threw = false;
            try { catalog.depth_of(130); } catch (const TakeAbsentError&) { threw = true; }
            if (!threw) return 1;
            catalog.slate(130);
            catalog.slate(65);
            catalog.slate(195);
            catalog.slate(33);
            catalog.slate(98);
            catalog.slate(163);
            catalog.slate(228);
            catalog.slate(81);
            threw = false;
            try { catalog.slate(98); } catch (const TakeDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (catalog.takes() != 8U) return 3;
            if (catalog.floor_of(100) != 98) return 4;
            if (catalog.floor_of(32).has_value()) return 5;
            if (catalog.ceiling_of(100) != 130) return 6;
            if (catalog.ceiling_of(229).has_value()) return 7;
            if (catalog.floor_of(130) != 130) return 8;
            if (catalog.parent_of(81) != 98) return 9;
            if (catalog.parent_of(130).has_value()) return 10;
            if (catalog.depth_of(81) != 3) return 11;
            if (catalog.depth_of(130) != 0) return 12;
            threw = false;
            try { catalog.parent_of(999); } catch (const TakeAbsentError&) { threw = true; }
            if (!threw) return 13;
            return 0;
            """,
            "iterative linked takes with floor/ceiling search and parent reads",
            "an ordered container, a sorted std::vector, or a single-sided early-take chain that ignores ordering decisions as the core store",
            "exact floors, ceilings, parents, and depths after 130,65,195,33,98,163,228,81, with duplicate/absent channels",
            "interval-neighbor queries over structure",
            "navigation, successor, prune, two-phase, or rank ordered tree",
        ),
        c(
            "f26bst-glacier-stake-grid",
            "Glacier stake grid",
            "glacier_stake",
            """
            class PegDuplicateError : public std::runtime_error {
            public:
                explicit PegDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class PegAbsentError : public std::logic_error {
            public:
                explicit PegAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class GlacierStakeGrid {
            public:
                void stake(std::int64_t peg);
                bool staked(std::int64_t peg) const;
                std::size_t pegs() const;
                std::vector<std::pair<std::int64_t, std::int32_t>> survey(std::int64_t low, std::int64_t high) const;
                std::int32_t depth_of(std::int64_t peg) const;
            };
            """,
            """
            class PegDuplicateError : public std::runtime_error {
            public:
                explicit PegDuplicateError(const std::string& message) : std::runtime_error(message) {}
            };
            class PegAbsentError : public std::logic_error {
            public:
                explicit PegAbsentError(const std::string& message) : std::logic_error(message) {}
            };
            class GlacierStakeGrid {
            public:
                void stake(std::int64_t peg);
                bool staked(std::int64_t peg) const;
                std::size_t pegs() const;
                std::vector<std::pair<std::int64_t, std::int32_t>> survey(std::int64_t low, std::int64_t high) const;
                std::int32_t depth_of(std::int64_t peg) const;
            private:
                struct Node {
                    std::int64_t peg;
                    std::unique_ptr<Node> shallow_peg;
                    std::unique_ptr<Node> deep_peg;
                    explicit Node(std::int64_t value);
                };
                std::unique_ptr<Node> glacier_;
                std::size_t pegs_ = 0;
            };
            """,
            """
            GlacierStakeGrid::Node::Node(std::int64_t value) : peg(value) {}
            bool GlacierStakeGrid::staked(std::int64_t peg) const {
                const Node* current = glacier_.get();
                while (current) {
                    if (peg == current->peg) return true;
                    current = peg < current->peg ? current->shallow_peg.get() : current->deep_peg.get();
                }
                return false;
            }
            std::size_t GlacierStakeGrid::pegs() const { return pegs_; }
            void GlacierStakeGrid::stake(std::int64_t peg) {
                if (!glacier_) {
                    glacier_ = std::make_unique<Node>(peg);
                    pegs_ = 1;
                    return;
                }
                Node* current = glacier_.get();
                for (;;) {
                    if (peg == current->peg) throw PegDuplicateError("peg already staked");
                    if (peg < current->peg) {
                        if (!current->shallow_peg) {
                            current->shallow_peg = std::make_unique<Node>(peg);
                            ++pegs_;
                            return;
                        }
                        current = current->shallow_peg.get();
                    } else {
                        if (!current->deep_peg) {
                            current->deep_peg = std::make_unique<Node>(peg);
                            ++pegs_;
                            return;
                        }
                        current = current->deep_peg.get();
                    }
                }
            }
            std::vector<std::pair<std::int64_t, std::int32_t>> GlacierStakeGrid::survey(std::int64_t low, std::int64_t high) const {
                std::vector<std::pair<std::int64_t, std::int32_t>> found;
                std::vector<std::pair<const Node*, std::int32_t>> stack;
                const Node* current = glacier_.get();
                std::int32_t depth = 0;
                while (current || !stack.empty()) {
                    while (current) {
                        stack.emplace_back(current, depth);
                        current = current->shallow_peg.get();
                        ++depth;
                    }
                    const Node* node = stack.back().first;
                    const std::int32_t node_depth = stack.back().second;
                    stack.pop_back();
                    if (node->peg >= low && node->peg <= high) found.emplace_back(node->peg, node_depth);
                    current = node->deep_peg.get();
                    depth = node_depth + 1;
                }
                return found;
            }
            std::int32_t GlacierStakeGrid::depth_of(std::int64_t peg) const {
                const Node* current = glacier_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (peg == current->peg) return depth;
                    ++depth;
                    current = peg < current->peg ? current->shallow_peg.get() : current->deep_peg.get();
                }
                throw PegAbsentError("peg is not staked");
            }
            """,
            """
            GlacierStakeGrid::Node::Node(std::int64_t value) : peg(value) {}
            bool GlacierStakeGrid::staked(std::int64_t peg) const {
                const Node* current = glacier_.get();
                while (current) {
                    if (peg == current->peg) return true;
                    current = current->deep_peg.get();
                }
                return false;
            }
            std::size_t GlacierStakeGrid::pegs() const { return pegs_; }
            void GlacierStakeGrid::stake(std::int64_t peg) {
                if (staked(peg)) throw PegDuplicateError("peg already staked");
                if (!glacier_) {
                    glacier_ = std::make_unique<Node>(peg);
                    pegs_ = 1;
                    return;
                }
                Node* current = glacier_.get();
                while (current->deep_peg) current = current->deep_peg.get();
                current->deep_peg = std::make_unique<Node>(peg);
                ++pegs_;
            }
            std::vector<std::pair<std::int64_t, std::int32_t>> GlacierStakeGrid::survey(std::int64_t low, std::int64_t high) const {
                std::vector<std::pair<std::int64_t, std::int32_t>> found;
                const Node* current = glacier_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (current->peg >= low && current->peg <= high) found.emplace_back(current->peg, depth);
                    ++depth;
                    current = current->deep_peg.get();
                }
                return found;
            }
            std::int32_t GlacierStakeGrid::depth_of(std::int64_t peg) const {
                const Node* current = glacier_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (peg == current->peg) return depth;
                    ++depth;
                    current = current->deep_peg.get();
                }
                throw PegAbsentError("peg is not staked");
            }
            """,
            """
            GlacierStakeGrid grid;
            grid.stake(5000);
            grid.stake(2500);
            grid.stake(7500);
            if (!grid.staked(2500) || grid.staked(9999)) return 1;
            if (grid.pegs() != 3U) return 2;
            return 0;
            """,
            """
            GlacierStakeGrid grid;
            bool threw = false;
            try { grid.depth_of(5000); } catch (const PegAbsentError&) { threw = true; }
            if (!threw) return 1;
            grid.stake(5000);
            grid.stake(2500);
            grid.stake(7500);
            grid.stake(1250);
            grid.stake(3750);
            grid.stake(6250);
            grid.stake(8750);
            grid.stake(3000);
            threw = false;
            try { grid.stake(3750); } catch (const PegDuplicateError&) { threw = true; }
            if (!threw) return 2;
            if (grid.pegs() != 8U) return 3;
            std::vector<std::pair<std::int64_t, std::int32_t>> expected = {
                {2500, 1}, {3000, 3}, {3750, 2}, {5000, 0}, {6250, 2},
            };
            if (grid.survey(2000, 7000) != expected) return 4;
            std::vector<std::pair<std::int64_t, std::int32_t>> edge;
            if (grid.survey(1, 2) != edge) return 5;
            std::vector<std::pair<std::int64_t, std::int32_t>> whole = {
                {1250, 2}, {2500, 1}, {3000, 3}, {3750, 2}, {5000, 0}, {6250, 2}, {7500, 1}, {8750, 2},
            };
            if (grid.survey(0, 9999) != whole) return 6;
            if (grid.depth_of(3000) != 3) return 7;
            if (grid.depth_of(5000) != 0) return 8;
            threw = false;
            try { grid.depth_of(9999); } catch (const PegAbsentError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "sixty-four-bit linked pegs with depth-annotated in-order range surveys",
            "an ordered container, a sorted std::vector, or a single-sided deep-peg chain that ignores ordering decisions as the core store",
            "exact (peg, depth) survey pairs after 5000,2500,7500,1250,3750,6250,8750,3000, empty ranges, and duplicate/absent channels",
            "range queries coupled with per-key depth",
            "navigation, successor, prune, two-phase, or rank ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-planetarium-seat-grid",
            "Planetarium seat grid",
            "planetarium_seat",
            """
            class SeatBookedError : public std::logic_error {
            public:
                explicit SeatBookedError(const std::string& message) : std::logic_error(message) {}
            };
            class SeatMissingError : public std::runtime_error {
            public:
                explicit SeatMissingError(const std::string& message) : std::runtime_error(message) {}
            };
            class PlanetariumSeatGrid {
            public:
                void book(const std::string& seat);
                bool booked(const std::string& seat) const;
                std::size_t seats() const;
                std::string usher_path(const std::string& seat) const;
                std::optional<std::string> parent_of(const std::string& seat) const;
                std::int32_t depth_of(const std::string& seat) const;
            };
            """,
            """
            class SeatBookedError : public std::logic_error {
            public:
                explicit SeatBookedError(const std::string& message) : std::logic_error(message) {}
            };
            class SeatMissingError : public std::runtime_error {
            public:
                explicit SeatMissingError(const std::string& message) : std::runtime_error(message) {}
            };
            class PlanetariumSeatGrid {
            public:
                void book(const std::string& seat);
                bool booked(const std::string& seat) const;
                std::size_t seats() const;
                std::string usher_path(const std::string& seat) const;
                std::optional<std::string> parent_of(const std::string& seat) const;
                std::int32_t depth_of(const std::string& seat) const;
            private:
                struct Node {
                    std::string seat;
                    std::unique_ptr<Node> front_seat;
                    std::unique_ptr<Node> back_seat;
                    explicit Node(std::string value);
                };
                std::unique_ptr<Node> dome_;
                std::size_t seats_ = 0;
            };
            """,
            """
            PlanetariumSeatGrid::Node::Node(std::string value) : seat(std::move(value)) {}
            bool PlanetariumSeatGrid::booked(const std::string& seat) const {
                const Node* current = dome_.get();
                while (current) {
                    if (seat == current->seat) return true;
                    current = seat < current->seat ? current->front_seat.get() : current->back_seat.get();
                }
                return false;
            }
            std::size_t PlanetariumSeatGrid::seats() const { return seats_; }
            void PlanetariumSeatGrid::book(const std::string& seat) {
                if (!dome_) {
                    dome_ = std::make_unique<Node>(seat);
                    seats_ = 1;
                    return;
                }
                Node* current = dome_.get();
                for (;;) {
                    if (seat == current->seat) throw SeatBookedError("seat already booked");
                    if (seat < current->seat) {
                        if (!current->front_seat) {
                            current->front_seat = std::make_unique<Node>(seat);
                            ++seats_;
                            return;
                        }
                        current = current->front_seat.get();
                    } else {
                        if (!current->back_seat) {
                            current->back_seat = std::make_unique<Node>(seat);
                            ++seats_;
                            return;
                        }
                        current = current->back_seat.get();
                    }
                }
            }
            std::string PlanetariumSeatGrid::usher_path(const std::string& seat) const {
                const Node* current = dome_.get();
                std::string path = "base";
                while (current) {
                    if (seat == current->seat) return path;
                    if (seat < current->seat) {
                        path += "|L";
                        current = current->front_seat.get();
                    } else {
                        path += "|R";
                        current = current->back_seat.get();
                    }
                }
                throw SeatMissingError("seat is not booked");
            }
            std::optional<std::string> PlanetariumSeatGrid::parent_of(const std::string& seat) const {
                const Node* current = dome_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (seat == current->seat) {
                        if (!parent) return std::nullopt;
                        return parent->seat;
                    }
                    parent = current;
                    current = seat < current->seat ? current->front_seat.get() : current->back_seat.get();
                }
                throw SeatMissingError("seat is not booked");
            }
            std::int32_t PlanetariumSeatGrid::depth_of(const std::string& seat) const {
                const Node* current = dome_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (seat == current->seat) return depth;
                    ++depth;
                    current = seat < current->seat ? current->front_seat.get() : current->back_seat.get();
                }
                throw SeatMissingError("seat is not booked");
            }
            """,
            """
            PlanetariumSeatGrid::Node::Node(std::string value) : seat(std::move(value)) {}
            bool PlanetariumSeatGrid::booked(const std::string& seat) const {
                const Node* current = dome_.get();
                while (current) {
                    if (seat == current->seat) return true;
                    current = current->front_seat.get();
                }
                return false;
            }
            std::size_t PlanetariumSeatGrid::seats() const { return seats_; }
            void PlanetariumSeatGrid::book(const std::string& seat) {
                if (booked(seat)) throw SeatBookedError("seat already booked");
                if (!dome_) {
                    dome_ = std::make_unique<Node>(seat);
                    seats_ = 1;
                    return;
                }
                Node* current = dome_.get();
                while (current->front_seat) current = current->front_seat.get();
                current->front_seat = std::make_unique<Node>(seat);
                ++seats_;
            }
            std::string PlanetariumSeatGrid::usher_path(const std::string& seat) const {
                const Node* current = dome_.get();
                std::string path = "base";
                while (current) {
                    if (seat == current->seat) return path;
                    path += "|L";
                    current = current->front_seat.get();
                }
                throw SeatMissingError("seat is not booked");
            }
            std::optional<std::string> PlanetariumSeatGrid::parent_of(const std::string& seat) const {
                const Node* current = dome_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (seat == current->seat) {
                        if (!parent) return std::nullopt;
                        return parent->seat;
                    }
                    parent = current;
                    current = current->front_seat.get();
                }
                throw SeatMissingError("seat is not booked");
            }
            std::int32_t PlanetariumSeatGrid::depth_of(const std::string& seat) const {
                const Node* current = dome_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (seat == current->seat) return depth;
                    ++depth;
                    current = current->front_seat.get();
                }
                throw SeatMissingError("seat is not booked");
            }
            """,
            """
            PlanetariumSeatGrid grid;
            grid.book("C12");
            grid.book("C06");
            grid.book("C18");
            if (!grid.booked("C06") || grid.booked("C99")) return 1;
            if (grid.seats() != 3U) return 2;
            return 0;
            """,
            """
            PlanetariumSeatGrid grid;
            bool threw = false;
            try { grid.depth_of("C12"); } catch (const SeatMissingError&) { threw = true; }
            if (!threw) return 1;
            grid.book("C12");
            grid.book("C06");
            grid.book("C18");
            grid.book("C03");
            grid.book("C09");
            grid.book("C15");
            grid.book("C21");
            grid.book("C08");
            threw = false;
            try { grid.book("C09"); } catch (const SeatBookedError&) { threw = true; }
            if (!threw) return 2;
            if (grid.seats() != 8U) return 3;
            if (grid.usher_path("C08") != "base|L|R|L") return 4;
            if (grid.usher_path("C15") != "base|R|L") return 5;
            if (grid.usher_path("C12") != "base") return 6;
            if (grid.parent_of("C08").value_or("NONE") != "C09") return 7;
            if (grid.parent_of("C12").has_value()) return 8;
            if (grid.depth_of("C08") != 3) return 9;
            if (grid.depth_of("C12") != 0) return 10;
            threw = false;
            try { grid.parent_of("C99"); } catch (const SeatMissingError&) { threw = true; }
            if (!threw) return 11;
            return 0;
            """,
            "string-keyed linked seats with usher paths and parents",
            "an ordered container, a sorted std::vector, or a single-sided front-seat chain that ignores ordering decisions as the core store",
            "exact usher paths, parents, and depths after C12,C06,C18,C03,C09,C15,C21,C08, with duplicate/absent channels",
            "string-keyed navigation grammar",
            "navigation, successor, prune, two-phase, or rank ordered tree",
        ),
        c(
            "f26bst-tunnel-bolt-map",
            "Tunnel bolt map",
            "tunnel_bolt",
            """
            class BoltDuplicateError : public std::out_of_range {
            public:
                explicit BoltDuplicateError(const std::string& message) : std::out_of_range(message) {}
            };
            class BoltAbsentError : public std::invalid_argument {
            public:
                explicit BoltAbsentError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TunnelBoltMap {
            public:
                void bolt(std::int32_t anchor);
                void unbolt(std::int32_t anchor);
                bool bolted(std::int32_t anchor) const;
                std::size_t anchors() const;
                std::string bore_path(std::int32_t anchor) const;
                std::optional<std::int32_t> parent_of(std::int32_t anchor) const;
            };
            """,
            """
            class BoltDuplicateError : public std::out_of_range {
            public:
                explicit BoltDuplicateError(const std::string& message) : std::out_of_range(message) {}
            };
            class BoltAbsentError : public std::invalid_argument {
            public:
                explicit BoltAbsentError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TunnelBoltMap {
            public:
                void bolt(std::int32_t anchor);
                void unbolt(std::int32_t anchor);
                bool bolted(std::int32_t anchor) const;
                std::size_t anchors() const;
                std::string bore_path(std::int32_t anchor) const;
                std::optional<std::int32_t> parent_of(std::int32_t anchor) const;
            private:
                struct Node {
                    std::int32_t anchor;
                    std::unique_ptr<Node> shallow_bolt;
                    std::unique_ptr<Node> deep_bolt;
                    explicit Node(std::int32_t value);
                };
                std::unique_ptr<Node> face_;
                std::size_t anchors_ = 0;
                static std::unique_ptr<Node> unlink(std::unique_ptr<Node> node, std::int32_t anchor, bool& removed);
            };
            """,
            """
            TunnelBoltMap::Node::Node(std::int32_t value) : anchor(value) {}
            bool TunnelBoltMap::bolted(std::int32_t anchor) const {
                const Node* current = face_.get();
                while (current) {
                    if (anchor == current->anchor) return true;
                    current = anchor < current->anchor ? current->shallow_bolt.get() : current->deep_bolt.get();
                }
                return false;
            }
            std::size_t TunnelBoltMap::anchors() const { return anchors_; }
            void TunnelBoltMap::bolt(std::int32_t anchor) {
                if (!face_) {
                    face_ = std::make_unique<Node>(anchor);
                    anchors_ = 1;
                    return;
                }
                Node* current = face_.get();
                for (;;) {
                    if (anchor == current->anchor) throw BoltDuplicateError("anchor already bolted");
                    if (anchor < current->anchor) {
                        if (!current->shallow_bolt) {
                            current->shallow_bolt = std::make_unique<Node>(anchor);
                            ++anchors_;
                            return;
                        }
                        current = current->shallow_bolt.get();
                    } else {
                        if (!current->deep_bolt) {
                            current->deep_bolt = std::make_unique<Node>(anchor);
                            ++anchors_;
                            return;
                        }
                        current = current->deep_bolt.get();
                    }
                }
            }
            std::unique_ptr<TunnelBoltMap::Node> TunnelBoltMap::unlink(std::unique_ptr<Node> node, std::int32_t anchor, bool& removed) {
                if (!node) return nullptr;
                if (anchor < node->anchor) {
                    node->shallow_bolt = unlink(std::move(node->shallow_bolt), anchor, removed);
                    return node;
                }
                if (node->anchor < anchor) {
                    node->deep_bolt = unlink(std::move(node->deep_bolt), anchor, removed);
                    return node;
                }
                removed = true;
                if (!node->shallow_bolt) return std::move(node->deep_bolt);
                if (!node->deep_bolt) return std::move(node->shallow_bolt);
                Node* predecessor = node->shallow_bolt.get();
                while (predecessor->deep_bolt) predecessor = predecessor->deep_bolt.get();
                node->anchor = predecessor->anchor;
                bool ignored = false;
                node->shallow_bolt = unlink(std::move(node->shallow_bolt), predecessor->anchor, ignored);
                return node;
            }
            void TunnelBoltMap::unbolt(std::int32_t anchor) {
                bool removed = false;
                face_ = unlink(std::move(face_), anchor, removed);
                if (!removed) throw BoltAbsentError("anchor is not bolted");
                --anchors_;
            }
            std::string TunnelBoltMap::bore_path(std::int32_t anchor) const {
                const Node* current = face_.get();
                std::string path = "head";
                while (current) {
                    if (anchor == current->anchor) return path;
                    if (anchor < current->anchor) {
                        path += ">l";
                        current = current->shallow_bolt.get();
                    } else {
                        path += ">r";
                        current = current->deep_bolt.get();
                    }
                }
                throw BoltAbsentError("anchor is not bolted");
            }
            std::optional<std::int32_t> TunnelBoltMap::parent_of(std::int32_t anchor) const {
                const Node* current = face_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (anchor == current->anchor) {
                        if (!parent) return std::nullopt;
                        return parent->anchor;
                    }
                    parent = current;
                    current = anchor < current->anchor ? current->shallow_bolt.get() : current->deep_bolt.get();
                }
                return std::nullopt;
            }
            """,
            """
            TunnelBoltMap::Node::Node(std::int32_t value) : anchor(value) {}
            bool TunnelBoltMap::bolted(std::int32_t anchor) const {
                const Node* current = face_.get();
                while (current) {
                    if (anchor == current->anchor) return true;
                    current = current->deep_bolt.get();
                }
                return false;
            }
            std::size_t TunnelBoltMap::anchors() const { return anchors_; }
            void TunnelBoltMap::bolt(std::int32_t anchor) {
                if (bolted(anchor)) throw BoltDuplicateError("anchor already bolted");
                if (!face_) {
                    face_ = std::make_unique<Node>(anchor);
                    anchors_ = 1;
                    return;
                }
                Node* current = face_.get();
                while (current->deep_bolt) current = current->deep_bolt.get();
                current->deep_bolt = std::make_unique<Node>(anchor);
                ++anchors_;
            }
            void TunnelBoltMap::unbolt(std::int32_t anchor) {
                if (!face_) throw BoltAbsentError("anchor is not bolted");
                if (face_->anchor == anchor) {
                    face_ = std::move(face_->deep_bolt);
                    --anchors_;
                    return;
                }
                Node* parent = face_.get();
                while (parent->deep_bolt && parent->deep_bolt->anchor != anchor) parent = parent->deep_bolt.get();
                if (!parent->deep_bolt) throw BoltAbsentError("anchor is not bolted");
                parent->deep_bolt = std::move(parent->deep_bolt->deep_bolt);
                --anchors_;
            }
            std::string TunnelBoltMap::bore_path(std::int32_t anchor) const {
                const Node* current = face_.get();
                std::string path = "head";
                while (current) {
                    if (anchor == current->anchor) return path;
                    path += ">r";
                    current = current->deep_bolt.get();
                }
                throw BoltAbsentError("anchor is not bolted");
            }
            std::optional<std::int32_t> TunnelBoltMap::parent_of(std::int32_t anchor) const {
                const Node* current = face_.get();
                const Node* parent = nullptr;
                while (current) {
                    if (anchor == current->anchor) {
                        if (!parent) return std::nullopt;
                        return parent->anchor;
                    }
                    parent = current;
                    current = current->deep_bolt.get();
                }
                return std::nullopt;
            }
            """,
            """
            TunnelBoltMap map;
            map.bolt(96);
            map.bolt(48);
            map.bolt(144);
            if (!map.bolted(48) || map.bolted(999)) return 1;
            if (map.anchors() != 3U) return 2;
            map.unbolt(48);
            if (map.bolted(48)) return 3;
            if (map.anchors() != 2U) return 4;
            return 0;
            """,
            """
            TunnelBoltMap map;
            map.bolt(96);
            map.bolt(48);
            map.bolt(144);
            map.bolt(24);
            map.bolt(72);
            map.bolt(120);
            map.bolt(168);
            map.bolt(60);
            map.bolt(84);
            bool threw = false;
            try { map.bolt(72); } catch (const BoltDuplicateError&) { threw = true; }
            if (!threw) return 1;
            if (map.anchors() != 9U) return 2;
            if (map.bore_path(84) != "head>l>r>r") return 3;
            if (map.parent_of(84) != 72) return 4;
            if (map.parent_of(96).has_value()) return 5;
            map.unbolt(48);
            if (map.parent_of(72) != 24) return 6;
            if (map.bore_path(72) != "head>l>r") return 7;
            if (map.bore_path(60) != "head>l>r>l") return 8;
            map.unbolt(96);
            if (map.parent_of(144) != 84) return 9;
            if (map.bore_path(24) != "head>l") return 10;
            if (map.parent_of(84).has_value()) return 11;
            if (map.bolted(96)) return 12;
            if (map.anchors() != 7U) return 13;
            threw = false;
            try { map.unbolt(96); } catch (const BoltAbsentError&) { threw = true; }
            if (!threw) return 14;
            return 0;
            """,
            "predecessor-side two-child removal over owned linked anchors",
            "an ordered container, a sorted std::vector, or a single-sided deep-bolt chain that ignores ordering decisions as the core store",
            "exact post-removal paths and parents after 96,48,144,24,72,120,168,60,84 with predecessor-side unbolts",
            "predecessor replacement contrasted with successor roots",
            "navigation, successor, prune, two-phase, or rank ordered tree",
            project_support=True,
        ),
        c(
            "f26bst-desert-well-index",
            "Desert well index",
            "desert_well",
            """
            class WellDuplicateError : public std::logic_error {
            public:
                explicit WellDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class WellAbsentError : public std::runtime_error {
            public:
                explicit WellAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class DesertWellIndex {
            public:
                void drill(std::int64_t well);
                bool drilled(std::int64_t well) const;
                std::size_t wells() const;
                std::optional<std::int64_t> kth_shallowest(std::size_t rank) const;
                std::int32_t depth_of(std::int64_t well) const;
            };
            """,
            """
            class WellDuplicateError : public std::logic_error {
            public:
                explicit WellDuplicateError(const std::string& message) : std::logic_error(message) {}
            };
            class WellAbsentError : public std::runtime_error {
            public:
                explicit WellAbsentError(const std::string& message) : std::runtime_error(message) {}
            };
            class DesertWellIndex {
            public:
                void drill(std::int64_t well);
                bool drilled(std::int64_t well) const;
                std::size_t wells() const;
                std::optional<std::int64_t> kth_shallowest(std::size_t rank) const;
                std::int32_t depth_of(std::int64_t well) const;
            private:
                struct Node {
                    std::int64_t well;
                    std::size_t below = 1;
                    std::unique_ptr<Node> shallow_well;
                    std::unique_ptr<Node> deep_well;
                    explicit Node(std::int64_t value);
                };
                std::unique_ptr<Node> basin_;
                std::size_t wells_ = 0;
                static std::unique_ptr<Node> link(std::unique_ptr<Node> node, std::int64_t well, bool& added);
            };
            """,
            """
            DesertWellIndex::Node::Node(std::int64_t value) : well(value) {}
            bool DesertWellIndex::drilled(std::int64_t well) const {
                const Node* current = basin_.get();
                while (current) {
                    if (well == current->well) return true;
                    current = well < current->well ? current->shallow_well.get() : current->deep_well.get();
                }
                return false;
            }
            std::size_t DesertWellIndex::wells() const { return wells_; }
            std::unique_ptr<DesertWellIndex::Node> DesertWellIndex::link(std::unique_ptr<Node> node, std::int64_t well, bool& added) {
                if (!node) {
                    added = true;
                    return std::make_unique<Node>(well);
                }
                if (well == node->well) return node;
                if (well < node->well) {
                    node->shallow_well = link(std::move(node->shallow_well), well, added);
                } else {
                    node->deep_well = link(std::move(node->deep_well), well, added);
                }
                if (added) node->below += 1;
                return node;
            }
            void DesertWellIndex::drill(std::int64_t well) {
                bool added = false;
                basin_ = link(std::move(basin_), well, added);
                if (!added) throw WellDuplicateError("well already drilled");
                ++wells_;
            }
            std::optional<std::int64_t> DesertWellIndex::kth_shallowest(std::size_t rank) const {
                if (rank == 0 || rank > wells_) return std::nullopt;
                const Node* current = basin_.get();
                while (current) {
                    const std::size_t left_size = current->shallow_well ? current->shallow_well->below : 0;
                    if (rank == left_size + 1) return current->well;
                    if (rank <= left_size) {
                        current = current->shallow_well.get();
                    } else {
                        rank -= left_size + 1;
                        current = current->deep_well.get();
                    }
                }
                return std::nullopt;
            }
            std::int32_t DesertWellIndex::depth_of(std::int64_t well) const {
                const Node* current = basin_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (well == current->well) return depth;
                    ++depth;
                    current = well < current->well ? current->shallow_well.get() : current->deep_well.get();
                }
                throw WellAbsentError("well is not drilled");
            }
            """,
            """
            DesertWellIndex::Node::Node(std::int64_t value) : well(value) {}
            bool DesertWellIndex::drilled(std::int64_t well) const {
                const Node* current = basin_.get();
                while (current) {
                    if (well == current->well) return true;
                    current = current->shallow_well.get();
                }
                return false;
            }
            std::size_t DesertWellIndex::wells() const { return wells_; }
            void DesertWellIndex::drill(std::int64_t well) {
                if (drilled(well)) throw WellDuplicateError("well already drilled");
                if (!basin_) {
                    basin_ = std::make_unique<Node>(well);
                    wells_ = 1;
                    return;
                }
                Node* current = basin_.get();
                for (;;) {
                    current->below += 1;
                    if (!current->shallow_well) {
                        current->shallow_well = std::make_unique<Node>(well);
                        ++wells_;
                        return;
                    }
                    current = current->shallow_well.get();
                }
            }
            std::optional<std::int64_t> DesertWellIndex::kth_shallowest(std::size_t rank) const {
                if (rank == 0 || rank > wells_) return std::nullopt;
                const Node* current = basin_.get();
                while (current && rank > 1) {
                    --rank;
                    current = current->shallow_well.get();
                }
                if (!current) return std::nullopt;
                return current->well;
            }
            std::int32_t DesertWellIndex::depth_of(std::int64_t well) const {
                const Node* current = basin_.get();
                std::int32_t depth = 0;
                while (current) {
                    if (well == current->well) return depth;
                    ++depth;
                    current = current->shallow_well.get();
                }
                throw WellAbsentError("well is not drilled");
            }
            """,
            """
            DesertWellIndex index;
            index.drill(640);
            index.drill(320);
            index.drill(960);
            if (!index.drilled(320) || index.drilled(9999)) return 1;
            if (index.wells() != 3U) return 2;
            return 0;
            """,
            """
            DesertWellIndex index;
            bool threw = false;
            try { index.depth_of(640); } catch (const WellAbsentError&) { threw = true; }
            if (!threw) return 1;
            if (index.kth_shallowest(1).has_value()) return 2;
            index.drill(640);
            index.drill(320);
            index.drill(960);
            index.drill(160);
            index.drill(480);
            index.drill(800);
            index.drill(1120);
            index.drill(240);
            index.drill(400);
            threw = false;
            try { index.drill(480); } catch (const WellDuplicateError&) { threw = true; }
            if (!threw) return 3;
            if (index.wells() != 9U) return 4;
            if (index.kth_shallowest(1) != 160) return 5;
            if (index.kth_shallowest(3) != 320) return 6;
            if (index.kth_shallowest(5) != 480) return 7;
            if (index.kth_shallowest(9) != 1120) return 8;
            if (index.kth_shallowest(0).has_value()) return 9;
            if (index.kth_shallowest(10).has_value()) return 10;
            if (index.depth_of(400) != 3) return 11;
            if (index.depth_of(240) != 3) return 12;
            if (index.depth_of(640) != 0) return 13;
            threw = false;
            try { index.depth_of(9999); } catch (const WellAbsentError&) { threw = true; }
            if (!threw) return 14;
            return 0;
            """,
            "subtree-size augmentation over owned linked wells for one-based rank queries",
            "an ordered container, a sorted std::vector, or a single-sided shallow-well chain that ignores ordering decisions as the core store",
            "exact ranks and depths after 640,320,960,160,480,800,1120,240,400, with rank zero and overflow nullopt",
            "order-statistic augmentation on owned nodes",
            "navigation, successor, prune, two-phase, or rank ordered tree",
            project_support=True,
        ),
    )
    return rows


CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-bst-seven-dimension-artifacts-v1"
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

Implement a clean-room C++17 ordered linked-node tree component for a local
binary-search-tree analog. This root is independently authored for SFT
task-family construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep node ownership, insertion-ordered structure, duplicate policy,
structural queries, and traversal or trace order deterministic and explicit for
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
                "source": "w8-biayn clean-room fixed26 binary-search-tree analog curriculum",
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
description = "{spec.title}: structural paths, depths, parents, traversal order, duplicate policy, and wrong-substitute rejection"

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
            "family": "binary-search-tree",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "binary-search-tree",
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
    text = re.sub(r"\bf26bst[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        "schema_version": "fixed26-bst-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-bst-fresh-") as temporary:
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
        "schema_version": "fixed26-bst-core-v1",
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
for task_root in sorted(ROOT.glob("f26bst-*")):
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
            "schema_version": "fixed26-bst-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-bst-docker-") as temporary:
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
        "schema_version": "fixed26-bst-docker-sanity-v1",
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
        "schema_version": "fixed26-bst-creator-preflight-v1",
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
        "capability": "fixed26-binary-search-tree-analog",
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
            "task": "implement clean-room fixed26 binary-search-tree analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned linked-node structure with insertion-ordered shape; explicit duplicate policy; structure-dependent observables; rejected operations never mutate; deterministic traversals and traces",
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
            "target_family": "binary-search-tree",
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
