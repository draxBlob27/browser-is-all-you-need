"""Materialize newly-authored local circular-buffer Aider curriculum tasks."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/circular-buffer")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_CIRCULAR_BUFFER_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; add: str; take: str; snapshot: str; policy: str; contract: str

_ROWS = (
 ("ring-telemetry-history","TelemetryHistory","record_sample","discard_oldest","ordered_samples","optional","Record samples; callers explicitly select oldest-sample overwrite."),
 ("ring-audio-frame-store","AudioFrameStore","queue_frame","play_next","queued_frames","reject","Queue audio frames FIFO and reject overflow."),
 ("ring-camera-preview","CameraPreview","capture_frame","release_oldest","preview_frames","optional","Forced capture evicts exactly one oldest preview frame when full."),
 ("ring-gps-trail","GpsTrail","append_coordinate","drop_oldest","coordinates","overwrite","Retain newest route coordinates, replacing the oldest at capacity."),
 ("ring-ui-event-queue","UiEventQueue","enqueue_event","dispatch_next","pending_events","reject","Enqueue and dispatch bounded UI events without overwriting."),
 ("ring-keyboard-input","KeyboardInput","buffer_key","consume_next","buffered_keys","reject","Buffer keystrokes FIFO and reject overflow without state mutation."),
 ("ring-network-packets","NetworkPackets","receive_packet","read_next","packet_metadata","reject","Receive packet metadata FIFO and reject arrivals after capacity."),
 ("ring-stock-ticks","StockTickWindow","record_tick","remove_oldest","ticks","overwrite","Store a recent price window and replace its oldest tick at capacity."),
 ("ring-workout-laps","WorkoutLaps","add_lap","remove_oldest","laps","overwrite","Add lap records while retaining a recent fixed-capacity history."),
 ("ring-print-spool","PrintSpool","submit_job","dispatch_next","queued_jobs","reject","Accept print jobs until full and dispatch the oldest queued job."),
 ("ring-game-replay","GameReplay","record_event","discard_oldest","events","overwrite","Maintain a fixed replay-event tail in chronological order."),
 ("ring-machine-alerts","MachineAlerts","record_alert","acknowledge_oldest","alerts","optional","Critical alerts may force-record by evicting exactly one oldest alert."),
 ("ring-log-tail","LogTail","append_line","remove_oldest","lines","overwrite","Append a bounded log suffix while retaining insertion order."),
 ("ring-currency-quotes","CurrencyQuotes","record_quote","discard_oldest","quotes","overwrite","Keep a bounded quote stream and evict its oldest quote at capacity."),
 ("ring-medication-reminders","MedicationReminders","queue_reminder","deliver_next","pending_reminders","optional","Permit stale-reminder overwrite only when explicitly requested."),
 ("ring-customer-arrivals","CustomerArrivals","record_arrival","serve_next","waiting_customers","reject","Record arrivals and serve the oldest customer FIFO."),
 ("ring-bus-messages","BusMessages","send_message","read_next","messages","optional","Distinguish a rejected full-buffer send from caller-authorized overwrite."),
 ("ring-build-events","BuildEvents","record_event","take_oldest","events","overwrite","Retain recent compiler events in chronological sequence order."),
 ("ring-weather-readings","WeatherReadings","record_reading","remove_oldest","readings","overwrite","Maintain a rolling environmental reading window."),
 ("ring-delivery-scans","DeliveryScans","add_scan","pop_oldest","scans","reject","Add parcel scans FIFO and expose wraparound-safe snapshots."),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)

def _decl(s: TaskSpec) -> str: return f"bool {s.add}(int value, bool overwrite_oldest);" if s.policy == "optional" else f"bool {s.add}(int value);"
def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {{
class {s.class_name} {{ public:
  explicit {s.class_name}(std::size_t capacity); std::size_t capacity() const; std::size_t size() const; bool empty() const;
  {_decl(s)} std::optional<int> {s.take}(); std::vector<int> {s.snapshot}() const; void clear();
  std::optional<int> oldest() const; std::optional<int> newest() const;
private: bool push(int value, bool overwrite); std::optional<int> pop_front(); int at(std::size_t index) const;
  std::vector<int> slots_; std::size_t head_ = 0, size_ = 0;
}}; }}  // namespace curriculum
#endif
'''
def _reference(s: TaskSpec) -> str:
    add = f"bool {s.class_name}::{s.add}(int value, bool overwrite_oldest) {{ return push(value, overwrite_oldest); }}" if s.policy == "optional" else f"bool {s.class_name}::{s.add}(int value) {{ return push(value, {'true' if s.policy == 'overwrite' else 'false'}); }}"
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : slots_(capacity) {{}}
std::size_t {s.class_name}::capacity() const {{ return slots_.size(); }} std::size_t {s.class_name}::size() const {{ return size_; }} bool {s.class_name}::empty() const {{ return size_ == 0U; }}
bool {s.class_name}::push(int value, bool overwrite) {{ if (slots_.empty()) return false; if (size_ == slots_.size()) {{ if (!overwrite) return false; slots_[head_] = value; head_ = (head_ + 1U) % slots_.size(); return true; }} slots_[(head_ + size_) % slots_.size()] = value; ++size_; return true; }}
std::optional<int> {s.class_name}::pop_front() {{ if (empty()) return std::nullopt; const int value = slots_[head_]; head_ = (head_ + 1U) % slots_.size(); --size_; return value; }}
int {s.class_name}::at(std::size_t index) const {{ return slots_[(head_ + index) % slots_.size()]; }}
{add}
std::optional<int> {s.class_name}::{s.take}() {{ return pop_front(); }} std::vector<int> {s.class_name}::{s.snapshot}() const {{ std::vector<int> out; for (std::size_t i=0;i<size_;++i) out.push_back(at(i)); return out; }}
void {s.class_name}::clear() {{ head_ = 0; size_ = 0; }} std::optional<int> {s.class_name}::oldest() const {{ return empty() ? std::nullopt : std::optional<int>(at(0)); }} std::optional<int> {s.class_name}::newest() const {{ return empty() ? std::nullopt : std::optional<int>(at(size_-1U)); }}
}}  // namespace curriculum
'''
def _starter(s: TaskSpec) -> str:
    add = f"bool {s.class_name}::{s.add}(int, bool) {{ return false; }}" if s.policy == "optional" else f"bool {s.class_name}::{s.add}(int) {{ return false; }}"
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t) {{}} std::size_t {s.class_name}::capacity() const {{ return 0; }} std::size_t {s.class_name}::size() const {{ return 0; }} bool {s.class_name}::empty() const {{ return true; }}
bool {s.class_name}::push(int, bool) {{ return false; }} std::optional<int> {s.class_name}::pop_front() {{ return std::nullopt; }} int {s.class_name}::at(std::size_t) const {{ return 0; }} {add}
std::optional<int> {s.class_name}::{s.take}() {{ return std::nullopt; }} std::vector<int> {s.class_name}::{s.snapshot}() const {{ return {{}}; }} void {s.class_name}::clear() {{}} std::optional<int> {s.class_name}::oldest() const {{ return std::nullopt; }} std::optional<int> {s.class_name}::newest() const {{ return std::nullopt; }}
}}  // namespace curriculum
'''
def _call(s: TaskSpec, obj: str, value: str, overwrite: str = "false") -> str: return f"{obj}.{s.add}({value}, {overwrite})" if s.policy == "optional" else f"{obj}.{s.add}({value})"
def _test(s: TaskSpec, hidden: bool) -> str:
    initial = " ".join(f"check({_call(s, 'buffer', str(n))});" for n in (10,20,30)); full = _call(s,"buffer","40")
    if s.policy == "optional": full_check, expected = f"check(!{full}); check({_call(s,'buffer','40','true')});", "std::vector<int>{20, 30, 40}"
    elif s.policy == "overwrite": full_check, expected = f"check({full});", "std::vector<int>{20, 30, 40}"
    else: full_check, expected = f"check(!{full});", "std::vector<int>{10, 20, 30}"
    trace = ""
    if hidden:
      action = _call(s,"trace","value","step % 5 == 0")
      oracle = "if (oracle.size()==4U) oracle.pop_front(); oracle.push_back(value); expected=true;" if s.policy == "overwrite" else ("if (oracle.size()<4U) { oracle.push_back(value); expected=true; } else if (step%5==0) { oracle.pop_front(); oracle.push_back(value); expected=true; }" if s.policy == "optional" else "if (oracle.size()<4U) { oracle.push_back(value); expected=true; }")
      trace = f'''\n  curriculum::{s.class_name} trace(4); std::deque<int> oracle; for (int step=1;step<=240;++step) {{ if (step%3==0) {{ const auto got=trace.{s.take}(); check(got==(oracle.empty()?std::nullopt:std::optional<int>(oracle.front()))); if(!oracle.empty()) oracle.pop_front(); }} else {{ int value=(step*37)%101; bool expected=false; {oracle} check({action}==expected); }} check(trace.{s.snapshot}()==std::vector<int>(oracle.begin(),oracle.end())); }}'''
    return f'''#include "task.h"
#include <deque>
#include <optional>
#include <vector>
int main() {{ int failures=0; const auto check=[&](bool ok){{if(!ok)++failures;}}; curriculum::{s.class_name} zero(0); check(zero.empty()); check(!{_call(s,'zero','1','true')}); curriculum::{s.class_name} buffer(3); check(!buffer.{s.take}()); {initial} {full_check} check(buffer.{s.snapshot}()=={expected}); check(buffer.oldest()==std::optional<int>({expected}[0])); check(buffer.newest()==std::optional<int>({expected}[2])); buffer.clear(); check(buffer.empty());{trace} return failures==0?0:1; }}
'''
def _cmake() -> str: return '''cmake_minimum_required(VERSION 3.16)
project(circular_buffer_curriculum LANGUAGES CXX)
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
    roots=[]
    for s in TASKS:
      root=out/s.task_id; header=_header(s); config={"authors":["w8-biayn"],"blurb":s.contract,"files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
      provenance={"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"Not derived from the official Aider Polyglot circular-buffer task; domain API, policies, and observable contract are independently authored."}
      policy={"reject":"A full write is rejected without state mutation.","overwrite":"A full write replaces exactly one oldest item.","optional":"A full write is rejected unless the explicit overwrite flag is true; then it replaces exactly one oldest item."}[s.policy]
      files={".docs/introduction.md":f"# {s.class_name}\n\nA newly authored local fixed-capacity FIFO diagnostic task.\n",".docs/instructions.md":f"# Instructions\n\nImplement `{s.class_name}`. {s.contract} Zero capacity is valid but cannot retain an item. `{s.take}` returns and removes the oldest item or no value when empty. `{s.snapshot}()` is oldest-to-newest and does not mutate state. {policy}\n",".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n",".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n",".meta/tests.toml":"[visible]\ndescription = \"domain API, empty/full policy, FIFO order, and wraparound snapshots\"\n\n[hidden]\ndescription = \"zero/singleton boundaries, repeated wraparound, state-preserving rejection, overwrite transitions, and randomized std::deque oracle traces\"\n","task.h":header,"task.cpp":_starter(s),".meta/example.h":header,".meta/example.cpp":_reference(s),"task_visible_test.cpp":_test(s,False),".meta/task_hidden_test.cpp":_test(s,True),"CMakeLists.txt":_cmake()}
      files = task_named_files(root, files)
      for relative,content in files.items(): _write(root/relative,content,force)
      roots.append(root)
    return tuple(roots)
def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out/s.task_id for s in TASKS):
      with tempfile.TemporaryDirectory(prefix="circular-buffer-curriculum-") as temporary:
       copied=Path(temporary)/root.name; shutil.copytree(root,copied); reference=copied/".meta/example.cpp"
       for name,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
        build_dir=copied/f"build-{name}"; subprocess.run(["cmake","-S",str(copied),"-B",str(build_dir),f"-DTASK_SOURCE={reference}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Materialize local Aider-format circular-buffer curriculum tasks."); parser.add_argument("--out",type=Path,default=DEFAULT_OUT); parser.add_argument("--force",action="store_true"); parser.add_argument("--verify",action="store_true"); args=parser.parse_args(argv); roots=build(args.out,args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} circular-buffer curriculum tasks under {args.out}"); return 0
if __name__ == "__main__": raise SystemExit(main())
