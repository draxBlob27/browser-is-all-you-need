"""Materialize the newly-authored deterministic skip-list curriculum."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT=Path(".w8-biayn/data/aider-tasks/aider-dsa/skip-list")
CURRICULUM="docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SKIP_LIST_CURRICULUM.md"
@dataclass(frozen=True)
class Task: task_id:str; cls:str; entity:str; add:str; remove:str; revise:str; page:str; order:str
_ROWS=(
("skip-live-leaderboard","LiveLeaderboard","player","join_player","remove_player","update_score","leaderboard_page","score descending, ID ascending"),("skip-event-timeline","EventTimeline","event","record_event","retract_event","retime_event","events_from","timestamp ascending, ID ascending"),("skip-percentile-meter","PercentileMeter","observation","add_observation","discard_observation","correct_observation","quantile_page","value ascending, ID ascending"),("skip-log-retention","LogRetention","log record","append_record","delete_record","renumber_record","records_after","sequence ascending, ID ascending"),("skip-route-markers","RouteMarkers","marker","place_marker","remove_marker","move_marker","markers_from","distance ascending, ID ascending"),("skip-cargo-priorities","CargoPriorities","cargo item","register_cargo","withdraw_cargo","reprioritize_cargo","priority_slice","priority descending, ID ascending"),("skip-reservation-waitlist","ReservationWaitlist","reservation","join_waitlist","cancel_reservation","reprioritize_reservation","waitlist_page","priority descending, ID ascending"),("skip-notebook-lines","NotebookLines","line","insert_line","delete_line","renumber_line","lines_from","ordinal ascending, ID ascending"),("skip-student-ranks","StudentRanks","student","enroll_student","remove_student","update_score","nearby_students","score descending, ID ascending"),("skip-search-result-pages","SearchResultPages","result","index_result","remove_result","rescore_result","results_after","score descending, ID ascending"),("skip-metric-window","MetricWindow","sample","add_sample","evict_sample","correct_sample","samples_from","value ascending, ID ascending"),("skip-file-offset-index","FileOffsetIndex","file block","add_block","remove_block","relocate_block","blocks_from","offset ascending, ID ascending"),("skip-order-statistics","OrderStatistics","entry","insert_value","erase_value","replace_value","values_from","value ascending, ID ascending"),("skip-feature-rollout","FeatureRollout","threshold","add_threshold","retire_threshold","change_threshold","thresholds_from","bucket ascending, ID ascending"),("skip-expiring-cache-index","ExpiringCacheIndex","cache key","register_expiry","remove_key","reschedule_expiry","expiries_from","expiry ascending, ID ascending"),("skip-auction-price-levels","AuctionPriceLevels","price level","add_level","cancel_level","amend_level","levels_from","price descending, ID ascending"),("skip-calendar-slots","CalendarSlots","slot","reserve_slot","cancel_slot","reschedule_slot","available_from","time ascending, ID ascending"),("skip-inventory-reorder","InventoryReorder","stock level","track_stock","remove_stock","adjust_reorder_point","affected_from","point ascending, ID ascending"),("skip-document-anchors","DocumentAnchors","anchor","insert_anchor","remove_anchor","move_anchor","anchors_from","position ascending, ID ascending"),("skip-transit-departures","TransitDepartures","departure","schedule_departure","cancel_departure","retime_departure","departures_from","time ascending, ID ascending"))
TASKS=tuple(Task(*r) for r in _ROWS)
def write(p:Path,s:str,force:bool):
 if p.exists() and p.read_text()!=s and not force: raise FileExistsError(f"{p} differs; pass --force")
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
def header(t:Task): return f'''#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
namespace curriculum {{ class {t.cls} {{ public: struct Entry {{ int id; int key; std::string label; }}; explicit {t.cls}(unsigned seed=1,int levels=8); ~{t.cls}(); {t.cls}(const {t.cls}&)=delete; bool {t.add}(int,int,const std::string&); bool {t.remove}(int); bool {t.revise}(int,int,const std::string&); std::optional<std::size_t> rank_of(int) const; std::optional<Entry> select(std::size_t) const; std::vector<Entry> {t.page}(int,int,std::size_t) const; std::vector<Entry> range(int,int) const; std::size_t size() const; bool links_consistent() const; private: struct Node {{ Entry e; std::vector<Node*> next; }}; int levels_; unsigned seed_; Node* head_; std::unordered_map<int,Node*> ids_; int level_for(int,int) const; static bool before(const Entry&,const Entry&); }}; }}
'''
def reference(t:Task): return f'''#include "task.h"
#include <stdexcept>
namespace curriculum {{
{t.cls}::{t.cls}(unsigned seed,int levels):levels_(levels),seed_(seed),head_(nullptr){{if(levels<1||levels>16)throw std::invalid_argument("levels");head_=new Node{{{{0,0,""}},std::vector<Node*>(levels,nullptr)}};}}
{t.cls}::~{t.cls}(){{for(Node*n=head_->next[0];n;){{Node*x=n->next[0];delete n;n=x;}}delete head_;}}
bool {t.cls}::before(const Entry&a,const Entry&b){{return a.key!=b.key?a.key<b.key:a.id<b.id;}}
int {t.cls}::level_for(int id,int key)const{{unsigned x=seed_^unsigned(id*2654435761U)^unsigned(key*2246822519U);int n=1;while(n<levels_&&(x&3U)==0U){{++n;x=x*1664525U+1013904223U;}}return n;}}
bool {t.cls}::{t.add}(int id,int key,const std::string&label){{if(id<=0||key<0||label.empty()||ids_.count(id))return false;Entry e{{id,key,label}};std::vector<Node*>u(levels_,head_);Node*c=head_;for(int l=levels_-1;l>=0;--l){{while(c->next[l]&&before(c->next[l]->e,e))c=c->next[l];u[l]=c;}}Node*n=new Node{{e,std::vector<Node*>(level_for(id,key),nullptr)}};for(size_t l=0;l<n->next.size();++l){{n->next[l]=u[l]->next[l];u[l]->next[l]=n;}}ids_[id]=n;return true;}}
bool {t.cls}::{t.remove}(int id){{auto it=ids_.find(id);if(it==ids_.end())return false;Node*x=it->second;std::vector<Node*>u(levels_,head_);Node*c=head_;for(int l=levels_-1;l>=0;--l){{while(c->next[l]&&c->next[l]!=x&&before(c->next[l]->e,x->e))c=c->next[l];u[l]=c;}}for(size_t l=0;l<x->next.size();++l)if(u[l]->next[l]==x)u[l]->next[l]=x->next[l];ids_.erase(it);delete x;return true;}}
bool {t.cls}::{t.revise}(int id,int key,const std::string&label){{if(!ids_.count(id)||key<0||label.empty())return false;{t.remove}(id);return {t.add}(id,key,label);}}
std::optional<std::size_t> {t.cls}::rank_of(int id)const{{size_t i=0;for(Node*n=head_->next[0];n;n=n->next[0],++i)if(n->e.id==id)return i;return {{}};}}
std::optional<{t.cls}::Entry> {t.cls}::select(size_t i)const{{for(Node*n=head_->next[0];n;n=n->next[0])if(i--==0)return n->e;return {{}};}}
std::vector<{t.cls}::Entry> {t.cls}::{t.page}(int key,int id,size_t limit)const{{std::vector<Entry>r;if(key<0||id<0)return r;Entry c{{id,key,""}};Node*n=head_;for(int l=levels_-1;l>=0;--l)while(n->next[l]&&!before(c,n->next[l]->e))n=n->next[l];for(n=n->next[0];n&&r.size()<limit;n=n->next[0])r.push_back(n->e);return r;}}
std::vector<{t.cls}::Entry> {t.cls}::range(int lo,int hi)const{{std::vector<Entry>r;if(lo>hi||lo<0)return r;for(Node*n=head_->next[0];n;n=n->next[0])if(n->e.key>=lo&&n->e.key<=hi)r.push_back(n->e);return r;}}
std::size_t {t.cls}::size()const{{return ids_.size();}}
bool {t.cls}::links_consistent()const{{std::unordered_map<const Node*,bool>zero;const Node*p=nullptr;for(const Node*n=head_->next[0];n;n=n->next[0]){{if((p&&!before(p->e,n->e))||!ids_.count(n->e.id))return false;zero[n]=true;p=n;}}if(zero.size()!=ids_.size())return false;for(int l=1;l<levels_;++l){{p=nullptr;for(const Node*n=head_->next[l];n;n=n->next[l]){{if(n->next.size()<=size_t(l)||!zero.count(n)||(p&&!before(p->e,n->e)))return false;p=n;}}}}return true;}}
}}'''
def starter(t:Task): return f'''#include "task.h"
#include <stdexcept>
namespace curriculum {{ {t.cls}::{t.cls}(unsigned s,int l):levels_(l),seed_(s),head_(nullptr){{if(l<1)throw std::invalid_argument("levels");}} {t.cls}::~{t.cls}()=default; bool {t.cls}::{t.add}(int,int,const std::string&){{return false;}} bool {t.cls}::{t.remove}(int){{return false;}} bool {t.cls}::{t.revise}(int,int,const std::string&){{return false;}} std::optional<std::size_t> {t.cls}::rank_of(int)const{{return {{}};}} std::optional<{t.cls}::Entry> {t.cls}::select(std::size_t)const{{return {{}};}} std::vector<{t.cls}::Entry> {t.cls}::{t.page}(int,int,std::size_t)const{{return {{}};}} std::vector<{t.cls}::Entry> {t.cls}::range(int,int)const{{return {{}};}} std::size_t {t.cls}::size()const{{return 0;}} bool {t.cls}::links_consistent()const{{return false;}} int {t.cls}::level_for(int,int)const{{return 1;}} bool {t.cls}::before(const Entry&,const Entry&){{return false;}} }}'''
def test(t:Task,hidden:bool):
 extra='for(int i=3;i<120;++i)ok(x.'+t.add+'(i,(i*37)%97,"v"));for(int i=3;i<120;i+=5)ok(x.'+t.remove+'(i));for(size_t i=1;i<x.size();++i){auto a=x.select(i-1),b=x.select(i);ok(a&&b&&(a->key<b->key||(a->key==b->key&&a->id<b->id)));}' if hidden else ''
 return f'''#include "task.h"
int main(){{int f=0;auto ok=[&](bool v){{if(!v)++f;}};curriculum::{t.cls} x(7,6);ok(!x.{t.add}(0,1,"x"));ok(x.{t.add}(10,20,"a"));ok(x.{t.add}(2,10,"b"));ok(x.{t.add}(7,20,"c"));ok(!x.{t.add}(10,2,"d"));ok(x.links_consistent());ok(x.rank_of(2).value()==0);auto p=x.{t.page}(10,2,2);ok(p.size()==2&&p[0].id==10&&p[1].id==7);ok(x.{t.revise}(10,5,"z"));ok(x.rank_of(10).value()==0);ok(x.{t.remove}(7)&&!x.{t.remove}(7));{extra}ok(x.links_consistent());return f?1:0;}}'''
def cmake(): return '''cmake_minimum_required(VERSION 3.16)
project(skip_list LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(n task_visible task_hidden)
 target_include_directories(${n} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 target_compile_options(${n} PRIVATE -Wall -Wextra -Wpedantic -Werror)
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''
def build(out:Path=DEFAULT_OUT,force:bool=False)->tuple[Path,...]:
 roots=[]
 for t in TASKS:
  r=out/t.task_id;h=header(t);cfg={"authors":["w8-biayn"],"blurb":f"New deterministic skip-list diagnostic for {t.entity} ordering.","files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}};prov={"curriculum_document":CURRICULUM,"curriculum_task_id":t.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"Newly authored domain API, seeded promotion, tests, and reference; not derived from official Aider Polyglot artifacts."}
  ins=f"# Instructions\n\nImplement `{t.cls}` for ordered {t.entity} records. `{t.add}` accepts a positive unique ID, nonnegative key, and nonempty label. `{t.remove}` and `{t.revise}` leave state unchanged on failure. Records use {t.order}. `rank_of` and `select` are zero based. `{t.page}` is strictly after its `(key, id)` cursor and `range` includes both boundaries. The seed makes promotion reproducible. `links_consistent` must check sorted level-zero membership and every promoted level.\n"
  files={".docs/introduction.md":f"# {t.cls}\n\nNew local skip-list diagnostic for {t.entity} ordering.\n",".docs/instructions.md":ins,".meta/config.json":json.dumps(cfg,indent=2)+"\n",".meta/provenance.json":json.dumps(prov,indent=2)+"\n",".meta/tests.toml":"[visible]\ndescription = \"validation, rank/select, cursor and ordering\"\n\n[hidden]\ndescription = \"seeded mutations, promoted-node removal and level-link invariants\"\n","task.h":h,"task.cpp":starter(t),".meta/example.h":h,".meta/example.cpp":reference(t),"task_visible_test.cpp":test(t,False),".meta/task_hidden_test.cpp":test(t,True),"CMakeLists.txt":cmake()}
  files = task_named_files(r, files)
  for n,c in files.items():write(r/n,c,force)
  roots.append(r)
 return tuple(roots)
def verify(out:Path):
 if not shutil.which("cmake") or not shutil.which("c++"):raise RuntimeError("verification requires cmake and c++")
 for t in TASKS:
  with tempfile.TemporaryDirectory(prefix="skip-list-") as d:
   r=Path(d)/t.task_id;shutil.copytree(out/t.task_id,r)
   for n,f in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
    b=r/f"build-{n}";subprocess.run(["cmake","-S",str(r),"-B",str(b),f"-DTASK_SOURCE={r/'.meta/example.cpp'}",*f],check=True);subprocess.run(["cmake","--build",str(b)],check=True);subprocess.run(["ctest","--test-dir",str(b),"--output-on-failure"],check=True)
def main(argv:Sequence[str]|None=None)->int:
 p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=DEFAULT_OUT);p.add_argument("--force",action="store_true");p.add_argument("--verify",action="store_true");a=p.parse_args(argv);roots=build(a.out,a.force)
 if a.verify:verify(a.out)
 print(f"Wrote {len(roots)} skip-list curriculum tasks under {a.out}");return 0
if __name__=="__main__":raise SystemExit(main())
