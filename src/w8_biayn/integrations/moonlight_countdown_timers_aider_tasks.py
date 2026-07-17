"""Materialize the newly authored countdown-timers local Aider curriculum.

These roots are deliberately local diagnostic artifacts.  They model elapsed
durations inside domain state machines; they are not variations of the
Polyglot ``clock`` holdout and are not admitted SFT data.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/countdown-timers")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_COUNTDOWN_TIMERS_ARITHMETIC_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    summary: str
    header: str
    reference: str
    starter: str
    visible: str
    hidden: str
    contract: str


def _task(task_id: str, class_name: str, summary: str, header: str, body: str, checks: str, hidden: str, contract: str) -> TaskSpec:
    prefix = '#include "task.h"\n#include <algorithm>\n#include <stdexcept>\nnamespace curriculum {\n'
    suffix = '}  // namespace curriculum\n'
    starter = '#include "task.h"\nnamespace curriculum {\n// TODO: implement every public method declared in task.h.\n' + suffix
    test_prefix = "#include \"task.h\"\n#include <stdexcept>\n"
    return TaskSpec(task_id, class_name, summary, header, prefix + body.replace("/*REFERENCE*/", "") + suffix, starter, test_prefix + checks.replace("\\n", "\n"), test_prefix + hidden.replace("\\n", "\n"), contract)


TASKS = (
    _task("timer-launch-hold", "LaunchHoldController", "A guarded launch sequence with hold, resume, abort, and exactly-once launch evidence.", r'''#ifndef LAUNCH_HOLD_CONTROLLER_H
#define LAUNCH_HOLD_CONTROLLER_H
namespace curriculum { class LaunchHoldController { public: enum class State { armed, holding, counting, aborted, launched }; struct Update { int remaining; State state; bool launched_now; bool accepted; }; explicit LaunchHoldController(int seconds); bool hold(); bool resume(); bool abort(); Update advance(int elapsed); State state() const; private: int remaining_; State state_ = State::armed; }; }
#endif
''', r'''LaunchHoldController::LaunchHoldController(int seconds) : remaining_(seconds) { if (seconds < 0) throw std::invalid_argument("seconds"); }
bool LaunchHoldController::hold() { if (state_ != State::armed && state_ != State::counting) return false; state_ = State::holding; return true; }
bool LaunchHoldController::resume() { if (state_ != State::holding) return false; state_ = State::counting; return true; }
bool LaunchHoldController::abort() { if (state_ == State::launched || state_ == State::aborted) return false; state_ = State::aborted; return true; }
LaunchHoldController::Update LaunchHoldController::advance(int elapsed) { if (elapsed < 0) return {remaining_, state_, false, false}; if (state_ == State::armed) state_ = State::counting; if (state_ != State::counting) return {remaining_, state_, false, true}; const bool now = elapsed >= remaining_; remaining_ = now ? 0 : remaining_ - elapsed; if (now) state_ = State::launched; return {remaining_, state_, now, true}; }
LaunchHoldController::State LaunchHoldController::state() const { return state_; }
/*REFERENCE*/''', r'''int main() { using C=curriculum::LaunchHoldController; C c(3); auto a=c.advance(1); if(a.remaining!=2||a.launched_now) return 1; if(!c.hold()||c.advance(9).remaining!=2||!c.resume()) return 2; auto b=c.advance(2); return b.launched_now&&b.remaining==0&&!c.advance(0).launched_now ? 0 : 3; }\n''', r'''int main() { using C=curriculum::LaunchHoldController; C c(1); if(!c.abort()||c.advance(1).state!=C::State::aborted||c.resume()) return 1; C z(0); if(!z.advance(0).launched_now||z.advance(1).launched_now) return 2; return c.advance(-1).accepted ? 3 : 0; }\n''', "Elapsed values are non-negative. Holding freezes the count; abort is terminal; reaching zero launches exactly once."),
    _task("timer-auction-extension", "AuctionExtensionMonitor", "A bid-history monitor with an inclusive anti-sniping window and a capped extension budget.", r'''#ifndef AUCTION_EXTENSION_MONITOR_H
#define AUCTION_EXTENSION_MONITOR_H
namespace curriculum { class AuctionExtensionMonitor { public: struct Result { int deadline; int extension_used; bool accepted; }; AuctionExtensionMonitor(int deadline, int window, int cap); Result bid_at(int position); private: int deadline_, window_, cap_, used_=0, last_=-1; }; }
#endif
''', r'''AuctionExtensionMonitor::AuctionExtensionMonitor(int deadline,int window,int cap):deadline_(deadline),window_(window),cap_(cap){if(deadline<0||window<0||cap<0)throw std::invalid_argument("policy");}
AuctionExtensionMonitor::Result AuctionExtensionMonitor::bid_at(int position){if(position<0||position<last_||position>deadline_)return{deadline_,used_,false};last_=position; const int want=position>=deadline_-window_?window_:0; const int add=std::min(want,cap_-used_); deadline_+=add; used_+=add; return{deadline_,used_,true};}
/*REFERENCE*/''', r'''int main(){curriculum::AuctionExtensionMonitor a(10,3,5); auto x=a.bid_at(7); auto y=a.bid_at(12); return x.deadline==13&&y.deadline==15&&y.extension_used==5&&!a.bid_at(11).accepted?0:1;}\n''', r'''int main(){curriculum::AuctionExtensionMonitor a(4,2,1); if(!a.bid_at(2).accepted||a.bid_at(1).accepted) return 1; return a.bid_at(20).accepted?2:0;}\n''', "Bid positions are caller supplied and monotonic. A bid exactly at the window boundary qualifies; rejected bids do not mutate policy state."),
    _task("timer-parking-credit", "ParkingCreditMeter", "A bounded prepaid credit ledger that reports unpaid elapsed units without negative credit.", r'''#ifndef PARKING_CREDIT_METER_H
#define PARKING_CREDIT_METER_H
namespace curriculum { class ParkingCreditMeter { public: struct Charge { int credit; int unpaid; bool accepted; }; ParkingCreditMeter(int rate,int cap,int initial); Charge elapse(int units); bool top_up(int credit); int credit() const; private:int rate_,cap_,credit_; }; }
#endif
''', r'''ParkingCreditMeter::ParkingCreditMeter(int rate,int cap,int initial):rate_(rate),cap_(cap),credit_(initial){if(rate<=0||cap<0||initial<0||initial>cap)throw std::invalid_argument("meter");}
ParkingCreditMeter::Charge ParkingCreditMeter::elapse(int units){if(units<0)return{credit_,0,false}; const long long due=static_cast<long long>(units)*rate_; const int paid=static_cast<int>(std::min<long long>(credit_,due)); credit_-=paid; return{credit_,static_cast<int>(due-paid),true};} bool ParkingCreditMeter::top_up(int x){if(x<0||x>cap_-credit_)return false;credit_+=x;return true;} int ParkingCreditMeter::credit()const{return credit_;}
/*REFERENCE*/''', r'''int main(){curriculum::ParkingCreditMeter m(2,10,5); auto x=m.elapse(4); if(x.credit||x.unpaid!=3||!m.top_up(7))return 1; return !m.top_up(4)&&m.credit()==7?0:2;}\n''', r'''int main(){curriculum::ParkingCreditMeter m(1,2,2); if(m.elapse(-1).accepted||m.credit()!=2)return 1; auto x=m.elapse(1000000); return x.credit==0&&x.unpaid==999998?0:2;}\n''', "Rate is positive and all balances are bounded. Overlarge elapsed updates saturate credit at zero and expose the unpaid remainder."),
    _task("timer-chess-round", "ChessRoundAdjudicator", "A two-player turn-owned budget with post-move increment and precise flag-fall handling.", r'''#ifndef CHESS_ROUND_ADJUDICATOR_H
#define CHESS_ROUND_ADJUDICATOR_H
namespace curriculum { class ChessRoundAdjudicator { public: struct Move { int player; int elapsed; }; struct Result { int white; int black; int flagged; bool accepted; }; ChessRoundAdjudicator(int initial,int increment); Result play(Move move); private:int clocks_[2];int increment_;int turn_=0;int flagged_=-1; }; }
#endif
''', r'''ChessRoundAdjudicator::ChessRoundAdjudicator(int initial,int increment):clocks_{initial,initial},increment_(increment){if(initial<0||increment<0)throw std::invalid_argument("clock");}
ChessRoundAdjudicator::Result ChessRoundAdjudicator::play(Move m){if(m.player!=turn_||m.elapsed<0||flagged_>=0)return{clocks_[0],clocks_[1],flagged_,false};if(m.elapsed>=clocks_[turn_]){clocks_[turn_]=0;flagged_=turn_;return{clocks_[0],clocks_[1],flagged_,true};}clocks_[turn_]-=m.elapsed;clocks_[turn_]+=increment_;turn_=1-turn_;return{clocks_[0],clocks_[1],-1,true};}
/*REFERENCE*/''', r'''int main(){curriculum::ChessRoundAdjudicator c(5,1); auto a=c.play({0,4}); auto b=c.play({1,5}); return a.white==2&&a.accepted&&b.flagged==1&&b.black==0?0:1;}\n''', r'''int main(){curriculum::ChessRoundAdjudicator c(1,0); if(c.play({1,0}).accepted||c.play({0,-1}).accepted)return 1; c.play({0,1}); return c.play({1,0}).accepted?2:0;}\n''', "Only the active player consumes time. A move that lands exactly at zero flags before increment; invalid order leaves both clocks unchanged."),
    _task("timer-incubator-checkpoints", "IncubatorCheckpointTracker", "An elapsed-progress tracker that emits positive unique checkpoints exactly once in ascending order.", r'''#ifndef INCUBATOR_CHECKPOINT_TRACKER_H
#define INCUBATOR_CHECKPOINT_TRACKER_H
#include <vector>
namespace curriculum { class IncubatorCheckpointTracker { public: explicit IncubatorCheckpointTracker(std::vector<int> checkpoints); std::vector<int> advance(int elapsed); int elapsed() const; private:std::vector<int> points_;int elapsed_=0; }; }
#endif
''', r'''IncubatorCheckpointTracker::IncubatorCheckpointTracker(std::vector<int> p):points_(std::move(p)){std::sort(points_.begin(),points_.end());if(std::any_of(points_.begin(),points_.end(),[](int x){return x<=0;})||std::adjacent_find(points_.begin(),points_.end())!=points_.end())throw std::invalid_argument("points");}
std::vector<int> IncubatorCheckpointTracker::advance(int x){if(x<0)return{};const int old=elapsed_;elapsed_+=x;std::vector<int> out;for(int p:points_)if(p>old&&p<=elapsed_)out.push_back(p);return out;} int IncubatorCheckpointTracker::elapsed()const{return elapsed_;}
/*REFERENCE*/''', r'''int main(){curriculum::IncubatorCheckpointTracker t({2,5,9}); auto a=t.advance(6); auto b=t.advance(3); return a==std::vector<int>({2,5})&&b==std::vector<int>({9})&&t.advance(0).empty()?0:1;}\n''', r'''int main(){try{curriculum::IncubatorCheckpointTracker x({1,1});return 1;}catch(const std::invalid_argument&){ } curriculum::IncubatorCheckpointTracker t({1}); return t.advance(-2).empty()&&t.elapsed()==0?0:2;}\n''', "Checkpoints are positive and unique. A large update can cross many checkpoints; invalid elapsed input never advances progress."),
    _task("timer-evacuation-drill", "EvacuationDrillScorecard", "A staged deadline assessment with inclusive passing, grace bands, and first-failure evidence.", r'''#ifndef EVACUATION_DRILL_SCORECARD_H
#define EVACUATION_DRILL_SCORECARD_H
#include <vector>
namespace curriculum { class EvacuationDrillScorecard { public: struct Stage{int deadline;int grace;}; struct Result{int first_failure;int passed;bool accepted;}; explicit EvacuationDrillScorecard(std::vector<Stage> stages); Result assess(const std::vector<int>& observed) const; private:std::vector<Stage> stages_; }; }
#endif
''', r'''EvacuationDrillScorecard::EvacuationDrillScorecard(std::vector<Stage> s):stages_(std::move(s)){if(std::any_of(stages_.begin(),stages_.end(),[](Stage x){return x.deadline<0||x.grace<0;}))throw std::invalid_argument("stage");}
EvacuationDrillScorecard::Result EvacuationDrillScorecard::assess(const std::vector<int>& o)const{if(o.size()!=stages_.size())return{-1,0,false};int pass=0,fail=-1;for(int i=0;i<(int)o.size();++i){if(o[i]<0)return{-1,pass,false};if(o[i]<=stages_[i].deadline)++pass;else if(fail<0)fail=i;}return{fail,pass,true};}
/*REFERENCE*/''', r'''int main(){curriculum::EvacuationDrillScorecard s({{3,1},{5,2}}); auto r=s.assess({3,6}); return r.accepted&&r.passed==1&&r.first_failure==1?0:1;}\n''', r'''int main(){curriculum::EvacuationDrillScorecard s({{1,0}}); return !s.assess({}).accepted&&!s.assess({-1}).accepted?0:1;}\n''', "Observed durations are non-negative. Equality at a deadline passes; all stages are inspected, but the first late stage is reported."),
    _task("timer-game-cooldown-registry", "GameCooldownRegistry", "A keyed simultaneous cooldown collection returning newly-ready ability IDs in stable lexical order.", r'''#ifndef GAME_COOLDOWN_REGISTRY_H
#define GAME_COOLDOWN_REGISTRY_H
#include <map>
#include <string>
#include <vector>
namespace curriculum { class GameCooldownRegistry { public: bool register_ability(const std::string&,int); std::vector<std::string> advance_all(int); bool reset(const std::string&,int); int remaining(const std::string&) const; private:std::map<std::string,int> items_; }; }
#endif
''', r'''bool GameCooldownRegistry::register_ability(const std::string& id,int x){return !id.empty()&&x>=0&&items_.emplace(id,x).second;}std::vector<std::string> GameCooldownRegistry::advance_all(int x){std::vector<std::string> out;if(x<0)return out;for(auto& e:items_){const int before=e.second;e.second=std::max(0,e.second-x);if(before>0&&e.second==0)out.push_back(e.first);}return out;}bool GameCooldownRegistry::reset(const std::string& id,int x){auto it=items_.find(id);if(it==items_.end()||x<0||it->second==0)return false;it->second=x;return true;}int GameCooldownRegistry::remaining(const std::string& id)const{auto it=items_.find(id);return it==items_.end()?-1:it->second;}
/*REFERENCE*/''', r'''int main(){curriculum::GameCooldownRegistry r;r.register_ability("zap",2);r.register_ability("arc",1);auto a=r.advance_all(1);return a==std::vector<std::string>({"arc"})&&r.reset("zap",3)&&r.advance_all(3)==std::vector<std::string>({"zap"})?0:1;}\n''', r'''int main(){curriculum::GameCooldownRegistry r;if(r.register_ability("",1)||!r.register_ability("a",0)||r.reset("a",2))return 1;return r.advance_all(-1).empty()&&r.remaining("missing")==-1?0:2;}\n''', "Ability IDs are unique. Advancement is simultaneous and saturates at zero; reset rejects unknown and already-ready abilities."),
    _task("timer-oven-safety-lock", "OvenSafetyLock", "A child-safety lock with bounded relock credits and irreversible permanent disablement.", r'''#ifndef OVEN_SAFETY_LOCK_H
#define OVEN_SAFETY_LOCK_H
namespace curriculum { class OvenSafetyLock { public: enum class State{active,expired,disabled}; OvenSafetyLock(int seconds,int relocks); State advance(int); bool relock(int); bool disable(); int remaining()const; State state()const; private:int remaining_,credits_;State state_=State::active; }; }
#endif
''', r'''OvenSafetyLock::OvenSafetyLock(int x,int c):remaining_(x),credits_(c){if(x<0||c<0)throw std::invalid_argument("lock");if(!x)state_=State::expired;} OvenSafetyLock::State OvenSafetyLock::advance(int x){if(x<0||state_!=State::active)return state_;remaining_=x>=remaining_?0:remaining_-x;if(!remaining_)state_=State::expired;return state_;}bool OvenSafetyLock::relock(int x){if(state_!=State::expired||x<=0||credits_==0)return false;remaining_=x;--credits_;state_=State::active;return true;}bool OvenSafetyLock::disable(){if(state_==State::disabled)return false;state_=State::disabled;remaining_=0;return true;}int OvenSafetyLock::remaining()const{return remaining_;}OvenSafetyLock::State OvenSafetyLock::state()const{return state_;}
/*REFERENCE*/''', r'''int main(){curriculum::OvenSafetyLock l(2,1);l.advance(2);if(!l.relock(3)||l.remaining()!=3)return 1;l.disable();return !l.relock(2)&&l.state()==curriculum::OvenSafetyLock::State::disabled?0:2;}\n''', r'''int main(){curriculum::OvenSafetyLock l(0,0);return !l.relock(1)&&l.advance(-1)==curriculum::OvenSafetyLock::State::expired?0:1;}\n''', "Relocking is allowed only after expiry and consumes one credit. Permanent disablement cannot be reversed."),
    _task("timer-build-lease", "BuildAgentLeaseManager", "A generation-checked multi-worker lease manager with stable simultaneous-expiry reporting.", r'''#ifndef BUILD_AGENT_LEASE_MANAGER_H
#define BUILD_AGENT_LEASE_MANAGER_H
#include <map>
#include <string>
#include <vector>
namespace curriculum { class BuildAgentLeaseManager { public: bool grant(const std::string&,int,int); bool renew(const std::string&,int,int,int); std::vector<std::string> advance(int,int); private:struct Lease{int generation;int remaining;};std::map<std::string,Lease> leases_;int sequence_=-1; }; }
#endif
''', r'''bool BuildAgentLeaseManager::grant(const std::string& id,int g,int ttl){return !id.empty()&&g>=0&&ttl>0&&leases_.emplace(id,Lease{g,ttl}).second;}bool BuildAgentLeaseManager::renew(const std::string& id,int g,int ttl,int seq){auto it=leases_.find(id);if(seq<=sequence_||ttl<=0||it==leases_.end()||it->second.generation!=g)return false;sequence_=seq;it->second.remaining=ttl;return true;}std::vector<std::string> BuildAgentLeaseManager::advance(int x,int seq){std::vector<std::string> out;if(x<0||seq<=sequence_)return out;sequence_=seq;for(auto it=leases_.begin();it!=leases_.end();){if(x>=it->second.remaining){out.push_back(it->first);it=leases_.erase(it);}else{it->second.remaining-=x;++it;}}return out;}
/*REFERENCE*/''', r'''int main(){curriculum::BuildAgentLeaseManager m;m.grant("b",1,2);m.grant("a",1,1);auto x=m.advance(1,1);return x==std::vector<std::string>({"a"})&&m.renew("b",1,4,2)&&m.advance(4,3)==std::vector<std::string>({"b"})?0:1;}\n''', r'''int main(){curriculum::BuildAgentLeaseManager m;m.grant("a",2,1);if(m.renew("a",1,3,1))return 1;m.advance(0,1);return m.advance(1,1).empty()?0:2;}\n''', "Event sequence numbers must increase. Renewal checks worker identity and generation; one advance may expire several leases in identifier order."),
    _task("timer-study-session-budget", "StudySessionBudget", "An ordered focus/break ledger that refuses overspend and reports mandatory-break policy violations.", r'''#ifndef STUDY_SESSION_BUDGET_H
#define STUDY_SESSION_BUDGET_H
namespace curriculum { class StudySessionBudget { public: struct Report{int unused;int violations;bool accepted;}; StudySessionBudget(int budget,int focus_before_break); Report focus(int); bool take_break(int); private:int unused_,threshold_,since_break_=0,violations_=0; }; }
#endif
''', r'''StudySessionBudget::StudySessionBudget(int b,int t):unused_(b),threshold_(t){if(b<0||t<=0)throw std::invalid_argument("budget");}StudySessionBudget::Report StudySessionBudget::focus(int x){if(x<0||x>unused_)return{unused_,violations_,false};if(since_break_+x>threshold_)++violations_;unused_-=x;since_break_+=x;return{unused_,violations_,true};}bool StudySessionBudget::take_break(int x){if(x<=0)return false;since_break_=0;return true;}
/*REFERENCE*/''', r'''int main(){curriculum::StudySessionBudget s(8,3);auto a=s.focus(3);s.take_break(1);auto b=s.focus(4);return a.accepted&&b.unused==1&&b.violations==1&&!s.focus(2).accepted?0:1;}\n''', r'''int main(){curriculum::StudySessionBudget s(1,1);if(s.take_break(0)||s.focus(-1).accepted)return 1;return s.focus(1).unused==0?0:2;}\n''', "Focus events are ordered. An overspending event is rejected without partial consumption; a positive break resets the consecutive-focus counter."),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(countdown_timers_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots = []
    for spec in TASKS:
        root = out / spec.task_id
        config = {"authors": ["w8-biayn"], "blurb": spec.summary, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": spec.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Domain state machine and public API are independently authored; this root is not derived from the permanent Aider Polyglot clock, gigasecond, or meetup holdouts."}
        files = {".docs/introduction.md": f"# {spec.class_name}\n\n{spec.summary}\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract}\n\nDo not use a host clock, threads, randomness, files, or networking; all elapsed values are supplied by the caller.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API and primary state transitions\"\n\n[hidden]\ndescription = \"zero, boundary, invalid-input, saturation, repeated-transition, and stable-order cases\"\n", "task.h": spec.header, "task.cpp": spec.starter, ".meta/example.h": spec.header, ".meta/example.cpp": spec.reference, "task_visible_test.cpp": spec.visible, ".meta/task_hidden_test.cpp": spec.hidden, "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        root = out / spec.task_id
        with tempfile.TemporaryDirectory(prefix="countdown-timers-") as temp:
            copied = Path(temp) / spec.task_id
            shutil.copytree(root, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                common = ["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={copied / '.meta' / 'example.cpp'}", *flags]
                subprocess.run(common, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format countdown-timer curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} countdown-timer curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
