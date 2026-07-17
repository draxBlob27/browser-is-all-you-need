"""Materialize newly-authored local robot state-simulation tasks."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/robot-simulation")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ROBOT_SIMULATION_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; action: str; refill: str; resource: str; result: str; domain: str

_ROWS = (
 ("sim-warehouse-picker","WarehousePicker","PickShelf","UnloadDock","load_units","picked_items","shelf map"),("sim-greenhouse-cart","GreenhouseCart","WaterPlot","FillTank","water_units","watered_plots","greenhouse lanes"),("sim-drone-delivery","DroneDelivery","DropParcel","RechargePad","battery_units","delivered_parcels","altitude-layer flight map"),("sim-harbor-crane","HarborCrane","PlaceContainer","ServiceBay","lift_energy","placed_containers","rail and stack map"),("sim-mars-rover-energy","MarsRoverEnergy","SampleTerrain","SolarCharge","energy_units","terrain_samples","terrain grid"),("sim-subway-maintenance","SubwayMaintenanceCart","InspectSection","SwitchBay","inspection_units","inspected_sections","connected track map"),("sim-firefighter-bot","FirefighterBot","ExtinguishFire","RefillHydrant","water_units","extinguished_fires","room and smoke map"),("sim-orchard-harvester","OrchardHarvester","HarvestTree","EmptyBin","bin_capacity","harvested_fruit","orchard rows"),("sim-hospital-courier","HospitalCourier","DeliverSample","SterilizeCart","sterile_units","delivered_samples","department corridor map"),("sim-ocean-survey","OceanSurveyVehicle","ScanSeafloor","SurfaceAtBuoy","oxygen_units","survey_scans","depth-layer survey map"),("sim-construction-hauler","ConstructionHauler","UnloadMaterial","LoadDepot","weight_capacity","delivered_material","weight-limited road map"),("sim-library-sorter","LibrarySorter","SortBook","ClearScanner","scan_units","sorted_books","return-station map"),("sim-factory-inspector","FactoryInspector","RecordFault","ResetLockout","inspection_units","recorded_faults","factory inspection route"),("sim-snowplow-route","SnowplowRoute","ClearRoad","RefillSalt","salt_units","cleared_roads","one-way road grid"),("sim-space-station-repair","SpaceStationRepair","SealLeak","RestockKits","repair_kits","sealed_leaks","airlock module map"),("sim-museum-guide","MuseumGuide","PresentLandmark","ResetTour","tour_energy","visited_landmarks","gallery map"),("sim-recycling-sorter","RecyclingSorter","SortMaterial","ClearJam","sort_units","sorted_items","conveyor map"),("sim-farm-irrigator","FarmIrrigator","WaterField","PressurizePump","pressure_units","watered_cells","irrigation-field map"),("sim-search-and-rescue","SearchAndRescueRover","RescueTarget","RestockMarkers","marker_units","rescued_targets","rubble exploration grid"),("sim-airport-tug","AirportTug","DecoupleAircraft","CoupleAtStand","tow_energy","delivered_aircraft","taxiway map"),)
TASKS = tuple(TaskSpec(*r) for r in _ROWS)

def write(p: Path, s: str, force: bool) -> None:
    if p.exists() and p.read_text() != s and not force: raise FileExistsError(f"{p} differs; pass --force")
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(s)

def header(x: TaskSpec) -> str: return f'''#pragma once
#include <vector>
namespace curriculum {{ class {x.class_name} {{ public: enum class Command {{ MoveForward, TurnClockwise, TurnCounterClockwise, {x.action}, {x.refill}, Halt }}; struct Report {{ bool completed=false; int {x.resource}=0; int {x.result}=0; int rejected=0; std::vector<int> trace; }}; explicit {x.class_name}(int initial_{x.resource}=4); Report execute(const std::vector<Command>&); Report snapshot() const; private: int r_=0,c_=0,h_=1,{x.resource}_=0,{x.result}_=0,rejected_=0; bool completed_=false; std::vector<int> trace_; }}; }}
'''

def reference(x: TaskSpec) -> str: return f'''#include "task.h"
#include <stdexcept>
namespace curriculum {{ {x.class_name}::{x.class_name}(int n):{x.resource}_(n){{if(n<0)throw std::invalid_argument("resource");}} {x.class_name}::Report {x.class_name}::snapshot()const{{return{{completed_,{x.resource}_,{x.result}_,rejected_,trace_}};}} {x.class_name}::Report {x.class_name}::execute(const std::vector<Command>& cs){{static const int dr[]={{-1,0,1,0}},dc[]={{0,1,0,-1}};for(auto q:cs){{if(q==Command::Halt){{completed_={x.result}_>0;trace_.push_back(6);}}else if(q==Command::TurnClockwise){{h_=(h_+1)%4;trace_.push_back(2);}}else if(q==Command::TurnCounterClockwise){{h_=(h_+3)%4;trace_.push_back(3);}}else if(q==Command::MoveForward){{int nr=r_+dr[h_],nc=c_+dc[h_];if(nr<0||nr>3||nc<0||nc>3||(nr==2&&nc==1)||{x.resource}_==0){{++rejected_;trace_.push_back(-1);}}else{{r_=nr;c_=nc;--{x.resource}_;trace_.push_back(1);}}}}else if(q==Command::{x.refill}){{if(r_==0&&c_==0){{{x.resource}_=4;trace_.push_back(5);}}else{{++rejected_;trace_.push_back(-5);}}}}else if(q==Command::{x.action}){{if(r_==3&&c_==3&&{x.resource}_>0){{--{x.resource}_;++{x.result}_;trace_.push_back(4);}}else{{++rejected_;trace_.push_back(-4);}}}}}}return snapshot();}} }}
'''

def starter(x: TaskSpec) -> str: return f'''#include "task.h"
namespace curriculum {{ {x.class_name}::{x.class_name}(int n):{x.resource}_(n){{}} {x.class_name}::Report {x.class_name}::snapshot()const{{return{{}};}} {x.class_name}::Report {x.class_name}::execute(const std::vector<Command>&){{return{{}};}} }}
'''

def test(x: TaskSpec, hidden: bool) -> str:
    route="MoveForward,C::MoveForward,C::TurnClockwise,C::MoveForward,C::MoveForward,C::TurnCounterClockwise,C::MoveForward,C::MoveForward"
    extra=f''' curriculum::{x.class_name} bad(1);auto b=bad.execute({{C::MoveForward,C::MoveForward,C::{x.action}}});check(b.rejected==2&&b.{x.result}==0); curriculum::{x.class_name} refill(0);check(refill.execute({{C::{x.refill}}}).{x.resource}==4);''' if hidden else ""
    return f'''#include "task.h"
#include <stdexcept>
int main(){{int f=0;auto check=[&](bool v){{if(!v)++f;}};using C=curriculum::{x.class_name}::Command;try{{curriculum::{x.class_name} n(-1);check(false);}}catch(const std::invalid_argument&){{}} curriculum::{x.class_name} u(4);auto a=u.execute({{C::{route},C::{x.action},C::Halt}});check(a.completed&&a.{x.result}==1&&a.{x.resource}==0&&a.rejected==0);{extra}return f?1:0;}}
'''

CMAKE='''cmake_minimum_required(VERSION 3.16)
project(robot_simulation LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(n visible hidden) target_include_directories(task_${n} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}") target_compile_options(task_${n} PRIVATE -Wall -Wextra -Wpedantic -Werror) add_test(NAME ${n} COMMAND task_${n}) endforeach()
enable_testing()
'''
def build(out: Path=DEFAULT_OUT, force: bool=False) -> tuple[Path,...]:
    roots=[]
    for x in TASKS:
        root=out/x.task_id; h=header(x); cfg={"authors":["w8-biayn"],"blurb":f"A newly authored {x.domain} state simulation.","files":{"solution":["task.h","task.cpp"],"test":[".meta/task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}; prov={"curriculum_document":CURRICULUM,"curriculum_task_id":x.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"Task-specific state, commands, API, resource rules, and tests; not derived from an Aider robot holdout."}
        files={".docs/introduction.md":f"# {x.class_name}\n\nA newly authored local {x.domain} diagnostic.\n", ".docs/instructions.md":f"# Instructions\n\nImplement `{x.class_name}`. It starts at depot (0,0), faces east, uses a 4x4 map, and cannot enter (2,1). Moving consumes `{x.resource}` and rejected moves do not mutate position. `{x.action}` only succeeds at (3,3) with resource remaining; `{x.refill}` only succeeds at depot and restores four units. Turns do not consume resources. `Halt` completes only after an action. Reports preserve ordered trace and rejected-command count.\n", ".meta/config.json":json.dumps(cfg,indent=2)+"\n", ".meta/provenance.json":json.dumps(prov,indent=2)+"\n", ".meta/tests.toml":"[visible]\ndescription = \"movement, resource, action, report\"\n\n[hidden]\ndescription = \"boundaries, no-mutation failures, refill, and sanitizer\"\n", "task.h":h,"task.cpp":starter(x),".meta/example.h":h,".meta/example.cpp":reference(x),"task_visible_test.cpp":test(x,False),".meta/task_hidden_test.cpp":test(x,True),"CMakeLists.txt":CMAKE}
        files = task_named_files(root, files)
        for n,v in files.items(): write(root/n,v,force)
        roots.append(root)
    return tuple(roots)
def verify(out:Path)->None:
    if not shutil.which("cmake") or not shutil.which("c++"): raise RuntimeError("verification requires cmake and c++")
    for root in (out/x.task_id for x in TASKS):
      with tempfile.TemporaryDirectory() as tmp:
       copy=Path(tmp)/root.name;shutil.copytree(root,copy)
       for n,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
        b=copy/f"build-{n}";subprocess.run(["cmake","-S",str(copy),"-B",str(b),f"-DTASK_SOURCE={copy/'.meta/example.cpp'}",*flags],check=True);subprocess.run(["cmake","--build",str(b)],check=True);subprocess.run(["ctest","--test-dir",str(b),"--output-on-failure"],check=True)
def main(argv:Sequence[str]|None=None)->int:
 p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=DEFAULT_OUT);p.add_argument("--force",action="store_true");p.add_argument("--verify",action="store_true");a=p.parse_args(argv);roots=build(a.out,a.force);a.verify and verify(a.out);print(f"Wrote {len(roots)} robot-state-simulation curriculum tasks under {a.out}");return 0
if __name__=="__main__":raise SystemExit(main())
