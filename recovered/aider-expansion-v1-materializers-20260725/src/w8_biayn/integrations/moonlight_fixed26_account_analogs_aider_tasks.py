"""Create and verify the fixed-26 bank-account clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b003-bank-account.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b003-bank-account"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_account_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_account_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b003-bank-account"
FAMILY_ID = "aider-fixed26-bank-account-analogs-v1"
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
        "f26acc-transit-fare-purse",
        "f26acc-storage-unit-lease",
        "f26acc-arcade-token-card",
        "f26acc-tool-lending-register",
        "f26acc-photo-studio-booking",
        "f26acc-karaoke-room-session",
        "f26acc-farm-csa-share",
        "f26acc-journal-delivery-plan",
        "f26acc-season-ticket-gate",
        "f26acc-coworking-desk-pass",
        "f26acc-library-hold-shelf",
        "f26acc-aquarium-club-fund",
        "f26acc-sports-league-roster",
        "f26acc-language-class-enrollment",
        "f26acc-chess-match-clock",
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
#include <map>
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
            "f26acc-library-card-desk",
            "Library card desk",
            "library_card",
            """
            class CardError : public std::logic_error {
            public:
                explicit CardError(const std::string& message) : std::logic_error(message) {}
            };
            class CountError : public std::invalid_argument {
            public:
                explicit CountError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LimitError : public std::out_of_range {
            public:
                explicit LimitError(const std::string& message) : std::out_of_range(message) {}
            };
            class DeskCard {
            public:
                void activate();
                void retire();
                void borrow(std::int32_t count);
                void give_back(std::int32_t count);
                std::int32_t borrowed() const;
                bool active() const;
            };
            """,
            """
            class CardError : public std::logic_error {
            public:
                explicit CardError(const std::string& message) : std::logic_error(message) {}
            };
            class CountError : public std::invalid_argument {
            public:
                explicit CountError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LimitError : public std::out_of_range {
            public:
                explicit LimitError(const std::string& message) : std::out_of_range(message) {}
            };
            class DeskCard {
            public:
                void activate();
                void retire();
                void borrow(std::int32_t count);
                void give_back(std::int32_t count);
                std::int32_t borrowed() const;
                bool active() const;
            private:
                bool active_ = false;
                std::int32_t borrowed_ = 0;
            };
            """,
            """
            namespace {
            constexpr std::int32_t kBorrowLimit = 7;
            }  // namespace
            void DeskCard::activate() {
                if (active_) throw CardError("card already active");
                active_ = true;
                borrowed_ = 0;
            }
            void DeskCard::retire() {
                if (!active_) throw CardError("card is not active");
                if (borrowed_ != 0) throw CardError("loans still outstanding");
                active_ = false;
            }
            void DeskCard::borrow(std::int32_t count) {
                if (!active_) throw CardError("card is not active");
                if (count <= 0) throw CountError("borrow count must be positive");
                if (borrowed_ + count > kBorrowLimit) throw LimitError("borrow limit exceeded");
                borrowed_ += count;
            }
            void DeskCard::give_back(std::int32_t count) {
                if (!active_) throw CardError("card is not active");
                if (count <= 0) throw CountError("return count must be positive");
                if (count > borrowed_) throw LimitError("cannot return more than borrowed");
                borrowed_ -= count;
            }
            std::int32_t DeskCard::borrowed() const { return borrowed_; }
            bool DeskCard::active() const { return active_; }
            """,
            """
            namespace {
            constexpr std::int32_t kBorrowLimit = 7;
            }  // namespace
            void DeskCard::activate() { active_ = true; }
            void DeskCard::retire() { active_ = false; }
            void DeskCard::borrow(std::int32_t count) {
                if (count <= 0) throw CountError("borrow count must be positive");
                if (borrowed_ + count > kBorrowLimit) throw LimitError("borrow limit exceeded");
                borrowed_ += count;
            }
            void DeskCard::give_back(std::int32_t count) {
                if (count <= 0) throw CountError("return count must be positive");
                if (count > borrowed_) throw LimitError("cannot return more than borrowed");
                borrowed_ -= count;
            }
            std::int32_t DeskCard::borrowed() const { return borrowed_; }
            bool DeskCard::active() const { return active_; }
            """,
            """
            DeskCard card;
            card.activate();
            card.borrow(3);
            if (card.borrowed() != 3) return 1;
            card.give_back(1);
            if (card.borrowed() != 2) return 2;
            if (!card.active()) return 3;
            return 0;
            """,
            """
            DeskCard card;
            bool threw = false;
            try { card.borrow(1); } catch (const CardError&) { threw = true; }
            if (!threw) return 1;
            card.activate();
            threw = false;
            try { card.borrow(0); } catch (const CountError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { card.borrow(8); } catch (const LimitError&) { threw = true; }
            if (!threw) return 3;
            if (card.borrowed() != 0) return 4;
            card.borrow(7);
            threw = false;
            try { card.retire(); } catch (const CardError&) { threw = true; }
            if (!threw) return 5;
            card.give_back(7);
            card.retire();
            if (card.active()) return 6;
            card.activate();
            if (card.borrowed() != 0) return 7;
            return 0;
            """,
            "lifecycle guards on every loan operation so an inactive card can never borrow or return",
            "unguarded loan operations that work while retired or clamp counts instead of throwing",
            "borrows before activation, non-positive counts, limit overflow with unchanged state, retire with loans, and reactivation",
            "lifecycle-guarded mutation with typed failure channels in a two-file API",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-pool-locker-room",
            "Pool locker room",
            "pool_lockers",
            """
            class LockerError : public std::runtime_error {
            public:
                explicit LockerError(const std::string& message) : std::runtime_error(message) {}
            };
            class LockerBoard {
            public:
                void assign(std::string_view member);
                void release();
                void store(std::int32_t items);
                void retrieve(std::int32_t items);
                std::int32_t stored() const;
                std::string holder() const;
            };
            """,
            """
            class LockerError : public std::runtime_error {
            public:
                explicit LockerError(const std::string& message) : std::runtime_error(message) {}
            };
            class LockerBoard {
            public:
                void assign(std::string_view member);
                void release();
                void store(std::int32_t items);
                void retrieve(std::int32_t items);
                std::int32_t stored() const;
                std::string holder() const;
            private:
                bool assigned_ = false;
                std::string holder_;
                std::int32_t stored_ = 0;
            };
            """,
            """
            void LockerBoard::assign(std::string_view member) {
                if (assigned_) throw LockerError("locker already assigned");
                if (member.empty()) throw LockerError("member name required");
                assigned_ = true;
                holder_ = std::string(member);
                stored_ = 0;
            }
            void LockerBoard::release() {
                if (!assigned_) throw LockerError("locker is not assigned");
                if (stored_ != 0) throw LockerError("locker still holds items");
                assigned_ = false;
                holder_.clear();
            }
            void LockerBoard::store(std::int32_t items) {
                if (!assigned_) throw LockerError("locker is not assigned");
                if (items <= 0) throw LockerError("item count must be positive");
                stored_ += items;
            }
            void LockerBoard::retrieve(std::int32_t items) {
                if (!assigned_) throw LockerError("locker is not assigned");
                if (items <= 0) throw LockerError("item count must be positive");
                if (items > stored_) throw LockerError("not enough stored items");
                stored_ -= items;
            }
            std::int32_t LockerBoard::stored() const { return stored_; }
            std::string LockerBoard::holder() const { return holder_; }
            """,
            """
            void LockerBoard::assign(std::string_view member) {
                holder_ = std::string(member);
                assigned_ = true;
                stored_ = 0;
            }
            void LockerBoard::release() {
                assigned_ = false;
                holder_.clear();
                stored_ = 0;
            }
            void LockerBoard::store(std::int32_t items) {
                if (items <= 0) throw LockerError("item count must be positive");
                stored_ += items;
            }
            void LockerBoard::retrieve(std::int32_t items) {
                if (items <= 0) throw LockerError("item count must be positive");
                if (items > stored_) throw LockerError("not enough stored items");
                stored_ -= items;
            }
            std::int32_t LockerBoard::stored() const { return stored_; }
            std::string LockerBoard::holder() const { return holder_; }
            """,
            """
            LockerBoard board;
            board.assign("mira");
            board.store(2);
            board.retrieve(1);
            if (board.stored() != 1) return 1;
            if (board.holder() != "mira") return 2;
            board.retrieve(1);
            board.release();
            if (board.stored() != 0) return 3;
            if (!board.holder().empty()) return 4;
            return 0;
            """,
            """
            LockerBoard board;
            bool threw = false;
            try { board.store(1); } catch (const LockerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { board.assign(""); } catch (const LockerError&) { threw = true; }
            if (!threw) return 2;
            board.assign("oda");
            board.store(3);
            threw = false;
            try { board.retrieve(4); } catch (const LockerError&) { threw = true; }
            if (!threw) return 3;
            if (board.stored() != 3) return 4;
            threw = false;
            try { board.release(); } catch (const LockerError&) { threw = true; }
            if (!threw) return 5;
            board.retrieve(3);
            board.release();
            board.assign("kip");
            if (board.holder() != "kip") return 6;
            if (board.stored() != 0) return 7;
            return 0;
            """,
            "single-locker assignment lifecycle where unassigned storage operations always fail",
            "storage without assignment or releases that silently discard stored contents",
            "operations before assignment, empty names, over-retrieval with unchanged state, release with contents, and reassignment",
            "single-owner lifecycle discipline with exact exception behavior",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-museum-member-pass",
            "Museum member pass",
            "museum_pass",
            """
            class PassError : public std::domain_error {
            public:
                explicit PassError(const std::string& message) : std::domain_error(message) {}
            };
            class MemberPass {
            public:
                void renew(std::int32_t months);
                void expire();
                void admit(std::int32_t visitors);
                std::int32_t visits() const;
                std::int32_t months_left() const;
                bool lapsed() const;
            };
            """,
            """
            class PassError : public std::domain_error {
            public:
                explicit PassError(const std::string& message) : std::domain_error(message) {}
            };
            class MemberPass {
            public:
                void renew(std::int32_t months);
                void expire();
                void admit(std::int32_t visitors);
                std::int32_t visits() const;
                std::int32_t months_left() const;
                bool lapsed() const;
            private:
                bool active_ = false;
                std::int32_t months_ = 0;
                std::int32_t visits_left_ = 0;
                std::int32_t visits_ = 0;
            };
            """,
            """
            void MemberPass::renew(std::int32_t months) {
                if (months < 1 || months > 24) throw PassError("renewal months out of range");
                if (active_) throw PassError("pass already current");
                active_ = true;
                months_ = months;
                visits_left_ = months * 10;
            }
            void MemberPass::expire() {
                if (!active_) throw PassError("pass is not current");
                active_ = false;
            }
            void MemberPass::admit(std::int32_t visitors) {
                if (!active_) throw PassError("pass has lapsed");
                if (visitors < 1 || visitors > 4) throw PassError("party size out of range");
                if (visitors > visits_left_) throw PassError("visit budget exhausted");
                visits_left_ -= visitors;
                visits_ += visitors;
            }
            std::int32_t MemberPass::visits() const { return visits_; }
            std::int32_t MemberPass::months_left() const { return active_ ? months_ : 0; }
            bool MemberPass::lapsed() const { return !active_; }
            """,
            """
            void MemberPass::renew(std::int32_t months) {
                if (months < 1 || months > 24) throw PassError("renewal months out of range");
                active_ = true;
                months_ = months;
                visits_left_ = months * 10;
            }
            void MemberPass::expire() { active_ = false; }
            void MemberPass::admit(std::int32_t visitors) {
                if (visitors < 1 || visitors > 4) throw PassError("party size out of range");
                visits_ += visitors;
            }
            std::int32_t MemberPass::visits() const { return visits_; }
            std::int32_t MemberPass::months_left() const { return active_ ? months_ : 0; }
            bool MemberPass::lapsed() const { return !active_; }
            """,
            """
            MemberPass pass;
            pass.renew(2);
            pass.admit(3);
            if (pass.visits() != 3) return 1;
            if (pass.months_left() != 2) return 2;
            pass.expire();
            if (!pass.lapsed()) return 3;
            return 0;
            """,
            """
            MemberPass pass;
            bool threw = false;
            try { pass.admit(1); } catch (const PassError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { pass.renew(25); } catch (const PassError&) { threw = true; }
            if (!threw) return 2;
            pass.renew(1);
            threw = false;
            try { pass.admit(5); } catch (const PassError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { pass.renew(1); } catch (const PassError&) { threw = true; }
            if (!threw) return 4;
            pass.admit(4);
            pass.admit(4);
            pass.admit(2);
            threw = false;
            try { pass.admit(1); } catch (const PassError&) { threw = true; }
            if (!threw) return 5;
            if (pass.visits() != 10) return 6;
            pass.expire();
            threw = false;
            try { pass.admit(1); } catch (const PassError&) { threw = true; }
            if (!threw) return 7;
            pass.renew(1);
            if (pass.lapsed()) return 8;
            return 0;
            """,
            "visit budgets fed by renewal so a lapsed or exhausted pass can never admit",
            "admission that ignores lapse state or the remaining visit budget",
            "admission before renewal, oversized parties, budget exhaustion, admission after expiry, and re-renewal rules",
            "budget-coupled lifecycle guards absent from single-file rows",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-transit-fare-purse",
            "Transit fare purse",
            "transit_fare",
            """
            class FareError : public std::runtime_error {
            public:
                explicit FareError(const std::string& message) : std::runtime_error(message) {}
            };
            class CapError : public std::out_of_range {
            public:
                explicit CapError(const std::string& message) : std::out_of_range(message) {}
            };
            class FarePurse {
            public:
                void activate();
                void block();
                void load(std::int64_t cents);
                void ride(std::int64_t fare_cents);
                std::int64_t purse_cents() const;
                std::int32_t rides() const;
            };
            """,
            """
            class FareError : public std::runtime_error {
            public:
                explicit FareError(const std::string& message) : std::runtime_error(message) {}
            };
            class CapError : public std::out_of_range {
            public:
                explicit CapError(const std::string& message) : std::out_of_range(message) {}
            };
            class FarePurse {
            public:
                void activate();
                void block();
                void load(std::int64_t cents);
                void ride(std::int64_t fare_cents);
                std::int64_t purse_cents() const;
                std::int32_t rides() const;
            private:
                bool active_ = false;
                std::int64_t purse_ = 0;
                std::int32_t rides_ = 0;
            };
            """,
            """
            namespace {
            constexpr std::int32_t kRideCap = 20;
            }  // namespace
            void FarePurse::activate() {
                if (active_) throw FareError("purse already active");
                active_ = true;
                rides_ = 0;
            }
            void FarePurse::block() {
                if (!active_) throw FareError("purse is blocked");
                active_ = false;
            }
            void FarePurse::load(std::int64_t cents) {
                if (!active_) throw FareError("purse is blocked");
                if (cents <= 0) throw FareError("load must be positive");
                purse_ += cents;
            }
            void FarePurse::ride(std::int64_t fare_cents) {
                if (!active_) throw FareError("purse is blocked");
                if (fare_cents <= 0) throw FareError("fare must be positive");
                if (rides_ >= kRideCap) throw CapError("ride cap reached");
                if (fare_cents > purse_) throw FareError("insufficient purse");
                purse_ -= fare_cents;
                ++rides_;
            }
            std::int64_t FarePurse::purse_cents() const { return purse_; }
            std::int32_t FarePurse::rides() const { return rides_; }
            """,
            """
            void FarePurse::activate() { active_ = true; rides_ = 0; }
            void FarePurse::block() { active_ = false; }
            void FarePurse::load(std::int64_t cents) {
                if (cents <= 0) throw FareError("load must be positive");
                purse_ += cents;
            }
            void FarePurse::ride(std::int64_t fare_cents) {
                if (fare_cents <= 0) throw FareError("fare must be positive");
                purse_ = fare_cents > purse_ ? 0 : purse_ - fare_cents;
                ++rides_;
            }
            std::int64_t FarePurse::purse_cents() const { return purse_; }
            std::int32_t FarePurse::rides() const { return rides_; }
            """,
            """
            FarePurse purse;
            purse.activate();
            purse.load(1000);
            purse.ride(275);
            if (purse.purse_cents() != 725) return 1;
            if (purse.rides() != 1) return 2;
            purse.block();
            purse.activate();
            if (purse.purse_cents() != 725) return 3;
            return 0;
            """,
            """
            FarePurse purse;
            bool threw = false;
            try { purse.ride(100); } catch (const FareError&) { threw = true; }
            if (!threw) return 1;
            purse.activate();
            purse.load(500);
            threw = false;
            try { purse.ride(600); } catch (const FareError&) { threw = true; }
            if (!threw) return 2;
            if (purse.purse_cents() != 500) return 3;
            purse.block();
            threw = false;
            try { purse.load(100); } catch (const FareError&) { threw = true; }
            if (!threw) return 4;
            purse.activate();
            for (int i = 0; i < 20; ++i) purse.ride(20);
            if (purse.rides() != 20) return 5;
            threw = false;
            try { purse.ride(20); } catch (const CapError&) { threw = true; }
            if (!threw) return 6;
            if (purse.purse_cents() != 100) return 7;
            return 0;
            """,
            "atomic insufficient-funds rejection with a per-activation ride cap on a guarded purse",
            "clamping rides to a zero balance or riding while the purse is blocked",
            "rides before activation, over-purse rides with unchanged balance, blocked loads, the twenty-ride cap, and reactivation",
            "atomic rejection and balance invariants without copying any monetary benchmark contract",
            "exception-throwing lifecycle class with open/close guards",
            project_support=True,
        ),
        c(
            "f26acc-gym-checkin-gate",
            "Gym check-in gate",
            "gym_gate",
            """
            class GateError : public std::logic_error {
            public:
                explicit GateError(const std::string& message) : std::logic_error(message) {}
            };
            class TurnstileGate {
            public:
                void enroll(std::string_view member);
                void cancel();
                void check_in();
                void check_out();
                bool inside() const;
                std::int32_t visits() const;
            };
            """,
            """
            class GateError : public std::logic_error {
            public:
                explicit GateError(const std::string& message) : std::logic_error(message) {}
            };
            class TurnstileGate {
            public:
                void enroll(std::string_view member);
                void cancel();
                void check_in();
                void check_out();
                bool inside() const;
                std::int32_t visits() const;
            private:
                bool enrolled_ = false;
                bool inside_ = false;
                std::int32_t visits_ = 0;
                std::string member_;
            };
            """,
            """
            void TurnstileGate::enroll(std::string_view member) {
                if (enrolled_) throw GateError("member already enrolled");
                if (member.empty()) throw GateError("member name required");
                enrolled_ = true;
                inside_ = false;
                visits_ = 0;
                member_ = std::string(member);
            }
            void TurnstileGate::cancel() {
                if (!enrolled_) throw GateError("no member enrolled");
                if (inside_) throw GateError("member is inside");
                enrolled_ = false;
                member_.clear();
            }
            void TurnstileGate::check_in() {
                if (!enrolled_) throw GateError("no member enrolled");
                if (inside_) throw GateError("member already inside");
                inside_ = true;
                ++visits_;
            }
            void TurnstileGate::check_out() {
                if (!enrolled_) throw GateError("no member enrolled");
                if (!inside_) throw GateError("member is not inside");
                inside_ = false;
            }
            bool TurnstileGate::inside() const { return inside_; }
            std::int32_t TurnstileGate::visits() const { return visits_; }
            """,
            """
            void TurnstileGate::enroll(std::string_view member) {
                enrolled_ = true;
                inside_ = false;
                member_ = std::string(member);
            }
            void TurnstileGate::cancel() {
                enrolled_ = false;
                inside_ = false;
                member_.clear();
            }
            void TurnstileGate::check_in() {
                inside_ = !inside_;
                if (inside_) ++visits_;
            }
            void TurnstileGate::check_out() { inside_ = false; }
            bool TurnstileGate::inside() const { return inside_; }
            std::int32_t TurnstileGate::visits() const { return visits_; }
            """,
            """
            TurnstileGate gate;
            gate.enroll("sam");
            gate.check_in();
            if (!gate.inside()) return 1;
            gate.check_out();
            if (gate.visits() != 1) return 2;
            return 0;
            """,
            """
            TurnstileGate gate;
            bool threw = false;
            try { gate.check_in(); } catch (const GateError&) { threw = true; }
            if (!threw) return 1;
            gate.enroll("lee");
            gate.check_in();
            threw = false;
            try { gate.check_in(); } catch (const GateError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { gate.cancel(); } catch (const GateError&) { threw = true; }
            if (!threw) return 3;
            gate.check_out();
            gate.cancel();
            threw = false;
            try { gate.check_out(); } catch (const GateError&) { threw = true; }
            if (!threw) return 4;
            gate.enroll("ajo");
            if (gate.visits() != 0) return 5;
            return 0;
            """,
            "turnstile pairing so every check-in matches a check-out under one enrolled member",
            "free toggling that ignores entry/exit pairing or membership state",
            "check-in before enrollment, double check-ins, cancel while inside, operations after cancel, and re-enrollment",
            "paired-transition lifecycle discipline",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-storage-unit-lease",
            "Storage unit lease",
            "storage_lease",
            """
            class LeaseError : public std::runtime_error {
            public:
                explicit LeaseError(const std::string& message) : std::runtime_error(message) {}
            };
            class CapacityError : public std::out_of_range {
            public:
                explicit CapacityError(const std::string& message) : std::out_of_range(message) {}
            };
            class UnitLease {
            public:
                void sign(std::int32_t term_days);
                void terminate();
                void store_crates(std::int32_t n);
                void remove_crates(std::int32_t n);
                std::int32_t crates() const;
                std::int32_t days_left() const;
            };
            """,
            """
            class LeaseError : public std::runtime_error {
            public:
                explicit LeaseError(const std::string& message) : std::runtime_error(message) {}
            };
            class CapacityError : public std::out_of_range {
            public:
                explicit CapacityError(const std::string& message) : std::out_of_range(message) {}
            };
            class UnitLease {
            public:
                void sign(std::int32_t term_days);
                void terminate();
                void store_crates(std::int32_t n);
                void remove_crates(std::int32_t n);
                std::int32_t crates() const;
                std::int32_t days_left() const;
            private:
                bool signed_ = false;
                std::int32_t days_ = 0;
                std::int32_t crates_ = 0;
            };
            """,
            """
            namespace {
            constexpr std::int32_t kCrateCapacity = 40;
            }  // namespace
            void UnitLease::sign(std::int32_t term_days) {
                if (signed_) throw LeaseError("lease already signed");
                if (term_days <= 0 || term_days > 365) throw LeaseError("term out of range");
                signed_ = true;
                days_ = term_days;
                crates_ = 0;
            }
            void UnitLease::terminate() {
                if (!signed_) throw LeaseError("no lease signed");
                if (crates_ != 0) throw LeaseError("unit still holds crates");
                signed_ = false;
                days_ = 0;
            }
            void UnitLease::store_crates(std::int32_t n) {
                if (!signed_) throw LeaseError("no lease signed");
                if (n <= 0) throw LeaseError("crate count must be positive");
                if (crates_ + n > kCrateCapacity) throw CapacityError("unit capacity exceeded");
                crates_ += n;
            }
            void UnitLease::remove_crates(std::int32_t n) {
                if (!signed_) throw LeaseError("no lease signed");
                if (n <= 0) throw LeaseError("crate count must be positive");
                if (n > crates_) throw LeaseError("not enough crates stored");
                crates_ -= n;
            }
            std::int32_t UnitLease::crates() const { return crates_; }
            std::int32_t UnitLease::days_left() const { return signed_ ? days_ : 0; }
            """,
            """
            void UnitLease::sign(std::int32_t term_days) {
                signed_ = true;
                days_ = term_days;
                crates_ = 0;
            }
            void UnitLease::terminate() {
                signed_ = false;
                days_ = 0;
                crates_ = 0;
            }
            void UnitLease::store_crates(std::int32_t n) {
                if (n <= 0) throw LeaseError("crate count must be positive");
                crates_ = crates_ + n > 40 ? 40 : crates_ + n;
            }
            void UnitLease::remove_crates(std::int32_t n) {
                if (n <= 0) throw LeaseError("crate count must be positive");
                if (n > crates_) throw LeaseError("not enough crates stored");
                crates_ -= n;
            }
            std::int32_t UnitLease::crates() const { return crates_; }
            std::int32_t UnitLease::days_left() const { return signed_ ? days_ : 0; }
            """,
            """
            UnitLease lease;
            lease.sign(30);
            lease.store_crates(10);
            lease.remove_crates(4);
            if (lease.crates() != 6) return 1;
            if (lease.days_left() != 30) return 2;
            return 0;
            """,
            """
            UnitLease lease;
            bool threw = false;
            try { lease.store_crates(1); } catch (const LeaseError&) { threw = true; }
            if (!threw) return 1;
            lease.sign(10);
            lease.store_crates(40);
            threw = false;
            try { lease.store_crates(1); } catch (const CapacityError&) { threw = true; }
            if (!threw) return 2;
            if (lease.crates() != 40) return 3;
            threw = false;
            try { lease.remove_crates(41); } catch (const LeaseError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { lease.terminate(); } catch (const LeaseError&) { threw = true; }
            if (!threw) return 5;
            lease.remove_crates(40);
            lease.terminate();
            if (lease.days_left() != 0) return 6;
            lease.sign(5);
            if (lease.crates() != 0) return 7;
            return 0;
            """,
            "capacity-bounded lease where over-capacity stores fail atomically instead of clamping",
            "clamping stores at capacity or terminating with crates still inside",
            "stores before signing, exact capacity then overflow with unchanged state, over-removal, termination with crates, and re-signing",
            "capacity-bound lifecycle guards with exact failure channels",
            "exception-throwing lifecycle class with open/close guards",
            project_support=True,
        ),
        c(
            "f26acc-cinema-season-pass",
            "Cinema season pass",
            "cinema_pass",
            """
            class PassVoidError : public std::logic_error {
            public:
                explicit PassVoidError(const std::string& message) : std::logic_error(message) {}
            };
            class PartyError : public std::invalid_argument {
            public:
                explicit PartyError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BudgetError : public std::out_of_range {
            public:
                explicit BudgetError(const std::string& message) : std::out_of_range(message) {}
            };
            class SeasonPass {
            public:
                void issue(std::int32_t seat_budget);
                void void_pass();
                void admit(std::int32_t seats);
                std::int32_t seats_left() const;
                std::int32_t admissions() const;
            };
            """,
            """
            class PassVoidError : public std::logic_error {
            public:
                explicit PassVoidError(const std::string& message) : std::logic_error(message) {}
            };
            class PartyError : public std::invalid_argument {
            public:
                explicit PartyError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BudgetError : public std::out_of_range {
            public:
                explicit BudgetError(const std::string& message) : std::out_of_range(message) {}
            };
            class SeasonPass {
            public:
                void issue(std::int32_t seat_budget);
                void void_pass();
                void admit(std::int32_t seats);
                std::int32_t seats_left() const;
                std::int32_t admissions() const;
            private:
                bool issued_ = false;
                bool voided_ = false;
                std::int32_t budget_ = 0;
                std::int32_t admissions_ = 0;
            };
            """,
            """
            void SeasonPass::issue(std::int32_t seat_budget) {
                if (voided_) throw PassVoidError("pass was voided");
                if (issued_) throw PartyError("pass already issued");
                if (seat_budget <= 0) throw PartyError("seat budget must be positive");
                issued_ = true;
                budget_ = seat_budget;
            }
            void SeasonPass::void_pass() {
                if (voided_) throw PassVoidError("pass was voided");
                if (!issued_) throw PartyError("no pass to void");
                voided_ = true;
                issued_ = false;
            }
            void SeasonPass::admit(std::int32_t seats) {
                if (voided_) throw PassVoidError("pass was voided");
                if (!issued_) throw PartyError("no pass issued");
                if (seats < 1 || seats > 6) throw PartyError("party size out of range");
                if (seats > budget_) throw BudgetError("seat budget exceeded");
                budget_ -= seats;
                ++admissions_;
            }
            std::int32_t SeasonPass::seats_left() const { return issued_ ? budget_ : 0; }
            std::int32_t SeasonPass::admissions() const { return admissions_; }
            """,
            """
            void SeasonPass::issue(std::int32_t seat_budget) {
                if (seat_budget <= 0) throw PartyError("seat budget must be positive");
                issued_ = true;
                voided_ = false;
                budget_ = seat_budget;
            }
            void SeasonPass::void_pass() {
                voided_ = true;
                issued_ = false;
            }
            void SeasonPass::admit(std::int32_t seats) {
                if (seats < 1 || seats > 6) throw PartyError("party size out of range");
                if (seats > budget_) throw BudgetError("seat budget exceeded");
                budget_ -= seats;
                ++admissions_;
            }
            std::int32_t SeasonPass::seats_left() const { return issued_ ? budget_ : 0; }
            std::int32_t SeasonPass::admissions() const { return admissions_; }
            """,
            """
            SeasonPass pass;
            pass.issue(12);
            pass.admit(4);
            if (pass.seats_left() != 8) return 1;
            if (pass.admissions() != 1) return 2;
            return 0;
            """,
            """
            SeasonPass pass;
            bool threw = false;
            try { pass.admit(2); } catch (const PartyError&) { threw = true; }
            if (!threw) return 1;
            pass.issue(10);
            threw = false;
            try { pass.admit(7); } catch (const PartyError&) { threw = true; }
            if (!threw) return 2;
            pass.admit(6);
            threw = false;
            try { pass.admit(6); } catch (const BudgetError&) { threw = true; }
            if (!threw) return 3;
            if (pass.seats_left() != 4) return 4;
            threw = false;
            try { pass.admit(0); } catch (const PartyError&) { threw = true; }
            if (!threw) return 5;
            pass.void_pass();
            threw = false;
            try { pass.admit(1); } catch (const PassVoidError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { pass.issue(20); } catch (const PassVoidError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            "a permanent void terminal state with no re-open path beside budget arithmetic",
            "voided passes that still admit guests or reissue cleanly",
            "admission before issue, party bounds, exact budget exhaustion with unchanged state, voided admission, and voided reissue",
            "terminal-state rejection, a distinct lifecycle shape",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-parking-garage-permit",
            "Parking garage permit",
            "garage_permit",
            """
            class PermitError : public std::runtime_error {
            public:
                explicit PermitError(const std::string& message) : std::runtime_error(message) {}
            };
            class PermitGate {
            public:
                void issue();
                void revoke();
                void enter();
                void exit();
                bool parked() const;
                std::int32_t entries() const;
            };
            """,
            """
            class PermitError : public std::runtime_error {
            public:
                explicit PermitError(const std::string& message) : std::runtime_error(message) {}
            };
            class PermitGate {
            public:
                void issue();
                void revoke();
                void enter();
                void exit();
                bool parked() const;
                std::int32_t entries() const;
            private:
                bool issued_ = false;
                bool parked_ = false;
                std::int32_t entries_ = 0;
            };
            """,
            """
            void PermitGate::issue() {
                if (issued_) throw PermitError("permit already issued");
                issued_ = true;
                parked_ = false;
                entries_ = 0;
            }
            void PermitGate::revoke() {
                if (!issued_) throw PermitError("no permit issued");
                if (parked_) throw PermitError("vehicle still parked");
                issued_ = false;
            }
            void PermitGate::enter() {
                if (!issued_) throw PermitError("no permit issued");
                if (parked_) throw PermitError("vehicle already parked");
                parked_ = true;
                ++entries_;
            }
            void PermitGate::exit() {
                if (!issued_) throw PermitError("no permit issued");
                if (!parked_) throw PermitError("vehicle is not parked");
                parked_ = false;
            }
            bool PermitGate::parked() const { return parked_; }
            std::int32_t PermitGate::entries() const { return entries_; }
            """,
            """
            void PermitGate::issue() {
                issued_ = true;
                parked_ = false;
                entries_ = 0;
            }
            void PermitGate::revoke() {
                issued_ = false;
                parked_ = false;
            }
            void PermitGate::enter() {
                parked_ = true;
                ++entries_;
            }
            void PermitGate::exit() { parked_ = false; }
            bool PermitGate::parked() const { return parked_; }
            std::int32_t PermitGate::entries() const { return entries_; }
            """,
            """
            PermitGate gate;
            gate.issue();
            gate.enter();
            if (!gate.parked()) return 1;
            gate.exit();
            if (gate.entries() != 1) return 2;
            gate.revoke();
            if (gate.parked()) return 3;
            return 0;
            """,
            """
            PermitGate gate;
            bool threw = false;
            try { gate.enter(); } catch (const PermitError&) { threw = true; }
            if (!threw) return 1;
            gate.issue();
            gate.enter();
            threw = false;
            try { gate.enter(); } catch (const PermitError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { gate.revoke(); } catch (const PermitError&) { threw = true; }
            if (!threw) return 3;
            gate.exit();
            threw = false;
            try { gate.exit(); } catch (const PermitError&) { threw = true; }
            if (!threw) return 4;
            gate.revoke();
            gate.issue();
            if (gate.entries() != 0) return 5;
            return 0;
            """,
            "one-car occupancy pairing where entries count only accepted transitions",
            "entry counting that ignores occupancy state or revocation while parked",
            "entries before issue, double entries, revocation while parked, unmatched exits, and reissue reset",
            "occupancy-state pairing with attempt accounting",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-ski-lift-pass",
            "Ski lift pass",
            "ski_lift",
            """
            class LiftError : public std::domain_error {
            public:
                explicit LiftError(const std::string& message) : std::domain_error(message) {}
            };
            class RetiredError : public std::logic_error {
            public:
                explicit RetiredError(const std::string& message) : std::logic_error(message) {}
            };
            class LiftPass {
            public:
                void validate(std::int32_t scans);
                void retire();
                void scan();
                std::int32_t scans_left() const;
                std::int32_t total_scans() const;
            };
            """,
            """
            class LiftError : public std::domain_error {
            public:
                explicit LiftError(const std::string& message) : std::domain_error(message) {}
            };
            class RetiredError : public std::logic_error {
            public:
                explicit RetiredError(const std::string& message) : std::logic_error(message) {}
            };
            class LiftPass {
            public:
                void validate(std::int32_t scans);
                void retire();
                void scan();
                std::int32_t scans_left() const;
                std::int32_t total_scans() const;
            private:
                bool validated_ = false;
                bool retired_ = false;
                std::int32_t scans_left_ = 0;
                std::int32_t total_scans_ = 0;
            };
            """,
            """
            void LiftPass::validate(std::int32_t scans) {
                if (retired_) throw RetiredError("pass is retired");
                if (validated_) throw LiftError("pass already validated");
                if (scans < 1 || scans > 100) throw LiftError("scan count out of range");
                validated_ = true;
                scans_left_ = scans;
            }
            void LiftPass::retire() {
                if (retired_) throw RetiredError("pass is retired");
                if (!validated_) throw LiftError("pass is not validated");
                retired_ = true;
                validated_ = false;
            }
            void LiftPass::scan() {
                if (retired_) throw RetiredError("pass is retired");
                if (!validated_) throw LiftError("pass is not validated");
                if (scans_left_ == 0) throw LiftError("no scans left");
                --scans_left_;
                ++total_scans_;
            }
            std::int32_t LiftPass::scans_left() const { return retired_ ? 0 : scans_left_; }
            std::int32_t LiftPass::total_scans() const { return total_scans_; }
            """,
            """
            void LiftPass::validate(std::int32_t scans) {
                if (scans < 1 || scans > 100) throw LiftError("scan count out of range");
                retired_ = false;
                validated_ = true;
                scans_left_ = scans;
            }
            void LiftPass::retire() {
                retired_ = true;
                validated_ = false;
            }
            void LiftPass::scan() {
                if (!validated_) throw LiftError("pass is not validated");
                if (scans_left_ == 0) throw LiftError("no scans left");
                --scans_left_;
                ++total_scans_;
            }
            std::int32_t LiftPass::scans_left() const { return retired_ ? 0 : scans_left_; }
            std::int32_t LiftPass::total_scans() const { return total_scans_; }
            """,
            """
            LiftPass pass;
            pass.validate(3);
            pass.scan();
            if (pass.scans_left() != 2) return 1;
            if (pass.total_scans() != 1) return 2;
            return 0;
            """,
            """
            LiftPass pass;
            bool threw = false;
            try { pass.scan(); } catch (const LiftError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { pass.validate(0); } catch (const LiftError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { pass.validate(101); } catch (const LiftError&) { threw = true; }
            if (!threw) return 3;
            pass.validate(1);
            pass.scan();
            threw = false;
            try { pass.scan(); } catch (const LiftError&) { threw = true; }
            if (!threw) return 4;
            pass.retire();
            threw = false;
            try { pass.validate(10); } catch (const RetiredError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { pass.scan(); } catch (const RetiredError&) { threw = true; }
            if (!threw) return 6;
            if (pass.total_scans() != 1) return 7;
            return 0;
            """,
            "consumable scans beside a permanent retired terminal state that forbids revalidation",
            "revalidation of retired passes or scan counting that ignores exhaustion",
            "scans before validation, invalid scan counts, exact exhaustion, retirement, and blocked revalidation",
            "permanent terminal states contrasting with re-openable lifecycles",
            "exception-throwing lifecycle class with open/close guards",
        ),
        c(
            "f26acc-arcade-token-card",
            "Arcade token card",
            "arcade_card",
            """
            class CardStateError : public std::logic_error {
            public:
                explicit CardStateError(const std::string& message) : std::logic_error(message) {}
            };
            class TokenError : public std::out_of_range {
            public:
                explicit TokenError(const std::string& message) : std::out_of_range(message) {}
            };
            class TokenCard {
            public:
                void load_card();
                void eject();
                void add_tokens(std::int32_t n);
                void play(std::int32_t cost);
                std::int32_t tokens() const;
                std::int32_t games() const;
            };
            """,
            """
            class CardStateError : public std::logic_error {
            public:
                explicit CardStateError(const std::string& message) : std::logic_error(message) {}
            };
            class TokenError : public std::out_of_range {
            public:
                explicit TokenError(const std::string& message) : std::out_of_range(message) {}
            };
            class TokenCard {
            public:
                void load_card();
                void eject();
                void add_tokens(std::int32_t n);
                void play(std::int32_t cost);
                std::int32_t tokens() const;
                std::int32_t games() const;
            private:
                bool loaded_ = false;
                std::int32_t tokens_ = 0;
                std::int32_t games_ = 0;
            };
            """,
            """
            namespace {
            constexpr std::int32_t kTokenCap = 500;
            }  // namespace
            void TokenCard::load_card() {
                if (loaded_) throw CardStateError("card already loaded");
                loaded_ = true;
                games_ = 0;
            }
            void TokenCard::eject() {
                if (!loaded_) throw CardStateError("card is ejected");
                loaded_ = false;
            }
            void TokenCard::add_tokens(std::int32_t n) {
                if (!loaded_) throw CardStateError("card is ejected");
                if (n <= 0) throw TokenError("token count must be positive");
                if (tokens_ + n > kTokenCap) throw TokenError("token cap exceeded");
                tokens_ += n;
            }
            void TokenCard::play(std::int32_t cost) {
                if (!loaded_) throw CardStateError("card is ejected");
                if (cost <= 0) throw TokenError("cost must be positive");
                if (cost > tokens_) throw TokenError("not enough tokens");
                tokens_ -= cost;
                ++games_;
            }
            std::int32_t TokenCard::tokens() const { return tokens_; }
            std::int32_t TokenCard::games() const { return games_; }
            """,
            """
            void TokenCard::load_card() { loaded_ = true; }
            void TokenCard::eject() { loaded_ = false; }
            void TokenCard::add_tokens(std::int32_t n) {
                if (n <= 0) throw TokenError("token count must be positive");
                tokens_ += n;
            }
            void TokenCard::play(std::int32_t cost) {
                if (cost <= 0) throw TokenError("cost must be positive");
                tokens_ = cost > tokens_ ? 0 : tokens_ - cost;
                ++games_;
            }
            std::int32_t TokenCard::tokens() const { return tokens_; }
            std::int32_t TokenCard::games() const { return games_; }
            """,
            """
            TokenCard card;
            card.load_card();
            card.add_tokens(100);
            card.play(30);
            if (card.tokens() != 70) return 1;
            if (card.games() != 1) return 2;
            card.eject();
            card.load_card();
            if (card.tokens() != 70) return 3;
            return 0;
            """,
            """
            TokenCard card;
            bool threw = false;
            try { card.play(10); } catch (const CardStateError&) { threw = true; }
            if (!threw) return 1;
            card.load_card();
            card.add_tokens(50);
            threw = false;
            try { card.play(60); } catch (const TokenError&) { threw = true; }
            if (!threw) return 2;
            if (card.tokens() != 50) return 3;
            threw = false;
            try { card.add_tokens(600); } catch (const TokenError&) { threw = true; }
            if (!threw) return 4;
            if (card.tokens() != 50) return 5;
            card.eject();
            threw = false;
            try { card.add_tokens(10); } catch (const CardStateError&) { threw = true; }
            if (!threw) return 6;
            return 0;
            """,
            "reloadable card with atomic spend checks and a hard token cap",
            "balance flooring at zero or plays accepted while the card is ejected",
            "plays while ejected, cap overflow with unchanged balance, overspend atomicity, and reload behavior",
            "spend-atomicity discipline on a reloadable lifecycle",
            "exception-throwing lifecycle class with open/close guards",
            project_support=True,
        ),
        c(
            "f26acc-bike-share-dock",
            "Bike share dock",
            "bike_dock",
            """
            class DockSession {
            public:
                bool unlock();
                bool lock();
                bool ride(std::int32_t minutes);
                std::optional<std::int32_t> trip_minutes() const;
                bool docked() const;
            };
            """,
            """
            class DockSession {
            public:
                bool unlock();
                bool lock();
                bool ride(std::int32_t minutes);
                std::optional<std::int32_t> trip_minutes() const;
                bool docked() const;
            private:
                bool docked_ = true;
                std::int32_t trip_ = 0;
            };
            """,
            """
            bool DockSession::unlock() {
                if (!docked_) return false;
                docked_ = false;
                trip_ = 0;
                return true;
            }
            bool DockSession::lock() {
                if (docked_) return false;
                docked_ = true;
                return true;
            }
            bool DockSession::ride(std::int32_t minutes) {
                if (docked_) return false;
                if (minutes < 1 || minutes > 240) return false;
                trip_ += minutes;
                return true;
            }
            std::optional<std::int32_t> DockSession::trip_minutes() const {
                if (!docked_) return std::nullopt;
                return trip_;
            }
            bool DockSession::docked() const { return docked_; }
            """,
            """
            bool DockSession::unlock() {
                docked_ = false;
                trip_ = 0;
                return true;
            }
            bool DockSession::lock() {
                docked_ = true;
                return true;
            }
            bool DockSession::ride(std::int32_t minutes) {
                if (minutes < 1 || minutes > 240) return false;
                trip_ += minutes;
                return true;
            }
            std::optional<std::int32_t> DockSession::trip_minutes() const {
                if (!docked_) return std::nullopt;
                return trip_;
            }
            bool DockSession::docked() const { return docked_; }
            """,
            """
            DockSession session;
            if (!session.docked()) return 1;
            if (session.trip_minutes() != std::optional<std::int32_t>(0)) return 2;
            if (!session.unlock()) return 3;
            if (!session.ride(45)) return 4;
            if (session.trip_minutes().has_value()) return 5;
            if (!session.lock()) return 6;
            if (session.trip_minutes() != std::optional<std::int32_t>(45)) return 7;
            return 0;
            """,
            """
            DockSession session;
            if (session.ride(10)) return 1;
            if (session.trip_minutes() != std::optional<std::int32_t>(0)) return 2;
            if (!session.unlock()) return 3;
            if (session.unlock()) return 4;
            if (session.ride(0)) return 5;
            if (session.ride(241)) return 6;
            if (!session.ride(120)) return 7;
            if (!session.lock()) return 8;
            if (session.lock()) return 9;
            if (session.trip_minutes() != std::optional<std::int32_t>(120)) return 10;
            return 0;
            """,
            "boolean-channel dock/out lifecycle with optional trip reporting",
            "rides that accrue while docked or status channels that throw instead of returning false",
            "rides while docked, double unlocks, lock while docked, minute bounds, and trip reads in both states",
            "the bool/optional error channel as an alternative to exceptions",
            "status-returning lifecycle class (bool/std::optional channels)",
        ),
        c(
            "f26acc-tool-lending-register",
            "Tool lending register",
            "tool_register",
            """
            class ToolRegister {
            public:
                bool enroll(std::string_view member);
                bool suspend();
                bool reinstate();
                std::optional<std::int32_t> borrow(std::string_view tool);
                bool give_back(std::string_view tool);
                std::size_t borrowed_count() const;
            };
            """,
            """
            class ToolRegister {
            public:
                bool enroll(std::string_view member);
                bool suspend();
                bool reinstate();
                std::optional<std::int32_t> borrow(std::string_view tool);
                bool give_back(std::string_view tool);
                std::size_t borrowed_count() const;
            private:
                enum class Standing { none, active, suspended };
                Standing standing_ = Standing::none;
                std::string member_;
                std::map<std::string, std::int32_t> loans_;
            };
            """,
            """
            namespace {
            constexpr std::pair<const char*, std::int32_t> kTools[] = {
                {"hammer", 1}, {"drill", 2}, {"saw", 3}, {"wrench", 4}, {"ladder", 5},
            };
            constexpr std::size_t kBorrowLimit = 3;
            std::int32_t tool_slot(std::string_view tool) {
                for (const auto& entry : kTools) {
                    if (tool == entry.first) return entry.second;
                }
                return -1;
            }
            }  // namespace
            bool ToolRegister::enroll(std::string_view member) {
                if (standing_ != Standing::none) return false;
                if (member.empty()) return false;
                standing_ = Standing::active;
                member_ = std::string(member);
                return true;
            }
            bool ToolRegister::suspend() {
                if (standing_ != Standing::active) return false;
                if (!loans_.empty()) return false;
                standing_ = Standing::suspended;
                return true;
            }
            bool ToolRegister::reinstate() {
                if (standing_ != Standing::suspended) return false;
                standing_ = Standing::active;
                return true;
            }
            std::optional<std::int32_t> ToolRegister::borrow(std::string_view tool) {
                if (standing_ != Standing::active) return std::nullopt;
                const std::int32_t slot = tool_slot(tool);
                if (slot < 0) return std::nullopt;
                if (loans_.size() >= kBorrowLimit) return std::nullopt;
                const std::string name(tool);
                if (loans_.count(name) != 0) return std::nullopt;
                loans_[name] = slot;
                return slot;
            }
            bool ToolRegister::give_back(std::string_view tool) {
                if (standing_ != Standing::active) return false;
                const std::string name(tool);
                if (loans_.count(name) == 0) return false;
                loans_.erase(name);
                return true;
            }
            std::size_t ToolRegister::borrowed_count() const { return loans_.size(); }
            """,
            """
            namespace {
            constexpr std::pair<const char*, std::int32_t> kTools[] = {
                {"hammer", 1}, {"drill", 2}, {"saw", 3}, {"wrench", 4}, {"ladder", 5},
            };
            constexpr std::size_t kBorrowLimit = 3;
            std::int32_t tool_slot(std::string_view tool) {
                for (const auto& entry : kTools) {
                    if (tool == entry.first) return entry.second;
                }
                return -1;
            }
            }  // namespace
            bool ToolRegister::enroll(std::string_view member) {
                if (standing_ != Standing::none) return false;
                if (member.empty()) return false;
                standing_ = Standing::active;
                member_ = std::string(member);
                return true;
            }
            bool ToolRegister::suspend() {
                if (standing_ != Standing::active) return false;
                if (!loans_.empty()) return false;
                standing_ = Standing::suspended;
                return true;
            }
            bool ToolRegister::reinstate() {
                if (standing_ != Standing::suspended) return false;
                standing_ = Standing::active;
                return true;
            }
            std::optional<std::int32_t> ToolRegister::borrow(std::string_view tool) {
                if (standing_ == Standing::none) return std::nullopt;
                const std::int32_t slot = tool_slot(tool);
                if (slot < 0) return std::nullopt;
                if (loans_.size() >= kBorrowLimit) return std::nullopt;
                const std::string name(tool);
                if (loans_.count(name) != 0) return std::nullopt;
                loans_[name] = slot;
                return slot;
            }
            bool ToolRegister::give_back(std::string_view tool) {
                if (standing_ != Standing::active) return false;
                const std::string name(tool);
                if (loans_.count(name) == 0) return false;
                loans_.erase(name);
                return true;
            }
            std::size_t ToolRegister::borrowed_count() const { return loans_.size(); }
            """,
            """
            ToolRegister reg;
            if (!reg.enroll("pat")) return 1;
            auto slot = reg.borrow("drill");
            if (!slot.has_value()) return 2;
            if (reg.borrowed_count() != 1) return 3;
            if (!reg.give_back("drill")) return 4;
            if (reg.borrowed_count() != 0) return 5;
            return 0;
            """,
            """
            ToolRegister reg;
            if (reg.borrow("saw").has_value()) return 1;
            if (!reg.enroll("ron")) return 2;
            if (reg.enroll("dup")) return 3;
            if (reg.borrow("nail").has_value()) return 4;
            if (!reg.borrow("hammer").has_value()) return 5;
            if (!reg.borrow("saw").has_value()) return 6;
            if (!reg.borrow("drill").has_value()) return 7;
            if (reg.borrow("wrench").has_value()) return 8;
            if (reg.suspend()) return 9;
            if (!reg.give_back("saw")) return 10;
            if (!reg.give_back("hammer")) return 11;
            if (!reg.give_back("drill")) return 12;
            if (!reg.suspend()) return 13;
            if (reg.borrow("saw").has_value()) return 14;
            if (!reg.reinstate()) return 15;
            if (!reg.borrow("saw").has_value()) return 16;
            return 0;
            """,
            "membership standing lifecycle with a fixed tool table and a three-item borrow limit",
            "borrows that ignore suspension or invent slots for unknown tools",
            "borrows before enrollment, suspended borrows, unknown tools, the borrow limit, suspension with loans, and reinstatement",
            "optional-valued guarded operations over a named table",
            "status-returning lifecycle class (bool/std::optional channels)",
            project_support=True,
        ),
        c(
            "f26acc-laundromat-machine",
            "Laundromat machine",
            "laundromat",
            """
            class WasherUnit {
            public:
                bool load(std::int32_t kg);
                bool start();
                bool stop_early();
                bool unload();
                std::optional<std::int32_t> cycle_minutes() const;
                std::string_view stage() const;
            };
            """,
            """
            class WasherUnit {
            public:
                bool load(std::int32_t kg);
                bool start();
                bool stop_early();
                bool unload();
                std::optional<std::int32_t> cycle_minutes() const;
                std::string_view stage() const;
            private:
                enum class Stage { empty, loaded, running, done };
                Stage stage_ = Stage::empty;
                std::int32_t kg_ = 0;
            };
            """,
            """
            bool WasherUnit::load(std::int32_t kg) {
                if (stage_ != Stage::empty) return false;
                if (kg < 1 || kg > 9) return false;
                kg_ = kg;
                stage_ = Stage::loaded;
                return true;
            }
            bool WasherUnit::start() {
                if (stage_ != Stage::loaded) return false;
                stage_ = Stage::running;
                return true;
            }
            bool WasherUnit::stop_early() {
                if (stage_ != Stage::running) return false;
                stage_ = Stage::done;
                return true;
            }
            bool WasherUnit::unload() {
                if (stage_ != Stage::done) return false;
                kg_ = 0;
                stage_ = Stage::empty;
                return true;
            }
            std::optional<std::int32_t> WasherUnit::cycle_minutes() const {
                if (stage_ != Stage::running) return std::nullopt;
                return 45;
            }
            std::string_view WasherUnit::stage() const {
                switch (stage_) {
                    case Stage::empty: return "empty";
                    case Stage::loaded: return "loaded";
                    case Stage::running: return "running";
                    case Stage::done: return "done";
                }
                return "empty";
            }
            """,
            """
            bool WasherUnit::load(std::int32_t kg) {
                if (stage_ != Stage::empty) return false;
                if (kg < 1 || kg > 9) return false;
                kg_ = kg;
                stage_ = Stage::loaded;
                return true;
            }
            bool WasherUnit::start() {
                if (stage_ == Stage::running) return false;
                stage_ = Stage::running;
                return true;
            }
            bool WasherUnit::stop_early() {
                if (stage_ != Stage::running) return false;
                stage_ = Stage::done;
                return true;
            }
            bool WasherUnit::unload() {
                if (stage_ != Stage::done) return false;
                kg_ = 0;
                stage_ = Stage::empty;
                return true;
            }
            std::optional<std::int32_t> WasherUnit::cycle_minutes() const {
                if (stage_ != Stage::running) return std::nullopt;
                return 45;
            }
            std::string_view WasherUnit::stage() const {
                switch (stage_) {
                    case Stage::empty: return "empty";
                    case Stage::loaded: return "loaded";
                    case Stage::running: return "running";
                    case Stage::done: return "done";
                }
                return "empty";
            }
            """,
            """
            WasherUnit unit;
            if (unit.stage() != "empty") return 1;
            if (!unit.load(4)) return 2;
            if (unit.stage() != "loaded") return 3;
            if (!unit.start()) return 4;
            if (unit.cycle_minutes() != std::optional<std::int32_t>(45)) return 5;
            if (!unit.stop_early()) return 6;
            if (unit.stage() != "done") return 7;
            if (!unit.unload()) return 8;
            return 0;
            """,
            """
            WasherUnit unit;
            if (unit.start()) return 1;
            if (unit.unload()) return 2;
            if (unit.load(0)) return 3;
            if (unit.load(10)) return 4;
            if (!unit.load(9)) return 5;
            if (unit.load(1)) return 6;
            if (unit.stop_early()) return 7;
            if (unit.unload()) return 8;
            if (!unit.start()) return 9;
            if (unit.start()) return 10;
            if (!unit.stop_early()) return 11;
            if (unit.cycle_minutes().has_value()) return 12;
            if (!unit.unload()) return 13;
            if (unit.stage() != "empty") return 14;
            return 0;
            """,
            "four-stage washer lifecycle where transitions only fire from their documented stage",
            "starting a cycle from empty or skipping stages without state checks",
            "start from empty, double loads, kilogram bounds, unload ordering, and per-stage cycle minutes",
            "explicit multi-stage state machines in status style",
            "status-returning lifecycle class (bool/std::optional channels)",
        ),
        c(
            "f26acc-photo-studio-booking",
            "Photo studio booking",
            "photo_studio",
            """
            class StudioBook {
            public:
                bool open_day(std::int32_t slots);
                bool close_day();
                std::optional<std::int32_t> reserve(std::int32_t slot);
                bool release(std::int32_t slot);
                std::int32_t taken() const;
            };
            """,
            """
            class StudioBook {
            public:
                bool open_day(std::int32_t slots);
                bool close_day();
                std::optional<std::int32_t> reserve(std::int32_t slot);
                bool release(std::int32_t slot);
                std::int32_t taken() const;
            private:
                bool open_ = false;
                std::int32_t slots_ = 0;
                std::map<std::int32_t, bool> reserved_;
            };
            """,
            """
            bool StudioBook::open_day(std::int32_t slots) {
                if (open_) return false;
                if (slots < 1 || slots > 12) return false;
                open_ = true;
                slots_ = slots;
                reserved_.clear();
                return true;
            }
            bool StudioBook::close_day() {
                if (!open_) return false;
                if (!reserved_.empty()) return false;
                open_ = false;
                return true;
            }
            std::optional<std::int32_t> StudioBook::reserve(std::int32_t slot) {
                if (!open_) return std::nullopt;
                if (slot < 1 || slot > slots_) return std::nullopt;
                if (reserved_.count(slot) != 0) return std::nullopt;
                reserved_[slot] = true;
                return slot;
            }
            bool StudioBook::release(std::int32_t slot) {
                if (!open_) return false;
                if (reserved_.count(slot) == 0) return false;
                reserved_.erase(slot);
                return true;
            }
            std::int32_t StudioBook::taken() const { return static_cast<std::int32_t>(reserved_.size()); }
            """,
            """
            bool StudioBook::open_day(std::int32_t slots) {
                if (open_) return false;
                if (slots < 1 || slots > 12) return false;
                open_ = true;
                slots_ = slots;
                reserved_.clear();
                return true;
            }
            bool StudioBook::close_day() {
                if (!open_) return false;
                if (!reserved_.empty()) return false;
                open_ = false;
                return true;
            }
            std::optional<std::int32_t> StudioBook::reserve(std::int32_t slot) {
                if (!open_) return std::nullopt;
                if (slot < 1 || slot > slots_) return std::nullopt;
                reserved_[slot] = true;
                return slot;
            }
            bool StudioBook::release(std::int32_t slot) {
                if (!open_) return false;
                if (reserved_.count(slot) == 0) return false;
                reserved_.erase(slot);
                return true;
            }
            std::int32_t StudioBook::taken() const { return static_cast<std::int32_t>(reserved_.size()); }
            """,
            """
            StudioBook book;
            if (!book.open_day(6)) return 1;
            auto slot = book.reserve(3);
            if (slot != std::optional<std::int32_t>(3)) return 2;
            if (book.taken() != 1) return 3;
            if (!book.release(3)) return 4;
            if (!book.close_day()) return 5;
            return 0;
            """,
            """
            StudioBook book;
            if (book.reserve(1).has_value()) return 1;
            if (!book.open_day(4)) return 2;
            if (book.open_day(4)) return 3;
            if (book.reserve(0).has_value()) return 4;
            if (book.reserve(5).has_value()) return 5;
            if (!book.reserve(2).has_value()) return 6;
            if (book.reserve(2).has_value()) return 7;
            if (book.close_day()) return 8;
            if (!book.release(2)) return 9;
            if (book.release(2)) return 10;
            if (!book.close_day()) return 11;
            return 0;
            """,
            "per-slot reservation lifecycle with optional allocation and a drain-before-close rule",
            "double booking a slot or forcing a close over live reservations",
            "closed-day reserves, out-of-range slots, double booking, free-slot releases, and closes with reservations",
            "slot-allocation lifecycle with exact optional semantics",
            "status-returning lifecycle class (bool/std::optional channels)",
            project_support=True,
        ),
        c(
            "f26acc-community-garden-plot",
            "Community garden plot",
            "garden_plot",
            """
            class GardenPlot {
            public:
                bool claim(std::string_view gardener);
                bool release();
                bool plant(std::string_view crop);
                std::optional<std::string> harvest();
                std::int32_t standing() const;
            };
            """,
            """
            class GardenPlot {
            public:
                bool claim(std::string_view gardener);
                bool release();
                bool plant(std::string_view crop);
                std::optional<std::string> harvest();
                std::int32_t standing() const;
            private:
                bool claimed_ = false;
                std::string gardener_;
                std::deque<std::string> crops_;
            };
            """,
            """
            bool GardenPlot::claim(std::string_view gardener) {
                if (claimed_) return false;
                if (gardener.empty()) return false;
                claimed_ = true;
                gardener_ = std::string(gardener);
                crops_.clear();
                return true;
            }
            bool GardenPlot::release() {
                if (!claimed_) return false;
                if (!crops_.empty()) return false;
                claimed_ = false;
                gardener_.clear();
                return true;
            }
            bool GardenPlot::plant(std::string_view crop) {
                if (!claimed_) return false;
                if (crop.empty()) return false;
                if (crops_.size() >= 5) return false;
                crops_.push_back(std::string(crop));
                return true;
            }
            std::optional<std::string> GardenPlot::harvest() {
                if (!claimed_ || crops_.empty()) return std::nullopt;
                std::string crop = crops_.front();
                crops_.pop_front();
                return crop;
            }
            std::int32_t GardenPlot::standing() const { return static_cast<std::int32_t>(crops_.size()); }
            """,
            """
            bool GardenPlot::claim(std::string_view gardener) {
                if (claimed_) return false;
                if (gardener.empty()) return false;
                claimed_ = true;
                gardener_ = std::string(gardener);
                crops_.clear();
                return true;
            }
            bool GardenPlot::release() {
                claimed_ = false;
                gardener_.clear();
                crops_.clear();
                return true;
            }
            bool GardenPlot::plant(std::string_view crop) {
                if (!claimed_) return false;
                if (crop.empty()) return false;
                if (crops_.size() >= 5) return false;
                crops_.push_back(std::string(crop));
                return true;
            }
            std::optional<std::string> GardenPlot::harvest() {
                if (!claimed_ || crops_.empty()) return std::nullopt;
                std::string crop = crops_.front();
                crops_.pop_front();
                return crop;
            }
            std::int32_t GardenPlot::standing() const { return static_cast<std::int32_t>(crops_.size()); }
            """,
            """
            GardenPlot plot;
            if (!plot.claim("ivy")) return 1;
            if (!plot.plant("kale")) return 2;
            if (!plot.plant("sage")) return 3;
            if (plot.standing() != 2) return 4;
            auto crop = plot.harvest();
            if (crop != std::optional<std::string>("kale")) return 5;
            return 0;
            """,
            """
            GardenPlot plot;
            if (plot.plant("dill")) return 1;
            if (plot.harvest().has_value()) return 2;
            if (!plot.claim("fern")) return 3;
            if (plot.claim("reed")) return 4;
            if (!plot.plant("a")) return 5;
            if (!plot.plant("b")) return 6;
            if (!plot.plant("c")) return 7;
            if (!plot.plant("d")) return 8;
            if (!plot.plant("e")) return 9;
            if (plot.plant("f")) return 10;
            if (plot.release()) return 11;
            if (plot.harvest() != std::optional<std::string>("a")) return 12;
            if (plot.harvest() != std::optional<std::string>("b")) return 13;
            if (plot.harvest() != std::optional<std::string>("c")) return 14;
            if (plot.harvest() != std::optional<std::string>("d")) return 15;
            if (plot.harvest() != std::optional<std::string>("e")) return 16;
            if (plot.harvest().has_value()) return 17;
            if (!plot.release()) return 18;
            return 0;
            """,
            "FIFO crop queue inside a claim/release plot lifecycle",
            "releases that silently discard standing crops",
            "planting before claiming, the five-crop bound, harvest order, empty harvests, and blocked releases",
            "queue-backed lifecycle state with drain rules",
            "status-returning lifecycle class (bool/std::optional channels)",
        ),
        c(
            "f26acc-karaoke-room-session",
            "Karaoke room session",
            "karaoke_room",
            """
            class KaraokeRoom {
            public:
                bool open_room();
                bool close_room();
                bool queue_song(std::string_view title);
                std::optional<std::string> next_song();
                std::size_t queued() const;
            };
            """,
            """
            class KaraokeRoom {
            public:
                bool open_room();
                bool close_room();
                bool queue_song(std::string_view title);
                std::optional<std::string> next_song();
                std::size_t queued() const;
            private:
                bool open_ = false;
                std::deque<std::string> queue_;
            };
            """,
            """
            bool KaraokeRoom::open_room() {
                if (open_) return false;
                open_ = true;
                queue_.clear();
                return true;
            }
            bool KaraokeRoom::close_room() {
                if (!open_) return false;
                if (!queue_.empty()) return false;
                open_ = false;
                return true;
            }
            bool KaraokeRoom::queue_song(std::string_view title) {
                if (!open_) return false;
                if (title.empty()) return false;
                if (queue_.size() >= 20) return false;
                queue_.push_back(std::string(title));
                return true;
            }
            std::optional<std::string> KaraokeRoom::next_song() {
                if (!open_ || queue_.empty()) return std::nullopt;
                std::string song = queue_.front();
                queue_.pop_front();
                return song;
            }
            std::size_t KaraokeRoom::queued() const { return queue_.size(); }
            """,
            """
            bool KaraokeRoom::open_room() {
                if (open_) return false;
                open_ = true;
                queue_.clear();
                return true;
            }
            bool KaraokeRoom::close_room() {
                open_ = false;
                queue_.clear();
                return true;
            }
            bool KaraokeRoom::queue_song(std::string_view title) {
                if (!open_) return false;
                if (title.empty()) return false;
                if (queue_.size() >= 20) return false;
                queue_.push_back(std::string(title));
                return true;
            }
            std::optional<std::string> KaraokeRoom::next_song() {
                if (!open_ || queue_.empty()) return std::nullopt;
                std::string song = queue_.front();
                queue_.pop_front();
                return song;
            }
            std::size_t KaraokeRoom::queued() const { return queue_.size(); }
            """,
            """
            KaraokeRoom room;
            if (!room.open_room()) return 1;
            if (!room.queue_song("aurora")) return 2;
            if (!room.queue_song("ballad")) return 3;
            auto song = room.next_song();
            if (song != std::optional<std::string>("aurora")) return 4;
            if (room.queued() != 1) return 5;
            return 0;
            """,
            """
            KaraokeRoom room;
            if (room.queue_song("x")) return 1;
            if (room.next_song().has_value()) return 2;
            if (room.close_room()) return 3;
            if (!room.open_room()) return 4;
            if (room.open_room()) return 5;
            if (room.queue_song("")) return 6;
            if (!room.queue_song("cedar")) return 7;
            if (room.close_room()) return 8;
            if (room.next_song() != std::optional<std::string>("cedar")) return 9;
            if (room.next_song().has_value()) return 10;
            if (!room.close_room()) return 11;
            return 0;
            """,
            "bounded FIFO queue behind an open/close room lifecycle",
            "closes that silently drop the pending queue",
            "queueing while closed, empty titles, queue draining order, closes with pending songs, and reopening",
            "bounded-queue lifecycle discipline",
            "status-returning lifecycle class (bool/std::optional channels)",
            project_support=True,
        ),
        c(
            "f26acc-climbing-gym-belay",
            "Climbing gym belay",
            "belay_desk",
            """
            class BelayDesk {
            public:
                bool certify(std::string_view climber);
                bool expire(std::string_view climber);
                bool clip_in(std::string_view climber);
                bool unclip(std::string_view climber);
                std::size_t on_wall() const;
            };
            """,
            """
            class BelayDesk {
            public:
                bool certify(std::string_view climber);
                bool expire(std::string_view climber);
                bool clip_in(std::string_view climber);
                bool unclip(std::string_view climber);
                std::size_t on_wall() const;
            private:
                std::map<std::string, bool> certified_;
                std::map<std::string, bool> climbing_;
            };
            """,
            """
            bool BelayDesk::certify(std::string_view climber) {
                if (climber.empty()) return false;
                const std::string name(climber);
                if (certified_.count(name) != 0) return false;
                certified_[name] = true;
                return true;
            }
            bool BelayDesk::expire(std::string_view climber) {
                const std::string name(climber);
                if (certified_.count(name) == 0) return false;
                if (climbing_.count(name) != 0) return false;
                certified_.erase(name);
                return true;
            }
            bool BelayDesk::clip_in(std::string_view climber) {
                const std::string name(climber);
                if (certified_.count(name) == 0) return false;
                if (climbing_.count(name) != 0) return false;
                if (climbing_.size() >= 4) return false;
                climbing_[name] = true;
                return true;
            }
            bool BelayDesk::unclip(std::string_view climber) {
                const std::string name(climber);
                if (climbing_.count(name) == 0) return false;
                climbing_.erase(name);
                return true;
            }
            std::size_t BelayDesk::on_wall() const { return climbing_.size(); }
            """,
            """
            bool BelayDesk::certify(std::string_view climber) {
                if (climber.empty()) return false;
                const std::string name(climber);
                if (certified_.count(name) != 0) return false;
                certified_[name] = true;
                return true;
            }
            bool BelayDesk::expire(std::string_view climber) {
                const std::string name(climber);
                if (certified_.count(name) == 0) return false;
                if (climbing_.count(name) != 0) return false;
                certified_.erase(name);
                return true;
            }
            bool BelayDesk::clip_in(std::string_view climber) {
                if (climber.empty()) return false;
                const std::string name(climber);
                if (climbing_.count(name) != 0) return false;
                if (climbing_.size() >= 4) return false;
                climbing_[name] = true;
                return true;
            }
            bool BelayDesk::unclip(std::string_view climber) {
                const std::string name(climber);
                if (climbing_.count(name) == 0) return false;
                climbing_.erase(name);
                return true;
            }
            std::size_t BelayDesk::on_wall() const { return climbing_.size(); }
            """,
            """
            BelayDesk desk;
            if (!desk.certify("mia")) return 1;
            if (!desk.clip_in("mia")) return 2;
            if (desk.on_wall() != 1) return 3;
            if (!desk.unclip("mia")) return 4;
            if (desk.on_wall() != 0) return 5;
            return 0;
            """,
            """
            BelayDesk desk;
            if (desk.clip_in("oak")) return 1;
            if (!desk.certify("oak")) return 2;
            if (desk.certify("oak")) return 3;
            if (!desk.certify("eli")) return 4;
            if (!desk.clip_in("oak")) return 5;
            if (desk.expire("oak")) return 6;
            if (!desk.expire("eli")) return 7;
            if (desk.clip_in("eli")) return 8;
            if (!desk.certify("ana")) return 9;
            if (!desk.certify("max")) return 10;
            if (!desk.certify("rue")) return 11;
            if (!desk.clip_in("ana")) return 12;
            if (!desk.clip_in("max")) return 13;
            if (!desk.clip_in("rue")) return 14;
            if (!desk.certify("ivy")) return 15;
            if (desk.clip_in("ivy")) return 16;
            if (!desk.unclip("oak")) return 17;
            if (!desk.clip_in("ivy")) return 18;
            if (desk.unclip("oak")) return 19;
            return 0;
            """,
            "certification registry with a four-climber wall bound and multi-entity state",
            "uncertified wall access or expirations that strand climbers on the wall",
            "uncertified clip-ins, duplicate certifications, the wall bound, on-wall expirations, and absent unclips",
            "registry-style lifecycle over many named entities",
            "status-returning lifecycle class (bool/std::optional channels)",
        ),
        c(
            "f26acc-farm-csa-share",
            "Farm CSA share",
            "csa_share",
            """
            class CsaShare {
            public:
                bool subscribe(std::string_view name, std::int32_t weeks);
                bool pause();
                bool resume();
                bool pickup(std::int32_t items);
                std::optional<std::int32_t> credit() const;
            };
            """,
            """
            class CsaShare {
            public:
                bool subscribe(std::string_view name, std::int32_t weeks);
                bool pause();
                bool resume();
                bool pickup(std::int32_t items);
                std::optional<std::int32_t> credit() const;
            private:
                enum class Standing { none, active, paused };
                Standing standing_ = Standing::none;
                std::string name_;
                std::int32_t weeks_left_ = 0;
            };
            """,
            """
            bool CsaShare::subscribe(std::string_view name, std::int32_t weeks) {
                if (standing_ != Standing::none) return false;
                if (name.empty()) return false;
                if (weeks < 1 || weeks > 20) return false;
                standing_ = Standing::active;
                name_ = std::string(name);
                weeks_left_ = weeks;
                return true;
            }
            bool CsaShare::pause() {
                if (standing_ != Standing::active) return false;
                standing_ = Standing::paused;
                return true;
            }
            bool CsaShare::resume() {
                if (standing_ != Standing::paused) return false;
                standing_ = Standing::active;
                return true;
            }
            bool CsaShare::pickup(std::int32_t items) {
                if (standing_ != Standing::active) return false;
                if (items < 1 || items > 8) return false;
                if (weeks_left_ <= 0) return false;
                --weeks_left_;
                return true;
            }
            std::optional<std::int32_t> CsaShare::credit() const {
                if (standing_ != Standing::active) return std::nullopt;
                return weeks_left_;
            }
            """,
            """
            bool CsaShare::subscribe(std::string_view name, std::int32_t weeks) {
                if (standing_ != Standing::none) return false;
                if (name.empty()) return false;
                if (weeks < 1 || weeks > 20) return false;
                standing_ = Standing::active;
                name_ = std::string(name);
                weeks_left_ = weeks;
                return true;
            }
            bool CsaShare::pause() {
                if (standing_ != Standing::active) return false;
                standing_ = Standing::paused;
                return true;
            }
            bool CsaShare::resume() {
                if (standing_ != Standing::paused) return false;
                standing_ = Standing::active;
                return true;
            }
            bool CsaShare::pickup(std::int32_t items) {
                if (standing_ == Standing::none) return false;
                if (items < 1 || items > 8) return false;
                if (weeks_left_ <= 0) return false;
                --weeks_left_;
                return true;
            }
            std::optional<std::int32_t> CsaShare::credit() const {
                if (standing_ != Standing::active) return std::nullopt;
                return weeks_left_;
            }
            """,
            """
            CsaShare share;
            if (!share.subscribe("nia", 4)) return 1;
            if (share.credit() != std::optional<std::int32_t>(4)) return 2;
            if (!share.pickup(3)) return 3;
            if (share.credit() != std::optional<std::int32_t>(3)) return 4;
            return 0;
            """,
            """
            CsaShare share;
            if (share.pickup(1)) return 1;
            if (share.credit().has_value()) return 2;
            if (!share.subscribe("eli", 3)) return 3;
            if (share.subscribe("two", 3)) return 4;
            if (!share.pause()) return 5;
            if (share.pause()) return 6;
            if (share.pickup(2)) return 7;
            if (share.credit().has_value()) return 8;
            if (!share.resume()) return 9;
            if (share.pickup(9)) return 10;
            if (!share.pickup(1)) return 11;
            if (!share.pickup(1)) return 12;
            if (!share.pickup(1)) return 13;
            if (share.pickup(1)) return 14;
            if (share.credit() != std::optional<std::int32_t>(0)) return 15;
            return 0;
            """,
            "pauseable subscription with week accounting and an optional credit query",
            "pickups that succeed while the share is paused",
            "pickups before subscribing, double pauses, paused pickups, item bounds, week exhaustion, and credit reads",
            "pause/resume lifecycle in the status channel",
            "status-returning lifecycle class (bool/std::optional channels)",
            project_support=True,
        ),
        c(
            "f26acc-streaming-subscription",
            "Streaming subscription",
            "stream_sub",
            """
            class SubError : public std::logic_error {
            public:
                explicit SubError(const std::string& message) : std::logic_error(message) {}
            };
            class CancelledError : public std::runtime_error {
            public:
                explicit CancelledError(const std::string& message) : std::runtime_error(message) {}
            };
            class CapError : public std::out_of_range {
            public:
                explicit CapError(const std::string& message) : std::out_of_range(message) {}
            };
            class StreamSub {
            public:
                void start();
                void pause();
                void resume();
                void cancel();
                void watch(std::int32_t minutes);
                std::int32_t minutes() const;
                std::string_view status() const;
            };
            """,
            """
            class SubError : public std::logic_error {
            public:
                explicit SubError(const std::string& message) : std::logic_error(message) {}
            };
            class CancelledError : public std::runtime_error {
            public:
                explicit CancelledError(const std::string& message) : std::runtime_error(message) {}
            };
            class CapError : public std::out_of_range {
            public:
                explicit CapError(const std::string& message) : std::out_of_range(message) {}
            };
            class StreamSub {
            public:
                void start();
                void pause();
                void resume();
                void cancel();
                void watch(std::int32_t minutes);
                std::int32_t minutes() const;
                std::string_view status() const;
            private:
                enum class State { inactive, active, paused, cancelled };
                State state_ = State::inactive;
                std::int32_t minutes_ = 0;
            };
            """,
            """
            namespace {
            constexpr std::int32_t kDailyCap = 600;
            }  // namespace
            void StreamSub::start() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::inactive) throw SubError("subscription already started");
                state_ = State::active;
            }
            void StreamSub::pause() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::active) throw SubError("subscription not active");
                state_ = State::paused;
            }
            void StreamSub::resume() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::paused) throw SubError("subscription not paused");
                state_ = State::active;
            }
            void StreamSub::cancel() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                state_ = State::cancelled;
            }
            void StreamSub::watch(std::int32_t minutes) {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::active) throw SubError("subscription not active");
                if (minutes < 1) throw SubError("minutes must be positive");
                if (minutes_ + minutes > kDailyCap) throw CapError("daily watch cap exceeded");
                minutes_ += minutes;
            }
            std::int32_t StreamSub::minutes() const { return minutes_; }
            std::string_view StreamSub::status() const {
                switch (state_) {
                    case State::inactive: return "inactive";
                    case State::active: return "active";
                    case State::paused: return "paused";
                    case State::cancelled: return "cancelled";
                }
                return "inactive";
            }
            """,
            """
            namespace {
            constexpr std::int32_t kDailyCap = 600;
            }  // namespace
            void StreamSub::start() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::inactive) throw SubError("subscription already started");
                state_ = State::active;
            }
            void StreamSub::pause() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::active) throw SubError("subscription not active");
                state_ = State::paused;
            }
            void StreamSub::resume() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (state_ != State::paused) throw SubError("subscription not paused");
                state_ = State::active;
            }
            void StreamSub::cancel() {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                state_ = State::cancelled;
            }
            void StreamSub::watch(std::int32_t minutes) {
                if (state_ == State::cancelled) throw CancelledError("subscription cancelled");
                if (minutes < 1) throw SubError("minutes must be positive");
                if (minutes_ + minutes > kDailyCap) throw CapError("daily watch cap exceeded");
                minutes_ += minutes;
            }
            std::int32_t StreamSub::minutes() const { return minutes_; }
            std::string_view StreamSub::status() const {
                switch (state_) {
                    case State::inactive: return "inactive";
                    case State::active: return "active";
                    case State::paused: return "paused";
                    case State::cancelled: return "cancelled";
                }
                return "inactive";
            }
            """,
            """
            StreamSub sub;
            if (sub.status() != "inactive") return 1;
            sub.start();
            sub.watch(90);
            if (sub.minutes() != 90) return 2;
            sub.pause();
            if (sub.status() != "paused") return 3;
            sub.resume();
            if (sub.status() != "active") return 4;
            return 0;
            """,
            """
            StreamSub sub;
            bool threw = false;
            try { sub.watch(10); } catch (const SubError&) { threw = true; }
            if (!threw) return 1;
            sub.start();
            sub.pause();
            threw = false;
            try { sub.pause(); } catch (const SubError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { sub.watch(10); } catch (const SubError&) { threw = true; }
            if (!threw) return 3;
            sub.resume();
            sub.watch(600);
            threw = false;
            try { sub.watch(1); } catch (const CapError&) { threw = true; }
            if (!threw) return 4;
            if (sub.minutes() != 600) return 5;
            sub.cancel();
            threw = false;
            try { sub.resume(); } catch (const CancelledError&) { threw = true; }
            if (!threw) return 6;
            if (sub.status() != "cancelled") return 7;
            return 0;
            """,
            "four-state subscription machine with a daily watch cap and a terminal cancelled state",
            "watching while paused or resuming a cancelled plan",
            "watching before start, double pauses, paused watches, the daily cap with unchanged minutes, cancel then resume, and status strings",
            "four-state lifecycle machines with exact status reporting",
            "multi-state suspend/resume lifecycle machine",
        ),
        c(
            "f26acc-journal-delivery-plan",
            "Journal delivery plan",
            "journal_plan",
            """
            class DeliveryError : public std::logic_error {
            public:
                explicit DeliveryError(const std::string& message) : std::logic_error(message) {}
            };
            class HoldError : public std::out_of_range {
            public:
                explicit HoldError(const std::string& message) : std::out_of_range(message) {}
            };
            class DeliveryPlan {
            public:
                void begin(std::int32_t issues);
                void hold(std::int32_t days);
                void unhold();
                void deliver();
                std::int32_t issues_left() const;
                bool on_hold() const;
            };
            """,
            """
            class DeliveryError : public std::logic_error {
            public:
                explicit DeliveryError(const std::string& message) : std::logic_error(message) {}
            };
            class HoldError : public std::out_of_range {
            public:
                explicit HoldError(const std::string& message) : std::out_of_range(message) {}
            };
            class DeliveryPlan {
            public:
                void begin(std::int32_t issues);
                void hold(std::int32_t days);
                void unhold();
                void deliver();
                std::int32_t issues_left() const;
                bool on_hold() const;
            private:
                bool begun_ = false;
                std::int32_t issues_left_ = 0;
                bool held_ = false;
                std::int32_t hold_days_used_ = 0;
            };
            """,
            """
            void DeliveryPlan::begin(std::int32_t issues) {
                if (begun_) throw DeliveryError("plan already begun");
                if (issues < 1 || issues > 52) throw DeliveryError("issue count out of range");
                begun_ = true;
                issues_left_ = issues;
            }
            void DeliveryPlan::hold(std::int32_t days) {
                if (!begun_) throw DeliveryError("plan not begun");
                if (held_) throw HoldError("plan already on hold");
                if (days < 1) throw HoldError("hold days must be positive");
                if (hold_days_used_ + days > 30) throw HoldError("hold budget exhausted");
                held_ = true;
                hold_days_used_ += days;
            }
            void DeliveryPlan::unhold() {
                if (!begun_) throw DeliveryError("plan not begun");
                if (!held_) throw HoldError("plan not on hold");
                held_ = false;
            }
            void DeliveryPlan::deliver() {
                if (!begun_) throw DeliveryError("plan not begun");
                if (held_) throw DeliveryError("plan is on hold");
                if (issues_left_ == 0) throw DeliveryError("plan has lapsed");
                --issues_left_;
            }
            std::int32_t DeliveryPlan::issues_left() const { return issues_left_; }
            bool DeliveryPlan::on_hold() const { return held_; }
            """,
            """
            void DeliveryPlan::begin(std::int32_t issues) {
                if (begun_) throw DeliveryError("plan already begun");
                if (issues < 1 || issues > 52) throw DeliveryError("issue count out of range");
                begun_ = true;
                issues_left_ = issues;
            }
            void DeliveryPlan::hold(std::int32_t days) {
                if (!begun_) throw DeliveryError("plan not begun");
                if (held_) throw HoldError("plan already on hold");
                if (days < 1) throw HoldError("hold days must be positive");
                if (hold_days_used_ + days > 30) throw HoldError("hold budget exhausted");
                held_ = true;
                hold_days_used_ += days;
            }
            void DeliveryPlan::unhold() {
                if (!begun_) throw DeliveryError("plan not begun");
                if (!held_) throw HoldError("plan not on hold");
                held_ = false;
            }
            void DeliveryPlan::deliver() {
                if (!begun_) throw DeliveryError("plan not begun");
                if (issues_left_ == 0) throw DeliveryError("plan has lapsed");
                --issues_left_;
            }
            std::int32_t DeliveryPlan::issues_left() const { return issues_left_; }
            bool DeliveryPlan::on_hold() const { return held_; }
            """,
            """
            DeliveryPlan plan;
            plan.begin(3);
            plan.deliver();
            if (plan.issues_left() != 2) return 1;
            plan.hold(5);
            if (!plan.on_hold()) return 2;
            plan.unhold();
            plan.deliver();
            if (plan.issues_left() != 1) return 3;
            return 0;
            """,
            """
            DeliveryPlan plan;
            bool threw = false;
            try { plan.deliver(); } catch (const DeliveryError&) { threw = true; }
            if (!threw) return 1;
            plan.begin(2);
            plan.hold(20);
            threw = false;
            try { plan.deliver(); } catch (const DeliveryError&) { threw = true; }
            if (!threw) return 2;
            plan.unhold();
            threw = false;
            try { plan.hold(11); } catch (const HoldError&) { threw = true; }
            if (!threw) return 3;
            plan.hold(10);
            plan.unhold();
            plan.deliver();
            plan.deliver();
            threw = false;
            try { plan.deliver(); } catch (const DeliveryError&) { threw = true; }
            if (!threw) return 4;
            if (plan.issues_left() != 0) return 5;
            return 0;
            """,
            "issue-count lifecycle with a cumulative thirty-day hold budget and lapse detection",
            "deliveries that continue while the plan is on hold",
            "deliveries before begin, held deliveries, the cumulative hold budget, issue exhaustion, and lapsed deliveries",
            "budgeted holds over a countable lifecycle",
            "multi-state suspend/resume lifecycle machine",
            project_support=True,
        ),
        c(
            "f26acc-gym-membership-freeze",
            "Gym membership freeze",
            "gym_freeze",
            """
            class FreezeError : public std::logic_error {
            public:
                explicit FreezeError(const std::string& message) : std::logic_error(message) {}
            };
            class VisitError : public std::runtime_error {
            public:
                explicit VisitError(const std::string& message) : std::runtime_error(message) {}
            };
            class FreezeMembership {
            public:
                void activate();
                void freeze(std::int32_t days);
                void thaw();
                void attend();
                std::int32_t visits() const;
                std::int32_t freeze_days_used() const;
            };
            """,
            """
            class FreezeError : public std::logic_error {
            public:
                explicit FreezeError(const std::string& message) : std::logic_error(message) {}
            };
            class VisitError : public std::runtime_error {
            public:
                explicit VisitError(const std::string& message) : std::runtime_error(message) {}
            };
            class FreezeMembership {
            public:
                void activate();
                void freeze(std::int32_t days);
                void thaw();
                void attend();
                std::int32_t visits() const;
                std::int32_t freeze_days_used() const;
            private:
                bool active_ = false;
                bool frozen_ = false;
                std::int32_t visits_ = 0;
                std::int32_t freeze_days_used_ = 0;
            };
            """,
            """
            void FreezeMembership::activate() {
                if (active_) throw FreezeError("membership already active");
                active_ = true;
            }
            void FreezeMembership::freeze(std::int32_t days) {
                if (!active_) throw FreezeError("membership inactive");
                if (frozen_) throw FreezeError("membership already frozen");
                if (days < 1 || days > 14) throw FreezeError("freeze length out of range");
                if (freeze_days_used_ + days > 60) throw FreezeError("freeze budget exhausted");
                frozen_ = true;
                freeze_days_used_ += days;
            }
            void FreezeMembership::thaw() {
                if (!active_) throw FreezeError("membership inactive");
                if (!frozen_) throw FreezeError("membership not frozen");
                frozen_ = false;
            }
            void FreezeMembership::attend() {
                if (!active_) throw VisitError("membership inactive");
                if (frozen_) throw VisitError("membership frozen");
                ++visits_;
            }
            std::int32_t FreezeMembership::visits() const { return visits_; }
            std::int32_t FreezeMembership::freeze_days_used() const { return freeze_days_used_; }
            """,
            """
            void FreezeMembership::activate() {
                if (active_) throw FreezeError("membership already active");
                active_ = true;
            }
            void FreezeMembership::freeze(std::int32_t days) {
                if (!active_) throw FreezeError("membership inactive");
                if (frozen_) throw FreezeError("membership already frozen");
                if (days < 1 || days > 14) throw FreezeError("freeze length out of range");
                frozen_ = true;
                freeze_days_used_ += days;
            }
            void FreezeMembership::thaw() {
                if (!active_) throw FreezeError("membership inactive");
                if (!frozen_) throw FreezeError("membership not frozen");
                frozen_ = false;
            }
            void FreezeMembership::attend() {
                if (!active_) throw VisitError("membership inactive");
                if (frozen_) throw VisitError("membership frozen");
                ++visits_;
            }
            std::int32_t FreezeMembership::visits() const { return visits_; }
            std::int32_t FreezeMembership::freeze_days_used() const { return freeze_days_used_; }
            """,
            """
            FreezeMembership member;
            member.activate();
            member.attend();
            if (member.visits() != 1) return 1;
            member.freeze(7);
            member.thaw();
            if (member.freeze_days_used() != 7) return 2;
            member.attend();
            if (member.visits() != 2) return 3;
            return 0;
            """,
            """
            FreezeMembership member;
            bool threw = false;
            try { member.attend(); } catch (const VisitError&) { threw = true; }
            if (!threw) return 1;
            member.activate();
            threw = false;
            try { member.freeze(15); } catch (const FreezeError&) { threw = true; }
            if (!threw) return 2;
            member.freeze(14);
            threw = false;
            try { member.attend(); } catch (const VisitError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { member.freeze(1); } catch (const FreezeError&) { threw = true; }
            if (!threw) return 4;
            member.thaw();
            member.freeze(14);
            member.thaw();
            member.freeze(14);
            member.thaw();
            member.freeze(14);
            member.thaw();
            member.freeze(4);
            member.thaw();
            threw = false;
            try { member.freeze(1); } catch (const FreezeError&) { threw = true; }
            if (!threw) return 5;
            if (member.freeze_days_used() != 60) return 6;
            member.attend();
            if (member.visits() != 1) return 7;
            return 0;
            """,
            "freeze/thaw lifecycle with a sixty-day cumulative freeze budget",
            "attendance while frozen or freezes beyond the cumulative budget",
            "attendance before activation, freeze length bounds, frozen attendance, double freezes, and exact budget exhaustion",
            "cumulative-budget suspension semantics",
            "multi-state suspend/resume lifecycle machine",
        ),
        c(
            "f26acc-season-ticket-gate",
            "Season ticket gate",
            "season_ticket",
            """
            class AdmitError : public std::runtime_error {
            public:
                explicit AdmitError(const std::string& message) : std::runtime_error(message) {}
            };
            class SuspendError : public std::logic_error {
            public:
                explicit SuspendError(const std::string& message) : std::logic_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SeasonTicket {
            public:
                void issue();
                void suspend();
                void reinstate();
                void admit_event(std::string_view event);
                std::int32_t events() const;
                std::string_view standing() const;
            };
            """,
            """
            class AdmitError : public std::runtime_error {
            public:
                explicit AdmitError(const std::string& message) : std::runtime_error(message) {}
            };
            class SuspendError : public std::logic_error {
            public:
                explicit SuspendError(const std::string& message) : std::logic_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SeasonTicket {
            public:
                void issue();
                void suspend();
                void reinstate();
                void admit_event(std::string_view event);
                std::int32_t events() const;
                std::string_view standing() const;
            private:
                bool issued_ = false;
                bool suspended_ = false;
                std::map<std::string, bool> seen_;
            };
            """,
            """
            void SeasonTicket::issue() {
                if (issued_) throw SuspendError("ticket already issued");
                issued_ = true;
                suspended_ = false;
                seen_.clear();
            }
            void SeasonTicket::suspend() {
                if (!issued_) throw AdmitError("no ticket issued");
                if (suspended_) throw SuspendError("ticket already suspended");
                suspended_ = true;
            }
            void SeasonTicket::reinstate() {
                if (!issued_) throw AdmitError("no ticket issued");
                if (!suspended_) throw SuspendError("ticket not suspended");
                suspended_ = false;
            }
            void SeasonTicket::admit_event(std::string_view event) {
                if (!issued_) throw AdmitError("no ticket issued");
                if (suspended_) throw AdmitError("ticket is suspended");
                if (event.empty()) throw AdmitError("event name required");
                const std::string name(event);
                if (seen_.count(name) != 0) throw DuplicateError("event already admitted");
                seen_[name] = true;
            }
            std::int32_t SeasonTicket::events() const { return static_cast<std::int32_t>(seen_.size()); }
            std::string_view SeasonTicket::standing() const {
                if (!issued_) return "none";
                return suspended_ ? "suspended" : "issued";
            }
            """,
            """
            void SeasonTicket::issue() {
                if (issued_) throw SuspendError("ticket already issued");
                issued_ = true;
                suspended_ = false;
                seen_.clear();
            }
            void SeasonTicket::suspend() {
                if (!issued_) throw AdmitError("no ticket issued");
                if (suspended_) throw SuspendError("ticket already suspended");
                suspended_ = true;
            }
            void SeasonTicket::reinstate() {
                if (!issued_) throw AdmitError("no ticket issued");
                if (!suspended_) throw SuspendError("ticket not suspended");
                suspended_ = false;
            }
            void SeasonTicket::admit_event(std::string_view event) {
                if (!issued_) throw AdmitError("no ticket issued");
                if (event.empty()) throw AdmitError("event name required");
                const std::string name(event);
                if (seen_.count(name) != 0) throw DuplicateError("event already admitted");
                seen_[name] = true;
            }
            std::int32_t SeasonTicket::events() const { return static_cast<std::int32_t>(seen_.size()); }
            std::string_view SeasonTicket::standing() const {
                if (!issued_) return "none";
                return suspended_ ? "suspended" : "issued";
            }
            """,
            """
            SeasonTicket ticket;
            ticket.issue();
            ticket.admit_event("derby");
            if (ticket.events() != 1) return 1;
            ticket.suspend();
            if (ticket.standing() != "suspended") return 2;
            ticket.reinstate();
            if (ticket.standing() != "issued") return 3;
            return 0;
            """,
            """
            SeasonTicket ticket;
            bool threw = false;
            try { ticket.admit_event("cup"); } catch (const AdmitError&) { threw = true; }
            if (!threw) return 1;
            ticket.issue();
            ticket.admit_event("cup");
            ticket.suspend();
            threw = false;
            try { ticket.suspend(); } catch (const SuspendError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { ticket.admit_event("final"); } catch (const AdmitError&) { threw = true; }
            if (!threw) return 3;
            ticket.reinstate();
            threw = false;
            try { ticket.admit_event("cup"); } catch (const DuplicateError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { ticket.reinstate(); } catch (const SuspendError&) { threw = true; }
            if (!threw) return 5;
            ticket.admit_event("final");
            if (ticket.events() != 2) return 6;
            return 0;
            """,
            "attendance lifecycle with per-event duplicate detection under suspension",
            "admissions while suspended or silently repeated events",
            "admissions before issue, double suspensions, suspended admissions, duplicate events, reinstatement, and standings",
            "duplicate-event rejection on a suspendable lifecycle",
            "multi-state suspend/resume lifecycle machine",
            project_support=True,
        ),
        c(
            "f26acc-meal-kit-plan",
            "Meal kit plan",
            "meal_kit",
            """
            class PlanError : public std::invalid_argument {
            public:
                explicit PlanError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CookError : public std::out_of_range {
            public:
                explicit CookError(const std::string& message) : std::out_of_range(message) {}
            };
            class SkipError : public std::logic_error {
            public:
                explicit SkipError(const std::string& message) : std::logic_error(message) {}
            };
            class MealPlan {
            public:
                void enroll(std::int32_t weekly_meals);
                void skip_week();
                void unskip();
                void cook(std::int32_t meals);
                std::int32_t meals_left() const;
                std::int32_t weeks_skipped() const;
            };
            """,
            """
            class PlanError : public std::invalid_argument {
            public:
                explicit PlanError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CookError : public std::out_of_range {
            public:
                explicit CookError(const std::string& message) : std::out_of_range(message) {}
            };
            class SkipError : public std::logic_error {
            public:
                explicit SkipError(const std::string& message) : std::logic_error(message) {}
            };
            class MealPlan {
            public:
                void enroll(std::int32_t weekly_meals);
                void skip_week();
                void unskip();
                void cook(std::int32_t meals);
                std::int32_t meals_left() const;
                std::int32_t weeks_skipped() const;
            private:
                bool enrolled_ = false;
                std::int32_t weekly_ = 0;
                std::int32_t cooked_ = 0;
                bool skipped_ = false;
                std::int32_t weeks_skipped_ = 0;
            };
            """,
            """
            void MealPlan::enroll(std::int32_t weekly_meals) {
                if (enrolled_) throw PlanError("plan already enrolled");
                if (weekly_meals < 2 || weekly_meals > 6) throw PlanError("weekly meals out of range");
                enrolled_ = true;
                weekly_ = weekly_meals;
                cooked_ = 0;
            }
            void MealPlan::skip_week() {
                if (!enrolled_) throw SkipError("no plan enrolled");
                if (skipped_) throw SkipError("week already skipped");
                skipped_ = true;
                ++weeks_skipped_;
            }
            void MealPlan::unskip() {
                if (!enrolled_) throw SkipError("no plan enrolled");
                if (!skipped_) throw SkipError("week not skipped");
                skipped_ = false;
                cooked_ = 0;
            }
            void MealPlan::cook(std::int32_t meals) {
                if (!enrolled_) throw CookError("no plan enrolled");
                if (skipped_) throw CookError("week is skipped");
                if (meals <= 0) throw CookError("meal count must be positive");
                if (cooked_ + meals > weekly_) throw CookError("weekly quota exceeded");
                cooked_ += meals;
            }
            std::int32_t MealPlan::meals_left() const { return enrolled_ ? weekly_ - cooked_ : 0; }
            std::int32_t MealPlan::weeks_skipped() const { return weeks_skipped_; }
            """,
            """
            void MealPlan::enroll(std::int32_t weekly_meals) {
                if (enrolled_) throw PlanError("plan already enrolled");
                if (weekly_meals < 2 || weekly_meals > 6) throw PlanError("weekly meals out of range");
                enrolled_ = true;
                weekly_ = weekly_meals;
                cooked_ = 0;
            }
            void MealPlan::skip_week() {
                if (!enrolled_) throw SkipError("no plan enrolled");
                if (skipped_) throw SkipError("week already skipped");
                skipped_ = true;
                ++weeks_skipped_;
            }
            void MealPlan::unskip() {
                if (!enrolled_) throw SkipError("no plan enrolled");
                if (!skipped_) throw SkipError("week not skipped");
                skipped_ = false;
                cooked_ = 0;
            }
            void MealPlan::cook(std::int32_t meals) {
                if (meals <= 0) throw CookError("meal count must be positive");
                cooked_ = cooked_ + meals > weekly_ ? weekly_ : cooked_ + meals;
            }
            std::int32_t MealPlan::meals_left() const { return enrolled_ ? weekly_ - cooked_ : 0; }
            std::int32_t MealPlan::weeks_skipped() const { return weeks_skipped_; }
            """,
            """
            MealPlan plan;
            plan.enroll(4);
            plan.cook(2);
            if (plan.meals_left() != 2) return 1;
            plan.skip_week();
            if (plan.weeks_skipped() != 1) return 2;
            plan.unskip();
            if (plan.meals_left() != 4) return 3;
            return 0;
            """,
            """
            MealPlan plan;
            bool threw = false;
            try { plan.cook(1); } catch (const CookError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { plan.enroll(7); } catch (const PlanError&) { threw = true; }
            if (!threw) return 2;
            plan.enroll(3);
            plan.cook(3);
            threw = false;
            try { plan.cook(1); } catch (const CookError&) { threw = true; }
            if (!threw) return 3;
            if (plan.meals_left() != 0) return 4;
            plan.skip_week();
            threw = false;
            try { plan.skip_week(); } catch (const SkipError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { plan.cook(1); } catch (const CookError&) { threw = true; }
            if (!threw) return 6;
            plan.unskip();
            if (plan.meals_left() != 3) return 7;
            return 0;
            """,
            "weekly-quota lifecycle with skip semantics and atomic quota checks",
            "clamping cooks to the weekly quota or cooking through a skipped week",
            "cooking before enrollment, enrollment bounds, exact quota exhaustion with unchanged state, double skips, skipped cooks, and unskip resets",
            "quota-plus-skip lifecycle behavior",
            "multi-state suspend/resume lifecycle machine",
        ),
        c(
            "f26acc-coworking-desk-pass",
            "Coworking desk pass",
            "desk_pass",
            """
            class DeskError : public std::logic_error {
            public:
                explicit DeskError(const std::string& message) : std::logic_error(message) {}
            };
            class ExpiredError : public std::runtime_error {
            public:
                explicit ExpiredError(const std::string& message) : std::runtime_error(message) {}
            };
            class DeskPass {
            public:
                void issue(std::int32_t days);
                void suspend();
                void resume();
                void check_in();
                void check_out();
                std::int32_t days_left() const;
                bool inside() const;
            };
            """,
            """
            class DeskError : public std::logic_error {
            public:
                explicit DeskError(const std::string& message) : std::logic_error(message) {}
            };
            class ExpiredError : public std::runtime_error {
            public:
                explicit ExpiredError(const std::string& message) : std::runtime_error(message) {}
            };
            class DeskPass {
            public:
                void issue(std::int32_t days);
                void suspend();
                void resume();
                void check_in();
                void check_out();
                std::int32_t days_left() const;
                bool inside() const;
            private:
                bool issued_ = false;
                bool suspended_ = false;
                bool inside_ = false;
                std::int32_t days_left_ = 0;
            };
            """,
            """
            void DeskPass::issue(std::int32_t days) {
                if (issued_) throw DeskError("pass already issued");
                if (days < 1 || days > 30) throw DeskError("pass days out of range");
                issued_ = true;
                days_left_ = days;
            }
            void DeskPass::suspend() {
                if (!issued_) throw DeskError("no pass issued");
                if (inside_) throw DeskError("cannot suspend while inside");
                if (suspended_) throw DeskError("pass already suspended");
                suspended_ = true;
            }
            void DeskPass::resume() {
                if (!issued_) throw DeskError("no pass issued");
                if (!suspended_) throw DeskError("pass not suspended");
                suspended_ = false;
            }
            void DeskPass::check_in() {
                if (!issued_) throw DeskError("no pass issued");
                if (suspended_) throw DeskError("pass is suspended");
                if (inside_) throw DeskError("already inside");
                if (days_left_ <= 0) throw ExpiredError("pass has expired");
                --days_left_;
                inside_ = true;
            }
            void DeskPass::check_out() {
                if (!issued_) throw DeskError("no pass issued");
                if (!inside_) throw DeskError("not inside");
                inside_ = false;
            }
            std::int32_t DeskPass::days_left() const { return issued_ ? days_left_ : 0; }
            bool DeskPass::inside() const { return inside_; }
            """,
            """
            void DeskPass::issue(std::int32_t days) {
                if (issued_) throw DeskError("pass already issued");
                if (days < 1 || days > 30) throw DeskError("pass days out of range");
                issued_ = true;
                days_left_ = days;
            }
            void DeskPass::suspend() {
                if (!issued_) throw DeskError("no pass issued");
                if (inside_) throw DeskError("cannot suspend while inside");
                if (suspended_) throw DeskError("pass already suspended");
                suspended_ = true;
            }
            void DeskPass::resume() {
                if (!issued_) throw DeskError("no pass issued");
                if (!suspended_) throw DeskError("pass not suspended");
                suspended_ = false;
            }
            void DeskPass::check_in() {
                if (!issued_) throw DeskError("no pass issued");
                if (inside_) throw DeskError("already inside");
                if (days_left_ <= 0) throw ExpiredError("pass has expired");
                --days_left_;
                inside_ = true;
            }
            void DeskPass::check_out() {
                if (!issued_) throw DeskError("no pass issued");
                if (!inside_) throw DeskError("not inside");
                inside_ = false;
            }
            std::int32_t DeskPass::days_left() const { return issued_ ? days_left_ : 0; }
            bool DeskPass::inside() const { return inside_; }
            """,
            """
            DeskPass pass;
            pass.issue(2);
            pass.check_in();
            if (!pass.inside()) return 1;
            pass.check_out();
            if (pass.days_left() != 1) return 2;
            return 0;
            """,
            """
            DeskPass pass;
            bool threw = false;
            try { pass.check_in(); } catch (const DeskError&) { threw = true; }
            if (!threw) return 1;
            pass.issue(1);
            pass.suspend();
            threw = false;
            try { pass.check_in(); } catch (const DeskError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { pass.suspend(); } catch (const DeskError&) { threw = true; }
            if (!threw) return 3;
            pass.resume();
            pass.check_in();
            threw = false;
            try { pass.suspend(); } catch (const DeskError&) { threw = true; }
            if (!threw) return 4;
            pass.check_out();
            threw = false;
            try { pass.check_in(); } catch (const ExpiredError&) { threw = true; }
            if (!threw) return 5;
            if (pass.days_left() != 0) return 6;
            return 0;
            """,
            "day-counted pass with inside/outside pairing and suspension",
            "check-ins that ignore suspension or day exhaustion",
            "check-ins before issue, suspended check-ins, double suspensions, suspension while inside, day exhaustion, and unmatched check-outs",
            "counted-day passes with occupancy pairing",
            "multi-state suspend/resume lifecycle machine",
            project_support=True,
        ),
        c(
            "f26acc-music-lesson-enrollment",
            "Music lesson enrollment",
            "music_lessons",
            """
            class LessonError : public std::logic_error {
            public:
                explicit LessonError(const std::string& message) : std::logic_error(message) {}
            };
            class CreditError : public std::out_of_range {
            public:
                explicit CreditError(const std::string& message) : std::out_of_range(message) {}
            };
            class LessonEnrollment {
            public:
                void enroll(std::int32_t credits);
                void defer();
                void resume();
                void attend();
                std::int32_t credits() const;
                std::int32_t attended() const;
            };
            """,
            """
            class LessonError : public std::logic_error {
            public:
                explicit LessonError(const std::string& message) : std::logic_error(message) {}
            };
            class CreditError : public std::out_of_range {
            public:
                explicit CreditError(const std::string& message) : std::out_of_range(message) {}
            };
            class LessonEnrollment {
            public:
                void enroll(std::int32_t credits);
                void defer();
                void resume();
                void attend();
                std::int32_t credits() const;
                std::int32_t attended() const;
            private:
                bool enrolled_ = false;
                bool deferred_ = false;
                std::int32_t credits_ = 0;
                std::int32_t attended_ = 0;
            };
            """,
            """
            void LessonEnrollment::enroll(std::int32_t credits) {
                if (enrolled_) throw LessonError("already enrolled");
                if (credits < 1 || credits > 40) throw LessonError("credit count out of range");
                enrolled_ = true;
                credits_ = credits;
            }
            void LessonEnrollment::defer() {
                if (!enrolled_) throw LessonError("not enrolled");
                if (deferred_) throw LessonError("already deferred");
                deferred_ = true;
            }
            void LessonEnrollment::resume() {
                if (!enrolled_) throw LessonError("not enrolled");
                if (!deferred_) throw LessonError("not deferred");
                deferred_ = false;
            }
            void LessonEnrollment::attend() {
                if (!enrolled_) throw LessonError("not enrolled");
                if (deferred_) throw LessonError("enrollment deferred");
                if (credits_ <= 0) throw CreditError("no credits left");
                --credits_;
                ++attended_;
            }
            std::int32_t LessonEnrollment::credits() const { return credits_; }
            std::int32_t LessonEnrollment::attended() const { return attended_; }
            """,
            """
            void LessonEnrollment::enroll(std::int32_t credits) {
                if (enrolled_) throw LessonError("already enrolled");
                if (credits < 1 || credits > 40) throw LessonError("credit count out of range");
                enrolled_ = true;
                credits_ = credits;
            }
            void LessonEnrollment::defer() {
                if (!enrolled_) throw LessonError("not enrolled");
                if (deferred_) throw LessonError("already deferred");
                deferred_ = true;
            }
            void LessonEnrollment::resume() {
                if (!enrolled_) throw LessonError("not enrolled");
                if (!deferred_) throw LessonError("not deferred");
                deferred_ = false;
            }
            void LessonEnrollment::attend() {
                if (!enrolled_) throw LessonError("not enrolled");
                --credits_;
                ++attended_;
            }
            std::int32_t LessonEnrollment::credits() const { return credits_; }
            std::int32_t LessonEnrollment::attended() const { return attended_; }
            """,
            """
            LessonEnrollment enrollment;
            enrollment.enroll(2);
            enrollment.attend();
            if (enrollment.credits() != 1) return 1;
            enrollment.defer();
            enrollment.resume();
            enrollment.attend();
            if (enrollment.attended() != 2) return 2;
            return 0;
            """,
            """
            LessonEnrollment enrollment;
            bool threw = false;
            try { enrollment.attend(); } catch (const LessonError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { enrollment.enroll(41); } catch (const LessonError&) { threw = true; }
            if (!threw) return 2;
            enrollment.enroll(1);
            enrollment.defer();
            threw = false;
            try { enrollment.attend(); } catch (const LessonError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { enrollment.defer(); } catch (const LessonError&) { threw = true; }
            if (!threw) return 4;
            enrollment.resume();
            enrollment.attend();
            threw = false;
            try { enrollment.attend(); } catch (const CreditError&) { threw = true; }
            if (!threw) return 5;
            if (enrollment.credits() != 0) return 6;
            return 0;
            """,
            "credit-ledger enrollment with deferral and an exhaustion boundary",
            "attendance that drives credits below zero or slips through deferral",
            "attendance before enrollment, enrollment bounds, deferred attendance, double deferrals, and exact credit exhaustion",
            "credit exhaustion as a lifecycle boundary",
            "multi-state suspend/resume lifecycle machine",
        ),
        c(
            "f26acc-library-hold-shelf",
            "Library hold shelf",
            "hold_shelf",
            """
            class HoldError : public std::logic_error {
            public:
                explicit HoldError(const std::string& message) : std::logic_error(message) {}
            };
            class PickupError : public std::runtime_error {
            public:
                explicit PickupError(const std::string& message) : std::runtime_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HoldShelf {
            public:
                void place(std::string_view item);
                void cancel(std::string_view item);
                void mark_ready(std::string_view item);
                void pickup(std::string_view item);
                std::size_t waiting() const;
            };
            """,
            """
            class HoldError : public std::logic_error {
            public:
                explicit HoldError(const std::string& message) : std::logic_error(message) {}
            };
            class PickupError : public std::runtime_error {
            public:
                explicit PickupError(const std::string& message) : std::runtime_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HoldShelf {
            public:
                void place(std::string_view item);
                void cancel(std::string_view item);
                void mark_ready(std::string_view item);
                void pickup(std::string_view item);
                std::size_t waiting() const;
            private:
                std::map<std::string, bool> holds_;
            };
            """,
            """
            void HoldShelf::place(std::string_view item) {
                if (item.empty()) throw HoldError("item name required");
                const std::string name(item);
                if (holds_.count(name) != 0) throw DuplicateError("item already placed");
                holds_[name] = false;
            }
            void HoldShelf::cancel(std::string_view item) {
                const std::string name(item);
                if (holds_.count(name) == 0) throw HoldError("unknown item");
                if (holds_.at(name)) throw HoldError("cannot cancel a ready item");
                holds_.erase(name);
            }
            void HoldShelf::mark_ready(std::string_view item) {
                const std::string name(item);
                if (holds_.count(name) == 0) throw HoldError("unknown item");
                if (holds_.at(name)) throw HoldError("item already ready");
                holds_[name] = true;
            }
            void HoldShelf::pickup(std::string_view item) {
                const std::string name(item);
                if (holds_.count(name) == 0) throw PickupError("unknown item");
                if (!holds_.at(name)) throw PickupError("item is not ready");
                holds_.erase(name);
            }
            std::size_t HoldShelf::waiting() const { return holds_.size(); }
            """,
            """
            void HoldShelf::place(std::string_view item) {
                if (item.empty()) throw HoldError("item name required");
                const std::string name(item);
                if (holds_.count(name) != 0) throw DuplicateError("item already placed");
                holds_[name] = false;
            }
            void HoldShelf::cancel(std::string_view item) {
                const std::string name(item);
                if (holds_.count(name) == 0) throw HoldError("unknown item");
                if (holds_.at(name)) throw HoldError("cannot cancel a ready item");
                holds_.erase(name);
            }
            void HoldShelf::mark_ready(std::string_view item) {
                const std::string name(item);
                if (holds_.count(name) == 0) throw HoldError("unknown item");
                if (holds_.at(name)) throw HoldError("item already ready");
                holds_[name] = true;
            }
            void HoldShelf::pickup(std::string_view item) {
                const std::string name(item);
                if (holds_.count(name) == 0) throw PickupError("unknown item");
                holds_.erase(name);
            }
            std::size_t HoldShelf::waiting() const { return holds_.size(); }
            """,
            """
            HoldShelf shelf;
            shelf.place("atlas");
            shelf.mark_ready("atlas");
            if (shelf.waiting() != 1) return 1;
            shelf.pickup("atlas");
            if (shelf.waiting() != 0) return 2;
            return 0;
            """,
            """
            HoldShelf shelf;
            bool threw = false;
            try { shelf.pickup("atlas"); } catch (const PickupError&) { threw = true; }
            if (!threw) return 1;
            shelf.place("atlas");
            threw = false;
            try { shelf.place("atlas"); } catch (const DuplicateError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { shelf.pickup("atlas"); } catch (const PickupError&) { threw = true; }
            if (!threw) return 3;
            shelf.mark_ready("atlas");
            threw = false;
            try { shelf.cancel("atlas"); } catch (const HoldError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { shelf.mark_ready("globe"); } catch (const HoldError&) { threw = true; }
            if (!threw) return 5;
            shelf.place("globe");
            shelf.cancel("globe");
            if (shelf.waiting() != 1) return 6;
            shelf.pickup("atlas");
            if (shelf.waiting() != 0) return 7;
            return 0;
            """,
            "per-item two-stage state machine with a registry of held items",
            "pickups straight from placed or stateless item handling",
            "duplicate placements, pickups before ready, ready-state cancellations, unknown items, and waiting counts",
            "per-entity state machines, a richer lifecycle shape",
            "multi-state suspend/resume lifecycle machine",
            project_support=True,
        ),
        c(
            "f26acc-vending-journal",
            "Vending journal",
            "vending_journal",
            """
            class PowerError : public std::logic_error {
            public:
                explicit PowerError(const std::string& message) : std::logic_error(message) {}
            };
            class SlotError : public std::invalid_argument {
            public:
                explicit SlotError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StockError : public std::runtime_error {
            public:
                explicit StockError(const std::string& message) : std::runtime_error(message) {}
            };
            class VendingJournal {
            public:
                void power_on();
                void power_off();
                void restock(std::string_view slot, std::int32_t n);
                void vend(std::string_view slot, std::int32_t price);
                std::int32_t stock(std::string_view slot) const;
                std::vector<std::string> journal() const;
            };
            """,
            """
            class PowerError : public std::logic_error {
            public:
                explicit PowerError(const std::string& message) : std::logic_error(message) {}
            };
            class SlotError : public std::invalid_argument {
            public:
                explicit SlotError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StockError : public std::runtime_error {
            public:
                explicit StockError(const std::string& message) : std::runtime_error(message) {}
            };
            class VendingJournal {
            public:
                void power_on();
                void power_off();
                void restock(std::string_view slot, std::int32_t n);
                void vend(std::string_view slot, std::int32_t price);
                std::int32_t stock(std::string_view slot) const;
                std::vector<std::string> journal() const;
            private:
                bool on_ = false;
                std::map<std::string, std::int32_t> stock_;
                std::vector<std::string> journal_;
            };
            """,
            """
            namespace {
            bool known_slot(std::string_view slot) {
                return slot == "A1" || slot == "A2" || slot == "B1" || slot == "B2";
            }
            }  // namespace
            void VendingJournal::power_on() {
                if (on_) throw PowerError("machine already on");
                on_ = true;
            }
            void VendingJournal::power_off() {
                if (!on_) throw PowerError("machine is off");
                on_ = false;
            }
            void VendingJournal::restock(std::string_view slot, std::int32_t n) {
                if (!on_) throw PowerError("machine is off");
                if (!known_slot(slot)) throw SlotError("unknown slot");
                if (n <= 0) throw SlotError("restock must be positive");
                stock_[std::string(slot)] += n;
                journal_.push_back("restock:" + std::string(slot) + ":" + std::to_string(n));
            }
            void VendingJournal::vend(std::string_view slot, std::int32_t price) {
                if (!on_) throw PowerError("machine is off");
                if (!known_slot(slot)) throw SlotError("unknown slot");
                if (price <= 0) throw SlotError("price must be positive");
                const std::string name(slot);
                if (stock_[name] <= 0) throw StockError("slot is empty");
                --stock_[name];
                journal_.push_back("vend:" + name + ":" + std::to_string(price));
            }
            std::int32_t VendingJournal::stock(std::string_view slot) const {
                if (!known_slot(slot)) throw SlotError("unknown slot");
                const std::string name(slot);
                return stock_.count(name) == 0 ? 0 : stock_.at(name);
            }
            std::vector<std::string> VendingJournal::journal() const { return journal_; }
            """,
            """
            namespace {
            bool known_slot(std::string_view slot) {
                return slot == "A1" || slot == "A2" || slot == "B1" || slot == "B2";
            }
            }  // namespace
            void VendingJournal::power_on() {
                if (on_) throw PowerError("machine already on");
                on_ = true;
            }
            void VendingJournal::power_off() {
                if (!on_) throw PowerError("machine is off");
                on_ = false;
            }
            void VendingJournal::restock(std::string_view slot, std::int32_t n) {
                if (!on_) throw PowerError("machine is off");
                if (!known_slot(slot)) throw SlotError("unknown slot");
                if (n <= 0) throw SlotError("restock must be positive");
                stock_[std::string(slot)] += n;
                journal_.push_back("restock:" + std::string(slot) + ":" + std::to_string(n));
            }
            void VendingJournal::vend(std::string_view slot, std::int32_t price) {
                if (!on_) throw PowerError("machine is off");
                if (!known_slot(slot)) throw SlotError("unknown slot");
                if (price <= 0) throw SlotError("price must be positive");
                const std::string name(slot);
                journal_.push_back("vend:" + name + ":" + std::to_string(price));
                if (stock_[name] <= 0) throw StockError("slot is empty");
                --stock_[name];
            }
            std::int32_t VendingJournal::stock(std::string_view slot) const {
                if (!known_slot(slot)) throw SlotError("unknown slot");
                const std::string name(slot);
                return stock_.count(name) == 0 ? 0 : stock_.at(name);
            }
            std::vector<std::string> VendingJournal::journal() const { return journal_; }
            """,
            """
            VendingJournal machine;
            machine.power_on();
            machine.restock("A1", 2);
            machine.vend("A1", 150);
            if (machine.stock("A1") != 1) return 1;
            if (machine.journal().size() != 2) return 2;
            return 0;
            """,
            """
            VendingJournal machine;
            bool threw = false;
            try { machine.vend("A1", 100); } catch (const PowerError&) { threw = true; }
            if (!threw) return 1;
            machine.power_on();
            threw = false;
            try { machine.vend("C9", 100); } catch (const SlotError&) { threw = true; }
            if (!threw) return 2;
            machine.restock("B2", 1);
            machine.vend("B2", 75);
            threw = false;
            try { machine.vend("B2", 75); } catch (const StockError&) { threw = true; }
            if (!threw) return 3;
            std::vector<std::string> want{"restock:B2:1", "vend:B2:75"};
            if (machine.journal() != want) return 4;
            machine.power_off();
            threw = false;
            try { machine.restock("A1", 1); } catch (const PowerError&) { threw = true; }
            if (!threw) return 5;
            if (machine.journal().size() != 2) return 6;
            return 0;
            """,
            "an operation journal that records only accepted mutations",
            "journaling rejected operations so the log disagrees with the state",
            "operations while off, unknown slots, empty vends with an unchanged journal, restock entries, and exact journal order",
            "journal atomicity: logs are part of the state mutation",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-laundry-card-ledger",
            "Laundry card ledger",
            "laundry_card",
            """
            class CardError : public std::logic_error {
            public:
                explicit CardError(const std::string& message) : std::logic_error(message) {}
            };
            class ChargeError : public std::out_of_range {
            public:
                explicit ChargeError(const std::string& message) : std::out_of_range(message) {}
            };
            class RefundError : public std::runtime_error {
            public:
                explicit RefundError(const std::string& message) : std::runtime_error(message) {}
            };
            class LaundryCard {
            public:
                void activate(std::int32_t cents);
                void deactivate();
                void charge(std::int32_t cents, std::string_view machine);
                void refund_last();
                std::int32_t balance_cents() const;
                std::vector<std::string> entries() const;
            };
            """,
            """
            class CardError : public std::logic_error {
            public:
                explicit CardError(const std::string& message) : std::logic_error(message) {}
            };
            class ChargeError : public std::out_of_range {
            public:
                explicit ChargeError(const std::string& message) : std::out_of_range(message) {}
            };
            class RefundError : public std::runtime_error {
            public:
                explicit RefundError(const std::string& message) : std::runtime_error(message) {}
            };
            class LaundryCard {
            public:
                void activate(std::int32_t cents);
                void deactivate();
                void charge(std::int32_t cents, std::string_view machine);
                void refund_last();
                std::int32_t balance_cents() const;
                std::vector<std::string> entries() const;
            private:
                bool active_ = false;
                std::int32_t balance_ = 0;
                std::vector<std::pair<std::string, std::int32_t>> charges_;
            };
            """,
            """
            void LaundryCard::activate(std::int32_t cents) {
                if (active_) throw CardError("card already active");
                if (cents <= 0) throw CardError("activation amount must be positive");
                active_ = true;
                balance_ = cents;
                charges_.clear();
            }
            void LaundryCard::deactivate() {
                if (!active_) throw CardError("card is not active");
                active_ = false;
            }
            void LaundryCard::charge(std::int32_t cents, std::string_view machine) {
                if (!active_) throw CardError("card is not active");
                if (cents <= 0) throw CardError("charge must be positive");
                if (machine.empty()) throw CardError("machine name required");
                if (cents > balance_) throw ChargeError("charge exceeds balance");
                balance_ -= cents;
                charges_.push_back({std::string(machine), cents});
            }
            void LaundryCard::refund_last() {
                if (!active_) throw CardError("card is not active");
                if (charges_.empty()) throw RefundError("nothing to refund");
                balance_ += charges_.back().second;
                charges_.pop_back();
            }
            std::int32_t LaundryCard::balance_cents() const { return balance_; }
            std::vector<std::string> LaundryCard::entries() const {
                std::vector<std::string> out;
                for (const auto& charge : charges_) {
                    out.push_back("charge:" + charge.first + ":" + std::to_string(charge.second));
                }
                return out;
            }
            """,
            """
            void LaundryCard::activate(std::int32_t cents) {
                if (active_) throw CardError("card already active");
                if (cents <= 0) throw CardError("activation amount must be positive");
                active_ = true;
                balance_ = cents;
                charges_.clear();
            }
            void LaundryCard::deactivate() {
                if (!active_) throw CardError("card is not active");
                active_ = false;
            }
            void LaundryCard::charge(std::int32_t cents, std::string_view machine) {
                if (!active_) throw CardError("card is not active");
                if (cents <= 0) throw CardError("charge must be positive");
                if (machine.empty()) throw CardError("machine name required");
                if (cents > balance_) throw ChargeError("charge exceeds balance");
                balance_ -= cents;
                charges_.push_back({std::string(machine), cents});
            }
            void LaundryCard::refund_last() {
                if (!active_) throw CardError("card is not active");
                if (charges_.empty()) throw RefundError("nothing to refund");
                balance_ += charges_.back().second;
            }
            std::int32_t LaundryCard::balance_cents() const { return balance_; }
            std::vector<std::string> LaundryCard::entries() const {
                std::vector<std::string> out;
                for (const auto& charge : charges_) {
                    out.push_back("charge:" + charge.first + ":" + std::to_string(charge.second));
                }
                return out;
            }
            """,
            """
            LaundryCard card;
            card.activate(1000);
            card.charge(275, "washer");
            if (card.balance_cents() != 725) return 1;
            if (card.entries() != std::vector<std::string>{"charge:washer:275"}) return 2;
            return 0;
            """,
            """
            LaundryCard card;
            bool threw = false;
            try { card.charge(100, "dryer"); } catch (const CardError&) { threw = true; }
            if (!threw) return 1;
            card.activate(500);
            threw = false;
            try { card.charge(600, "washer"); } catch (const ChargeError&) { threw = true; }
            if (!threw) return 2;
            if (card.balance_cents() != 500) return 3;
            if (!card.entries().empty()) return 4;
            card.charge(200, "washer");
            card.charge(100, "dryer");
            card.refund_last();
            if (card.balance_cents() != 300) return 5;
            if (card.entries() != std::vector<std::string>{"charge:washer:200"}) return 6;
            card.refund_last();
            threw = false;
            try { card.refund_last(); } catch (const RefundError&) { threw = true; }
            if (!threw) return 7;
            if (card.balance_cents() != 500) return 8;
            return 0;
            """,
            "a charge ledger with single-step rollback of the newest accepted charge",
            "balance-only refunds that leave the charge entry behind",
            "charges before activation, overcharges with unchanged balance and entries, double refunds, empty refunds, and deactivation",
            "exact undo semantics over an operation ledger",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-coffee-tab-board",
            "Coffee tab board",
            "coffee_tab",
            """
            class TabError : public std::logic_error {
            public:
                explicit TabError(const std::string& message) : std::logic_error(message) {}
            };
            class TabBoard {
            public:
                void open_tab(std::string_view guest);
                void close_tab(std::string_view guest);
                void order(std::string_view guest, std::int32_t cents);
                std::int32_t settle(std::string_view guest);
                std::optional<std::int32_t> total(std::string_view guest) const;
            };
            """,
            """
            class TabError : public std::logic_error {
            public:
                explicit TabError(const std::string& message) : std::logic_error(message) {}
            };
            class TabBoard {
            public:
                void open_tab(std::string_view guest);
                void close_tab(std::string_view guest);
                void order(std::string_view guest, std::int32_t cents);
                std::int32_t settle(std::string_view guest);
                std::optional<std::int32_t> total(std::string_view guest) const;
            private:
                std::map<std::string, std::int32_t> tabs_;
            };
            """,
            """
            void TabBoard::open_tab(std::string_view guest) {
                if (guest.empty()) throw TabError("guest name required");
                const std::string name(guest);
                if (tabs_.count(name) != 0) throw TabError("tab already open");
                tabs_[name] = 0;
            }
            void TabBoard::close_tab(std::string_view guest) {
                const std::string name(guest);
                if (tabs_.count(name) == 0) throw TabError("unknown tab");
                if (tabs_.at(name) != 0) throw TabError("tab still has a balance");
                tabs_.erase(name);
            }
            void TabBoard::order(std::string_view guest, std::int32_t cents) {
                const std::string name(guest);
                if (tabs_.count(name) == 0) throw TabError("unknown tab");
                if (cents <= 0) throw TabError("order must be positive");
                tabs_[name] += cents;
            }
            std::int32_t TabBoard::settle(std::string_view guest) {
                const std::string name(guest);
                if (tabs_.count(name) == 0) throw TabError("unknown tab");
                const std::int32_t owed = tabs_.at(name);
                tabs_.erase(name);
                return owed;
            }
            std::optional<std::int32_t> TabBoard::total(std::string_view guest) const {
                const std::string name(guest);
                if (tabs_.count(name) == 0) return std::nullopt;
                return tabs_.at(name);
            }
            """,
            """
            void TabBoard::open_tab(std::string_view guest) {
                if (guest.empty()) throw TabError("guest name required");
                const std::string name(guest);
                if (tabs_.count(name) != 0) throw TabError("tab already open");
                tabs_[name] = 0;
            }
            void TabBoard::close_tab(std::string_view guest) {
                const std::string name(guest);
                if (tabs_.count(name) == 0) throw TabError("unknown tab");
                if (tabs_.at(name) != 0) throw TabError("tab still has a balance");
                tabs_.erase(name);
            }
            void TabBoard::order(std::string_view guest, std::int32_t cents) {
                if (cents <= 0) throw TabError("order must be positive");
                tabs_[std::string(guest)] += cents;
            }
            std::int32_t TabBoard::settle(std::string_view guest) {
                const std::string name(guest);
                if (tabs_.count(name) == 0) throw TabError("unknown tab");
                const std::int32_t owed = tabs_.at(name);
                tabs_.erase(name);
                return owed;
            }
            std::optional<std::int32_t> TabBoard::total(std::string_view guest) const {
                const std::string name(guest);
                if (tabs_.count(name) == 0) return std::nullopt;
                return tabs_.at(name);
            }
            """,
            """
            TabBoard board;
            board.open_tab("ana");
            board.order("ana", 450);
            board.open_tab("lee");
            board.order("lee", 200);
            if (board.total("ana") != std::optional<std::int32_t>(450)) return 1;
            if (board.settle("lee") != 200) return 2;
            if (board.total("lee").has_value()) return 3;
            return 0;
            """,
            """
            TabBoard board;
            bool threw = false;
            try { board.order("mia", 100); } catch (const TabError&) { threw = true; }
            if (!threw) return 1;
            board.open_tab("mia");
            threw = false;
            try { board.open_tab("mia"); } catch (const TabError&) { threw = true; }
            if (!threw) return 2;
            board.order("mia", 300);
            board.open_tab("noa");
            board.order("noa", 150);
            threw = false;
            try { board.close_tab("mia"); } catch (const TabError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { board.order("ivy", 50); } catch (const TabError&) { threw = true; }
            if (!threw) return 4;
            if (board.settle("mia") != 300) return 5;
            if (board.settle("noa") != 150) return 6;
            threw = false;
            try { board.settle("mia"); } catch (const TabError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            "per-guest tab lifecycles interleaved on one board",
            "orders that accrue to closed or unknown tabs",
            "interleaved guests, orders on unknown tabs, duplicate opens, closes with balances, and settles",
            "deterministic interleaving across independent lifecycles",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-makerspace-usage-log",
            "Makerspace usage log",
            "makerspace_log",
            """
            class SessionError : public std::logic_error {
            public:
                explicit SessionError(const std::string& message) : std::logic_error(message) {}
            };
            class UsageError : public std::out_of_range {
            public:
                explicit UsageError(const std::string& message) : std::out_of_range(message) {}
            };
            class UsageLog {
            public:
                void begin_session(std::string_view member);
                void log_usage(std::string_view tool, std::int32_t minutes);
                void end_session();
                std::int32_t session_minutes() const;
                std::vector<std::string> log() const;
            };
            """,
            """
            class SessionError : public std::logic_error {
            public:
                explicit SessionError(const std::string& message) : std::logic_error(message) {}
            };
            class UsageError : public std::out_of_range {
            public:
                explicit UsageError(const std::string& message) : std::out_of_range(message) {}
            };
            class UsageLog {
            public:
                void begin_session(std::string_view member);
                void log_usage(std::string_view tool, std::int32_t minutes);
                void end_session();
                std::int32_t session_minutes() const;
                std::vector<std::string> log() const;
            private:
                bool open_ = false;
                std::string member_;
                std::int32_t minutes_ = 0;
                std::vector<std::string> log_;
            };
            """,
            """
            void UsageLog::begin_session(std::string_view member) {
                if (open_) throw SessionError("session already open");
                if (member.empty()) throw SessionError("member name required");
                open_ = true;
                member_ = std::string(member);
                minutes_ = 0;
            }
            void UsageLog::log_usage(std::string_view tool, std::int32_t minutes) {
                if (!open_) throw SessionError("no session open");
                if (tool.empty()) throw SessionError("tool name required");
                if (minutes <= 0) throw SessionError("minutes must be positive");
                if (minutes > 480) throw UsageError("single use too long");
                minutes_ += minutes;
                log_.push_back("use:" + std::string(tool) + ":" + std::to_string(minutes));
            }
            void UsageLog::end_session() {
                if (!open_) throw SessionError("no session open");
                log_.push_back("total:" + std::to_string(minutes_));
                open_ = false;
                member_.clear();
            }
            std::int32_t UsageLog::session_minutes() const { return open_ ? minutes_ : 0; }
            std::vector<std::string> UsageLog::log() const { return log_; }
            """,
            """
            void UsageLog::begin_session(std::string_view member) {
                if (open_) throw SessionError("session already open");
                if (member.empty()) throw SessionError("member name required");
                open_ = true;
                member_ = std::string(member);
                minutes_ = 0;
            }
            void UsageLog::log_usage(std::string_view tool, std::int32_t minutes) {
                if (tool.empty()) throw SessionError("tool name required");
                if (minutes <= 0) throw SessionError("minutes must be positive");
                if (minutes > 480) throw UsageError("single use too long");
                minutes_ += minutes;
                log_.push_back("use:" + std::string(tool) + ":" + std::to_string(minutes));
            }
            void UsageLog::end_session() {
                if (!open_) throw SessionError("no session open");
                log_.push_back("total:" + std::to_string(minutes_));
                open_ = false;
                member_.clear();
            }
            std::int32_t UsageLog::session_minutes() const { return open_ ? minutes_ : 0; }
            std::vector<std::string> UsageLog::log() const { return log_; }
            """,
            """
            UsageLog usage;
            usage.begin_session("kai");
            usage.log_usage("laser", 45);
            if (usage.session_minutes() != 45) return 1;
            usage.end_session();
            if (usage.log() != std::vector<std::string>{"use:laser:45", "total:45"}) return 2;
            return 0;
            """,
            """
            UsageLog usage;
            bool threw = false;
            try { usage.log_usage("saw", 10); } catch (const SessionError&) { threw = true; }
            if (!threw) return 1;
            usage.begin_session("rin");
            threw = false;
            try { usage.begin_session("two"); } catch (const SessionError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { usage.log_usage("lathe", 481); } catch (const UsageError&) { threw = true; }
            if (!threw) return 3;
            if (!usage.log().empty()) return 4;
            usage.log_usage("mill", 60);
            usage.end_session();
            if (usage.log() != std::vector<std::string>{"use:mill:60", "total:60"}) return 5;
            if (usage.session_minutes() != 0) return 6;
            return 0;
            """,
            "session-scoped usage journal with per-entry bounds",
            "sessionless logging or oversized entries that still append",
            "logging before a session, double begins, oversized usage with an unchanged log, end summaries, and post-end reads",
            "session scoping on a journal lifecycle",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-campsite-fee-ledger",
            "Campsite fee ledger",
            "campsite_fees",
            """
            class LedgerError : public std::logic_error {
            public:
                explicit LedgerError(const std::string& message) : std::logic_error(message) {}
            };
            class VoidError : public std::runtime_error {
            public:
                explicit VoidError(const std::string& message) : std::runtime_error(message) {}
            };
            class FeeLedger {
            public:
                void check_in(std::int32_t nights, std::int32_t nightly_cents);
                void add_fee(std::string_view item, std::int32_t cents);
                void void_last_fee();
                std::int32_t total_cents() const;
                std::vector<std::string> fees() const;
            };
            """,
            """
            class LedgerError : public std::logic_error {
            public:
                explicit LedgerError(const std::string& message) : std::logic_error(message) {}
            };
            class VoidError : public std::runtime_error {
            public:
                explicit VoidError(const std::string& message) : std::runtime_error(message) {}
            };
            class FeeLedger {
            public:
                void check_in(std::int32_t nights, std::int32_t nightly_cents);
                void add_fee(std::string_view item, std::int32_t cents);
                void void_last_fee();
                std::int32_t total_cents() const;
                std::vector<std::string> fees() const;
            private:
                bool open_ = false;
                std::int32_t base_cents_ = 0;
                std::vector<std::pair<std::string, std::int32_t>> fees_;
            };
            """,
            """
            void FeeLedger::check_in(std::int32_t nights, std::int32_t nightly_cents) {
                if (open_) throw LedgerError("stay already open");
                if (nights < 1 || nights > 14) throw LedgerError("night count out of range");
                if (nightly_cents <= 0) throw LedgerError("nightly rate must be positive");
                open_ = true;
                base_cents_ = nights * nightly_cents;
                fees_.clear();
            }
            void FeeLedger::add_fee(std::string_view item, std::int32_t cents) {
                if (!open_) throw LedgerError("no stay open");
                if (item.empty()) throw LedgerError("fee item required");
                if (cents <= 0) throw LedgerError("fee must be positive");
                fees_.push_back({std::string(item), cents});
            }
            void FeeLedger::void_last_fee() {
                if (!open_) throw LedgerError("no stay open");
                if (fees_.empty()) throw VoidError("no fee to void");
                fees_.pop_back();
            }
            std::int32_t FeeLedger::total_cents() const {
                if (!open_) return 0;
                std::int32_t total = base_cents_;
                for (const auto& fee : fees_) total += fee.second;
                return total;
            }
            std::vector<std::string> FeeLedger::fees() const {
                std::vector<std::string> out;
                for (const auto& fee : fees_) {
                    out.push_back(fee.first + ":" + std::to_string(fee.second));
                }
                return out;
            }
            """,
            """
            void FeeLedger::check_in(std::int32_t nights, std::int32_t nightly_cents) {
                if (open_) throw LedgerError("stay already open");
                if (nights < 1 || nights > 14) throw LedgerError("night count out of range");
                if (nightly_cents <= 0) throw LedgerError("nightly rate must be positive");
                open_ = true;
                base_cents_ = nights * nightly_cents;
                fees_.clear();
            }
            void FeeLedger::add_fee(std::string_view item, std::int32_t cents) {
                if (!open_) throw LedgerError("no stay open");
                if (item.empty()) throw LedgerError("fee item required");
                if (cents <= 0) throw LedgerError("fee must be positive");
                fees_.push_back({std::string(item), cents});
            }
            void FeeLedger::void_last_fee() {
                if (!open_) throw LedgerError("no stay open");
                if (fees_.empty()) throw VoidError("no fee to void");
                fees_.clear();
            }
            std::int32_t FeeLedger::total_cents() const {
                if (!open_) return 0;
                std::int32_t total = base_cents_;
                for (const auto& fee : fees_) total += fee.second;
                return total;
            }
            std::vector<std::string> FeeLedger::fees() const {
                std::vector<std::string> out;
                for (const auto& fee : fees_) {
                    out.push_back(fee.first + ":" + std::to_string(fee.second));
                }
                return out;
            }
            """,
            """
            FeeLedger ledger;
            ledger.check_in(2, 3000);
            ledger.add_fee("firewood", 700);
            if (ledger.total_cents() != 6700) return 1;
            ledger.void_last_fee();
            if (ledger.total_cents() != 6000) return 2;
            return 0;
            """,
            """
            FeeLedger ledger;
            bool threw = false;
            try { ledger.add_fee("ice", 200); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ledger.check_in(15, 1000); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 2;
            ledger.check_in(1, 2500);
            threw = false;
            try { ledger.add_fee("ice", 0); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 3;
            ledger.add_fee("ice", 250);
            ledger.add_fee("bait", 400);
            ledger.void_last_fee();
            if (ledger.fees() != std::vector<std::string>{"ice:250"}) return 4;
            if (ledger.total_cents() != 2750) return 5;
            ledger.void_last_fee();
            threw = false;
            try { ledger.void_last_fee(); } catch (const VoidError&) { threw = true; }
            if (!threw) return 6;
            if (ledger.total_cents() != 2500) return 7;
            return 0;
            """,
            "fee ledger with base-plus-extras accounting and newest-fee voiding",
            "voiding that clears every fee or touches the nightly base",
            "fees before check-in, check-in bounds, non-positive fees, selective voids, empty voids, and totals after voids",
            "selective rollback on an additive ledger",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-parking-meter-events",
            "Parking meter events",
            "parking_meter",
            """
            class MeterError : public std::logic_error {
            public:
                explicit MeterError(const std::string& message) : std::logic_error(message) {}
            };
            class LimitError : public std::out_of_range {
            public:
                explicit LimitError(const std::string& message) : std::out_of_range(message) {}
            };
            class MeterLog {
            public:
                void install(std::int32_t limit_minutes);
                void remove();
                void pay(std::int32_t minutes);
                void top_up(std::int32_t minutes);
                std::int32_t paid_minutes() const;
                std::vector<std::string> events() const;
            };
            """,
            """
            class MeterError : public std::logic_error {
            public:
                explicit MeterError(const std::string& message) : std::logic_error(message) {}
            };
            class LimitError : public std::out_of_range {
            public:
                explicit LimitError(const std::string& message) : std::out_of_range(message) {}
            };
            class MeterLog {
            public:
                void install(std::int32_t limit_minutes);
                void remove();
                void pay(std::int32_t minutes);
                void top_up(std::int32_t minutes);
                std::int32_t paid_minutes() const;
                std::vector<std::string> events() const;
            private:
                bool installed_ = false;
                std::int32_t limit_ = 0;
                std::int32_t paid_ = 0;
                bool has_payment_ = false;
                std::vector<std::string> events_;
            };
            """,
            """
            void MeterLog::install(std::int32_t limit_minutes) {
                if (installed_) throw MeterError("meter already installed");
                if (limit_minutes < 30 || limit_minutes > 480) throw MeterError("limit out of range");
                installed_ = true;
                limit_ = limit_minutes;
                paid_ = 0;
                has_payment_ = false;
                events_.clear();
            }
            void MeterLog::remove() {
                if (!installed_) throw MeterError("meter not installed");
                installed_ = false;
            }
            void MeterLog::pay(std::int32_t minutes) {
                if (!installed_) throw MeterError("meter not installed");
                if (minutes <= 0) throw MeterError("minutes must be positive");
                if (has_payment_) throw MeterError("use top_up for more time");
                if (minutes > limit_) throw LimitError("payment exceeds limit");
                paid_ = minutes;
                has_payment_ = true;
                events_.push_back("pay:" + std::to_string(minutes));
            }
            void MeterLog::top_up(std::int32_t minutes) {
                if (!installed_) throw MeterError("meter not installed");
                if (minutes <= 0) throw MeterError("minutes must be positive");
                if (!has_payment_) throw MeterError("pay first");
                if (paid_ + minutes > limit_) throw LimitError("top-up exceeds limit");
                paid_ += minutes;
                events_.push_back("topup:" + std::to_string(minutes));
            }
            std::int32_t MeterLog::paid_minutes() const { return installed_ ? paid_ : 0; }
            std::vector<std::string> MeterLog::events() const { return events_; }
            """,
            """
            void MeterLog::install(std::int32_t limit_minutes) {
                if (installed_) throw MeterError("meter already installed");
                if (limit_minutes < 30 || limit_minutes > 480) throw MeterError("limit out of range");
                installed_ = true;
                limit_ = limit_minutes;
                paid_ = 0;
                has_payment_ = false;
                events_.clear();
            }
            void MeterLog::remove() {
                if (!installed_) throw MeterError("meter not installed");
                installed_ = false;
            }
            void MeterLog::pay(std::int32_t minutes) {
                if (!installed_) throw MeterError("meter not installed");
                if (minutes <= 0) throw MeterError("minutes must be positive");
                paid_ = minutes > limit_ ? limit_ : minutes;
                has_payment_ = true;
                events_.push_back("pay:" + std::to_string(paid_));
            }
            void MeterLog::top_up(std::int32_t minutes) {
                if (!installed_) throw MeterError("meter not installed");
                if (minutes <= 0) throw MeterError("minutes must be positive");
                if (!has_payment_) throw MeterError("pay first");
                paid_ = paid_ + minutes > limit_ ? limit_ : paid_ + minutes;
                events_.push_back("topup:" + std::to_string(minutes));
            }
            std::int32_t MeterLog::paid_minutes() const { return installed_ ? paid_ : 0; }
            std::vector<std::string> MeterLog::events() const { return events_; }
            """,
            """
            MeterLog meter;
            meter.install(120);
            meter.pay(60);
            meter.top_up(30);
            if (meter.paid_minutes() != 90) return 1;
            if (meter.events() != std::vector<std::string>{"pay:60", "topup:30"}) return 2;
            return 0;
            """,
            """
            MeterLog meter;
            bool threw = false;
            try { meter.pay(30); } catch (const MeterError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { meter.install(20); } catch (const MeterError&) { threw = true; }
            if (!threw) return 2;
            meter.install(90);
            threw = false;
            try { meter.pay(120); } catch (const LimitError&) { threw = true; }
            if (!threw) return 3;
            if (meter.paid_minutes() != 0) return 4;
            if (!meter.events().empty()) return 5;
            meter.pay(90);
            threw = false;
            try { meter.pay(10); } catch (const MeterError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { meter.top_up(1); } catch (const LimitError&) { threw = true; }
            if (!threw) return 7;
            meter.remove();
            threw = false;
            try { meter.top_up(10); } catch (const MeterError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "bounded meter with an event trail and distinct pay/top-up rules",
            "clamping at the limit or accepting a second payment",
            "payments before install, install bounds, over-limit payments with unchanged state and events, second payments, exact-limit top-ups, and removal",
            "bounded additive state with an exact event trail",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-aquarium-club-fund",
            "Aquarium club fund",
            "club_fund",
            """
            class FundStateError : public std::logic_error {
            public:
                explicit FundStateError(const std::string& message) : std::logic_error(message) {}
            };
            class PendingError : public std::runtime_error {
            public:
                explicit PendingError(const std::string& message) : std::runtime_error(message) {}
            };
            class FundError : public std::out_of_range {
            public:
                explicit FundError(const std::string& message) : std::out_of_range(message) {}
            };
            class ClubFund {
            public:
                void open(std::int32_t cents);
                void close();
                void propose(std::string_view purpose, std::int32_t cents);
                void commit();
                void abort();
                std::int32_t balance_cents() const;
                std::vector<std::string> history() const;
            };
            """,
            """
            class FundStateError : public std::logic_error {
            public:
                explicit FundStateError(const std::string& message) : std::logic_error(message) {}
            };
            class PendingError : public std::runtime_error {
            public:
                explicit PendingError(const std::string& message) : std::runtime_error(message) {}
            };
            class FundError : public std::out_of_range {
            public:
                explicit FundError(const std::string& message) : std::out_of_range(message) {}
            };
            class ClubFund {
            public:
                void open(std::int32_t cents);
                void close();
                void propose(std::string_view purpose, std::int32_t cents);
                void commit();
                void abort();
                std::int32_t balance_cents() const;
                std::vector<std::string> history() const;
            private:
                bool open_ = false;
                std::int32_t balance_ = 0;
                bool pending_ = false;
                std::string purpose_;
                std::int32_t amount_ = 0;
                std::vector<std::string> history_;
            };
            """,
            """
            void ClubFund::open(std::int32_t cents) {
                if (open_) throw FundStateError("fund already open");
                if (cents <= 0) throw FundStateError("opening balance must be positive");
                open_ = true;
                balance_ = cents;
                history_.clear();
            }
            void ClubFund::close() {
                if (!open_) throw FundStateError("fund is closed");
                if (pending_) throw FundStateError("proposal still pending");
                open_ = false;
            }
            void ClubFund::propose(std::string_view purpose, std::int32_t cents) {
                if (!open_) throw FundStateError("fund is closed");
                if (purpose.empty()) throw FundStateError("purpose required");
                if (cents <= 0) throw FundStateError("amount must be positive");
                if (pending_) throw PendingError("a proposal is already pending");
                pending_ = true;
                purpose_ = std::string(purpose);
                amount_ = cents;
            }
            void ClubFund::commit() {
                if (!open_) throw FundStateError("fund is closed");
                if (!pending_) throw PendingError("nothing staged");
                if (amount_ > balance_) {
                    history_.push_back("rejected:" + purpose_ + ":" + std::to_string(amount_));
                    pending_ = false;
                    throw FundError("spend exceeds balance");
                }
                balance_ -= amount_;
                history_.push_back("spend:" + purpose_ + ":" + std::to_string(amount_));
                pending_ = false;
            }
            void ClubFund::abort() {
                if (!open_) throw FundStateError("fund is closed");
                if (!pending_) throw PendingError("nothing staged");
                history_.push_back("aborted:" + purpose_);
                pending_ = false;
            }
            std::int32_t ClubFund::balance_cents() const { return balance_; }
            std::vector<std::string> ClubFund::history() const { return history_; }
            """,
            """
            void ClubFund::open(std::int32_t cents) {
                if (open_) throw FundStateError("fund already open");
                if (cents <= 0) throw FundStateError("opening balance must be positive");
                open_ = true;
                balance_ = cents;
                history_.clear();
            }
            void ClubFund::close() {
                if (!open_) throw FundStateError("fund is closed");
                if (pending_) throw FundStateError("proposal still pending");
                open_ = false;
            }
            void ClubFund::propose(std::string_view purpose, std::int32_t cents) {
                if (!open_) throw FundStateError("fund is closed");
                if (purpose.empty()) throw FundStateError("purpose required");
                if (cents <= 0) throw FundStateError("amount must be positive");
                if (pending_) throw PendingError("a proposal is already pending");
                pending_ = true;
                purpose_ = std::string(purpose);
                amount_ = cents;
            }
            void ClubFund::commit() {
                if (!open_) throw FundStateError("fund is closed");
                if (!pending_) throw PendingError("nothing staged");
                balance_ -= amount_;
                history_.push_back("spend:" + purpose_ + ":" + std::to_string(amount_));
                pending_ = false;
            }
            void ClubFund::abort() {
                if (!open_) throw FundStateError("fund is closed");
                if (!pending_) throw PendingError("nothing staged");
                history_.push_back("aborted:" + purpose_);
                pending_ = false;
            }
            std::int32_t ClubFund::balance_cents() const { return balance_; }
            std::vector<std::string> ClubFund::history() const { return history_; }
            """,
            """
            ClubFund fund;
            fund.open(5000);
            fund.propose("filters", 1200);
            fund.commit();
            if (fund.balance_cents() != 3800) return 1;
            if (fund.history() != std::vector<std::string>{"spend:filters:1200"}) return 2;
            return 0;
            """,
            """
            ClubFund fund;
            bool threw = false;
            try { fund.commit(); } catch (const FundStateError&) { threw = true; }
            if (!threw) return 1;
            fund.open(1000);
            fund.propose("pump", 400);
            threw = false;
            try { fund.propose("food", 100); } catch (const PendingError&) { threw = true; }
            if (!threw) return 2;
            fund.abort();
            if (fund.history() != std::vector<std::string>{"aborted:pump"}) return 3;
            fund.propose("reef", 2000);
            threw = false;
            try { fund.commit(); } catch (const FundError&) { threw = true; }
            if (!threw) return 4;
            if (fund.balance_cents() != 1000) return 5;
            if (fund.history() != std::vector<std::string>{"aborted:pump", "rejected:reef:2000"}) return 6;
            fund.propose("food", 100);
            threw = false;
            try { fund.close(); } catch (const FundStateError&) { threw = true; }
            if (!threw) return 7;
            fund.commit();
            fund.close();
            threw = false;
            try { fund.propose("food", 100); } catch (const FundStateError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "explicit two-phase commit with abort and rejected-commit accounting",
            "partial application or silent staging loss on insufficient funds",
            "double proposals, aborts, insufficient commits with unchanged balance and rejection history, closes while pending, and closed-fund operations",
            "transactional staging, commit, and abort as first-class lifecycle",
            "journal, rollback, and two-phase commit lifecycle",
            project_support=True,
        ),
        c(
            "f26acc-robot-energy-budget",
            "Robot energy budget",
            "robot_energy",
            """
            class BootError : public std::logic_error {
            public:
                explicit BootError(const std::string& message) : std::logic_error(message) {}
            };
            class ReserveError : public std::out_of_range {
            public:
                explicit ReserveError(const std::string& message) : std::out_of_range(message) {}
            };
            class ShutdownError : public std::runtime_error {
            public:
                explicit ShutdownError(const std::string& message) : std::runtime_error(message) {}
            };
            class EnergyBudget {
            public:
                void boot(std::int32_t units);
                void shutdown();
                void reserve(std::int32_t units);
                void release();
                void consume(std::int32_t units);
                std::int32_t available() const;
                std::int32_t reserved() const;
            };
            """,
            """
            class BootError : public std::logic_error {
            public:
                explicit BootError(const std::string& message) : std::logic_error(message) {}
            };
            class ReserveError : public std::out_of_range {
            public:
                explicit ReserveError(const std::string& message) : std::out_of_range(message) {}
            };
            class ShutdownError : public std::runtime_error {
            public:
                explicit ShutdownError(const std::string& message) : std::runtime_error(message) {}
            };
            class EnergyBudget {
            public:
                void boot(std::int32_t units);
                void shutdown();
                void reserve(std::int32_t units);
                void release();
                void consume(std::int32_t units);
                std::int32_t available() const;
                std::int32_t reserved() const;
            private:
                bool booted_ = false;
                std::int32_t available_ = 0;
                std::int32_t reserved_ = 0;
            };
            """,
            """
            void EnergyBudget::boot(std::int32_t units) {
                if (booted_) throw BootError("system already booted");
                if (units <= 0) throw BootError("boot units must be positive");
                booted_ = true;
                available_ = units;
                reserved_ = 0;
            }
            void EnergyBudget::shutdown() {
                if (!booted_) throw BootError("system not booted");
                if (reserved_ > 0) throw ShutdownError("reservation still live");
                booted_ = false;
            }
            void EnergyBudget::reserve(std::int32_t units) {
                if (!booted_) throw BootError("system not booted");
                if (units <= 0) throw ReserveError("units must be positive");
                if (reserved_ > 0) throw ReserveError("reservation already live");
                if (units > available_) throw ReserveError("reserve exceeds available");
                available_ -= units;
                reserved_ = units;
            }
            void EnergyBudget::release() {
                if (!booted_) throw BootError("system not booted");
                if (reserved_ == 0) throw ReserveError("no reservation live");
                available_ += reserved_;
                reserved_ = 0;
            }
            void EnergyBudget::consume(std::int32_t units) {
                if (!booted_) throw BootError("system not booted");
                if (units <= 0) throw ReserveError("units must be positive");
                if (units > available_) throw ReserveError("consume exceeds available");
                available_ -= units;
            }
            std::int32_t EnergyBudget::available() const { return available_; }
            std::int32_t EnergyBudget::reserved() const { return reserved_; }
            """,
            """
            void EnergyBudget::boot(std::int32_t units) {
                if (booted_) throw BootError("system already booted");
                if (units <= 0) throw BootError("boot units must be positive");
                booted_ = true;
                available_ = units;
                reserved_ = 0;
            }
            void EnergyBudget::shutdown() {
                if (!booted_) throw BootError("system not booted");
                if (reserved_ > 0) throw ShutdownError("reservation still live");
                booted_ = false;
            }
            void EnergyBudget::reserve(std::int32_t units) {
                if (!booted_) throw BootError("system not booted");
                if (units <= 0) throw ReserveError("units must be positive");
                if (reserved_ > 0) throw ReserveError("reservation already live");
                const std::int32_t granted = units > available_ ? available_ : units;
                available_ -= granted;
                reserved_ = granted;
            }
            void EnergyBudget::release() {
                if (!booted_) throw BootError("system not booted");
                if (reserved_ == 0) throw ReserveError("no reservation live");
                available_ += reserved_;
                reserved_ = 0;
            }
            void EnergyBudget::consume(std::int32_t units) {
                if (!booted_) throw BootError("system not booted");
                if (units <= 0) throw ReserveError("units must be positive");
                if (units > available_) throw ReserveError("consume exceeds available");
                available_ -= units;
            }
            std::int32_t EnergyBudget::available() const { return available_; }
            std::int32_t EnergyBudget::reserved() const { return reserved_; }
            """,
            """
            EnergyBudget budget;
            budget.boot(100);
            budget.reserve(30);
            if (budget.available() != 70) return 1;
            if (budget.reserved() != 30) return 2;
            budget.release();
            if (budget.available() != 100) return 3;
            budget.consume(40);
            if (budget.available() != 60) return 4;
            return 0;
            """,
            """
            EnergyBudget budget;
            bool threw = false;
            try { budget.reserve(10); } catch (const BootError&) { threw = true; }
            if (!threw) return 1;
            budget.boot(50);
            threw = false;
            try { budget.reserve(60); } catch (const ReserveError&) { threw = true; }
            if (!threw) return 2;
            if (budget.available() != 50) return 3;
            budget.reserve(20);
            threw = false;
            try { budget.reserve(5); } catch (const ReserveError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { budget.shutdown(); } catch (const ShutdownError&) { threw = true; }
            if (!threw) return 5;
            budget.release();
            budget.consume(50);
            threw = false;
            try { budget.consume(1); } catch (const ReserveError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { budget.boot(10); } catch (const BootError&) { threw = true; }
            if (!threw) return 7;
            budget.shutdown();
            threw = false;
            try { budget.consume(1); } catch (const BootError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "reserve/release two-phase energy accounting with a shutdown invariant",
            "reservation clamping or shutdown with a live reservation",
            "reserves before boot, over-reserves with unchanged availability, double reserves, shutdown with a reservation, exact consumption, and double boots",
            "reservation semantics with a cleanup invariant",
            "journal, rollback, and two-phase commit lifecycle",
        ),
        c(
            "f26acc-board-game-voucher",
            "Board game voucher",
            "game_voucher",
            """
            class VoucherError : public std::out_of_range {
            public:
                explicit VoucherError(const std::string& message) : std::out_of_range(message) {}
            };
            class IssueError : public std::invalid_argument {
            public:
                explicit IssueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class Voucher {
            public:
                static Voucher issue(std::int32_t credits);
                Voucher redeem(std::int32_t credits) const;
                Voucher expire() const;
                bool live() const;
                std::int32_t credits() const;
                friend bool operator==(const Voucher&, const Voucher&);
                friend bool operator<(const Voucher&, const Voucher&);
            };
            """,
            """
            class VoucherError : public std::out_of_range {
            public:
                explicit VoucherError(const std::string& message) : std::out_of_range(message) {}
            };
            class IssueError : public std::invalid_argument {
            public:
                explicit IssueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class Voucher {
            public:
                static Voucher issue(std::int32_t credits);
                Voucher redeem(std::int32_t credits) const;
                Voucher expire() const;
                bool live() const;
                std::int32_t credits() const;
                friend bool operator==(const Voucher&, const Voucher&);
                friend bool operator<(const Voucher&, const Voucher&);
            private:
                Voucher(std::int32_t credits, bool live) : credits_(credits), live_(live) {}
                std::int32_t credits_;
                bool live_;
            };
            """,
            """
            Voucher Voucher::issue(std::int32_t credits) {
                if (credits <= 0) throw IssueError("credits must be positive");
                return Voucher(credits, true);
            }
            Voucher Voucher::redeem(std::int32_t credits) const {
                if (!live_) throw VoucherError("voucher expired");
                if (credits <= 0) throw VoucherError("redeem amount must be positive");
                if (credits > credits_) throw VoucherError("redeem exceeds balance");
                return Voucher(credits_ - credits, true);
            }
            Voucher Voucher::expire() const { return Voucher(credits_, false); }
            bool Voucher::live() const { return live_; }
            std::int32_t Voucher::credits() const { return credits_; }
            bool operator==(const Voucher& a, const Voucher& b) {
                return a.credits_ == b.credits_ && a.live_ == b.live_;
            }
            bool operator<(const Voucher& a, const Voucher& b) {
                if (a.credits_ != b.credits_) return a.credits_ < b.credits_;
                return a.live_ < b.live_;
            }
            """,
            """
            Voucher Voucher::issue(std::int32_t credits) {
                if (credits <= 0) throw IssueError("credits must be positive");
                return Voucher(credits, true);
            }
            Voucher Voucher::redeem(std::int32_t credits) const {
                if (!live_) throw VoucherError("voucher expired");
                if (credits <= 0) throw VoucherError("redeem amount must be positive");
                return Voucher(credits_ - credits, true);
            }
            Voucher Voucher::expire() const { return Voucher(credits_, false); }
            bool Voucher::live() const { return live_; }
            std::int32_t Voucher::credits() const { return credits_; }
            bool operator==(const Voucher& a, const Voucher& b) {
                return a.credits_ == b.credits_ && a.live_ == b.live_;
            }
            bool operator<(const Voucher& a, const Voucher& b) {
                if (a.credits_ != b.credits_) return a.credits_ < b.credits_;
                return a.live_ < b.live_;
            }
            """,
            """
            Voucher voucher = Voucher::issue(10);
            Voucher spent = voucher.redeem(4);
            if (voucher.credits() != 10) return 1;
            if (spent.credits() != 6) return 2;
            if (!(Voucher::issue(6) == spent)) return 3;
            if (!(spent < voucher)) return 4;
            return 0;
            """,
            """
            bool threw = false;
            try { Voucher::issue(0); } catch (const IssueError&) { threw = true; }
            if (!threw) return 1;
            Voucher voucher = Voucher::issue(5);
            threw = false;
            try { voucher.redeem(6); } catch (const VoucherError&) { threw = true; }
            if (!threw) return 2;
            if (voucher.credits() != 5) return 3;
            Voucher dead = voucher.expire();
            if (dead.live()) return 4;
            threw = false;
            try { dead.redeem(1); } catch (const VoucherError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { voucher.redeem(0); } catch (const VoucherError&) { threw = true; }
            if (!threw) return 6;
            Voucher rest = voucher.redeem(5);
            if (rest.credits() != 0) return 7;
            if (voucher < rest) return 8;
            return 0;
            """,
            "immutable transitions where every change produces a new voucher value",
            "redeeming past the balance into negative credits or through expiry",
            "over-balance redeems with an unchanged original, expired redeems, non-positive amounts, equality, and ordering",
            "value-semantics lifecycle transitions with operators",
            "immutable value type with transition operators",
        ),
        c(
            "f26acc-gift-token-wallet",
            "Gift token wallet",
            "gift_token",
            """
            class TokenError : public std::logic_error {
            public:
                explicit TokenError(const std::string& message) : std::logic_error(message) {}
            };
            class MergeError : public std::runtime_error {
            public:
                explicit MergeError(const std::string& message) : std::runtime_error(message) {}
            };
            class Token {
            public:
                static Token mint(std::int32_t value);
                Token activate() const;
                Token spend(std::int32_t value) const;
                Token merge(const Token& other) const;
                bool active() const;
                std::int32_t value() const;
                friend bool operator==(const Token&, const Token&);
                friend bool operator!=(const Token&, const Token&);
            };
            """,
            """
            class TokenError : public std::logic_error {
            public:
                explicit TokenError(const std::string& message) : std::logic_error(message) {}
            };
            class MergeError : public std::runtime_error {
            public:
                explicit MergeError(const std::string& message) : std::runtime_error(message) {}
            };
            class Token {
            public:
                static Token mint(std::int32_t value);
                Token activate() const;
                Token spend(std::int32_t value) const;
                Token merge(const Token& other) const;
                bool active() const;
                std::int32_t value() const;
                friend bool operator==(const Token&, const Token&);
                friend bool operator!=(const Token&, const Token&);
            private:
                Token(std::int32_t value, bool active) : value_(value), active_(active) {}
                std::int32_t value_;
                bool active_;
            };
            """,
            """
            Token Token::mint(std::int32_t value) {
                if (value <= 0) throw TokenError("mint value must be positive");
                return Token(value, false);
            }
            Token Token::activate() const {
                if (active_) throw TokenError("token already active");
                return Token(value_, true);
            }
            Token Token::spend(std::int32_t value) const {
                if (!active_) throw TokenError("token is not active");
                if (value <= 0) throw TokenError("spend must be positive");
                if (value > value_) throw TokenError("spend exceeds value");
                return Token(value_ - value, true);
            }
            Token Token::merge(const Token& other) const {
                if (!active_ || !other.active_) throw MergeError("both tokens must be active");
                return Token(value_ + other.value_, true);
            }
            bool Token::active() const { return active_; }
            std::int32_t Token::value() const { return value_; }
            bool operator==(const Token& a, const Token& b) {
                return a.value_ == b.value_ && a.active_ == b.active_;
            }
            bool operator!=(const Token& a, const Token& b) { return !(a == b); }
            """,
            """
            Token Token::mint(std::int32_t value) {
                if (value <= 0) throw TokenError("mint value must be positive");
                return Token(value, false);
            }
            Token Token::activate() const {
                if (active_) throw TokenError("token already active");
                return Token(value_, true);
            }
            Token Token::spend(std::int32_t value) const {
                if (value <= 0) throw TokenError("spend must be positive");
                if (value > value_) throw TokenError("spend exceeds value");
                return Token(value_ - value, active_);
            }
            Token Token::merge(const Token& other) const {
                if (!active_ || !other.active_) throw MergeError("both tokens must be active");
                return Token(value_ + other.value_, true);
            }
            bool Token::active() const { return active_; }
            std::int32_t Token::value() const { return value_; }
            bool operator==(const Token& a, const Token& b) {
                return a.value_ == b.value_ && a.active_ == b.active_;
            }
            bool operator!=(const Token& a, const Token& b) { return !(a == b); }
            """,
            """
            Token token = Token::mint(8);
            if (token.active()) return 1;
            Token live = token.activate();
            Token spent = live.spend(3);
            if (spent.value() != 5) return 2;
            Token merged = spent.merge(Token::mint(1).activate());
            if (merged.value() != 6) return 3;
            if (!(merged != token)) return 4;
            return 0;
            """,
            """
            bool threw = false;
            try { Token::mint(0); } catch (const TokenError&) { threw = true; }
            if (!threw) return 1;
            Token token = Token::mint(4);
            threw = false;
            try { token.spend(1); } catch (const TokenError&) { threw = true; }
            if (!threw) return 2;
            Token live = token.activate();
            threw = false;
            try { live.activate(); } catch (const TokenError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { live.merge(Token::mint(2)); } catch (const MergeError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { live.spend(5); } catch (const TokenError&) { threw = true; }
            if (!threw) return 5;
            if (live.value() != 4) return 6;
            Token both = live.merge(Token::mint(1).activate());
            if (!(both == Token::mint(5).activate())) return 7;
            return 0;
            """,
            "activation-gated immutable token with a combining operation",
            "spending inactive tokens or merging inactive inputs",
            "spends before activation, double activation, inactive merges, overspending with an unchanged original, and equality",
            "gated value transitions distinct from class-mutation roots",
            "immutable value type with transition operators",
        ),
        c(
            "f26acc-metro-day-ticket",
            "Metro day ticket",
            "metro_ticket",
            """
            class DateError : public std::invalid_argument {
            public:
                explicit DateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class VoidError : public std::logic_error {
            public:
                explicit VoidError(const std::string& message) : std::logic_error(message) {}
            };
            class DayTicket {
            public:
                static DayTicket valid_for(std::int32_t day);
                DayTicket advance(std::int32_t days) const;
                bool usable_on(std::int32_t day) const;
                DayTicket void_ticket() const;
                bool live() const;
                friend bool operator==(const DayTicket&, const DayTicket&);
                friend bool operator<(const DayTicket&, const DayTicket&);
            };
            """,
            """
            class DateError : public std::invalid_argument {
            public:
                explicit DateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class VoidError : public std::logic_error {
            public:
                explicit VoidError(const std::string& message) : std::logic_error(message) {}
            };
            class DayTicket {
            public:
                static DayTicket valid_for(std::int32_t day);
                DayTicket advance(std::int32_t days) const;
                bool usable_on(std::int32_t day) const;
                DayTicket void_ticket() const;
                bool live() const;
                friend bool operator==(const DayTicket&, const DayTicket&);
                friend bool operator<(const DayTicket&, const DayTicket&);
            private:
                DayTicket(std::int32_t day, bool live) : day_(day), live_(live) {}
                std::int32_t day_;
                bool live_;
            };
            """,
            """
            DayTicket DayTicket::valid_for(std::int32_t day) {
                if (day < 1) throw DateError("day must be positive");
                return DayTicket(day, true);
            }
            DayTicket DayTicket::advance(std::int32_t days) const {
                if (!live_) throw VoidError("ticket is void");
                if (days < 1 || days > 30) throw DateError("advance out of range");
                return DayTicket(day_ + days, true);
            }
            bool DayTicket::usable_on(std::int32_t day) const { return live_ && day == day_; }
            DayTicket DayTicket::void_ticket() const { return DayTicket(day_, false); }
            bool DayTicket::live() const { return live_; }
            bool operator==(const DayTicket& a, const DayTicket& b) {
                return a.day_ == b.day_ && a.live_ == b.live_;
            }
            bool operator<(const DayTicket& a, const DayTicket& b) {
                if (a.day_ != b.day_) return a.day_ < b.day_;
                return a.live_ < b.live_;
            }
            """,
            """
            DayTicket DayTicket::valid_for(std::int32_t day) {
                if (day < 1) throw DateError("day must be positive");
                return DayTicket(day, true);
            }
            DayTicket DayTicket::advance(std::int32_t days) const {
                if (!live_) throw VoidError("ticket is void");
                if (days < 1 || days > 30) throw DateError("advance out of range");
                return DayTicket(day_ + days, true);
            }
            bool DayTicket::usable_on(std::int32_t day) const { return day == day_; }
            DayTicket DayTicket::void_ticket() const { return DayTicket(day_, live_); }
            bool DayTicket::live() const { return live_; }
            bool operator==(const DayTicket& a, const DayTicket& b) {
                return a.day_ == b.day_ && a.live_ == b.live_;
            }
            bool operator<(const DayTicket& a, const DayTicket& b) {
                if (a.day_ != b.day_) return a.day_ < b.day_;
                return a.live_ < b.live_;
            }
            """,
            """
            DayTicket ticket = DayTicket::valid_for(12);
            if (!ticket.usable_on(12)) return 1;
            if (ticket.usable_on(13)) return 2;
            DayTicket later = ticket.advance(3);
            if (!later.usable_on(15)) return 3;
            if (!(ticket < later)) return 4;
            return 0;
            """,
            """
            bool threw = false;
            try { DayTicket::valid_for(0); } catch (const DateError&) { threw = true; }
            if (!threw) return 1;
            DayTicket ticket = DayTicket::valid_for(5);
            threw = false;
            try { ticket.advance(31); } catch (const DateError&) { threw = true; }
            if (!threw) return 2;
            DayTicket dead = ticket.void_ticket();
            if (dead.live()) return 3;
            if (dead.usable_on(5)) return 4;
            threw = false;
            try { dead.advance(1); } catch (const VoidError&) { threw = true; }
            if (!threw) return 5;
            if (!(dead == DayTicket::valid_for(5).void_ticket())) return 6;
            if (!(dead < ticket)) return 7;
            return 0;
            """,
            "date-bound immutable ticket with a void transition and exact-day usability",
            "usable-after-void tickets or arbitrary-day usability",
            "wrong-day usability, advance bounds, voided advances, equality across liveness, and ordering",
            "exact-date lifecycle semantics over values",
            "immutable value type with transition operators",
        ),
        c(
            "f26acc-stamp-booklet",
            "Stamp booklet",
            "stamp_booklet",
            """
            class StampError : public std::out_of_range {
            public:
                explicit StampError(const std::string& message) : std::out_of_range(message) {}
            };
            class IssueError : public std::invalid_argument {
            public:
                explicit IssueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CapError : public std::runtime_error {
            public:
                explicit CapError(const std::string& message) : std::runtime_error(message) {}
            };
            class Booklet {
            public:
                static Booklet of(std::int32_t stamps);
                Booklet use(std::int32_t n) const;
                Booklet combine(const Booklet& other) const;
                std::int32_t remaining() const;
                bool empty() const;
                friend bool operator==(const Booklet&, const Booklet&);
                friend bool operator<(const Booklet&, const Booklet&);
            };
            """,
            """
            class StampError : public std::out_of_range {
            public:
                explicit StampError(const std::string& message) : std::out_of_range(message) {}
            };
            class IssueError : public std::invalid_argument {
            public:
                explicit IssueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CapError : public std::runtime_error {
            public:
                explicit CapError(const std::string& message) : std::runtime_error(message) {}
            };
            class Booklet {
            public:
                static Booklet of(std::int32_t stamps);
                Booklet use(std::int32_t n) const;
                Booklet combine(const Booklet& other) const;
                std::int32_t remaining() const;
                bool empty() const;
                friend bool operator==(const Booklet&, const Booklet&);
                friend bool operator<(const Booklet&, const Booklet&);
            private:
                explicit Booklet(std::int32_t stamps) : stamps_(stamps) {}
                std::int32_t stamps_;
            };
            """,
            """
            Booklet Booklet::of(std::int32_t stamps) {
                if (stamps < 1 || stamps > 100) throw IssueError("booklet size out of range");
                return Booklet(stamps);
            }
            Booklet Booklet::use(std::int32_t n) const {
                if (n <= 0) throw StampError("use count must be positive");
                if (n > stamps_) throw StampError("not enough stamps");
                return Booklet(stamps_ - n);
            }
            Booklet Booklet::combine(const Booklet& other) const {
                if (stamps_ + other.stamps_ > 100) throw CapError("combined booklet too large");
                return Booklet(stamps_ + other.stamps_);
            }
            std::int32_t Booklet::remaining() const { return stamps_; }
            bool Booklet::empty() const { return stamps_ == 0; }
            bool operator==(const Booklet& a, const Booklet& b) { return a.stamps_ == b.stamps_; }
            bool operator<(const Booklet& a, const Booklet& b) { return a.stamps_ < b.stamps_; }
            """,
            """
            Booklet Booklet::of(std::int32_t stamps) {
                if (stamps < 1 || stamps > 100) throw IssueError("booklet size out of range");
                return Booklet(stamps);
            }
            Booklet Booklet::use(std::int32_t n) const {
                if (n <= 0) throw StampError("use count must be positive");
                return Booklet(n > stamps_ ? 0 : stamps_ - n);
            }
            Booklet Booklet::combine(const Booklet& other) const {
                if (stamps_ + other.stamps_ > 100) throw CapError("combined booklet too large");
                return Booklet(stamps_ + other.stamps_);
            }
            std::int32_t Booklet::remaining() const { return stamps_; }
            bool Booklet::empty() const { return stamps_ == 0; }
            bool operator==(const Booklet& a, const Booklet& b) { return a.stamps_ == b.stamps_; }
            bool operator<(const Booklet& a, const Booklet& b) { return a.stamps_ < b.stamps_; }
            """,
            """
            Booklet booklet = Booklet::of(10);
            Booklet used = booklet.use(4);
            if (booklet.remaining() != 10) return 1;
            if (used.remaining() != 6) return 2;
            Booklet joined = used.combine(Booklet::of(2));
            if (joined.remaining() != 8) return 3;
            if (!(used < booklet)) return 4;
            return 0;
            """,
            """
            bool threw = false;
            try { Booklet::of(0); } catch (const IssueError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { Booklet::of(101); } catch (const IssueError&) { threw = true; }
            if (!threw) return 2;
            Booklet booklet = Booklet::of(3);
            threw = false;
            try { booklet.use(4); } catch (const StampError&) { threw = true; }
            if (!threw) return 3;
            if (booklet.remaining() != 3) return 4;
            threw = false;
            try { Booklet::of(60).combine(Booklet::of(50)); } catch (const CapError&) { threw = true; }
            if (!threw) return 5;
            Booklet empty = booklet.use(3);
            if (!empty.empty()) return 6;
            threw = false;
            try { empty.use(1); } catch (const StampError&) { threw = true; }
            if (!threw) return 7;
            if (!(empty == Booklet::of(1).use(1))) return 8;
            return 0;
            """,
            "consumable immutable booklet with a capped combining operation",
            "uses that floor at zero or combines past the cap",
            "over-use with an unchanged original, issue bounds, capped combines, exact empties, and ordering",
            "capped-combine value semantics",
            "immutable value type with transition operators",
        ),
        c(
            "f26acc-ride-punch-card",
            "Ride punch card",
            "punch_card",
            """
            class PunchError : public std::logic_error {
            public:
                explicit PunchError(const std::string& message) : std::logic_error(message) {}
            };
            class IssueError : public std::invalid_argument {
            public:
                explicit IssueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PunchCard {
            public:
                static PunchCard issue(std::int32_t punches);
                PunchCard punch() const;
                PunchCard void_card() const;
                std::int32_t used() const;
                std::int32_t left() const;
                bool live() const;
                friend bool operator==(const PunchCard&, const PunchCard&);
            };
            """,
            """
            class PunchError : public std::logic_error {
            public:
                explicit PunchError(const std::string& message) : std::logic_error(message) {}
            };
            class IssueError : public std::invalid_argument {
            public:
                explicit IssueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PunchCard {
            public:
                static PunchCard issue(std::int32_t punches);
                PunchCard punch() const;
                PunchCard void_card() const;
                std::int32_t used() const;
                std::int32_t left() const;
                bool live() const;
                friend bool operator==(const PunchCard&, const PunchCard&);
            private:
                PunchCard(std::int32_t used, std::int32_t total, bool live) : used_(used), total_(total), live_(live) {}
                std::int32_t used_;
                std::int32_t total_;
                bool live_;
            };
            """,
            """
            PunchCard PunchCard::issue(std::int32_t punches) {
                if (punches < 1 || punches > 20) throw IssueError("punch count out of range");
                return PunchCard(0, punches, true);
            }
            PunchCard PunchCard::punch() const {
                if (!live_) throw PunchError("card is void");
                if (used_ >= total_) throw PunchError("no punches left");
                return PunchCard(used_ + 1, total_, true);
            }
            PunchCard PunchCard::void_card() const { return PunchCard(used_, total_, false); }
            std::int32_t PunchCard::used() const { return used_; }
            std::int32_t PunchCard::left() const { return live_ ? total_ - used_ : 0; }
            bool PunchCard::live() const { return live_; }
            bool operator==(const PunchCard& a, const PunchCard& b) {
                return a.used_ == b.used_ && a.total_ == b.total_ && a.live_ == b.live_;
            }
            """,
            """
            PunchCard PunchCard::issue(std::int32_t punches) {
                if (punches < 1 || punches > 20) throw IssueError("punch count out of range");
                return PunchCard(0, punches, true);
            }
            PunchCard PunchCard::punch() const {
                if (used_ >= total_) throw PunchError("no punches left");
                return PunchCard(used_ + 1, total_, live_);
            }
            PunchCard PunchCard::void_card() const { return PunchCard(used_, total_, false); }
            std::int32_t PunchCard::used() const { return used_; }
            std::int32_t PunchCard::left() const { return live_ ? total_ - used_ : 0; }
            bool PunchCard::live() const { return live_; }
            bool operator==(const PunchCard& a, const PunchCard& b) {
                return a.used_ == b.used_ && a.total_ == b.total_ && a.live_ == b.live_;
            }
            """,
            """
            PunchCard card = PunchCard::issue(2);
            PunchCard once = card.punch();
            if (once.used() != 1) return 1;
            if (once.left() != 1) return 2;
            if (card.used() != 0) return 3;
            return 0;
            """,
            """
            bool threw = false;
            try { PunchCard::issue(21); } catch (const IssueError&) { threw = true; }
            if (!threw) return 1;
            PunchCard card = PunchCard::issue(1);
            PunchCard done = card.punch();
            threw = false;
            try { done.punch(); } catch (const PunchError&) { threw = true; }
            if (!threw) return 2;
            PunchCard dead = card.void_card();
            if (dead.live()) return 3;
            if (dead.left() != 0) return 4;
            threw = false;
            try { dead.punch(); } catch (const PunchError&) { threw = true; }
            if (!threw) return 5;
            if (!(dead == PunchCard::issue(1).void_card())) return 6;
            if (card.punch().used() != 1) return 7;
            return 0;
            """,
            "countdown immutable card with exhaustion and void boundaries",
            "punching void or exhausted cards",
            "issue bounds, exact exhaustion, punches after exhaustion, voided punches, equality, and independent originals",
            "countdown lifecycle over immutable values",
            "immutable value type with transition operators",
        ),
        c(
            "f26acc-museum-ticket-value",
            "Museum ticket value",
            "museum_ticket",
            """
            class WingError : public std::invalid_argument {
            public:
                explicit WingError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SlotError : public std::out_of_range {
            public:
                explicit SlotError(const std::string& message) : std::out_of_range(message) {}
            };
            class ReissueError : public std::logic_error {
            public:
                explicit ReissueError(const std::string& message) : std::logic_error(message) {}
            };
            class GalleryTicket {
            public:
                static GalleryTicket admit(std::string_view wing, std::int32_t slot);
                GalleryTicket reissue(std::string_view wing) const;
                GalleryTicket revoke() const;
                std::string label() const;
                bool valid() const;
                friend bool operator==(const GalleryTicket&, const GalleryTicket&);
            };
            """,
            """
            class WingError : public std::invalid_argument {
            public:
                explicit WingError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SlotError : public std::out_of_range {
            public:
                explicit SlotError(const std::string& message) : std::out_of_range(message) {}
            };
            class ReissueError : public std::logic_error {
            public:
                explicit ReissueError(const std::string& message) : std::logic_error(message) {}
            };
            class GalleryTicket {
            public:
                static GalleryTicket admit(std::string_view wing, std::int32_t slot);
                GalleryTicket reissue(std::string_view wing) const;
                GalleryTicket revoke() const;
                std::string label() const;
                bool valid() const;
                friend bool operator==(const GalleryTicket&, const GalleryTicket&);
            private:
                GalleryTicket(std::string wing, std::int32_t slot, bool valid)
                    : wing_(std::move(wing)), slot_(slot), valid_(valid) {}
                std::string wing_;
                std::int32_t slot_;
                bool valid_;
            };
            """,
            """
            GalleryTicket GalleryTicket::admit(std::string_view wing, std::int32_t slot) {
                if (wing.empty()) throw WingError("wing name required");
                if (slot < 0 || slot > 999) throw SlotError("slot out of range");
                return GalleryTicket(std::string(wing), slot, true);
            }
            GalleryTicket GalleryTicket::reissue(std::string_view wing) const {
                if (!valid_) throw ReissueError("ticket revoked");
                if (wing.empty()) throw WingError("wing name required");
                return GalleryTicket(std::string(wing), slot_, true);
            }
            GalleryTicket GalleryTicket::revoke() const { return GalleryTicket(wing_, slot_, false); }
            std::string GalleryTicket::label() const {
                if (!valid_) return "revoked";
                return wing_ + "#" + std::to_string(slot_);
            }
            bool GalleryTicket::valid() const { return valid_; }
            bool operator==(const GalleryTicket& a, const GalleryTicket& b) {
                return a.wing_ == b.wing_ && a.slot_ == b.slot_ && a.valid_ == b.valid_;
            }
            """,
            """
            GalleryTicket GalleryTicket::admit(std::string_view wing, std::int32_t slot) {
                if (wing.empty()) throw WingError("wing name required");
                if (slot < 0 || slot > 999) throw SlotError("slot out of range");
                return GalleryTicket(std::string(wing), slot, true);
            }
            GalleryTicket GalleryTicket::reissue(std::string_view wing) const {
                if (wing.empty()) throw WingError("wing name required");
                return GalleryTicket(std::string(wing), slot_, true);
            }
            GalleryTicket GalleryTicket::revoke() const { return GalleryTicket(wing_, slot_, false); }
            std::string GalleryTicket::label() const {
                if (!valid_) return "revoked";
                return wing_ + "#" + std::to_string(slot_);
            }
            bool GalleryTicket::valid() const { return valid_; }
            bool operator==(const GalleryTicket& a, const GalleryTicket& b) {
                return a.wing_ == b.wing_ && a.slot_ == b.slot_ && a.valid_ == b.valid_;
            }
            """,
            """
            GalleryTicket ticket = GalleryTicket::admit("north", 42);
            if (ticket.label() != "north#42") return 1;
            GalleryTicket moved = ticket.reissue("south");
            if (moved.label() != "south#42") return 2;
            if (!(GalleryTicket::admit("south", 42) == moved)) return 3;
            return 0;
            """,
            """
            bool threw = false;
            try { GalleryTicket::admit("", 1); } catch (const WingError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { GalleryTicket::admit("east", 1000); } catch (const SlotError&) { threw = true; }
            if (!threw) return 2;
            GalleryTicket ticket = GalleryTicket::admit("east", 7);
            GalleryTicket dead = ticket.revoke();
            if (dead.valid()) return 3;
            if (dead.label() != "revoked") return 4;
            threw = false;
            try { dead.reissue("west"); } catch (const ReissueError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { ticket.reissue(""); } catch (const WingError&) { threw = true; }
            if (!threw) return 6;
            if (ticket.reissue("west").label() != "west#7") return 7;
            return 0;
            """,
            "immutable labelled ticket with reissue and revoke transitions and exact label rendering",
            "reissue of revoked tickets or labels that keep rendering after revocation",
            "empty wings, slot bounds, reissue correctness, revoked labels, revoked reissues, and equality",
            "exact string output on value lifecycle transitions",
            "immutable value type with transition operators",
        ),
        c(
            "f26acc-theater-subscription-tier",
            "Theater subscription tier",
            "theater_tier",
            """
            class TierError : public std::out_of_range {
            public:
                explicit TierError(const std::string& message) : std::out_of_range(message) {}
            };
            class SubError : public std::logic_error {
            public:
                explicit SubError(const std::string& message) : std::logic_error(message) {}
            };
            struct TierPolicy {
                std::int32_t max_guests;
                std::int32_t events_per_season;
            };
            class Sub {
            public:
                static std::optional<Sub> create(TierPolicy policy);
                void activate();
                void cancel();
                void attend(std::int32_t guests);
                std::int32_t events_attended() const;
                std::int32_t guests_total() const;
            };
            """,
            """
            class TierError : public std::out_of_range {
            public:
                explicit TierError(const std::string& message) : std::out_of_range(message) {}
            };
            class SubError : public std::logic_error {
            public:
                explicit SubError(const std::string& message) : std::logic_error(message) {}
            };
            struct TierPolicy {
                std::int32_t max_guests;
                std::int32_t events_per_season;
            };
            class Sub {
            public:
                static std::optional<Sub> create(TierPolicy policy);
                void activate();
                void cancel();
                void attend(std::int32_t guests);
                std::int32_t events_attended() const;
                std::int32_t guests_total() const;
            private:
                explicit Sub(TierPolicy policy) : policy_(policy) {}
                TierPolicy policy_;
                bool active_ = false;
                std::int32_t events_ = 0;
                std::int32_t guests_ = 0;
            };
            """,
            """
            std::optional<Sub> Sub::create(TierPolicy policy) {
                if (policy.max_guests < 1 || policy.max_guests > 4) return std::nullopt;
                if (policy.events_per_season < 1 || policy.events_per_season > 30) return std::nullopt;
                return Sub(policy);
            }
            void Sub::activate() {
                if (active_) throw SubError("subscription already active");
                active_ = true;
            }
            void Sub::cancel() {
                if (!active_) throw SubError("subscription not active");
                active_ = false;
            }
            void Sub::attend(std::int32_t guests) {
                if (!active_) throw SubError("subscription not active");
                if (guests < 1 || guests > policy_.max_guests) throw TierError("party outside tier");
                if (events_ >= policy_.events_per_season) throw TierError("season events exhausted");
                ++events_;
                guests_ += guests;
            }
            std::int32_t Sub::events_attended() const { return events_; }
            std::int32_t Sub::guests_total() const { return guests_; }
            """,
            """
            std::optional<Sub> Sub::create(TierPolicy policy) {
                if (policy.max_guests < 1 || policy.max_guests > 4) return std::nullopt;
                if (policy.events_per_season < 1 || policy.events_per_season > 30) return std::nullopt;
                return Sub(policy);
            }
            void Sub::activate() {
                if (active_) throw SubError("subscription already active");
                active_ = true;
            }
            void Sub::cancel() {
                if (!active_) throw SubError("subscription not active");
                active_ = false;
            }
            void Sub::attend(std::int32_t guests) {
                if (!active_) throw SubError("subscription not active");
                if (guests < 1) throw TierError("party outside tier");
                if (events_ >= policy_.events_per_season) throw TierError("season events exhausted");
                ++events_;
                guests_ += guests;
            }
            std::int32_t Sub::events_attended() const { return events_; }
            std::int32_t Sub::guests_total() const { return guests_; }
            """,
            """
            auto sub = Sub::create(TierPolicy{2, 3});
            if (!sub.has_value()) return 1;
            sub->activate();
            sub->attend(2);
            if (sub->events_attended() != 1) return 2;
            if (sub->guests_total() != 2) return 3;
            return 0;
            """,
            """
            if (Sub::create(TierPolicy{0, 5}).has_value()) return 1;
            if (Sub::create(TierPolicy{5, 5}).has_value()) return 2;
            if (Sub::create(TierPolicy{2, 31}).has_value()) return 3;
            auto sub = Sub::create(TierPolicy{1, 2});
            if (!sub.has_value()) return 4;
            bool threw = false;
            try { sub->attend(1); } catch (const SubError&) { threw = true; }
            if (!threw) return 5;
            sub->activate();
            threw = false;
            try { sub->attend(2); } catch (const TierError&) { threw = true; }
            if (!threw) return 6;
            sub->attend(1);
            sub->attend(1);
            threw = false;
            try { sub->attend(1); } catch (const TierError&) { threw = true; }
            if (!threw) return 7;
            if (sub->events_attended() != 2) return 8;
            if (sub->guests_total() != 2) return 9;
            sub->cancel();
            threw = false;
            try { sub->attend(1); } catch (const SubError&) { threw = true; }
            if (!threw) return 10;
            return 0;
            """,
            "constructor-injected tier policy validated once and enforced per attendance call",
            "attendance that ignores the injected guest policy",
            "invalid policies, attendance before activation, guest and event limits with unchanged totals, cancellation, and post-cancel attendance",
            "injected-policy lifecycle enforcement",
            "injected policy object or interleaved-stream service",
        ),
        c(
            "f26acc-sports-league-roster",
            "Sports league roster",
            "league_roster",
            """
            class RegistrationError : public std::logic_error {
            public:
                explicit RegistrationError(const std::string& message) : std::logic_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CapacityError : public std::out_of_range {
            public:
                explicit CapacityError(const std::string& message) : std::out_of_range(message) {}
            };
            class GuestError : public std::runtime_error {
            public:
                explicit GuestError(const std::string& message) : std::runtime_error(message) {}
            };
            struct RosterPolicy {
                std::int32_t max_players;
                bool allow_guests;
            };
            class Team {
            public:
                static std::optional<Team> create(RosterPolicy policy);
                void open_registration();
                void close_registration();
                void enroll(std::string_view player);
                void drop(std::string_view player);
                std::size_t size() const;
                bool enrolled(std::string_view player) const;
            };
            """,
            """
            class RegistrationError : public std::logic_error {
            public:
                explicit RegistrationError(const std::string& message) : std::logic_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CapacityError : public std::out_of_range {
            public:
                explicit CapacityError(const std::string& message) : std::out_of_range(message) {}
            };
            class GuestError : public std::runtime_error {
            public:
                explicit GuestError(const std::string& message) : std::runtime_error(message) {}
            };
            struct RosterPolicy {
                std::int32_t max_players;
                bool allow_guests;
            };
            class Team {
            public:
                static std::optional<Team> create(RosterPolicy policy);
                void open_registration();
                void close_registration();
                void enroll(std::string_view player);
                void drop(std::string_view player);
                std::size_t size() const;
                bool enrolled(std::string_view player) const;
            private:
                explicit Team(RosterPolicy policy) : policy_(policy) {}
                RosterPolicy policy_;
                bool open_ = false;
                std::map<std::string, bool> players_;
            };
            """,
            """
            std::optional<Team> Team::create(RosterPolicy policy) {
                if (policy.max_players < 2 || policy.max_players > 20) return std::nullopt;
                return Team(policy);
            }
            void Team::open_registration() {
                if (open_) throw RegistrationError("registration already open");
                open_ = true;
            }
            void Team::close_registration() {
                if (!open_) throw RegistrationError("registration not open");
                open_ = false;
            }
            void Team::enroll(std::string_view player) {
                if (!open_) throw RegistrationError("registration closed");
                if (player.empty()) throw RegistrationError("player name required");
                const std::string name(player);
                if (players_.count(name) != 0) throw DuplicateError("player already enrolled");
                if (name.substr(0, 6) == "guest-" && !policy_.allow_guests) throw GuestError("guests not allowed");
                if (static_cast<std::int32_t>(players_.size()) >= policy_.max_players) throw CapacityError("roster full");
                players_[name] = true;
            }
            void Team::drop(std::string_view player) {
                const std::string name(player);
                if (players_.count(name) == 0) throw RegistrationError("unknown player");
                players_.erase(name);
            }
            std::size_t Team::size() const { return players_.size(); }
            bool Team::enrolled(std::string_view player) const { return players_.count(std::string(player)) != 0; }
            """,
            """
            std::optional<Team> Team::create(RosterPolicy policy) {
                if (policy.max_players < 2 || policy.max_players > 20) return std::nullopt;
                return Team(policy);
            }
            void Team::open_registration() {
                if (open_) throw RegistrationError("registration already open");
                open_ = true;
            }
            void Team::close_registration() {
                if (!open_) throw RegistrationError("registration not open");
                open_ = false;
            }
            void Team::enroll(std::string_view player) {
                if (player.empty()) throw RegistrationError("player name required");
                const std::string name(player);
                if (players_.count(name) != 0) throw DuplicateError("player already enrolled");
                if (name.substr(0, 6) == "guest-" && !policy_.allow_guests) throw GuestError("guests not allowed");
                if (static_cast<std::int32_t>(players_.size()) >= policy_.max_players) throw CapacityError("roster full");
                players_[name] = true;
            }
            void Team::drop(std::string_view player) {
                const std::string name(player);
                if (players_.count(name) == 0) throw RegistrationError("unknown player");
                players_.erase(name);
            }
            std::size_t Team::size() const { return players_.size(); }
            bool Team::enrolled(std::string_view player) const { return players_.count(std::string(player)) != 0; }
            """,
            """
            auto team = Team::create(RosterPolicy{4, false});
            if (!team.has_value()) return 1;
            team->open_registration();
            team->enroll("ava");
            if (team->size() != 1) return 2;
            if (!team->enrolled("ava")) return 3;
            team->drop("ava");
            if (team->size() != 0) return 4;
            return 0;
            """,
            """
            if (Team::create(RosterPolicy{1, false}).has_value()) return 1;
            auto team = Team::create(RosterPolicy{2, false});
            if (!team.has_value()) return 2;
            bool threw = false;
            try { team->enroll("ben"); } catch (const RegistrationError&) { threw = true; }
            if (!threw) return 3;
            team->open_registration();
            team->enroll("ben");
            threw = false;
            try { team->enroll("ben"); } catch (const DuplicateError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { team->enroll("guest-kai"); } catch (const GuestError&) { threw = true; }
            if (!threw) return 5;
            team->enroll("cy");
            threw = false;
            try { team->enroll("di"); } catch (const CapacityError&) { threw = true; }
            if (!threw) return 6;
            if (team->size() != 2) return 7;
            threw = false;
            try { team->drop("eli"); } catch (const RegistrationError&) { threw = true; }
            if (!threw) return 8;
            auto guests = Team::create(RosterPolicy{2, true});
            if (!guests.has_value()) return 9;
            guests->open_registration();
            guests->enroll("guest-kai");
            if (!guests->enrolled("guest-kai")) return 10;
            return 0;
            """,
            "policy-gated roster lifecycle with capacity and guest name-class rules",
            "enrollment that ignores registration state or the guest policy",
            "enrollment before opening, invalid policies, duplicates, capacity with unchanged size, guest names under both policies, and unknown drops",
            "policy-gated registration with name classes",
            "injected policy object or interleaved-stream service",
            project_support=True,
        ),
        c(
            "f26acc-boat-club-fleet",
            "Boat club fleet",
            "boat_club",
            """
            class MemberError : public std::logic_error {
            public:
                explicit MemberError(const std::string& message) : std::logic_error(message) {}
            };
            class HourError : public std::out_of_range {
            public:
                explicit HourError(const std::string& message) : std::out_of_range(message) {}
            };
            class RentError : public std::runtime_error {
            public:
                explicit RentError(const std::string& message) : std::runtime_error(message) {}
            };
            class FleetError : public std::runtime_error {
            public:
                explicit FleetError(const std::string& message) : std::runtime_error(message) {}
            };
            struct FleetPolicy {
                std::int32_t max_hours;
                std::int32_t max_boats_out;
            };
            class Club {
            public:
                static std::optional<Club> create(FleetPolicy policy);
                void join(std::string_view member);
                void leave(std::string_view member);
                void rent(std::string_view member, std::int32_t hours);
                void return_boat(std::string_view member);
                std::size_t out_count() const;
                std::int32_t hours(std::string_view member) const;
            };
            """,
            """
            class MemberError : public std::logic_error {
            public:
                explicit MemberError(const std::string& message) : std::logic_error(message) {}
            };
            class HourError : public std::out_of_range {
            public:
                explicit HourError(const std::string& message) : std::out_of_range(message) {}
            };
            class RentError : public std::runtime_error {
            public:
                explicit RentError(const std::string& message) : std::runtime_error(message) {}
            };
            class FleetError : public std::runtime_error {
            public:
                explicit FleetError(const std::string& message) : std::runtime_error(message) {}
            };
            struct FleetPolicy {
                std::int32_t max_hours;
                std::int32_t max_boats_out;
            };
            class Club {
            public:
                static std::optional<Club> create(FleetPolicy policy);
                void join(std::string_view member);
                void leave(std::string_view member);
                void rent(std::string_view member, std::int32_t hours);
                void return_boat(std::string_view member);
                std::size_t out_count() const;
                std::int32_t hours(std::string_view member) const;
            private:
                explicit Club(FleetPolicy policy) : policy_(policy) {}
                FleetPolicy policy_;
                std::map<std::string, std::int32_t> members_;
                std::map<std::string, std::int32_t> out_;
            };
            """,
            """
            std::optional<Club> Club::create(FleetPolicy policy) {
                if (policy.max_hours < 1 || policy.max_hours > 12) return std::nullopt;
                if (policy.max_boats_out < 1 || policy.max_boats_out > 4) return std::nullopt;
                return Club(policy);
            }
            void Club::join(std::string_view member) {
                if (member.empty()) throw MemberError("member name required");
                const std::string name(member);
                if (members_.count(name) != 0) throw MemberError("member already joined");
                members_[name] = 0;
            }
            void Club::leave(std::string_view member) {
                const std::string name(member);
                if (members_.count(name) == 0) throw MemberError("unknown member");
                if (out_.count(name) != 0) throw MemberError("member has a boat out");
                members_.erase(name);
            }
            void Club::rent(std::string_view member, std::int32_t hours) {
                const std::string name(member);
                if (members_.count(name) == 0) throw MemberError("unknown member");
                if (out_.count(name) != 0) throw RentError("member already has a boat");
                if (hours < 1 || hours > policy_.max_hours) throw HourError("rental hours outside policy");
                if (static_cast<std::int32_t>(out_.size()) >= policy_.max_boats_out) throw FleetError("no boats available");
                out_[name] = hours;
                members_[name] += hours;
            }
            void Club::return_boat(std::string_view member) {
                const std::string name(member);
                if (out_.count(name) == 0) throw RentError("member has no boat out");
                out_.erase(name);
            }
            std::size_t Club::out_count() const { return out_.size(); }
            std::int32_t Club::hours(std::string_view member) const {
                const std::string name(member);
                if (members_.count(name) == 0) throw MemberError("unknown member");
                return members_.at(name);
            }
            """,
            """
            std::optional<Club> Club::create(FleetPolicy policy) {
                if (policy.max_hours < 1 || policy.max_hours > 12) return std::nullopt;
                if (policy.max_boats_out < 1 || policy.max_boats_out > 4) return std::nullopt;
                return Club(policy);
            }
            void Club::join(std::string_view member) {
                if (member.empty()) throw MemberError("member name required");
                const std::string name(member);
                if (members_.count(name) != 0) throw MemberError("member already joined");
                members_[name] = 0;
            }
            void Club::leave(std::string_view member) {
                const std::string name(member);
                if (members_.count(name) == 0) throw MemberError("unknown member");
                if (out_.count(name) != 0) throw MemberError("member has a boat out");
                members_.erase(name);
            }
            void Club::rent(std::string_view member, std::int32_t hours) {
                const std::string name(member);
                if (members_.count(name) == 0) throw MemberError("unknown member");
                if (out_.count(name) != 0) throw RentError("member already has a boat");
                if (hours < 1) throw HourError("rental hours outside policy");
                if (static_cast<std::int32_t>(out_.size()) >= policy_.max_boats_out) throw FleetError("no boats available");
                out_[name] = hours;
                members_[name] += hours;
            }
            void Club::return_boat(std::string_view member) {
                const std::string name(member);
                if (out_.count(name) == 0) throw RentError("member has no boat out");
                out_.erase(name);
            }
            std::size_t Club::out_count() const { return out_.size(); }
            std::int32_t Club::hours(std::string_view member) const {
                const std::string name(member);
                if (members_.count(name) == 0) throw MemberError("unknown member");
                return members_.at(name);
            }
            """,
            """
            auto club = Club::create(FleetPolicy{4, 2});
            if (!club.has_value()) return 1;
            club->join("amy");
            club->rent("amy", 2);
            if (club->out_count() != 1) return 2;
            if (club->hours("amy") != 2) return 3;
            club->return_boat("amy");
            if (club->out_count() != 0) return 4;
            return 0;
            """,
            """
            if (Club::create(FleetPolicy{0, 1}).has_value()) return 1;
            auto club = Club::create(FleetPolicy{3, 1});
            if (!club.has_value()) return 2;
            bool threw = false;
            try { club->rent("bob", 1); } catch (const MemberError&) { threw = true; }
            if (!threw) return 3;
            club->join("bob");
            club->join("cam");
            club->rent("bob", 3);
            threw = false;
            try { club->rent("bob", 1); } catch (const RentError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { club->rent("cam", 4); } catch (const HourError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { club->rent("cam", 1); } catch (const FleetError&) { threw = true; }
            if (!threw) return 6;
            if (club->hours("cam") != 0) return 7;
            threw = false;
            try { club->leave("bob"); } catch (const MemberError&) { threw = true; }
            if (!threw) return 8;
            club->return_boat("bob");
            club->rent("cam", 2);
            if (club->out_count() != 1) return 9;
            if (club->hours("cam") != 2) return 10;
            return 0;
            """,
            "multi-member rental lifecycle with per-member and fleet-wide invariants",
            "rentals that ignore the hour policy or the fleet capacity",
            "rentals before joining, double rentals, hour and fleet caps with unchanged state, leaves with boats out, and hour totals",
            "fleet-wide invariants over many member lifecycles",
            "injected policy object or interleaved-stream service",
        ),
        c(
            "f26acc-language-class-enrollment",
            "Language class enrollment",
            "language_class",
            """
            class ClassError : public std::logic_error {
            public:
                explicit ClassError(const std::string& message) : std::logic_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WaitlistError : public std::out_of_range {
            public:
                explicit WaitlistError(const std::string& message) : std::out_of_range(message) {}
            };
            struct ClassPolicy {
                std::int32_t capacity;
                std::int32_t max_waitlist;
            };
            class LanguageClass {
            public:
                static std::optional<LanguageClass> create(ClassPolicy policy);
                void open();
                void close();
                void enroll(std::string_view student);
                void leave(std::string_view student);
                std::size_t enrolled() const;
                std::size_t waitlisted() const;
            };
            """,
            """
            class ClassError : public std::logic_error {
            public:
                explicit ClassError(const std::string& message) : std::logic_error(message) {}
            };
            class DuplicateError : public std::invalid_argument {
            public:
                explicit DuplicateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WaitlistError : public std::out_of_range {
            public:
                explicit WaitlistError(const std::string& message) : std::out_of_range(message) {}
            };
            struct ClassPolicy {
                std::int32_t capacity;
                std::int32_t max_waitlist;
            };
            class LanguageClass {
            public:
                static std::optional<LanguageClass> create(ClassPolicy policy);
                void open();
                void close();
                void enroll(std::string_view student);
                void leave(std::string_view student);
                std::size_t enrolled() const;
                std::size_t waitlisted() const;
            private:
                explicit LanguageClass(ClassPolicy policy) : policy_(policy) {}
                ClassPolicy policy_;
                bool open_ = false;
                std::vector<std::string> enrolled_;
                std::deque<std::string> waitlist_;
            };
            """,
            """
            std::optional<LanguageClass> LanguageClass::create(ClassPolicy policy) {
                if (policy.capacity < 2 || policy.capacity > 30) return std::nullopt;
                if (policy.max_waitlist < 0 || policy.max_waitlist > 10) return std::nullopt;
                return LanguageClass(policy);
            }
            void LanguageClass::open() {
                if (open_) throw ClassError("class already open");
                open_ = true;
            }
            void LanguageClass::close() {
                if (!open_) throw ClassError("class not open");
                open_ = false;
            }
            void LanguageClass::enroll(std::string_view student) {
                if (!open_) throw ClassError("class is closed");
                if (student.empty()) throw ClassError("student name required");
                const std::string name(student);
                const bool in_enrolled = std::find(enrolled_.begin(), enrolled_.end(), name) != enrolled_.end();
                const bool in_waitlist = std::find(waitlist_.begin(), waitlist_.end(), name) != waitlist_.end();
                if (in_enrolled || in_waitlist) throw DuplicateError("student already enrolled");
                if (static_cast<std::int32_t>(enrolled_.size()) < policy_.capacity) {
                    enrolled_.push_back(name);
                    return;
                }
                if (static_cast<std::int32_t>(waitlist_.size()) >= policy_.max_waitlist) throw WaitlistError("waitlist full");
                waitlist_.push_back(name);
            }
            void LanguageClass::leave(std::string_view student) {
                const std::string name(student);
                const auto seat = std::find(enrolled_.begin(), enrolled_.end(), name);
                if (seat != enrolled_.end()) {
                    enrolled_.erase(seat);
                    if (!waitlist_.empty()) {
                        enrolled_.push_back(waitlist_.front());
                        waitlist_.pop_front();
                    }
                    return;
                }
                const auto spot = std::find(waitlist_.begin(), waitlist_.end(), name);
                if (spot != waitlist_.end()) {
                    waitlist_.erase(spot);
                    return;
                }
                throw ClassError("unknown student");
            }
            std::size_t LanguageClass::enrolled() const { return enrolled_.size(); }
            std::size_t LanguageClass::waitlisted() const { return waitlist_.size(); }
            """,
            """
            std::optional<LanguageClass> LanguageClass::create(ClassPolicy policy) {
                if (policy.capacity < 2 || policy.capacity > 30) return std::nullopt;
                if (policy.max_waitlist < 0 || policy.max_waitlist > 10) return std::nullopt;
                return LanguageClass(policy);
            }
            void LanguageClass::open() {
                if (open_) throw ClassError("class already open");
                open_ = true;
            }
            void LanguageClass::close() {
                if (!open_) throw ClassError("class not open");
                open_ = false;
            }
            void LanguageClass::enroll(std::string_view student) {
                if (!open_) throw ClassError("class is closed");
                if (student.empty()) throw ClassError("student name required");
                const std::string name(student);
                if (std::find(enrolled_.begin(), enrolled_.end(), name) != enrolled_.end()) throw DuplicateError("student already enrolled");
                enrolled_.push_back(name);
            }
            void LanguageClass::leave(std::string_view student) {
                const std::string name(student);
                const auto seat = std::find(enrolled_.begin(), enrolled_.end(), name);
                if (seat != enrolled_.end()) {
                    enrolled_.erase(seat);
                    if (!waitlist_.empty()) {
                        enrolled_.push_back(waitlist_.front());
                        waitlist_.pop_front();
                    }
                    return;
                }
                const auto spot = std::find(waitlist_.begin(), waitlist_.end(), name);
                if (spot != waitlist_.end()) {
                    waitlist_.erase(spot);
                    return;
                }
                throw ClassError("unknown student");
            }
            std::size_t LanguageClass::enrolled() const { return enrolled_.size(); }
            std::size_t LanguageClass::waitlisted() const { return waitlist_.size(); }
            """,
            """
            auto klass = LanguageClass::create(ClassPolicy{2, 2});
            if (!klass.has_value()) return 1;
            klass->open();
            klass->enroll("amy");
            klass->enroll("bob");
            klass->enroll("cy");
            if (klass->enrolled() != 2) return 2;
            if (klass->waitlisted() != 1) return 3;
            klass->leave("amy");
            if (klass->waitlisted() != 0) return 4;
            return 0;
            """,
            """
            if (LanguageClass::create(ClassPolicy{1, 0}).has_value()) return 1;
            auto klass = LanguageClass::create(ClassPolicy{2, 1});
            if (!klass.has_value()) return 2;
            bool threw = false;
            try { klass->enroll("amy"); } catch (const ClassError&) { threw = true; }
            if (!threw) return 3;
            klass->open();
            klass->enroll("amy");
            klass->enroll("bob");
            klass->enroll("cy");
            threw = false;
            try { klass->enroll("dee"); } catch (const WaitlistError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { klass->enroll("cy"); } catch (const DuplicateError&) { threw = true; }
            if (!threw) return 5;
            klass->leave("amy");
            if (klass->waitlisted() != 0) return 6;
            threw = false;
            try { klass->leave("eve"); } catch (const ClassError&) { threw = true; }
            if (!threw) return 7;
            klass->leave("cy");
            klass->leave("bob");
            threw = false;
            try { klass->leave("bob"); } catch (const ClassError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            "capacity lifecycle with FIFO waitlist promotion on leave",
            "unbounded enrollment without a waitlist or LIFO promotion",
            "enrollment before opening, invalid policies, waitlisting, waitlist overflow, duplicate rejection, promotion order, and unknown leavers",
            "waitlist promotion, a queue-coupled lifecycle",
            "injected policy object or interleaved-stream service",
            project_support=True,
        ),
        c(
            "f26acc-night-market-permit",
            "Night market permit",
            "night_market",
            """
            class MarketError : public std::logic_error {
            public:
                explicit MarketError(const std::string& message) : std::logic_error(message) {}
            };
            class FeeError : public std::invalid_argument {
            public:
                explicit FeeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StallError : public std::out_of_range {
            public:
                explicit StallError(const std::string& message) : std::out_of_range(message) {}
            };
            struct PermitPolicy {
                std::int32_t max_stalls;
                std::int32_t fee_cents;
            };
            class Market {
            public:
                static std::optional<Market> create(PermitPolicy policy);
                void open_night();
                void close_night();
                void register_stall(std::string_view vendor, std::int32_t fee_paid);
                void refund(std::string_view vendor);
                std::size_t stalls() const;
                std::int32_t collected_cents() const;
            };
            """,
            """
            class MarketError : public std::logic_error {
            public:
                explicit MarketError(const std::string& message) : std::logic_error(message) {}
            };
            class FeeError : public std::invalid_argument {
            public:
                explicit FeeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StallError : public std::out_of_range {
            public:
                explicit StallError(const std::string& message) : std::out_of_range(message) {}
            };
            struct PermitPolicy {
                std::int32_t max_stalls;
                std::int32_t fee_cents;
            };
            class Market {
            public:
                static std::optional<Market> create(PermitPolicy policy);
                void open_night();
                void close_night();
                void register_stall(std::string_view vendor, std::int32_t fee_paid);
                void refund(std::string_view vendor);
                std::size_t stalls() const;
                std::int32_t collected_cents() const;
            private:
                explicit Market(PermitPolicy policy) : policy_(policy) {}
                PermitPolicy policy_;
                bool open_ = false;
                std::map<std::string, std::int32_t> vendors_;
                std::int32_t collected_ = 0;
            };
            """,
            """
            std::optional<Market> Market::create(PermitPolicy policy) {
                if (policy.max_stalls < 1 || policy.max_stalls > 12) return std::nullopt;
                if (policy.fee_cents <= 0) return std::nullopt;
                return Market(policy);
            }
            void Market::open_night() {
                if (open_) throw MarketError("market already open");
                open_ = true;
            }
            void Market::close_night() {
                if (!open_) throw MarketError("market not open");
                if (!vendors_.empty()) throw MarketError("stalls still registered");
                open_ = false;
            }
            void Market::register_stall(std::string_view vendor, std::int32_t fee_paid) {
                if (!open_) throw MarketError("market not open");
                if (vendor.empty()) throw MarketError("vendor name required");
                const std::string name(vendor);
                if (vendors_.count(name) != 0) throw MarketError("vendor already registered");
                if (fee_paid != policy_.fee_cents) throw FeeError("incorrect fee");
                if (static_cast<std::int32_t>(vendors_.size()) >= policy_.max_stalls) throw StallError("no stalls left");
                vendors_[name] = fee_paid;
                collected_ += fee_paid;
            }
            void Market::refund(std::string_view vendor) {
                const std::string name(vendor);
                if (vendors_.count(name) == 0) throw MarketError("unknown vendor");
                collected_ -= vendors_.at(name);
                vendors_.erase(name);
            }
            std::size_t Market::stalls() const { return vendors_.size(); }
            std::int32_t Market::collected_cents() const { return collected_; }
            """,
            """
            std::optional<Market> Market::create(PermitPolicy policy) {
                if (policy.max_stalls < 1 || policy.max_stalls > 12) return std::nullopt;
                if (policy.fee_cents <= 0) return std::nullopt;
                return Market(policy);
            }
            void Market::open_night() {
                if (open_) throw MarketError("market already open");
                open_ = true;
            }
            void Market::close_night() {
                if (!open_) throw MarketError("market not open");
                if (!vendors_.empty()) throw MarketError("stalls still registered");
                open_ = false;
            }
            void Market::register_stall(std::string_view vendor, std::int32_t fee_paid) {
                if (!open_) throw MarketError("market not open");
                if (vendor.empty()) throw MarketError("vendor name required");
                const std::string name(vendor);
                if (vendors_.count(name) != 0) throw MarketError("vendor already registered");
                if (fee_paid <= 0) throw FeeError("incorrect fee");
                if (static_cast<std::int32_t>(vendors_.size()) >= policy_.max_stalls) throw StallError("no stalls left");
                vendors_[name] = fee_paid;
                collected_ += fee_paid;
            }
            void Market::refund(std::string_view vendor) {
                const std::string name(vendor);
                if (vendors_.count(name) == 0) throw MarketError("unknown vendor");
                collected_ -= vendors_.at(name);
                vendors_.erase(name);
            }
            std::size_t Market::stalls() const { return vendors_.size(); }
            std::int32_t Market::collected_cents() const { return collected_; }
            """,
            """
            auto market = Market::create(PermitPolicy{2, 500});
            if (!market.has_value()) return 1;
            market->open_night();
            market->register_stall("noodle", 500);
            if (market->stalls() != 1) return 2;
            if (market->collected_cents() != 500) return 3;
            market->refund("noodle");
            if (market->collected_cents() != 0) return 4;
            return 0;
            """,
            """
            if (Market::create(PermitPolicy{0, 100}).has_value()) return 1;
            auto market = Market::create(PermitPolicy{1, 300});
            if (!market.has_value()) return 2;
            bool threw = false;
            try { market->register_stall("tea", 300); } catch (const MarketError&) { threw = true; }
            if (!threw) return 3;
            market->open_night();
            threw = false;
            try { market->register_stall("tea", 250); } catch (const FeeError&) { threw = true; }
            if (!threw) return 4;
            if (market->stalls() != 0) return 5;
            if (market->collected_cents() != 0) return 6;
            market->register_stall("tea", 300);
            threw = false;
            try { market->register_stall("soup", 300); } catch (const StallError&) { threw = true; }
            if (!threw) return 7;
            threw = false;
            try { market->refund("soup"); } catch (const MarketError&) { threw = true; }
            if (!threw) return 8;
            threw = false;
            try { market->close_night(); } catch (const MarketError&) { threw = true; }
            if (!threw) return 9;
            market->refund("tea");
            market->close_night();
            if (market->collected_cents() != 0) return 10;
            return 0;
            """,
            "fee-verified registration lifecycle with exact-money checks",
            "accepting the wrong fee or clamping stall counts",
            "registration before opening, invalid policies, wrong fees with unchanged stalls and collections, stall caps, refunds, and closes with stalls",
            "exact-fee verification on a capacity lifecycle",
            "injected policy object or interleaved-stream service",
        ),
        c(
            "f26acc-ski-school-roster",
            "Ski school roster",
            "ski_school",
            """
            class SeasonError : public std::logic_error {
            public:
                explicit SeasonError(const std::string& message) : std::logic_error(message) {}
            };
            class PairError : public std::runtime_error {
            public:
                explicit PairError(const std::string& message) : std::runtime_error(message) {}
            };
            class SkiSchool {
            public:
                void open_season();
                void close_season();
                void book(std::string_view student, std::string_view instructor);
                void teach(std::string_view instructor, std::string_view student);
                void complete(std::string_view student);
                std::size_t pending(std::string_view instructor) const;
                std::size_t done() const;
            };
            """,
            """
            class SeasonError : public std::logic_error {
            public:
                explicit SeasonError(const std::string& message) : std::logic_error(message) {}
            };
            class PairError : public std::runtime_error {
            public:
                explicit PairError(const std::string& message) : std::runtime_error(message) {}
            };
            class SkiSchool {
            public:
                void open_season();
                void close_season();
                void book(std::string_view student, std::string_view instructor);
                void teach(std::string_view instructor, std::string_view student);
                void complete(std::string_view student);
                std::size_t pending(std::string_view instructor) const;
                std::size_t done() const;
            private:
                bool open_ = false;
                std::map<std::string, std::string> booked_;
                std::map<std::string, std::string> taught_;
                std::size_t done_ = 0;
            };
            """,
            """
            void SkiSchool::open_season() {
                if (open_) throw SeasonError("season already open");
                open_ = true;
            }
            void SkiSchool::close_season() {
                if (!open_) throw SeasonError("season not open");
                open_ = false;
            }
            void SkiSchool::book(std::string_view student, std::string_view instructor) {
                if (!open_) throw SeasonError("season not open");
                if (student.empty() || instructor.empty()) throw SeasonError("names required");
                const std::string who(student);
                if (booked_.count(who) != 0 || taught_.count(who) != 0) throw PairError("student already booked");
                booked_[who] = std::string(instructor);
            }
            void SkiSchool::teach(std::string_view instructor, std::string_view student) {
                if (!open_) throw SeasonError("season not open");
                const std::string who(student);
                if (booked_.count(who) == 0 || booked_.at(who) != instructor) throw PairError("no such booking");
                taught_[who] = booked_.at(who);
                booked_.erase(who);
            }
            void SkiSchool::complete(std::string_view student) {
                if (!open_) throw SeasonError("season not open");
                const std::string who(student);
                if (taught_.count(who) == 0) throw PairError("lesson not taught");
                taught_.erase(who);
                ++done_;
            }
            std::size_t SkiSchool::pending(std::string_view instructor) const {
                std::size_t total = 0;
                for (const auto& entry : booked_) {
                    if (entry.second == instructor) ++total;
                }
                return total;
            }
            std::size_t SkiSchool::done() const { return done_; }
            """,
            """
            void SkiSchool::open_season() {
                if (open_) throw SeasonError("season already open");
                open_ = true;
            }
            void SkiSchool::close_season() {
                if (!open_) throw SeasonError("season not open");
                open_ = false;
            }
            void SkiSchool::book(std::string_view student, std::string_view instructor) {
                if (!open_) throw SeasonError("season not open");
                if (student.empty() || instructor.empty()) throw SeasonError("names required");
                const std::string who(student);
                if (booked_.count(who) != 0 || taught_.count(who) != 0) throw PairError("student already booked");
                booked_[who] = std::string(instructor);
            }
            void SkiSchool::teach(std::string_view instructor, std::string_view student) {
                if (!open_) throw SeasonError("season not open");
                const std::string who(student);
                taught_[who] = std::string(instructor);
                booked_.erase(who);
            }
            void SkiSchool::complete(std::string_view student) {
                if (!open_) throw SeasonError("season not open");
                const std::string who(student);
                if (taught_.count(who) == 0) throw PairError("lesson not taught");
                taught_.erase(who);
                ++done_;
            }
            std::size_t SkiSchool::pending(std::string_view instructor) const {
                std::size_t total = 0;
                for (const auto& entry : booked_) {
                    if (entry.second == instructor) ++total;
                }
                return total;
            }
            std::size_t SkiSchool::done() const { return done_; }
            """,
            """
            SkiSchool school;
            school.open_season();
            school.book("mia", "oz");
            if (school.pending("oz") != 1) return 1;
            school.teach("oz", "mia");
            if (school.pending("oz") != 0) return 2;
            school.complete("mia");
            if (school.done() != 1) return 3;
            return 0;
            """,
            """
            SkiSchool school;
            bool threw = false;
            try { school.book("amy", "oz"); } catch (const SeasonError&) { threw = true; }
            if (!threw) return 1;
            school.open_season();
            school.book("amy", "oz");
            threw = false;
            try { school.book("amy", "bo"); } catch (const PairError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { school.teach("bo", "amy"); } catch (const PairError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { school.complete("amy"); } catch (const PairError&) { threw = true; }
            if (!threw) return 4;
            school.book("cy", "bo");
            school.teach("oz", "amy");
            school.teach("bo", "cy");
            school.complete("cy");
            school.complete("amy");
            if (school.done() != 2) return 5;
            threw = false;
            try { school.teach("oz", "amy"); } catch (const PairError&) { threw = true; }
            if (!threw) return 6;
            school.close_season();
            threw = false;
            try { school.book("amy", "oz"); } catch (const SeasonError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            "book/teach/complete pipeline with interleaved student-instructor pairs",
            "teaching unbooked pairs or completing untaught lessons",
            "bookings before opening, duplicate student bookings, unbooked and mismatched teaches, untaught completions, interleaved instructors, and closure",
            "pair-matched interleaving in lifecycle discipline",
            "injected policy object or interleaved-stream service",
        ),
        c(
            "f26acc-bowling-lane-desk",
            "Bowling lane desk",
            "bowling_lanes",
            """
            class LaneError : public std::out_of_range {
            public:
                explicit LaneError(const std::string& message) : std::out_of_range(message) {}
            };
            class GameError : public std::logic_error {
            public:
                explicit GameError(const std::string& message) : std::logic_error(message) {}
            };
            class PinsError : public std::invalid_argument {
            public:
                explicit PinsError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LaneDesk {
            public:
                void open(std::int32_t lanes);
                void close();
                void start_game(std::int32_t lane);
                void bowl(std::int32_t lane, std::int32_t pins);
                void end_game(std::int32_t lane);
                std::optional<std::int32_t> score(std::int32_t lane) const;
                std::int32_t games_played() const;
            };
            """,
            """
            class LaneError : public std::out_of_range {
            public:
                explicit LaneError(const std::string& message) : std::out_of_range(message) {}
            };
            class GameError : public std::logic_error {
            public:
                explicit GameError(const std::string& message) : std::logic_error(message) {}
            };
            class PinsError : public std::invalid_argument {
            public:
                explicit PinsError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LaneDesk {
            public:
                void open(std::int32_t lanes);
                void close();
                void start_game(std::int32_t lane);
                void bowl(std::int32_t lane, std::int32_t pins);
                void end_game(std::int32_t lane);
                std::optional<std::int32_t> score(std::int32_t lane) const;
                std::int32_t games_played() const;
            private:
                bool open_ = false;
                std::int32_t lanes_ = 0;
                std::map<std::int32_t, std::int32_t> games_;
                std::int32_t played_ = 0;
            };
            """,
            """
            void LaneDesk::open(std::int32_t lanes) {
                if (open_) throw GameError("desk already open");
                if (lanes < 1 || lanes > 8) throw LaneError("lane count out of range");
                open_ = true;
                lanes_ = lanes;
                games_.clear();
                played_ = 0;
            }
            void LaneDesk::close() {
                if (!open_) throw GameError("desk not open");
                if (!games_.empty()) throw GameError("games still active");
                open_ = false;
            }
            void LaneDesk::start_game(std::int32_t lane) {
                if (!open_) throw GameError("desk not open");
                if (lane < 1 || lane > lanes_) throw LaneError("unknown lane");
                if (games_.count(lane) != 0) throw GameError("game already active");
                games_[lane] = 0;
            }
            void LaneDesk::bowl(std::int32_t lane, std::int32_t pins) {
                if (!open_) throw GameError("desk not open");
                if (lane < 1 || lane > lanes_) throw LaneError("unknown lane");
                if (games_.count(lane) == 0) throw GameError("no active game");
                if (pins < 0 || pins > 10) throw PinsError("pins out of range");
                games_[lane] += pins;
            }
            void LaneDesk::end_game(std::int32_t lane) {
                if (!open_) throw GameError("desk not open");
                if (lane < 1 || lane > lanes_) throw LaneError("unknown lane");
                if (games_.count(lane) == 0) throw GameError("no active game");
                games_.erase(lane);
                ++played_;
            }
            std::optional<std::int32_t> LaneDesk::score(std::int32_t lane) const {
                if (!open_ || games_.count(lane) == 0) return std::nullopt;
                return games_.at(lane);
            }
            std::int32_t LaneDesk::games_played() const { return played_; }
            """,
            """
            void LaneDesk::open(std::int32_t lanes) {
                if (open_) throw GameError("desk already open");
                if (lanes < 1 || lanes > 8) throw LaneError("lane count out of range");
                open_ = true;
                lanes_ = lanes;
                games_.clear();
                played_ = 0;
            }
            void LaneDesk::close() {
                if (!open_) throw GameError("desk not open");
                if (!games_.empty()) throw GameError("games still active");
                open_ = false;
            }
            void LaneDesk::start_game(std::int32_t lane) {
                if (!open_) throw GameError("desk not open");
                if (lane < 1 || lane > lanes_) throw LaneError("unknown lane");
                if (games_.count(lane) != 0) throw GameError("game already active");
                games_[lane] = 0;
            }
            void LaneDesk::bowl(std::int32_t lane, std::int32_t pins) {
                if (!open_) throw GameError("desk not open");
                if (lane < 1 || lane > lanes_) throw LaneError("unknown lane");
                if (pins < 0 || pins > 10) throw PinsError("pins out of range");
                games_[lane] += pins;
            }
            void LaneDesk::end_game(std::int32_t lane) {
                if (!open_) throw GameError("desk not open");
                if (lane < 1 || lane > lanes_) throw LaneError("unknown lane");
                if (games_.count(lane) == 0) throw GameError("no active game");
                games_.erase(lane);
                ++played_;
            }
            std::optional<std::int32_t> LaneDesk::score(std::int32_t lane) const {
                if (!open_ || games_.count(lane) == 0) return std::nullopt;
                return games_.at(lane);
            }
            std::int32_t LaneDesk::games_played() const { return played_; }
            """,
            """
            LaneDesk desk;
            desk.open(2);
            desk.start_game(1);
            desk.bowl(1, 7);
            desk.bowl(1, 2);
            if (desk.score(1) != std::optional<std::int32_t>(9)) return 1;
            desk.end_game(1);
            if (desk.games_played() != 1) return 2;
            return 0;
            """,
            """
            LaneDesk desk;
            bool threw = false;
            try { desk.start_game(1); } catch (const GameError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { desk.open(9); } catch (const LaneError&) { threw = true; }
            if (!threw) return 2;
            desk.open(2);
            threw = false;
            try { desk.start_game(3); } catch (const LaneError&) { threw = true; }
            if (!threw) return 3;
            desk.start_game(1);
            desk.start_game(2);
            desk.bowl(1, 10);
            threw = false;
            try { desk.bowl(2, 11); } catch (const PinsError&) { threw = true; }
            if (!threw) return 4;
            desk.bowl(2, 4);
            if (desk.score(1) != std::optional<std::int32_t>(10)) return 5;
            if (desk.score(2) != std::optional<std::int32_t>(4)) return 6;
            threw = false;
            try { desk.close(); } catch (const GameError&) { threw = true; }
            if (!threw) return 7;
            desk.end_game(1);
            desk.end_game(2);
            if (desk.games_played() != 2) return 8;
            if (desk.score(1).has_value()) return 9;
            threw = false;
            try { desk.bowl(1, 5); } catch (const GameError&) { threw = true; }
            if (!threw) return 10;
            return 0;
            """,
            "per-lane independent game lifecycles under one desk",
            "bowling on lanes with no active game",
            "out-of-range lanes, bowls before starts, pin bounds, interleaved lanes, closes with active games, and post-end scores",
            "many independent interleaved lifecycles",
            "injected policy object or interleaved-stream service",
        ),
        c(
            "f26acc-chess-match-clock",
            "Chess match clock",
            "chess_match",
            """
            class ClockError : public std::logic_error {
            public:
                explicit ClockError(const std::string& message) : std::logic_error(message) {}
            };
            class SideError : public std::invalid_argument {
            public:
                explicit SideError(const std::string& message) : std::invalid_argument(message) {}
            };
            class FlagError : public std::runtime_error {
            public:
                explicit FlagError(const std::string& message) : std::runtime_error(message) {}
            };
            class MatchClock {
            public:
                void start(std::int32_t seconds_each);
                void abort();
                void press();
                void flag(std::string_view side);
                std::optional<std::int32_t> remaining(std::string_view side) const;
                std::string_view turn() const;
            };
            """,
            """
            class ClockError : public std::logic_error {
            public:
                explicit ClockError(const std::string& message) : std::logic_error(message) {}
            };
            class SideError : public std::invalid_argument {
            public:
                explicit SideError(const std::string& message) : std::invalid_argument(message) {}
            };
            class FlagError : public std::runtime_error {
            public:
                explicit FlagError(const std::string& message) : std::runtime_error(message) {}
            };
            class MatchClock {
            public:
                void start(std::int32_t seconds_each);
                void abort();
                void press();
                void flag(std::string_view side);
                std::optional<std::int32_t> remaining(std::string_view side) const;
                std::string_view turn() const;
            private:
                bool running_ = false;
                std::int32_t light_ = 0;
                std::int32_t shade_ = 0;
                bool light_turn_ = true;
            };
            """,
            """
            void MatchClock::start(std::int32_t seconds_each) {
                if (running_) throw ClockError("clock already running");
                if (seconds_each < 60 || seconds_each > 7200) throw ClockError("clock budget out of range");
                running_ = true;
                light_ = seconds_each;
                shade_ = seconds_each;
                light_turn_ = true;
            }
            void MatchClock::abort() {
                if (!running_) throw ClockError("clock not running");
                running_ = false;
            }
            void MatchClock::press() {
                if (!running_) throw ClockError("clock not running");
                if (light_turn_) {
                    if (light_ == 0) throw ClockError("light clock exhausted");
                    --light_;
                } else {
                    if (shade_ == 0) throw ClockError("shade clock exhausted");
                    --shade_;
                }
                light_turn_ = !light_turn_;
            }
            void MatchClock::flag(std::string_view side) {
                if (!running_) throw ClockError("clock not running");
                if (side == "light") {
                    if (light_ != 0) throw FlagError("light clock still running");
                } else if (side == "shade") {
                    if (shade_ != 0) throw FlagError("shade clock still running");
                } else {
                    throw SideError("unknown side");
                }
                running_ = false;
            }
            std::optional<std::int32_t> MatchClock::remaining(std::string_view side) const {
                if (!running_) return std::nullopt;
                if (side == "light") return light_;
                if (side == "shade") return shade_;
                throw SideError("unknown side");
            }
            std::string_view MatchClock::turn() const {
                if (!running_) return "none";
                return light_turn_ ? "light" : "shade";
            }
            """,
            """
            void MatchClock::start(std::int32_t seconds_each) {
                if (running_) throw ClockError("clock already running");
                if (seconds_each < 60 || seconds_each > 7200) throw ClockError("clock budget out of range");
                running_ = true;
                light_ = seconds_each;
                shade_ = seconds_each;
                light_turn_ = true;
            }
            void MatchClock::abort() {
                if (!running_) throw ClockError("clock not running");
                running_ = false;
            }
            void MatchClock::press() {
                if (!running_) throw ClockError("clock not running");
                if (shade_ == 0) throw ClockError("shade clock exhausted");
                --shade_;
                light_turn_ = !light_turn_;
            }
            void MatchClock::flag(std::string_view side) {
                if (!running_) throw ClockError("clock not running");
                if (side == "light") {
                    if (light_ != 0) throw FlagError("light clock still running");
                } else if (side == "shade") {
                    if (shade_ != 0) throw FlagError("shade clock still running");
                } else {
                    throw SideError("unknown side");
                }
                running_ = false;
            }
            std::optional<std::int32_t> MatchClock::remaining(std::string_view side) const {
                if (!running_) return std::nullopt;
                if (side == "light") return light_;
                if (side == "shade") return shade_;
                throw SideError("unknown side");
            }
            std::string_view MatchClock::turn() const {
                if (!running_) return "none";
                return light_turn_ ? "light" : "shade";
            }
            """,
            """
            MatchClock clock;
            clock.start(300);
            if (clock.turn() != "light") return 1;
            clock.press();
            if (clock.turn() != "shade") return 2;
            if (clock.remaining("light") != std::optional<std::int32_t>(299)) return 3;
            if (clock.remaining("shade") != std::optional<std::int32_t>(300)) return 4;
            return 0;
            """,
            """
            MatchClock clock;
            bool threw = false;
            try { clock.press(); } catch (const ClockError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { clock.start(30); } catch (const ClockError&) { threw = true; }
            if (!threw) return 2;
            clock.start(60);
            threw = false;
            try { clock.flag("light"); } catch (const FlagError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { clock.remaining("green"); } catch (const SideError&) { threw = true; }
            if (!threw) return 4;
            for (int i = 0; i < 119; ++i) clock.press();
            if (clock.remaining("light") != std::optional<std::int32_t>(0)) return 5;
            if (clock.remaining("shade") != std::optional<std::int32_t>(1)) return 6;
            if (clock.turn() != "shade") return 7;
            clock.flag("light");
            if (clock.remaining("light").has_value()) return 8;
            threw = false;
            try { clock.press(); } catch (const ClockError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            "strictly alternating two-sided clock as the deterministic stand-in for concurrent play",
            "presses that do not alternate sides or flags claimed on live clocks",
            "presses before starting, budget bounds, early flags, unknown sides, exact alternation to zero, flags at zero, and post-abort presses",
            "strict alternation as concurrent-like sequencing",
            "injected policy object or interleaved-stream service",
            project_support=True,
        ),
        c(
            "f26acc-radio-request-line",
            "Radio request line",
            "radio_requests",
            """
            class LineError : public std::logic_error {
            public:
                explicit LineError(const std::string& message) : std::logic_error(message) {}
            };
            class EmptyError : public std::runtime_error {
            public:
                explicit EmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RequestLine {
            public:
                void open_lines();
                void close_lines();
                bool call_in(std::string_view caller);
                void play_next();
                std::size_t queued() const;
                std::size_t played() const;
            };
            """,
            """
            class LineError : public std::logic_error {
            public:
                explicit LineError(const std::string& message) : std::logic_error(message) {}
            };
            class EmptyError : public std::runtime_error {
            public:
                explicit EmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RequestLine {
            public:
                void open_lines();
                void close_lines();
                bool call_in(std::string_view caller);
                void play_next();
                std::size_t queued() const;
                std::size_t played() const;
            private:
                bool open_ = false;
                std::deque<std::string> queue_;
                std::size_t played_ = 0;
            };
            """,
            """
            void RequestLine::open_lines() {
                if (open_) throw LineError("lines already open");
                open_ = true;
            }
            void RequestLine::close_lines() {
                if (!open_) throw LineError("lines not open");
                if (!queue_.empty()) throw LineError("callers still waiting");
                open_ = false;
            }
            bool RequestLine::call_in(std::string_view caller) {
                if (!open_ || caller.empty()) return false;
                if (queue_.size() >= 5) return false;
                const std::string name(caller);
                if (std::find(queue_.begin(), queue_.end(), name) != queue_.end()) return false;
                queue_.push_back(name);
                return true;
            }
            void RequestLine::play_next() {
                if (!open_) throw LineError("lines not open");
                if (queue_.empty()) throw EmptyError("no callers waiting");
                queue_.pop_front();
                ++played_;
            }
            std::size_t RequestLine::queued() const { return queue_.size(); }
            std::size_t RequestLine::played() const { return played_; }
            """,
            """
            void RequestLine::open_lines() {
                if (open_) throw LineError("lines already open");
                open_ = true;
            }
            void RequestLine::close_lines() {
                if (!open_) throw LineError("lines not open");
                if (!queue_.empty()) throw LineError("callers still waiting");
                open_ = false;
            }
            bool RequestLine::call_in(std::string_view caller) {
                if (!open_ || caller.empty()) return false;
                const std::string name(caller);
                if (std::find(queue_.begin(), queue_.end(), name) != queue_.end()) return false;
                queue_.push_back(name);
                return true;
            }
            void RequestLine::play_next() {
                if (!open_) throw LineError("lines not open");
                if (queue_.empty()) throw EmptyError("no callers waiting");
                queue_.pop_front();
                ++played_;
            }
            std::size_t RequestLine::queued() const { return queue_.size(); }
            std::size_t RequestLine::played() const { return played_; }
            """,
            """
            RequestLine line;
            line.open_lines();
            if (!line.call_in("amy")) return 1;
            if (!line.call_in("bob")) return 2;
            line.play_next();
            if (line.queued() != 1) return 3;
            if (line.played() != 1) return 4;
            return 0;
            """,
            """
            RequestLine line;
            if (line.call_in("amy")) return 1;
            line.open_lines();
            bool threw = false;
            try { line.play_next(); } catch (const EmptyError&) { threw = true; }
            if (!threw) return 2;
            if (!line.call_in("amy")) return 3;
            if (line.call_in("amy")) return 4;
            if (!line.call_in("bob")) return 5;
            if (!line.call_in("cy")) return 6;
            if (!line.call_in("dee")) return 7;
            if (!line.call_in("eli")) return 8;
            if (line.call_in("fred")) return 9;
            line.play_next();
            if (!line.call_in("fred")) return 10;
            if (line.queued() != 5) return 11;
            threw = false;
            try { line.close_lines(); } catch (const LineError&) { threw = true; }
            if (!threw) return 12;
            for (int i = 0; i < 5; ++i) line.play_next();
            if (line.played() != 6) return 13;
            line.close_lines();
            return 0;
            """,
            "bounded FIFO request queue with mixed status and exception channels",
            "queue growth past the bound or closes that drop waiting callers",
            "calls before opening, queue bounds, duplicate callers, empty plays, interleaved calls and plays, and closes with waiting callers",
            "mixed error channels on an interleaved queue",
            "injected policy object or interleaved-stream service",
        ),
        c(
            "f26acc-food-truck-shift",
            "Food truck shift",
            "food_truck",
            """
            class ShiftError : public std::logic_error {
            public:
                explicit ShiftError(const std::string& message) : std::logic_error(message) {}
            };
            class MenuError : public std::invalid_argument {
            public:
                explicit MenuError(const std::string& message) : std::invalid_argument(message) {}
            };
            class QueueError : public std::out_of_range {
            public:
                explicit QueueError(const std::string& message) : std::out_of_range(message) {}
            };
            class PrepError : public std::runtime_error {
            public:
                explicit PrepError(const std::string& message) : std::runtime_error(message) {}
            };
            class ServeError : public std::runtime_error {
            public:
                explicit ServeError(const std::string& message) : std::runtime_error(message) {}
            };
            class CloseError : public std::logic_error {
            public:
                explicit CloseError(const std::string& message) : std::logic_error(message) {}
            };
            class TruckShift {
            public:
                void open_shift();
                void close_shift();
                void order(std::string_view item);
                void prepare();
                void serve();
                std::size_t pending_orders() const;
                std::size_t ready() const;
                std::int32_t sales_cents() const;
            };
            """,
            """
            class ShiftError : public std::logic_error {
            public:
                explicit ShiftError(const std::string& message) : std::logic_error(message) {}
            };
            class MenuError : public std::invalid_argument {
            public:
                explicit MenuError(const std::string& message) : std::invalid_argument(message) {}
            };
            class QueueError : public std::out_of_range {
            public:
                explicit QueueError(const std::string& message) : std::out_of_range(message) {}
            };
            class PrepError : public std::runtime_error {
            public:
                explicit PrepError(const std::string& message) : std::runtime_error(message) {}
            };
            class ServeError : public std::runtime_error {
            public:
                explicit ServeError(const std::string& message) : std::runtime_error(message) {}
            };
            class CloseError : public std::logic_error {
            public:
                explicit CloseError(const std::string& message) : std::logic_error(message) {}
            };
            class TruckShift {
            public:
                void open_shift();
                void close_shift();
                void order(std::string_view item);
                void prepare();
                void serve();
                std::size_t pending_orders() const;
                std::size_t ready() const;
                std::int32_t sales_cents() const;
            private:
                bool open_ = false;
                std::deque<std::string> pending_;
                std::deque<std::string> ready_;
                std::int32_t sales_ = 0;
            };
            """,
            """
            namespace {
            constexpr std::pair<const char*, std::int32_t> kMenu[] = {
                {"taco", 450}, {"burrito", 680}, {"elote", 320}, {"agua", 200},
            };
            std::int32_t menu_price(std::string_view item) {
                for (const auto& entry : kMenu) {
                    if (item == entry.first) return entry.second;
                }
                return -1;
            }
            }  // namespace
            void TruckShift::open_shift() {
                if (open_) throw ShiftError("shift already open");
                open_ = true;
            }
            void TruckShift::close_shift() {
                if (!open_) throw ShiftError("shift not open");
                if (!pending_.empty() || !ready_.empty()) throw CloseError("orders outstanding");
                open_ = false;
            }
            void TruckShift::order(std::string_view item) {
                if (!open_) throw ShiftError("shift not open");
                if (menu_price(item) < 0) throw MenuError("unknown menu item");
                if (pending_.size() >= 8) throw QueueError("order queue full");
                pending_.push_back(std::string(item));
            }
            void TruckShift::prepare() {
                if (!open_) throw ShiftError("shift not open");
                if (pending_.empty()) throw PrepError("nothing to prepare");
                ready_.push_back(pending_.front());
                pending_.pop_front();
            }
            void TruckShift::serve() {
                if (!open_) throw ShiftError("shift not open");
                if (ready_.empty()) throw ServeError("nothing ready to serve");
                sales_ += menu_price(ready_.front());
                ready_.pop_front();
            }
            std::size_t TruckShift::pending_orders() const { return pending_.size(); }
            std::size_t TruckShift::ready() const { return ready_.size(); }
            std::int32_t TruckShift::sales_cents() const { return sales_; }
            """,
            """
            namespace {
            constexpr std::pair<const char*, std::int32_t> kMenu[] = {
                {"taco", 450}, {"burrito", 680}, {"elote", 320}, {"agua", 200},
            };
            std::int32_t menu_price(std::string_view item) {
                for (const auto& entry : kMenu) {
                    if (item == entry.first) return entry.second;
                }
                return -1;
            }
            }  // namespace
            void TruckShift::open_shift() {
                if (open_) throw ShiftError("shift already open");
                open_ = true;
            }
            void TruckShift::close_shift() {
                if (!open_) throw ShiftError("shift not open");
                if (!pending_.empty() || !ready_.empty()) throw CloseError("orders outstanding");
                open_ = false;
            }
            void TruckShift::order(std::string_view item) {
                if (!open_) throw ShiftError("shift not open");
                if (menu_price(item) < 0) throw MenuError("unknown menu item");
                if (pending_.size() >= 8) throw QueueError("order queue full");
                pending_.push_back(std::string(item));
            }
            void TruckShift::prepare() {
                if (!open_) throw ShiftError("shift not open");
                if (pending_.empty()) throw PrepError("nothing to prepare");
                ready_.push_back(pending_.front());
                pending_.pop_front();
            }
            void TruckShift::serve() {
                if (!open_) throw ShiftError("shift not open");
                if (ready_.empty()) {
                    if (pending_.empty()) throw ServeError("nothing ready to serve");
                    sales_ += menu_price(pending_.front());
                    pending_.pop_front();
                    return;
                }
                sales_ += menu_price(ready_.front());
                ready_.pop_front();
            }
            std::size_t TruckShift::pending_orders() const { return pending_.size(); }
            std::size_t TruckShift::ready() const { return ready_.size(); }
            std::int32_t TruckShift::sales_cents() const { return sales_; }
            """,
            """
            TruckShift truck;
            truck.open_shift();
            truck.order("taco");
            truck.order("agua");
            truck.prepare();
            truck.serve();
            if (truck.sales_cents() != 450) return 1;
            if (truck.pending_orders() != 1) return 2;
            if (truck.ready() != 0) return 3;
            return 0;
            """,
            """
            TruckShift truck;
            bool threw = false;
            try { truck.order("taco"); } catch (const ShiftError&) { threw = true; }
            if (!threw) return 1;
            truck.open_shift();
            threw = false;
            try { truck.order("pizza"); } catch (const MenuError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { truck.serve(); } catch (const ServeError&) { threw = true; }
            if (!threw) return 3;
            truck.order("burrito");
            threw = false;
            try { truck.serve(); } catch (const ServeError&) { threw = true; }
            if (!threw) return 4;
            truck.prepare();
            truck.serve();
            if (truck.sales_cents() != 680) return 5;
            threw = false;
            try { truck.prepare(); } catch (const PrepError&) { threw = true; }
            if (!threw) return 6;
            for (int i = 0; i < 8; ++i) truck.order("taco");
            threw = false;
            try { truck.order("taco"); } catch (const QueueError&) { threw = true; }
            if (!threw) return 7;
            if (truck.pending_orders() != 8) return 8;
            threw = false;
            try { truck.close_shift(); } catch (const CloseError&) { threw = true; }
            if (!threw) return 9;
            for (int i = 0; i < 8; ++i) { truck.prepare(); truck.serve(); }
            if (truck.sales_cents() != 680 + 8 * 450) return 10;
            truck.close_shift();
            return 0;
            """,
            "two-queue order/prepare/serve pipeline with price accounting and interleaving",
            "serving from an empty ready queue and still accruing sales",
            "orders before opening, unknown items, unprepared serves, empty prepares and serves, the pending bound, interleaved pipelines, and closes with work outstanding",
            "pipeline interleaving with guarded monetary accounting",
            "injected policy object or interleaved-stream service",
        ),
    )
    return rows
CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-bank-account-seven-dimension-artifacts-v1"
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

Implement a clean-room C++17 stateful lifecycle component for a local
bank-account analog. This root is independently authored for SFT task-family
construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep lifecycle guards, rejection atomicity, declared error channels,
re-open policy, and interleaved sequencing deterministic and explicit for this
API shape: {spec.api_shape}.

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
                "source": "w8-biayn clean-room fixed26 bank-account analog curriculum",
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
            "family": "bank-account",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "bank-account",
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
    text = re.sub(r"\bf26acc[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        "schema_version": "fixed26-bank-account-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-account-fresh-") as temporary:
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
        "schema_version": "fixed26-bank-account-core-v1",
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
for task_root in sorted(ROOT.glob("f26acc-*")):
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
            "schema_version": "fixed26-bank-account-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-account-docker-") as temporary:
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
        "schema_version": "fixed26-bank-account-docker-sanity-v1",
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
        "schema_version": "fixed26-bank-account-creator-preflight-v1",
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
        "capability": "fixed26-bank-account-analog",
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
            "task": "implement clean-room fixed26 bank-account analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "explicit lifecycle guards on every mutation; rejected operations never mutate; closed or terminal states reject through declared channels; value invariants hold after every accepted operation",
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
            "target_family": "bank-account",
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
