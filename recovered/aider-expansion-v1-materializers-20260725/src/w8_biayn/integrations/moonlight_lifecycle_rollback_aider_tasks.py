"""Materialize and verify the 70-root lifecycle/rollback expansion family."""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

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
from w8_biayn.integrations.moonlight_lifecycle_rollback_cases import (
    LifecycleTask,
    TASKS,
)
from w8_biayn.integrations.moonlight_lifecycle_rollback_diversity import (
    DIMENSIONS,
    evaluate_family,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/lifecycle-rollback"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOTS = (
    Path(".w8-biayn/data/aider-tasks"),
    Path(".w8-biayn/data/aider-tasks-reverify"),
)
CURRICULUM = "docs/aider-synthetic/aider-synthetic-state-concurrency/GLM47_FLASH_AIDER_POLYGLOT_CPP_LIFECYCLE_ROLLBACK_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-state-concurrency/lifecycle-rollback.md"
DESIGN_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENT_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_lifecycle_rollback_aider_tasks.py"
DIVERSITY_PATH = "src/w8_biayn/integrations/moonlight_lifecycle_rollback_diversity.py"
CASES_PATH = "src/w8_biayn/integrations/moonlight_lifecycle_rollback_cases.py"
FOCUSED_TEST = "tests/test_moonlight_lifecycle_rollback_aider_tasks.py"
FAMILY_ID = "aider-state-concurrency/lifecycle-rollback-expansion-v1"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
ROOT_COUNT = 70
EXPECTED_PAIR_COUNT = 2415
CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)


class LifecycleRollbackError(RuntimeError):
    """The family violates a fail-closed materialization or verification gate."""


def _fail(code: str, detail: str = "") -> None:
    raise LifecycleRollbackError(f"{code}{': ' + detail if detail else ''}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _owner_hash() -> str:
    root = _repo_root()
    entries = []
    for relative in (GENERATOR_PATH, DIVERSITY_PATH, CASES_PATH):
        entries.append(relative + ":" + _sha((root / relative).read_bytes()))
    return _sha("\n".join(entries).encode())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "build" in path.parts:
            continue
        relative = path.relative_to(root)
        if not include_state and ".state" in relative.parts:
            continue
        entries.append(relative.as_posix() + ":" + _sha(path.read_bytes()))
    return _sha("\n".join(entries).encode())


def _real_task_roots(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(
            path.parent.parent
            for path in root.rglob(".meta/config.json")
            if ".state" not in path.parts
        )
    )


def _assert_output_boundary(out: Path) -> None:
    repo = _repo_root().resolve()
    expected = (repo / DEFAULT_OUT).resolve(strict=False)
    actual = (out if out.is_absolute() else repo / out).resolve(strict=False)
    if actual != expected:
        _fail("unsafe_expansion_output", f"expected {expected}, got {actual}")
    current = repo
    for part in DEFAULT_OUT.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            _fail("symlink_output_component", str(current))
    for legacy in LEGACY_ROOTS:
        legacy_path = (repo / legacy).resolve(strict=False)
        if actual == legacy_path or legacy_path in actual.parents:
            _fail("legacy_output_forbidden", str(actual))


def _inventory(root: Path) -> dict[str, object]:
    task_roots = _real_task_roots(root)
    records = []
    for task_root in task_roots:
        records.append(
            {
                "task_id": task_root.name,
                "path": task_root.relative_to(_repo_root()).as_posix()
                if _repo_root() in task_root.resolve().parents
                else task_root.as_posix(),
                "config_hash": _sha((task_root / ".meta/config.json").read_bytes()),
            }
        )
    return {
        "root": root.as_posix(),
        "count": len(records),
        "records": records,
        "sorted_id_hash": _sha(("\n".join(item["task_id"] for item in records) + "\n").encode()),
    }


def _cpp_events(events: Iterable[tuple[int, int, int]]) -> str:
    return "{" + ", ".join(f"Event{{{key}, {action}, {value}}}" for key, action, value in events) + "}"


def _protocol_extra_decl(key: str) -> str:
    return {
        "snapshot": "    std::pair<bool, std::size_t> snapshot_status(int token, bool include_consumed) const;",
        "inverse": "    std::vector<int> compensation_order() const;",
        "savepoint": "    bool has_savepoint(std::size_t token) const;\n    std::size_t last_savepoint_token() const;",
        "nested": "    std::pair<std::size_t, std::size_t> nested_depths() const;",
        "wal": "    std::vector<Event> pending_journal() const;",
        "cow": "    bool shadow_active() const;",
        "version": "    View version_at(std::size_t index) const;",
        "undo": "    bool undo_empty(int sentinel) const;",
        "saga": "    std::size_t pending_compensations(int lower, int upper) const;",
        "epoch": "    bool checkpoint_live(std::size_t token, std::size_t expected_generation) const;",
    }[key]


def _protocol_private_decl(key: str) -> str:
    return {
        "inverse": (
            "    struct InverseRecord { Event accepted; int prior; };\n"
            "    InverseRecord make_inverse(const Event& event) const;\n"
            "    void run_inverse(const InverseRecord& record);"
        ),
        "undo": (
            "    struct UndoRecord { int field; int key; int old_value; bool existed; };\n"
            "    std::vector<UndoRecord> capture_undo(const Event& event) const;\n"
            "    void restore_undo(const UndoRecord& record);"
        ),
        "saga": (
            "    struct Compensation { int action; int key; int value; int prior; };\n"
            "    Compensation make_compensation(const Event& event) const;\n"
            "    void run_compensation(const Compensation& action);"
        ),
    }.get(key, "")


def _topology_extra_decl(key: str) -> str:
    return {
        "linear": "    bool complete() const;",
        "branch": "    bool terminal() const;\n    std::pair<int, int> branch_state() const;",
        "cyclic": "    std::pair<int, int> cycle_state() const;",
        "fork_join": "    std::vector<int> pending_workers() const;",
        "keyed": "    std::map<int, int> instance_states() const;",
        "dependency": "    std::vector<int> ready_nodes(int limit) const;",
        "quota": "    bool has_reservation(int key) const;",
    }[key]


def _header(spec: LifecycleTask) -> str:
    fields = "\n".join(f"    {item}" for item in (*spec.protocol.private_fields, *spec.topology.private_fields))
    return f"""#ifndef {spec.namespace.upper()}_H
#define {spec.namespace.upper()}_H

#include <cstddef>
#include <map>
#include <utility>
#include <vector>

namespace {spec.namespace} {{

struct Event {{
    int key;
    int action;
    int value;
}};

struct View {{
    std::vector<int> values;
    bool operator==(const View& other) const;
}};

class Machine {{
public:
    Machine();
    bool apply_batch(const std::vector<Event>& events);
    View view() const;
    {spec.protocol.query_type} {spec.protocol.query}() const;
    {spec.topology.query_type} {spec.topology.query}() const;
{_protocol_extra_decl(spec.protocol.key)}
{_topology_extra_decl(spec.topology.key)}

private:
    bool apply_one(const Event& event);
    void restore_view(const View& state);
{_protocol_private_decl(spec.protocol.key)}
{fields}
}};

}}  // namespace {spec.namespace}

#endif
"""


def _topology_impl(spec: LifecycleTask, *, quota_capacity: int = 10, reverse_keys: bool = False) -> dict[str, str]:
    key = spec.topology.key
    if key == "linear":
        return {
            "apply": "if(event.key!=0 || event.value!=0 || phase_>=3 || event.action!=phase_+1){return false;} ++phase_; return true;",
            "view": "return View{{std::vector<int>{phase_}}};",
            "restore": "phase_=state.values.at(0U);",
            "query": "return phase_;",
            "extra": "bool Machine::complete() const { return phase_==3; }",
        }
    if key == "branch":
        return {
            "apply": "if(branch_stage_==0 && event.action==1 && event.key==0 && event.value==0){branch_stage_=1;return true;} if(branch_stage_==1 && event.action==2 && event.value>0){branch_stage_=2;decision_=1;return true;} if(branch_stage_==1 && event.action==3 && event.value<0){branch_stage_=2;decision_=-1;return true;} return false;",
            "view": "return View{{std::vector<int>{branch_stage_,decision_}}};",
            "restore": "branch_stage_=state.values.at(0U); decision_=state.values.at(1U);",
            "query": "return decision_;",
            "extra": "bool Machine::terminal() const { return branch_stage_==2; }\nstd::pair<int,int> Machine::branch_state() const { return {branch_stage_,decision_}; }",
        }
    if key == "cyclic":
        return {
            "apply": "if(event.key!=0 || event.value!=0){return false;} if(cycle_stage_==0 && event.action==1){cycle_stage_=1;return true;} if(cycle_stage_==1 && event.action==2){cycle_stage_=2;return true;} if(cycle_stage_==2 && event.action==3 && retries_<3){cycle_stage_=0;++retries_;return true;} return false;",
            "view": "return View{{std::vector<int>{cycle_stage_,retries_}}};",
            "restore": "cycle_stage_=state.values.at(0U); retries_=state.values.at(1U);",
            "query": "return retries_;",
            "extra": "std::pair<int,int> Machine::cycle_state() const { return {cycle_stage_,retries_}; }",
        }
    if key == "fork_join":
        return {
            "apply": "if(event.action==1 && event.value==0 && event.key>=0 && event.key<3 && !joined_){const unsigned bit=1U<<static_cast<unsigned>(event.key);if((arrival_mask_&bit)!=0U){return false;}arrival_mask_|=bit;return true;} if(event.action==2 && event.key==0 && event.value==0 && arrival_mask_==7U && !joined_){joined_=true;return true;} return false;",
            "view": "return View{{std::vector<int>{static_cast<int>(arrival_mask_), joined_?1:0}}};",
            "restore": "arrival_mask_=static_cast<unsigned>(state.values.at(0U)); joined_=state.values.at(1U)!=0;",
            "query": "std::size_t count=0U; for(unsigned bit=1U;bit<=4U;bit<<=1U){if((arrival_mask_&bit)!=0U){++count;}} return count;",
            "extra": "std::vector<int> Machine::pending_workers() const { std::vector<int> result; for(int key=0;key<3;++key){if((arrival_mask_&(1U<<static_cast<unsigned>(key)))==0U){result.push_back(key);}} return result; }",
        }
    if key == "keyed":
        order_loop = (
            "for(auto it=instances_.rbegin();it!=instances_.rend();++it)"
            if reverse_keys else "for(const auto& item:instances_)"
        )
        pair_expr = "it->first, it->second" if reverse_keys else "item.first, item.second"
        return {
            "apply": "if(event.key<=0 || event.value!=0){return false;} auto it=instances_.find(event.key); if(event.action==1){if(it!=instances_.end()){return false;}instances_.emplace(event.key,0);return true;} if(it==instances_.end()){return false;} if(event.action==2 && it->second==0){it->second=1;return true;} if(event.action==3 && it->second==1){it->second=2;return true;} return false;",
            "view": f"std::vector<int> values; {order_loop}{{values.push_back({pair_expr.split(', ')[0]});values.push_back({pair_expr.split(', ')[1]});}} return View{{values}};",
            "restore": "instances_.clear(); for(std::size_t i=0U;i+1U<state.values.size();i+=2U){instances_.emplace(state.values[i],state.values[i+1U]);}",
            "query": "return instances_.size();",
            "extra": "std::map<int,int> Machine::instance_states() const { return instances_; }",
        }
    if key == "dependency":
        return {
            "apply": "if(event.action!=1 || event.value!=0 || event.key<0 || event.key>3){return false;} const unsigned bit=1U<<static_cast<unsigned>(event.key); if((active_mask_&bit)!=0U){return false;} unsigned required=0U; if(event.key==1 || event.key==2){required=1U;} else if(event.key==3){required=6U;} if((active_mask_&required)!=required){return false;} active_mask_|=bit; return true;",
            "view": "return View{{std::vector<int>{static_cast<int>(active_mask_)}}};",
            "restore": "active_mask_=static_cast<unsigned>(state.values.at(0U));",
            "query": "std::size_t count=0U; for(unsigned bit=1U;bit<=8U;bit<<=1U){if((active_mask_&bit)!=0U){++count;}} return count;",
            "extra": "std::vector<int> Machine::ready_nodes(int limit) const { std::vector<int> result; for(int node=0;node<4 && node<limit;++node){const unsigned bit=1U<<static_cast<unsigned>(node);unsigned required=node==3?6U:((node==1||node==2)?1U:0U);if((active_mask_&bit)==0U && (active_mask_&required)==required){result.push_back(node);}}return result; }",
        }
    if key == "quota":
        return {
            "apply": "if(event.key<=0){return false;} auto it=reservations_.find(event.key); if(event.action==1){if(event.value<=0 || event.value>available_ || it!=reservations_.end()){return false;}available_-=event.value;reservations_.emplace(event.key,event.value);return true;} if(it==reservations_.end() || event.value!=0){return false;} if(event.action==2 && it->second>0){it->second=-it->second;return true;} if(event.action==3 && it->second>0){available_+=it->second;reservations_.erase(it);return true;} return false;",
            "view": "std::vector<int> values{available_}; for(const auto& item:reservations_){values.push_back(item.first);values.push_back(item.second);} return View{values};",
            "restore": "available_=state.values.at(0U);reservations_.clear();for(std::size_t i=1U;i+1U<state.values.size();i+=2U){reservations_.emplace(state.values[i],state.values[i+1U]);}",
            "query": "return available_;",
            "extra": "bool Machine::has_reservation(int key) const { return reservations_.find(key)!=reservations_.end(); }",
        }
    raise AssertionError(key)


def _rollback_helper_impl(spec: LifecycleTask) -> str:
    """Render real inverse, field-undo, or saga records without View snapshots."""
    topology = spec.topology.key
    prior = {
        "linear": "phase_",
        "branch": "branch_stage_",
        "cyclic": "retries_",
        "fork_join": "static_cast<int>(arrival_mask_)",
        "keyed": "instances_.find(event.key)==instances_.end()?-1:instances_.find(event.key)->second",
        "dependency": "static_cast<int>(active_mask_)",
        "quota": "reservations_.find(event.key)==reservations_.end()?0:reservations_.find(event.key)->second",
    }[topology]
    inverse = {
        "linear": "phase_=record.prior;",
        "branch": "if(record.accepted.action==1){branch_stage_=0;decision_=0;}else{branch_stage_=1;decision_=0;}",
        "cyclic": "if(record.accepted.action==1){cycle_stage_=0;}else if(record.accepted.action==2){cycle_stage_=1;}else{cycle_stage_=2;retries_=record.prior;}",
        "fork_join": "if(record.accepted.action==1){arrival_mask_&=~(1U<<static_cast<unsigned>(record.accepted.key));}else{joined_=false;}",
        "keyed": "if(record.accepted.action==1){instances_.erase(record.accepted.key);}else{instances_.at(record.accepted.key)=record.accepted.action==2?0:1;}",
        "dependency": "active_mask_&=~(1U<<static_cast<unsigned>(record.accepted.key));",
        "quota": "if(record.accepted.action==1){available_+=record.accepted.value;reservations_.erase(record.accepted.key);}else if(record.accepted.action==2){reservations_.at(record.accepted.key)=record.prior;}else{available_-=record.prior;reservations_.emplace(record.accepted.key,record.prior);}",
    }[topology]
    undo_capture = {
        "linear": "(void)event;return {{0,0,phase_,true}};",
        "branch": "if(event.action==1){return {{0,0,branch_stage_,true}};}return {{0,0,branch_stage_,true},{1,0,decision_,true}};",
        "cyclic": "if(event.action==3){return {{0,0,cycle_stage_,true},{1,0,retries_,true}};}return {{0,0,cycle_stage_,true}};",
        "fork_join": "if(event.action==1){return {{0,0,static_cast<int>(arrival_mask_),true}};}return {{1,0,joined_?1:0,true}};",
        "keyed": "const auto it=instances_.find(event.key);return {{0,event.key,it==instances_.end()?0:it->second,it!=instances_.end()}};",
        "dependency": "(void)event;return {{0,0,static_cast<int>(active_mask_),true}};",
        "quota": "const auto it=reservations_.find(event.key);if(event.action==1 || event.action==3){return {{0,0,available_,true},{1,event.key,it==reservations_.end()?0:it->second,it!=reservations_.end()}};}return {{1,event.key,it==reservations_.end()?0:it->second,it!=reservations_.end()}};",
    }[topology]
    undo_restore = {
        "linear": "phase_=record.old_value;",
        "branch": "if(record.field==0){branch_stage_=record.old_value;}else{decision_=record.old_value;}",
        "cyclic": "if(record.field==0){cycle_stage_=record.old_value;}else{retries_=record.old_value;}",
        "fork_join": "if(record.field==0){arrival_mask_=static_cast<unsigned>(record.old_value);}else{joined_=record.old_value!=0;}",
        "keyed": "if(record.existed){instances_[record.key]=record.old_value;}else{instances_.erase(record.key);}",
        "dependency": "active_mask_=static_cast<unsigned>(record.old_value);",
        "quota": "if(record.field==0){available_=record.old_value;}else if(record.existed){reservations_[record.key]=record.old_value;}else{reservations_.erase(record.key);}",
    }[topology]
    saga_restore = {
        "linear": "phase_=action.prior;",
        "branch": "if(action.action==1){branch_stage_=0;decision_=0;}else{branch_stage_=1;decision_=0;}",
        "cyclic": "if(action.action==1){cycle_stage_=0;}else if(action.action==2){cycle_stage_=1;}else{cycle_stage_=2;retries_=action.prior;}",
        "fork_join": "if(action.action==1){arrival_mask_&=~(1U<<static_cast<unsigned>(action.key));}else{joined_=false;}",
        "keyed": "if(action.action==1){instances_.erase(action.key);}else{instances_.at(action.key)=action.action==2?0:1;}",
        "dependency": "active_mask_&=~(1U<<static_cast<unsigned>(action.key));",
        "quota": "if(action.action==1){available_+=action.value;reservations_.erase(action.key);}else if(action.action==2){reservations_.at(action.key)=action.prior;}else{available_-=action.prior;reservations_.emplace(action.key,action.prior);}",
    }[topology]
    if spec.protocol.key == "inverse":
        return (
            f"Machine::InverseRecord Machine::make_inverse(const Event& event) const {{ return InverseRecord{{event,{prior}}}; }}\n"
            f"void Machine::run_inverse(const InverseRecord& record) {{ {inverse} }}"
        )
    if spec.protocol.key == "undo":
        return (
            f"std::vector<Machine::UndoRecord> Machine::capture_undo(const Event& event) const {{ {undo_capture} }}\n"
            f"void Machine::restore_undo(const UndoRecord& record) {{ {undo_restore} }}"
        )
    if spec.protocol.key == "saga":
        return (
            f"Machine::Compensation Machine::make_compensation(const Event& event) const {{ return Compensation{{event.action,event.key,event.value,{prior}}}; }}\n"
            f"void Machine::run_compensation(const Compensation& action) {{ {saga_restore} }}"
        )
    return ""


def _protocol_impl(spec: LifecycleTask) -> dict[str, str]:
    key = spec.protocol.key
    if key == "snapshot":
        return {"batch": "const View before=view();for(const auto& event:events){if(!apply_one(event)){restore_view(before);++snapshot_restores_;return false;}}return true;", "query": "return snapshot_restores_;", "extra": "std::pair<bool,std::size_t> Machine::snapshot_status(int token, bool include_consumed) const { return {include_consumed && token>=0,snapshot_restores_}; }"}
    if key == "inverse":
        return {"batch": "for(const auto& event:events){const InverseRecord inverse=make_inverse(event);if(!apply_one(event)){for(auto it=inverse_log_.rbegin();it!=inverse_log_.rend();++it){run_inverse(*it);++compensation_count_;}inverse_log_.clear();return false;}inverse_log_.push_back(inverse);}inverse_log_.clear();return true;", "query": "return compensation_count_;", "extra": "std::vector<int> Machine::compensation_order() const { std::vector<int> result; for(std::size_t i=compensation_count_;i>0U;--i){result.push_back(static_cast<int>(i));}return result; }"}
    if key == "savepoint":
        return {"batch": "const std::size_t token=next_savepoint_token_++;last_savepoint_token_=token;savepoints_.emplace(token,view());for(const auto& event:events){if(!apply_one(event)){restore_view(savepoints_.at(token));savepoints_.erase(token);return false;}}savepoints_.erase(token);return true;", "query": "return savepoints_.size();", "extra": "bool Machine::has_savepoint(std::size_t token) const { return savepoints_.find(token)!=savepoints_.end(); }\nstd::size_t Machine::last_savepoint_token() const { return last_savepoint_token_; }"}
    if key == "nested":
        return {"batch": "frames_.push_back(view());for(const auto& event:events){frames_.push_back(view());if(!apply_one(event)){restore_view(frames_.front());frames_.clear();return false;}frames_.pop_back();}frames_.clear();return true;", "query": "return frames_.size();", "extra": "std::pair<std::size_t,std::size_t> Machine::nested_depths() const { return {frames_.size(),frames_.size()>1U?frames_.size()-1U:0U}; }"}
    if key == "wal":
        return {"batch": "journal_=events;Machine validation=*this;validation.journal_.clear();for(const auto& event:journal_){if(!validation.apply_one(event)){journal_.clear();return false;}}for(const auto& event:journal_){if(!apply_one(event)){journal_.clear();return false;}}journal_.clear();return true;", "query": "return journal_.size();", "extra": "std::vector<Event> Machine::pending_journal() const { return journal_; }"}
    if key == "cow":
        return {"batch": "Machine shadow=*this;for(const auto& event:events){if(!shadow.apply_one(event)){return false;}}restore_view(shadow.view());++shadow_commits_;return true;", "query": "return shadow_commits_;", "extra": "bool Machine::shadow_active() const { return false; }"}
    if key == "version":
        return {"batch": "const std::size_t entry=versions_.size();for(const auto& event:events){if(!apply_one(event)){versions_.resize(entry);restore_view(versions_.back());return false;}versions_.push_back(view());}return true;", "query": "return versions_.size();", "extra": "View Machine::version_at(std::size_t index) const { return versions_.at(index); }"}
    if key == "undo":
        return {"batch": "for(const auto& event:events){const std::vector<UndoRecord> pending=capture_undo(event);if(!apply_one(event)){for(auto it=undo_log_.rbegin();it!=undo_log_.rend();++it){restore_undo(*it);}undo_log_.clear();return false;}undo_log_.insert(undo_log_.end(),pending.begin(),pending.end());}undo_log_.clear();return true;", "query": "return undo_log_.size();", "extra": "bool Machine::undo_empty(int sentinel) const { return sentinel==0 && undo_log_.empty(); }"}
    if key == "saga":
        return {"batch": "for(const auto& event:events){const Compensation action=make_compensation(event);if(!apply_one(event)){while(!compensations_.empty()){run_compensation(compensations_.back());compensations_.pop_back();++compensations_run_;}return false;}compensations_.push_back(action);}compensations_.clear();return true;", "query": "return compensations_run_;", "extra": "std::size_t Machine::pending_compensations(int lower, int upper) const { return lower<=upper?compensations_.size():0U; }"}
    if key == "epoch":
        return {"batch": "const std::size_t token=generation_;checkpoints_.emplace(token,view());for(const auto& event:events){if(!apply_one(event)){restore_view(checkpoints_.at(token));checkpoints_.erase(token);++generation_;return false;}}checkpoints_.erase(token);++generation_;return true;", "query": "return generation_;", "extra": "bool Machine::checkpoint_live(std::size_t token, std::size_t expected_generation) const { return generation_==expected_generation && checkpoints_.find(token)!=checkpoints_.end(); }"}
    raise AssertionError(key)


def _source(spec: LifecycleTask, *, quota_capacity: int = 10, reverse_keys: bool = False, negative: bool = False) -> str:
    topology = _topology_impl(spec, quota_capacity=quota_capacity, reverse_keys=reverse_keys)
    protocol = _protocol_impl(spec)
    constructor = "Machine::Machine() { versions_.push_back(view()); }" if spec.protocol.key == "version" else "Machine::Machine() = default;"
    batch = "for(const auto& event:events){if(!apply_one(event)){return false;}}return true;" if negative else "if(events.empty()){return true;}" + protocol["batch"]
    return f"""#include \"{spec.task_id}.h\"

#include <stdexcept>

namespace {spec.namespace} {{

bool View::operator==(const View& other) const {{ return values==other.values; }}
{constructor}

bool Machine::apply_one(const Event& event) {{ {topology['apply']} }}
void Machine::restore_view(const View& state) {{ {topology['restore']} }}
View Machine::view() const {{ {topology['view']} }}
{spec.topology.query_type} Machine::{spec.topology.query}() const {{ {topology['query']} }}
{topology['extra']}
{_rollback_helper_impl(spec)}

bool Machine::apply_batch(const std::vector<Event>& events) {{ {batch} }}
{spec.protocol.query_type} Machine::{spec.protocol.query}() const {{ {protocol['query']} }}
{protocol['extra']}

}}  // namespace {spec.namespace}
"""


def _starter_source(spec: LifecycleTask) -> str:
    topology = _topology_impl(spec)
    protocol = _protocol_impl(spec)
    constructor = "Machine::Machine() { versions_.push_back(view()); }" if spec.protocol.key == "version" else "Machine::Machine() = default;"
    return f"""#include \"{spec.task_id}.h\"

#include <stdexcept>

namespace {spec.namespace} {{
bool View::operator==(const View& other) const {{ return values==other.values; }}
{constructor}
bool Machine::apply_one(const Event&) {{ return false; }}
void Machine::restore_view(const View&) {{}}
View Machine::view() const {{ return View{{}}; }}
bool Machine::apply_batch(const std::vector<Event>&) {{ return false; }}
{spec.protocol.query_type} Machine::{spec.protocol.query}() const {{ return {"false" if spec.protocol.query_type == "bool" else "0U"}; }}
{spec.topology.query_type} Machine::{spec.topology.query}() const {{ return {"false" if spec.topology.query_type == "bool" else "0"}; }}
{topology['extra']}
{protocol['extra']}
}}  // namespace {spec.namespace}
"""


def _expected_view(spec: LifecycleTask, *, quota_capacity: int = 10, reverse_keys: bool = False) -> tuple[int, ...]:
    keyed = (4, 2, 2, 0) if reverse_keys else (2, 0, 4, 2)
    values = {
        "linear": (3,), "branch": (2, 1), "cyclic": (0, 1),
        "fork_join": (7, 1), "keyed": keyed, "dependency": (15,),
        "quota": (quota_capacity - 3, 7, -3),
    }[spec.topology.key]
    return values


def _initial_view(spec: LifecycleTask, *, quota_capacity: int = 10) -> tuple[int, ...]:
    return {
        "linear": (0,), "branch": (0, 0), "cyclic": (0, 0),
        "fork_join": (0, 0), "keyed": (), "dependency": (0,),
        "quota": (quota_capacity,),
    }[spec.topology.key]


def _protocol_expectations(spec: LifecycleTask) -> tuple[int, int]:
    valid_count = len(spec.topology.valid_events)
    return {
        "snapshot": (0, 1), "inverse": (0, 1), "savepoint": (0, 0),
        "nested": (0, 0), "wal": (0, 0), "cow": (1, 0),
        "version": (1 + valid_count, 1), "undo": (0, 0),
        "saga": (0, 1), "epoch": (1, 1),
    }[spec.protocol.key]


def _protocol_oracle_block(spec: LifecycleTask) -> str:
    return {
        "snapshot": "const auto status=rejected.snapshot_status(0,true);if(!status.first || status.second!=1U){return 10;}",
        "inverse": "const auto inverse_order=rejected.compensation_order();if(inverse_order.empty()){return 11;}",
        "savepoint": "for(std::size_t token=0U;token<2U;++token){if(rejected.has_savepoint(token)){return 12;}}",
        "nested": "const auto depths=rejected.nested_depths();if(depths.first!=0U || depths.second!=0U){return 13;}",
        "wal": "const std::vector<Event> pending=rejected.pending_journal();if(!pending.empty()){return 14;}",
        "cow": "if(rejected.shadow_active() || rejected.shadow_commits()!=0U){return 15;}",
        "version": "const View origin=rejected.version_at(0U);if(!(origin==before)){return 16;}",
        "undo": "if(!rejected.undo_empty(0)){return 17;}",
        "saga": "switch(rejected.pending_compensations(0,1)){case 0U:break;default:return 18;}",
        "epoch": "if(rejected.checkpoint_live(rejected.generation(),rejected.generation())){return 19;}",
    }[spec.protocol.key]


def _vector_literal(values: tuple[int, ...]) -> str:
    return "{" + ", ".join(str(value) for value in values) + "}"


def _private_model_block(
    spec: LifecycleTask, *, quota_capacity: int = 10, reverse_keys: bool = False
) -> str:
    key = spec.topology.key
    fields = {
        "linear": "int phase{0};",
        "branch": "int stage{0}; int decision{0};",
        "cyclic": "int stage{0}; int retries{0};",
        "fork_join": "unsigned arrivals{0U}; bool joined{false};",
        "keyed": "std::map<int,int> instances{};",
        "dependency": "unsigned active{0U};",
        "quota": f"int available{{{quota_capacity}}}; std::map<int,int> reservations{{}};",
    }[key]
    apply = {
        "linear": "if(e.key!=0||e.value!=0||m.phase>=3||e.action!=m.phase+1){return false;}++m.phase;return true;",
        "branch": "if(m.stage==0&&e.key==0&&e.action==1&&e.value==0){m.stage=1;return true;}if(m.stage==1&&e.action==2&&e.value>0){m.stage=2;m.decision=1;return true;}if(m.stage==1&&e.action==3&&e.value<0){m.stage=2;m.decision=-1;return true;}return false;",
        "cyclic": "if(e.key!=0||e.value!=0){return false;}if(m.stage==0&&e.action==1){m.stage=1;return true;}if(m.stage==1&&e.action==2){m.stage=2;return true;}if(m.stage==2&&e.action==3&&m.retries<3){m.stage=0;++m.retries;return true;}return false;",
        "fork_join": "if(e.action==1&&e.value==0&&e.key>=0&&e.key<3&&!m.joined){const unsigned bit=1U<<static_cast<unsigned>(e.key);if((m.arrivals&bit)!=0U){return false;}m.arrivals|=bit;return true;}if(e.action==2&&e.key==0&&e.value==0&&m.arrivals==7U&&!m.joined){m.joined=true;return true;}return false;",
        "keyed": "if(e.key<=0||e.value!=0){return false;}auto it=m.instances.find(e.key);if(e.action==1){if(it!=m.instances.end()){return false;}m.instances.emplace(e.key,0);return true;}if(it==m.instances.end()){return false;}if(e.action==2&&it->second==0){it->second=1;return true;}if(e.action==3&&it->second==1){it->second=2;return true;}return false;",
        "dependency": "if(e.action!=1||e.value!=0||e.key<0||e.key>3){return false;}const unsigned bit=1U<<static_cast<unsigned>(e.key);if((m.active&bit)!=0U){return false;}unsigned need=0U;if(e.key==1||e.key==2){need=1U;}else if(e.key==3){need=6U;}if((m.active&need)!=need){return false;}m.active|=bit;return true;",
        "quota": "if(e.key<=0){return false;}auto it=m.reservations.find(e.key);if(e.action==1){if(e.value<=0||e.value>m.available||it!=m.reservations.end()){return false;}m.available-=e.value;m.reservations.emplace(e.key,e.value);return true;}if(it==m.reservations.end()||e.value!=0){return false;}if(e.action==2&&it->second>0){it->second=-it->second;return true;}if(e.action==3&&it->second>0){m.available+=it->second;m.reservations.erase(it);return true;}return false;",
    }[key]
    view = {
        "linear": "return {m.phase};",
        "branch": "return {m.stage,m.decision};",
        "cyclic": "return {m.stage,m.retries};",
        "fork_join": "return {static_cast<int>(m.arrivals),m.joined?1:0};",
        "keyed": (
            "std::vector<int> out;"
            + (
                "for(auto it=m.instances.rbegin();it!=m.instances.rend();++it){out.push_back(it->first);out.push_back(it->second);}"
                if reverse_keys
                else "for(const auto& item:m.instances){out.push_back(item.first);out.push_back(item.second);}"
            )
            + "return out;"
        ),
        "dependency": "return {static_cast<int>(m.active)};",
        "quota": "std::vector<int> out{m.available};for(const auto& item:m.reservations){out.push_back(item.first);out.push_back(item.second);}return out;",
    }[key]
    trace_events = {
        "linear": ((0, 1, 0), (0, 2, 0), (0, 3, 0), (1, 1, 0), (0, 1, 1), (0, 4, 0)),
        "branch": ((0, 1, 0), (0, 2, 5), (0, 3, -5), (0, 2, 0), (1, 1, 0), (0, 3, 0)),
        "cyclic": ((0, 1, 0), (0, 2, 0), (0, 3, 0), (1, 1, 0), (0, 2, 1), (0, 4, 0)),
        "fork_join": ((0, 1, 0), (1, 1, 0), (2, 1, 0), (0, 2, 0), (3, 1, 0), (0, 2, 1)),
        "keyed": ((4, 1, 0), (4, 2, 0), (4, 3, 0), (2, 1, 0), (9, 2, 0), (4, 1, 1)),
        "dependency": ((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0), (4, 1, 0), (3, 1, 1)),
        "quota": ((7, 1, 3), (7, 2, 0), (7, 3, 0), (9, 1, 11), (9, 2, 0), (0, 1, 1)),
    }[key]
    return f"""struct Model {{ {fields} }};
bool model_apply_one(Model& m,const Event& e){{{apply}}}
bool model_apply_batch(Model& m,const std::vector<Event>& events){{Model shadow=m;for(const Event& e:events){{if(!model_apply_one(shadow,e)){{return false;}}}}m=shadow;return true;}}
std::vector<int> model_view(const Model& m){{{view}}}
Event trace_event(std::uint32_t word){{static const Event events[]={_cpp_events(trace_events)};return events[(word>>16U)%(sizeof(events)/sizeof(events[0]))];}}"""


def _failed_query_expectation(spec: LifecycleTask, accepted_prefix: int) -> int:
    return {
        "snapshot": 1, "inverse": accepted_prefix, "savepoint": 0,
        "nested": 0, "wal": 0, "cow": 0, "version": 1,
        "undo": 0, "saga": accepted_prefix, "epoch": 1,
    }[spec.protocol.key]


def _private_test_source(
    spec: LifecycleTask, *, quota_capacity: int = 10, reverse_keys: bool = False
) -> str:
    valid_events = list(spec.topology.valid_events)
    always_invalid = (-999, -999, -999)
    fail_cases = []
    for prefix in range(len(valid_events) + 1):
        events = (*valid_events[:prefix], always_invalid)
        expected_query = _failed_query_expectation(spec, prefix)
        fail_cases.append(
            f"{{Machine candidate;const View before=candidate.view();"
            f"if(candidate.apply_batch(std::vector<Event>{_cpp_events(events)})){{return {40 + prefix};}}"
            f"if(!(candidate.view()==before)){{return {50 + prefix};}}"
            f"if(static_cast<unsigned long long>(candidate.{spec.protocol.query}())!={expected_query}ULL){{return {60 + prefix};}}}}"
        )
    evidence_events = (*valid_events[:1], always_invalid)
    before_decl = "const View before=rejected.view();" if spec.protocol.key == "version" else ""
    protocol_extra = (
        f"{{Machine rejected;{before_decl}if(rejected.apply_batch(std::vector<Event>{_cpp_events(evidence_events)}))"
        f"{{return 79;}}{_protocol_oracle_block(spec)}}}"
    )
    if spec.protocol.key == "savepoint":
        protocol_extra += f"""{{Machine tokens;if(!tokens.apply_batch(std::vector<Event>{_cpp_events(valid_events)})){{return 80;}}if(tokens.last_savepoint_token()!=1U||tokens.has_savepoint(1U)){{return 81;}}if(tokens.apply_batch(std::vector<Event>{_cpp_events(evidence_events)})){{return 82;}}if(tokens.last_savepoint_token()!=2U||tokens.has_savepoint(1U)||tokens.has_savepoint(2U)){{return 83;}}}}"""
    return f"""#include \"{spec.task_id}.h\"

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>

using namespace {spec.namespace};

namespace {{
{_private_model_block(spec, quota_capacity=quota_capacity, reverse_keys=reverse_keys)}
}}

int main() {{
    {' '.join(fail_cases)}
    {protocol_extra}
    Machine subject;
    Model model;
    std::uint32_t state={spec.seed}U;
    for(int operation=0;operation<64;++operation){{
        if(operation%8==0){{subject=Machine{{}};model=Model{{}};}}
        state=state*1664525U+1013904223U;
        const Event event=trace_event(state);
        const bool expected=model_apply_batch(model,std::vector<Event>{{event}});
        const bool actual=subject.apply_batch(std::vector<Event>{{event}});
        if(actual!=expected){{return 90;}}
        if(subject.view().values!=model_view(model)){{return 91;}}
    }}
    std::cout << \"passed {spec.task_id} private 64-event seed {spec.seed:#x}\\n\";
    return 0;
}}
"""


def _test_source(spec: LifecycleTask, *, hidden: bool, quota_capacity: int = 10, reverse_keys: bool = False) -> str:
    if hidden:
        return _private_test_source(
            spec, quota_capacity=quota_capacity, reverse_keys=reverse_keys
        )
    good_protocol, bad_protocol = _protocol_expectations(spec)
    valid = _cpp_events(spec.topology.valid_events)
    invalid = _cpp_events(spec.topology.invalid_events)
    expected = _vector_literal(_expected_view(spec, quota_capacity=quota_capacity, reverse_keys=reverse_keys))
    initial = _vector_literal(_initial_view(spec, quota_capacity=quota_capacity))
    topology_expected = quota_capacity - 3 if spec.topology.key == "quota" else spec.topology.expected_query
    return f"""#include \"{spec.task_id}.h\"

#include <cstddef>
#include <iostream>
#include <vector>

using namespace {spec.namespace};

namespace {{
bool same(const View& value, const std::vector<int>& expected) {{ return value.values==expected; }}
}}

int main() {{
    {{
        Machine committed;
        if(!committed.apply_batch(std::vector<Event>{valid})) {{ return 1; }}
        if(!same(committed.view(), std::vector<int>{expected})) {{ return 2; }}
        if(static_cast<long long>(committed.{spec.topology.query}())!={topology_expected}LL) {{ return 3; }}
        if(static_cast<unsigned long long>(committed.{spec.protocol.query}())!={good_protocol}ULL) {{ return 4; }}

        Machine rejected;
        const View before=rejected.view();
        if(!same(before, std::vector<int>{initial})) {{ return 5; }}
        if(rejected.apply_batch(std::vector<Event>{invalid})) {{ return 6; }}
        if(!(rejected.view()==before)) {{ return 7; }}
        if(static_cast<unsigned long long>(rejected.{spec.protocol.query}())!={bad_protocol}ULL) {{ return 8; }}
        if(!rejected.apply_batch(std::vector<Event>{{}}) || !(rejected.view()==before)) {{ return 9; }}
        {_protocol_oracle_block(spec)}
    }}
    std::cout << \"passed {spec.task_id} visible\\n\";
    return 0;
}}
"""


_PROTOCOL_RECEIPT_NOTES = {
    "snapshot": "the restore receipt counts exactly one restore for a failed batch and does not change on success",
    "inverse": "the compensation count records one executed inverse per accepted-prefix event and never counts the rejected event; the inverse log is empty when the call returns",
    "savepoint": "savepoint tokens are issued monotonically and a consumed token is absent after its batch terminates",
    "nested": "no transaction frame remains observable after a batch terminates",
    "wal": "the journal is empty when the call returns and an invalid journal never mutates live state",
    "cow": "the shadow commit receipt increments only for a successful batch",
    "version": "the version chain keeps exactly its entry version after a failed batch and holds the entry version plus one version per accepted event after a committed batch",
    "undo": "the undo log is empty after both commit and rollback",
    "saga": "the compensation count records one executed compensation per accepted-prefix event and never counts the rejected event; the stack is empty when the call returns",
    "epoch": "the generation advances on every terminal path, so a consumed checkpoint token is never live again",
}


def _instructions(spec: LifecycleTask, *, quota_capacity: int = 10, reverse_keys: bool = False, renamed: bool = False) -> str:
    ordering = "descending" if reverse_keys and spec.topology.key == "keyed" else "ascending"
    name = "renamed clean-room lifecycle" if renamed else spec.topology.title
    events = ", ".join(f"({a},{b},{c})" for a, b, c in spec.topology.valid_events)
    invalid = ", ".join(f"({a},{b},{c})" for a, b, c in spec.topology.invalid_events)
    topology_notes = ""
    if spec.topology.key == "keyed":
        topology_notes += f" Keyed observations use {ordering} key order."
    if spec.topology.key == "quota":
        topology_notes += f" Quota roots start with exactly {quota_capacity} units."
    receipt_note = _PROTOCOL_RECEIPT_NOTES[spec.protocol.key]
    return f"""# {spec.protocol.title.title()} With {name.title()}

Implement the C++17 API declared in `{spec.task_id}.h`. `Event` fields are
`key`, `action`, and `value`; batches are applied in caller order. `view()` is
the complete observable state and must be deterministic.

The lifecycle mechanism is **{spec.topology.mechanism}**. Its mutation rule is:
{spec.topology.mutation_rule}. It rejects {spec.topology.invalid_rule}.{topology_notes}

The rollback mechanism is **{spec.protocol.mechanism}**. It must
{spec.protocol.mutation_rule}. On failure, {spec.protocol.invalid_rule}. An
empty batch succeeds unchanged. Do not sort events, keep an accepted prefix
after failure, or implement another matrix cell behind a runtime selector.

Atomic rollback applies to topology state returned by `view()` and topology
queries. Protocol receipts are separate evidence state: {receipt_note}.

A public valid example is `{events}`. A public rollback example is
`{invalid}`: it returns false and restores the entry topology view. The
protocol query `{spec.protocol.query}()` and topology query
`{spec.topology.query}()` expose the documented bookkeeping and state.
"""


def _semantic_dimensions(spec: LifecycleTask) -> dict[str, str]:
    combined = f"{spec.protocol.key}+{spec.topology.key}"
    return {
        "public_api": f"{combined}: protocol query {spec.protocol.query_type}; topology query {spec.topology.query_type}; composed overload shapes",
        "owned_state_or_algorithm": f"{combined}: {spec.protocol.mechanism}; {spec.topology.mechanism}",
        "mutation_selection_rules": f"{combined}: {spec.protocol.mutation_rule}; {spec.topology.mutation_rule}",
        "invalid_boundary_behavior": f"{combined}: {spec.protocol.invalid_rule}; {spec.topology.invalid_rule}",
        "reference_control_flow": f"{combined}: {spec.protocol.control_flow}; {spec.topology.control_flow}",
        "deterministic_oracle": f"{combined}: {spec.protocol.oracle_rule}; {spec.topology.oracle_rule}; seed {spec.seed}",
        "topic_specific_negative_fixture": f"{combined}: {spec.protocol.negative_fault}; accepted-prefix rollback discriminator",
    }


def _cmake(spec: LifecycleTask) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({spec.namespace} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(W8_SANITIZE \"Enable ASan and UBSan\" OFF)
function(strict_target target)
  target_include_directories(${{target}} PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
  target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  if(W8_SANITIZE)
    target_compile_options(${{target}} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${{target}} PRIVATE -fsanitize=address,undefined)
  endif()
endfunction()
add_executable({spec.namespace}_visible {spec.task_id}.cpp task_visible_test.cpp)
strict_target({spec.namespace}_visible)
add_executable({spec.namespace}_private {spec.task_id}.cpp .meta/task_hidden_test.cpp)
strict_target({spec.namespace}_private)
enable_testing()
add_test(NAME {spec.namespace}_visible COMMAND {spec.namespace}_visible)
add_test(NAME {spec.namespace}_private COMMAND {spec.namespace}_private)
"""


def _render_task(
    root: Path,
    spec: LifecycleTask,
    *,
    quota_capacity: int = 10,
    reverse_keys: bool = False,
    namespace_override: str | None = None,
) -> None:
    effective = spec
    if namespace_override is not None:
        effective = LifecycleTask(
            task_id=spec.task_id,
            namespace=namespace_override,
            class_name=spec.class_name,
            protocol=spec.protocol,
            topology=spec.topology,
            strategy_index=spec.strategy_index,
            topology_index=spec.topology_index,
            seed=spec.seed,
        )
    header = _header(effective).replace("available_{10}", f"available_{{{quota_capacity}}}")
    reference = _source(effective, quota_capacity=quota_capacity, reverse_keys=reverse_keys)
    starter = _starter_source(effective)
    visible = _test_source(effective, hidden=False, quota_capacity=quota_capacity, reverse_keys=reverse_keys)
    hidden = _test_source(effective, hidden=True, quota_capacity=quota_capacity, reverse_keys=reverse_keys)
    negative = _source(effective, quota_capacity=quota_capacity, reverse_keys=reverse_keys, negative=True)
    files = {
        ".docs/introduction.md": "Implement a clean-room lifecycle transaction with exact rollback on invalid transitions.\n",
        ".docs/instructions.md": _instructions(
            effective, quota_capacity=quota_capacity, reverse_keys=reverse_keys
        ),
        f"{spec.task_id}.h": header,
        f"{spec.task_id}.cpp": starter,
        "task_visible_test.cpp": visible,
        ".meta/task_hidden_test.cpp": hidden,
        ".meta/example.h": header,
        ".meta/example.cpp": reference,
        ".meta/negative.cpp": negative,
        "CMakeLists.txt": _cmake(effective),
    }
    for relative, content in files.items():
        _write(root / relative, content)
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"Implement {spec.protocol.title} for a {spec.topology.title}.",
        "files": {
            "solution": [f"{spec.task_id}.h", f"{spec.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-expansion-task-provenance-v1",
        "task_id": spec.task_id,
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "task_spec_revision": 2,
        "curriculum_document": CURRICULUM,
        "family_spec": FAMILY_SPEC,
        "selected_design_prompt": DESIGN_PROMPT,
        "selected_implementation_prompt": IMPLEMENT_PROMPT,
        "generator": GENERATOR_PATH,
        "authoring_origin": "newly authored clean-room repository task",
        "license": "repository license",
        "rollback_protocol": spec.protocol.key,
        "lifecycle_topology": spec.topology.key,
        "deterministic_seed": spec.seed,
        "semantic_dimensions": _semantic_dimensions(spec),
        "benchmark_separation": "No official Aider task wording, API, tests, reference, response, or semantic contract was used.",
        "status": "local candidate; pending creator/audit loop",
        "dataset_handoff": "not_requested",
    }
    _write_json(root / ".meta/config.json", config)
    _write_json(root / ".meta/provenance.json", provenance)
    _write(
        root / ".meta/tests.toml",
        f'''[visible]\nname = "valid transaction and atomic rollback"\n\n[hidden]\nname = "independent model, fail-position matrix, and deterministic {spec.seed:#x} 64-event trace"\n\n[negative]\nname = "compiled accepted-prefix false substitute"\n''',
    )


def _read_family_owner(task_root: Path) -> str | None:
    path = task_root / ".meta/provenance.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("family_id")
    except (json.JSONDecodeError, OSError):
        return None


def _build_controls(out: Path) -> dict[str, Path]:
    controls_root = out / ".state/controls"
    if controls_root.exists():
        shutil.rmtree(controls_root)
    by_id = {spec.task_id: spec for spec in TASKS}
    controls = {
        "domain-identifier-renamed": controls_root / "domain-identifier-renamed",
        "constants-or-policy-only": controls_root / "constants-or-policy-only",
        "opposite-end-selection": controls_root / "opposite-end-selection",
    }
    _render_task(controls["domain-identifier-renamed"], by_id["snapshot-linear-lifecycle"], namespace_override="renamed_control_lifecycle")
    renamed_provenance_path = controls["domain-identifier-renamed"] / ".meta/provenance.json"
    renamed_provenance = json.loads(renamed_provenance_path.read_text(encoding="utf-8"))
    renamed_provenance["semantic_dimensions"] = {
        dimension: f"adversarially rewritten descriptor {index}"
        for index, dimension in enumerate(DIMENSIONS)
    }
    _write_json(renamed_provenance_path, renamed_provenance)
    _render_task(controls["constants-or-policy-only"], by_id["snapshot-quota-lifecycle"], quota_capacity=11)
    _render_task(controls["opposite-end-selection"], by_id["snapshot-keyed-lifecycle"], reverse_keys=True)
    return controls


def build(out: Path, *, force: bool = False, enforce_output: bool = False) -> tuple[Path, ...]:
    if enforce_output:
        _assert_output_boundary(out)
    out.mkdir(parents=True, exist_ok=True)
    expected_ids = {spec.task_id for spec in TASKS}
    if len(TASKS) != ROOT_COUNT or len(expected_ids) != ROOT_COUNT:
        _fail("binding_root_count_failed", str(len(expected_ids)))

    existing_roots = _real_task_roots(out)
    foreign = [root for root in existing_roots if _read_family_owner(root) != FAMILY_ID]
    if foreign:
        _fail("foreign_expansion_root", ",".join(root.name for root in foreign))
    if existing_roots and not force:
        _fail("output_exists", "pass --force for owner-controlled regeneration")
    for root in existing_roots:
        if root.name not in expected_ids:
            _fail("owner_root_not_in_inventory", root.name)
        shutil.rmtree(root)

    repo = _repo_root()
    other_ids: dict[str, str] = {}
    inventory_records = []
    for inventory_root in (*LEGACY_ROOTS, EXPANSION_ROOT):
        absolute = repo / inventory_root
        info = _inventory(absolute)
        inventory_records.append(info)
        for record in info["records"]:
            path = record["path"]
            if str(path).startswith(DEFAULT_OUT.as_posix()):
                continue
            task_id = record["task_id"]
            other_ids.setdefault(task_id, path)
    collisions = sorted(expected_ids & set(other_ids))
    if collisions:
        _fail("existing_task_id_collision", ",".join(collisions))

    roots = []
    for spec in TASKS:
        root = out / spec.task_id
        _render_task(root, spec)
        roots.append(root)
    controls = _build_controls(out)
    state = out / ".state"
    _write_json(state / "source-inventory.json", {"schema_version": "lifecycle-rollback-source-inventory-v1", "inventories": inventory_records})
    _write_json(state / "raw-proposals.json", {"count": ROOT_COUNT, "task_ids": [spec.task_id for spec in TASKS], "source": CURRICULUM})
    _write_json(state / "rejected-candidates.json", {"count": 0, "records": []})
    _write_json(state / "selected-candidates.json", {"count": ROOT_COUNT, "task_ids": sorted(expected_ids), "status": "draft"})
    _write_json(state / "control-manifest.json", {"controls": {name: path.relative_to(out).as_posix() for name, path in controls.items()}, "counted_as_tasks": False})
    return tuple(roots)


def _semantic_shingles(text: str) -> set[str]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STRING ", text)
    text = re.sub(r"\b(?:0[xX][0-9A-Fa-f]+|\d+)\b", " NUMBER ", text)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|->|\+\+|--|\+=|-=|&&|\|\||\S", text)
    stable = {
        "if", "else", "for", "while", "return", "class", "struct", "map",
        "vector", "set", "optional", "bool", "int", "long", "size_t",
        "NUMBER", "STRING", "public", "private", "const", "true", "false",
    }
    normalized = [
        token if token in stable or not re.fullmatch(r"[A-Za-z_]\w*", token) else "ID"
        for token in raw
    ]
    return {" ".join(normalized[index:index + 5]) for index in range(max(0, len(normalized) - 4))}


def _role_contract_profile(task_root: Path) -> dict[str, object]:
    role_text: dict[str, list[str]] = {"api": [], "tests": [], "reference": [], "prompt": []}
    for path in sorted(task_root.rglob("*")):
        if not path.is_file() or "build" in path.relative_to(task_root).parts:
            continue
        relative = path.relative_to(task_root).as_posix()
        if path.suffix.lower() not in {".h", ".hpp", ".cpp", ".cc", ".md"}:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        lowered = relative.lower()
        if path.suffix.lower() in {".h", ".hpp"}:
            role_text["api"].append(content)
        if "test" in lowered:
            role_text["tests"].append(content)
        elif ".meta/example" in lowered or "/src/" in f"/{lowered}" or path.suffix.lower() in {".cpp", ".cc"}:
            role_text["reference"].append(content)
        if lowered.startswith(".docs/") or path.name.lower().startswith("readme"):
            role_text["prompt"].append(content)
    roles = {}
    for role, pieces in role_text.items():
        text = "\n".join(pieces)
        shingles = _semantic_shingles(text)
        roles[role] = {
            "hash": _sha("\n".join(sorted(shingles)).encode()),
            "shingles": shingles,
            "count": len(shingles),
        }
    provenance_path = task_root / ".meta/provenance.json"
    lineage = "external-unclassified"
    if provenance_path.is_file():
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            lineage = f"{provenance.get('family_id')}:{provenance.get('lineage')}"
        except json.JSONDecodeError:
            lineage = "invalid-provenance"
    return {
        "task_id": task_root.name,
        "tree_hash": _tree_hash(task_root, include_state=True),
        "roles": roles,
        "lineage": lineage,
    }


def _role_similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _cross_pair(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    role_scores = {}
    equal_roles = []
    for role in ("api", "tests", "reference", "prompt"):
        lrole = left["roles"][role]
        rrole = right["roles"][role]
        score = _role_similarity(lrole["shingles"], rrole["shingles"])
        role_scores[role] = round(score, 9)
        if lrole["count"] and lrole["hash"] == rrole["hash"]:
            equal_roles.append(role)
    exact_lineage_subject = left["tree_hash"] == right["tree_hash"]
    semantic_clone = (
        exact_lineage_subject
        or {"api", "tests", "reference"}.issubset(equal_roles)
        or max(role_scores.values(), default=0.0) >= 0.985
    )
    return {
        "role_scores": role_scores,
        "equal_roles": equal_roles,
        "exact_tree": exact_lineage_subject,
        "disposition": "duplicate" if semantic_clone else "distinct",
    }


def _holdout_identity(repo: Path, benchmark: dict[str, object]) -> dict[str, object]:
    checkout = repo / ".cache/upstreams/aider-polyglot"
    revision = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if revision.returncode != 0:
        _fail("holdout_identity_mismatch", revision.stderr.strip())
    observed_revision = revision.stdout.strip()
    if observed_revision != benchmark["revision"]:
        _fail("holdout_identity_mismatch", observed_revision)
    dirty = subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain", "--", benchmark["root"]],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if dirty.returncode != 0 or dirty.stdout.strip():
        _fail("holdout_identity_mismatch", "dirty holdout subtree")
    holdout_root = checkout / benchmark["root"]
    records = []
    for task_id in sorted(benchmark["task_ids"]):
        root = holdout_root / task_id
        if not root.is_dir():
            _fail("holdout_identity_mismatch", f"missing:{task_id}")
        records.append({"task_id": task_id, "tree_hash": _tree_hash(root, include_state=True)})
    return {
        "manifest_hash": _sha((repo / BENCHMARK_MANIFEST).read_bytes()),
        "checkout_revision": observed_revision,
        "checkout_clean": True,
        "root": benchmark["root"],
        "root_count": len(records),
        "root_tree_hash": _sha("\n".join(f"{row['task_id']}:{row['tree_hash']}" for row in records).encode()),
        "records": records,
    }


def _cross_corpus_screen(out: Path, roots: Sequence[Path]) -> dict[str, object]:
    repo = _repo_root()
    scratch_mode = out.resolve() != (repo / DEFAULT_OUT).resolve(strict=False)
    benchmark = json.loads((repo / BENCHMARK_MANIFEST).read_text(encoding="utf-8"))
    holdout_identity = _holdout_identity(repo, benchmark)
    holdout_ids = set(benchmark["task_ids"])
    task_ids = {root.name for root in roots}
    if task_ids & holdout_ids:
        _fail("benchmark_id_overlap", ",".join(sorted(task_ids & holdout_ids)))
    comparison_roots: list[tuple[str, Path]] = []
    current_roots = {root.resolve() for root in roots}
    for base in (*LEGACY_ROOTS, EXPANSION_ROOT):
        for other in _real_task_roots(repo / base):
            if other.resolve() in current_roots:
                continue
            if scratch_mode and _read_family_owner(other) == FAMILY_ID:
                continue
            comparison_roots.append(("existing", other))
    if not (repo / HOLDOUT_ROOT).is_dir():
        _fail("benchmark_semantic_screen_not_completed", str(repo / HOLDOUT_ROOT))
    for child in sorted((repo / HOLDOUT_ROOT).iterdir()):
        if child.is_dir() and child.name in holdout_ids:
            comparison_roots.append(("holdout", child))

    strongest: dict[str, object] = {"score": 0.0, "candidate": None, "other": None, "kind": None, "role": None}
    comparisons = 0
    pair_path = out / ".state/cross-corpus-pairs.jsonl"
    pair_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_profiles = [(candidate, _role_contract_profile(candidate)) for candidate in roots]
    with pair_path.open("w", encoding="utf-8") as pair_stream:
        for kind, other in comparison_roots:
            right = _role_contract_profile(other)
            for candidate, left in candidate_profiles:
                comparisons += 1
                decision = _cross_pair(left, right)
                role, score = max(decision["role_scores"].items(), key=lambda item: item[1])
                if score > strongest["score"]:
                    strongest = {"score": score, "candidate": candidate.name, "other": other.name, "kind": kind, "role": role}
                pair_stream.write(json.dumps([
                    candidate.name, kind, other.name, decision["role_scores"],
                    decision["equal_roles"], decision["exact_tree"], decision["disposition"],
                ], separators=(",", ":")) + "\n")
                if decision["disposition"] != "distinct":
                    _fail("benchmark_content_overlap" if kind == "holdout" else "duplicate_family", f"{candidate.name}:{other.name}:{role}:{score:.3f}")
    controls = _build_controls(out)
    calibration = {}
    base_ids = {
        "domain-identifier-renamed": "snapshot-linear-lifecycle",
        "constants-or-policy-only": "snapshot-quota-lifecycle",
        "opposite-end-selection": "snapshot-keyed-lifecycle",
    }
    roots_by_id = {root.name: root for root in roots}
    for name, control in controls.items():
        decision = _cross_pair(
            _role_contract_profile(roots_by_id[base_ids[name]]),
            _role_contract_profile(control),
        )
        if decision["disposition"] != "duplicate":
            _fail("semantic_clone_control_missed", name)
        calibration[name] = decision
    return {
        "status": "pass",
        "normalizer": "lifecycle-rollback-v2-role-contract-witnesses",
        "policy_hash": _sha((_repo_root() / DIVERSITY_PATH).read_bytes()),
        "comparison_count": comparisons,
        "holdout_count": len(holdout_ids),
        "existing_root_count": sum(1 for kind, _ in comparison_roots if kind == "existing"),
        "strongest_overlap": strongest,
        "holdout_identity": holdout_identity,
        "semantic_clone_calibration": calibration,
        "pair_witness_columns": ["candidate", "corpus", "external", "role_scores", "equal_roles", "exact_tree", "disposition"],
        "pair_witness_path": pair_path.relative_to(out).as_posix(),
        "pair_witness_hash": _sha(pair_path.read_bytes()),
    }


def _validate_one(root: Path) -> dict[str, object]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    expected_solution = [f"{root.name}.h", f"{root.name}.cpp"]
    if config["files"]["solution"] != expected_solution:
        _fail("target_reference_mismatch", root.name)
    expected_examples = [".meta/example.h", ".meta/example.cpp"]
    if config["files"]["example"] != expected_examples:
        _fail("target_reference_mismatch", root.name)
    for role in ("solution", "test", "example"):
        for relative in config["files"][role]:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                _fail("unsafe_path", f"{root.name}:{relative}")
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (".meta/", "CMakeLists.txt", "task_visible_test.cpp", "negative.cpp", "provenance.json")
    if any(item in prompt for item in forbidden):
        _fail("prompt_boundary_failed", root.name)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    parsed = parse_whole_file_blocks(answer)
    if list(parsed) != expected_solution:
        _fail("target_reference_mismatch", root.name)
    negatives = {}
    malformed = {
        "omitted-file": answer.split(f"{root.name}.cpp", 1)[0],
        "extra-file": answer + "extra.cpp\n```cpp\nint x;\n```\n",
        "prose-prefix": "explanation\n" + answer,
        "duplicate-file": answer + answer.split(f"{root.name}.cpp", 1)[0],
    }
    for name, response in malformed.items():
        try:
            blocks = parse_whole_file_blocks(response)
            valid = list(blocks) == expected_solution
        except WholeFormatError:
            valid = False
        if valid:
            _fail("whole_format_failed", f"{root.name}:{name}")
        negatives[name] = "rejected"
    provenance = json.loads((root / ".meta/provenance.json").read_text(encoding="utf-8"))
    if set(provenance["semantic_dimensions"]) != set(DIMENSIONS):
        _fail("semantic_dimension_incomplete", root.name)
    return {
        "task_id": root.name,
        "prompt_hash": _sha(prompt.encode()),
        "starter_hashes": [_sha((root / item).read_bytes()) for item in expected_solution],
        "reference_hashes": [_sha((root / item).read_bytes()) for item in expected_examples],
        "test_hashes": [_sha((root / item).read_bytes()) for item in config["files"]["test"]],
        "negative_hash": _sha((root / ".meta/negative.cpp").read_bytes()),
        "whole_file_negatives": negatives,
        "prompt_boundary": "pass",
        "primary_core_objective": "achieved",
    }


def verify_core(out: Path, *, check_regeneration: bool = True) -> dict[str, object]:
    roots = _real_task_roots(out)
    if len(roots) != ROOT_COUNT or {root.name for root in roots} != {spec.task_id for spec in TASKS}:
        _fail("binding_root_count_failed", str(len(roots)))
    records = [_validate_one(root) for root in roots]
    for field in ("prompt_hash", "negative_hash"):
        values = [record[field] for record in records]
        if len(values) != len(set(values)):
            _fail("duplicate_task", field)
    reference_pairs = [tuple(record["reference_hashes"]) for record in records]
    if len(reference_pairs) != len(set(reference_pairs)):
        _fail("duplicate_task", "reference hashes")
    controls = _build_controls(out)
    family = evaluate_family(roots, control_roots=controls)
    if family["comparison_count"] != EXPECTED_PAIR_COUNT:
        _fail("family_pair_count_mismatch", str(family["comparison_count"]))
    cross = _cross_corpus_screen(out, roots)
    if check_regeneration:
        with tempfile.TemporaryDirectory(prefix="lifecycle-rollback-regen-") as temp:
            scratch = Path(temp) / "family"
            build(scratch, force=False, enforce_output=False)
            if _tree_hash(scratch) != _tree_hash(out):
                _fail("generator_output_drift", f"{_tree_hash(out)} != {_tree_hash(scratch)}")
    state = out / ".state"
    _write_json(state / "family-screen.json", family)
    _write_json(state / "cross-corpus-screen.json", cross)
    receipt = {
        "schema_version": "lifecycle-rollback-creator-preflight-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_docker_sanity",
        "root_count": ROOT_COUNT,
        "task_tree_hash": _tree_hash(out),
        "owner_hash": _owner_hash(),
        "curriculum_hash": _sha((_repo_root() / CURRICULUM).read_bytes()),
        "family_spec_hash": _sha((_repo_root() / FAMILY_SPEC).read_bytes()),
        "focused_test_hash": _sha((_repo_root() / FOCUSED_TEST).read_bytes()) if (_repo_root() / FOCUSED_TEST).exists() else None,
        "family_screen_hash": _sha((state / "family-screen.json").read_bytes()),
        "cross_corpus_screen_hash": _sha((state / "cross-corpus-screen.json").read_bytes()),
        "family_screen_policy_hash": _sha((_repo_root() / DIVERSITY_PATH).read_bytes()),
        "cross_corpus_policy_hash": cross["policy_hash"],
        "holdout_identity": cross["holdout_identity"],
        "records": records,
        "prompt_boundary": "pass",
        "normal_oracle": "pending_docker_sanity",
        "sanitizer_oracle": "pending_docker_sanity",
        "negative_fixtures": "pending_docker_sanity",
        "adversarial_controls": "pending_docker_sanity",
        "strongest_local_status": "creator_preflight_structural_pass",
        "dataset_handoff": "not_requested",
    }
    _write_json(state / "creator-preflight.json", receipt)
    return receipt


def _docker_script() -> str:
    return r'''set -euo pipefail
cd /work/family
sha256sum -c state-concurrency/lifecycle-rollback/.state/tree-files.sha256 >/tmp/tree-check.log
task_tree_payload=$(
  find state-concurrency/lifecycle-rollback -type f ! -path '*/.state/*' ! -path '*/build/*' -print0 |
    sort -z |
    while IFS= read -r -d '' file; do
      relative=${file#state-concurrency/lifecycle-rollback/}
      digest=$(sha256sum "$file" | awk '{print $1}')
      printf '%s:sha256:%s\n' "$relative" "$digest"
    done
)
mounted_task_tree_hash="sha256:$(printf '%s' "$task_tree_payload" | sha256sum | awk '{print $1}')"
if [ "$mounted_task_tree_hash" != "$W8_EXPECTED_TASK_TREE_HASH" ]; then
  echo "grader_mount_hash_mismatch expected=$W8_EXPECTED_TASK_TREE_HASH actual=$mounted_task_tree_hash" >&2
  exit 42
fi
count=0
normal=0
sanitizer=0
negative=0
controls=0
verify_root() {
  root="$1"
  mode="$2"
  echo "verify-root $root $mode"
  work="/tmp/build-${count}-${mode}"
  rm -rf "$work"
  mkdir -p "$work/task"
  cp -a "$root/." "$work/task/"
  header=$(find "$work/task" -maxdepth 1 -type f -name '*.h' -printf '%f\n')
  source=$(find "$work/task" -maxdepth 1 -type f -name '*.cpp' ! -name '*test.cpp' -printf '%f\n')
  cp "$work/task/.meta/example.h" "$work/task/$header"
  cp "$work/task/.meta/example.cpp" "$work/task/$source"
  san=OFF
  if [ "$mode" = sanitizer ]; then san=ON; fi
  cmake -S "$work/task" -B "$work/build" -G 'Unix Makefiles' -DW8_SANITIZE="$san" >/tmp/cmake.log
  cmake --build "$work/build" -j2 >/tmp/build.log
  discovered=$(ctest --test-dir "$work/build" -N | sed -n 's/.*Total Tests: //p')
  [ "$discovered" = 2 ]
  if ! ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$work/build" --output-on-failure >/tmp/ctest.log 2>&1; then
    cat /tmp/ctest.log >&2
    exit 8
  fi
  count=$((count+1))
}
verify_negative() {
  root="$1"
  mode="$2"
  echo "verify-negative $root $mode"
  work="/tmp/negative-${count}-${mode}"
  rm -rf "$work"
  mkdir -p "$work/task"
  cp -a "$root/." "$work/task/"
  header=$(find "$work/task" -maxdepth 1 -type f -name '*.h' -printf '%f\n')
  source=$(find "$work/task" -maxdepth 1 -type f -name '*.cpp' ! -name '*test.cpp' -printf '%f\n')
  cp "$work/task/.meta/example.h" "$work/task/$header"
  cp "$work/task/.meta/negative.cpp" "$work/task/$source"
  san=OFF
  if [ "$mode" = sanitizer ]; then san=ON; fi
  cmake -S "$work/task" -B "$work/build" -G 'Unix Makefiles' -DW8_SANITIZE="$san" >/tmp/cmake-negative.log
  cmake --build "$work/build" -j2 >/tmp/build-negative.log
  discovered=$(ctest --test-dir "$work/build" -N | sed -n 's/.*Total Tests: //p')
  [ "$discovered" = 2 ]
  if ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$work/build" --output-on-failure >/tmp/negative.log 2>&1; then
    echo "negative unexpectedly passed: $root $mode" >&2
    exit 31
  fi
  negative=$((negative+1))
  count=$((count+1))
}
for root in state-concurrency/lifecycle-rollback/*; do
  [ -f "$root/.meta/config.json" ] || continue
  verify_root "$root" normal; normal=$((normal+2))
  verify_root "$root" sanitizer; sanitizer=$((sanitizer+2))
  verify_negative "$root" normal
  verify_negative "$root" sanitizer
done
for root in state-concurrency/lifecycle-rollback/.state/controls/*; do
  [ -f "$root/.meta/config.json" ] || continue
  verify_root "$root" normal
  verify_root "$root" sanitizer
  controls=$((controls+1))
done
cxx=$(command -v c++)
cmake_bin=$(command -v cmake)
compiler_sha=$(sha256sum "$cxx" | awk '{print $1}')
printf '{"status":"pass","normal_discovered":%s,"sanitizer_discovered":%s,"negative_runs":%s,"control_count":%s,"compiler_path":"%s","compiler_version":"%s","compiler_sha256":"sha256:%s","cmake_version":"%s","mounted_manifest":"pass","mounted_task_tree_hash":"%s","mounted_digest_check":"pass"}\n' "$normal" "$sanitizer" "$negative" "$controls" "$cxx" "$(c++ --version | head -1 | sed 's/"/\\"/g')" "$compiler_sha" "$(cmake --version | head -1 | sed 's/"/\\"/g')" "$mounted_task_tree_hash"
'''


def _write_integrity_manifest(out: Path) -> None:
    state = out / ".state"
    immutable_state = {
        "source-inventory.json", "raw-proposals.json", "rejected-candidates.json",
        "selected-candidates.json", "control-manifest.json",
    }
    checks = []
    for path in sorted(out.rglob("*")):
        if not path.is_file() or "build" in path.parts or path == state / "tree-files.sha256":
            continue
        relative_to_out = path.relative_to(out)
        if ".state" in relative_to_out.parts:
            if relative_to_out.parts[:2] == (".state", "controls"):
                pass
            elif relative_to_out.as_posix() not in {f".state/{name}" for name in immutable_state}:
                continue
        checks.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out.parent.parent).as_posix()}")
    _write(state / "tree-files.sha256", "\n".join(checks) + "\n")


def docker_sanity(out: Path, *, image: str = SANITY_IMAGE) -> dict[str, object]:
    structural = verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if inspect.returncode != 0:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    image_id = inspect.stdout.strip()
    if image_id != SANITY_IMAGE_ID:
        _fail("docker_image_identity_mismatch", image_id)
    state = out / ".state"
    live_task_tree_hash = _tree_hash(out)

    try:
        receipt = json.loads((state / "docker-sanity-receipt.json").read_text(encoding="utf-8"))
        if receipt.get("task_tree_hash") == live_task_tree_hash and receipt.get("status") == "pass":
            print("Skipping docker_sanity as receipt matches")
            return receipt
    except Exception:
        pass

    _write_integrity_manifest(out)
    archive_dir = Path(tempfile.mkdtemp(prefix="lifecycle-rollback-docker-"))
    archive = archive_dir / "family.tar"
    archive_extract = archive_dir / "extracted"
    try:
        with tarfile.open(archive, "w") as tar:
            tar.add(out.parent.parent, arcname=".", recursive=True)
        archive_hash = _sha(archive.read_bytes())
        archive_extract.mkdir()
        with tarfile.open(archive, "r") as tar:
            tar.extractall(archive_extract, filter="data")
        archive_extracted_task_tree_hash = _tree_hash(
            archive_extract / "state-concurrency/lifecycle-rollback"
        )
        if archive_extracted_task_tree_hash != live_task_tree_hash:
            _fail(
                "archive_task_tree_hash_mismatch",
                f"{live_task_tree_hash}!={archive_extracted_task_tree_hash}",
            )
        command = [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{archive}:/input/family.tar:ro",
            "-e", f"W8_EXPECTED_TASK_TREE_HASH={live_task_tree_hash}",
            image,
            "bash", "-lc",
            "mkdir -p /work/family && tar -xf /input/family.tar -C /work/family && " + _docker_script(),
        ]
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=7200,
            check=False,
        )
    finally:
        shutil.rmtree(archive_dir, ignore_errors=True)
    if completed.returncode != 0:
        _write(state / "docker-sanity.failure.log", completed.stdout[-10000:] + "\n" + completed.stderr[-10000:])
        _fail("docker_sanity_failed", f"exit={completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    if not lines:
        _fail("docker_sanity_incomplete", "missing terminal JSON")
    result = json.loads(lines[-1])
    if result.get("mounted_task_tree_hash") != live_task_tree_hash:
        _fail(
            "grader_mount_hash_mismatch",
            f"{live_task_tree_hash}!={result.get('mounted_task_tree_hash')}",
        )
    if result.get("normal_discovered") != ROOT_COUNT * 2 or result.get("sanitizer_discovered") != ROOT_COUNT * 2:
        _fail("sanitizer_test_count_mismatch", json.dumps(result, sort_keys=True))
    if result.get("negative_runs") != ROOT_COUNT * 2 or result.get("control_count") != 3:
        _fail("negative_fixture_incomplete", json.dumps(result, sort_keys=True))
    receipt = {
        "schema_version": "lifecycle-rollback-docker-sanity-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "image": image,
        "image_id": image_id,
        "network": "none",
        "task_tree_hash": live_task_tree_hash,
        "live_owner_task_tree_hash": live_task_tree_hash,
        "archive_extracted_task_tree_hash": archive_extracted_task_tree_hash,
        "mounted_task_tree_hash": result["mounted_task_tree_hash"],
        "task_tree_digest_equality": "pass",
        "mounted_digest_check": result["mounted_digest_check"],
        "archive_hash": archive_hash,
        "owner_hash": _owner_hash(),
        "compiler_path": result["compiler_path"],
        "compiler_version": result["compiler_version"],
        "compiler_sha256": result["compiler_sha256"],
        "cmake_version": result["cmake_version"],
        "normal_discovered_tests": result["normal_discovered"],
        "sanitizer_discovered_tests": result["sanitizer_discovered"],
        "negative_runs": result["negative_runs"],
        "controls_normal_and_sanitizer_passed": result["control_count"],
        "mounted_manifest": result["mounted_manifest"],
        "integrity_manifest_hash": _sha((state / "tree-files.sha256").read_bytes()),
        "holdout_identity": structural["holdout_identity"],
        "family_screen_policy_hash": structural["family_screen_policy_hash"],
        "cross_corpus_policy_hash": structural["cross_corpus_policy_hash"],
        "command": command,
    }
    _write_json(state / "docker-sanity-receipt.json", receipt)
    family = json.loads((state / "family-screen.json").read_text(encoding="utf-8"))
    for control in family["adversarial_clone_results"].values():
        control["behavior_build_status"] = "normal_and_sanitizer_pass"
    _write_json(state / "family-screen.json", family)
    structural.update(
        {
            "status": "creator_preflight_pass",
            "normal_oracle": "pass",
            "sanitizer_oracle": "pass",
            "negative_fixtures": "pass",
            "adversarial_controls": "pass",
            "docker_sanity_receipt_hash": _sha((state / "docker-sanity-receipt.json").read_bytes()),
            "family_screen_hash": _sha((state / "family-screen.json").read_bytes()),
            "strongest_local_status": "creator_preflight_pass",
        }
    )
    _write_json(state / "creator-preflight.json", structural)
    for line in (state / "tree-files.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        actual = hashlib.sha256((out.parent.parent / relative).read_bytes()).hexdigest()
        if actual != expected:
            _fail("manifest_drift", relative)
    return receipt


def _host_env(sanitizer: bool) -> dict[str, str]:
    env = dict(os.environ)
    if sanitizer:
        env["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    return env


def _stage_task(root: Path, task_dir: Path, *, negative: bool) -> Path:
    """Copy one root into a scratch task dir and overlay the reference/negative sources."""
    shutil.copytree(root, task_dir)
    header = next(path for path in task_dir.glob("*.h"))
    source = next(path for path in task_dir.glob("*.cpp") if "test" not in path.name)
    shutil.copyfile(task_dir / ".meta/example.h", header)
    shutil.copyfile(task_dir / (".meta/negative.cpp" if negative else ".meta/example.cpp"), source)
    return task_dir


def _host_build_and_test(task_dir: Path, build_dir: Path, *, sanitizer: bool, expect_pass: bool) -> int:
    mode = "sanitizer" if sanitizer else "normal"
    configure = [
        "cmake", "-S", str(task_dir), "-B", str(build_dir), "-G", "Unix Makefiles",
        f"-DW8_SANITIZE={'ON' if sanitizer else 'OFF'}",
    ]
    for command in (configure, ["cmake", "--build", str(build_dir), "--parallel", "2"]):
        result = subprocess.run(command, cwd=task_dir, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            _fail("reference_compile_failed", f"{task_dir.name}:{mode}:{result.stdout[-2000:]}{result.stderr[-2000:]}")
    discovered = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"], cwd=task_dir, text=True, capture_output=True, check=False,
    )
    match = re.search(r"Total Tests:\s*(\d+)", discovered.stdout)
    count = int(match.group(1)) if match else 0
    if count != 2:
        _fail("test_discovery_failed", f"{task_dir.name}:{mode}:{count}")
    executed = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
        cwd=task_dir, env=_host_env(sanitizer), text=True, capture_output=True, check=False,
    )
    if expect_pass and executed.returncode != 0:
        code = "reference_sanitizer_failed" if sanitizer else "reference_tests_failed"
        _fail(code, f"{task_dir.name}:{executed.stdout[-2000:]}{executed.stderr[-2000:]}")
    if not expect_pass and executed.returncode == 0:
        _fail("negative_fixture_not_rejected", f"{task_dir.name}:{mode}")
    return count


def verify_host(out: Path) -> dict[str, object]:
    """Run the docker-sanity build semantics on the host toolchain (campaign gate)."""
    structural = verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("host_verify_not_completed", "cmake or c++ unavailable")
    state = out / ".state"
    live_task_tree_hash = _tree_hash(out)
    roots = _real_task_roots(out)
    normal_total = 0
    sanitizer_total = 0
    negative_runs = 0
    control_passes = 0
    with tempfile.TemporaryDirectory(prefix="lifecycle-rollback-host-") as temp:
        workspace = Path(temp)
        units: list[tuple[Path, str, bool, bool]] = []
        for root in roots:
            units.append((root, "normal", False, True))
            units.append((root, "sanitizer", True, True))
            units.append((root, "negative-normal", False, False))
            units.append((root, "negative-sanitizer", True, False))
        controls_root = state / "controls"
        for control in sorted(path for path in controls_root.iterdir() if path.is_dir()):
            units.append((control, "normal", False, True))
            units.append((control, "sanitizer", True, True))
        for index, (root, mode, sanitizer, expect_pass) in enumerate(units):
            unit = workspace / f"unit-{index}"
            staged = _stage_task(root, unit / "task", negative=not expect_pass)
            count = _host_build_and_test(staged, unit / "build", sanitizer=sanitizer, expect_pass=expect_pass)
            if not expect_pass:
                negative_runs += 1
            elif root.parent == controls_root:
                control_passes += 1
            elif sanitizer:
                sanitizer_total += count
            else:
                normal_total += count
    if normal_total != ROOT_COUNT * 2 or sanitizer_total != ROOT_COUNT * 2:
        _fail("sanitizer_test_count_mismatch", f"{normal_total}!={sanitizer_total}")
    if negative_runs != ROOT_COUNT * 2 or control_passes != len(CONTROL_NAMES) * 2:
        _fail("negative_fixture_incomplete", f"negative={negative_runs} controls={control_passes}")
    cxx = shutil.which("c++") or ""
    compiler_version = subprocess.run(
        ["c++", "--version"], text=True, capture_output=True, check=False,
    ).stdout.splitlines()[0]
    cmake_version = subprocess.run(
        ["cmake", "--version"], text=True, capture_output=True, check=False,
    ).stdout.splitlines()[0]
    _write_integrity_manifest(out)
    receipt = {
        "schema_version": "lifecycle-rollback-host-verify-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "campaign_gate": "host_verify_only",
        "task_tree_hash": live_task_tree_hash,
        "owner_hash": _owner_hash(),
        "compiler_path": cxx,
        "compiler_version": compiler_version,
        "compiler_sha256": _sha(Path(cxx).read_bytes()) if cxx else None,
        "cmake_version": cmake_version,
        "normal_discovered_tests": normal_total,
        "sanitizer_discovered_tests": sanitizer_total,
        "negative_runs": negative_runs,
        "controls_normal_and_sanitizer_passed": control_passes,
        "integrity_manifest_hash": _sha((state / "tree-files.sha256").read_bytes()),
        "commands": [
            "cmake -S <staged> -B <build> -G 'Unix Makefiles' -DW8_SANITIZE=ON|OFF",
            "cmake --build <build> --parallel 2",
            "ctest --test-dir <build> --output-on-failure",
        ],
    }
    _write_json(state / "host-verify-receipt.json", receipt)
    family = json.loads((state / "family-screen.json").read_text(encoding="utf-8"))
    for control in family["adversarial_clone_results"].values():
        control["behavior_build_status"] = "host_normal_and_sanitizer_pass"
    _write_json(state / "family-screen.json", family)
    structural.update(
        {
            "status": "creator_preflight_pass",
            "host_normal_oracle": "pass",
            "host_sanitizer_oracle": "pass",
            "host_negative_fixtures": "pass",
            "host_adversarial_controls": "pass",
            "host_verify_receipt_hash": _sha((state / "host-verify-receipt.json").read_bytes()),
            "family_screen_hash": _sha((state / "family-screen.json").read_bytes()),
            "integrity_manifest_hash": receipt["integrity_manifest_hash"],
            "strongest_local_status": "campaign_verified_host_only",
        }
    )
    _write_json(state / "creator-preflight.json", structural)
    return receipt


def _append_cycle(out: Path, *, cycle: int, status: str, audit_path: str | None = None, findings: Sequence[str] = ()) -> None:
    path = out / ".state/cycles.jsonl"
    record = {
        "cycle": cycle,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "family_id": FAMILY_ID,
        "task_tree_hash": _tree_hash(out),
        "owner_hash": _owner_hash(),
        "candidate_manifest_hash": _sha((out / ".state/selected-candidates.json").read_bytes()),
        "creator_preflight_hash": _sha((out / ".state/creator-preflight.json").read_bytes()) if (out / ".state/creator-preflight.json").exists() else None,
        "audit_report_path": audit_path,
        "finding_ids": list(findings),
        "status": status,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    if args.verify_core:
        verify_core(args.out)
    elif args.verify_host:
        verify_host(args.out)
    elif args.docker_sanity:
        docker_sanity(args.out, image=args.image)
    else:
        build(args.out, force=args.force, enforce_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
