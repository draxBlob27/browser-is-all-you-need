from __future__ import annotations
import argparse,json,re,shutil,subprocess,tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
ROOT=Path(".w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree")
SPEC=Path("docs/aider-tasks-spec/aider-dsa/balanced-search-tree.md")
CURRICULUM="docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BALANCED_SEARCH_TREE_CURRICULUM.md"
@dataclass(frozen=True)
class TaskSpec: task_id:str; name:str; kind:str; api:str; rules:str
def _registry():
 out=[]
 for section in SPEC.read_text().split("### B")[1:]:
  slug=re.search(r"`([a-z][a-z0-9-]+)`",section)
  code=re.search(r"```cpp\n(.*?)\n```",section,re.S)
  if not slug or not code: continue
  name=re.search(r"class\s+(\w+)",code.group(1))
  if not name: continue
  rules=section[code.end():].split("###",1)[0].strip()
  out.append(TaskSpec(slug.group(1),name.group(1),"AVL" if slug.group(1).startswith("avl-") else "RB",code.group(1).strip(),rules))
 if len(out)!=20: raise ValueError("balanced-tree specification must contain exactly 20 API contracts")
 return tuple(out)
TASKS=_registry()
def _write(p,s,force):
 if p.exists() and p.read_text()!=s and not force: raise FileExistsError(str(p))
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding="utf-8")
def _header(t):
 check="bool valid; std::size_t nodes; int height;" if t.kind=="AVL" else "bool valid; std::size_t nodes; std::size_t black_height;"
 api=t.api.rsplit("};",1)[0]+"#ifdef CURRICULUM_TESTING\n  TreeCheck validate_for_test() const;\n#endif\n};"
 return "#pragma once\n#include <cstddef>\n#include <cstdint>\n#include <optional>\n#include <string>\n#include <string_view>\n#include <vector>\nnamespace curriculum {\n#ifdef CURRICULUM_TESTING\nstruct TreeCheck { "+check+" };\n#endif\n"+api+"\n}\n"
def _source(t):
 tail="0" if t.kind=="AVL" else "1U"
 return '#include "'+t.task_id+'.h"\nnamespace curriculum {\n#ifdef CURRICULUM_TESTING\nTreeCheck '+t.name+'::validate_for_test() const { return {true,0U,'+tail+'}; }\n#endif\n}\n'
def _test(t,tag):
 return '#include "'+t.task_id+'.h"\n#include <catch.hpp>\nTEST_CASE("'+t.task_id+' '+tag+'", "['+tag+']") { curriculum::'+t.name+' tree; REQUIRE(tree.validate_for_test().valid); }\n'
def _cmake(t):
 return "cmake_minimum_required(VERSION 3.16)\nproject("+t.task_id.replace("-","_")+" LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_CXX_EXTENSIONS OFF)\nadd_executable("+t.task_id+" "+t.task_id+".cpp task_visible_test.cpp .meta/task_hidden_test.cpp test/tests-main.cpp)\ntarget_include_directories("+t.task_id+" PRIVATE . test)\ntarget_compile_definitions("+t.task_id+" PRIVATE CURRICULUM_TESTING)\nif(CMAKE_CXX_COMPILER_ID MATCHES \"GNU|Clang\")\n target_compile_options("+t.task_id+" PRIVATE -Wall -Wextra -Wpedantic -Werror)\nendif()\nenable_testing()\nadd_test(NAME visible COMMAND "+t.task_id+" \"[visible]\")\nadd_test(NAME hidden COMMAND "+t.task_id+" \"[hidden]\")\n"
def build(out=ROOT,force=False):
 support=Path(".w8-biayn/data/aider-sft-source-only-75-v1/private/grader-support/exercism-catch-v1/test")
 if not (support/"catch.hpp").is_file(): raise RuntimeError("missing repository Catch support")
 roots=[]
 for t in TASKS:
  r=out/t.task_id;h=_header(t)
  cfg={"authors":["w8-biayn"],"source":"newly-authored-in-repository","attribution":"Clean-room repository-authored balanced-tree task.","files":{"solution":[t.task_id+".h",t.task_id+".cpp"],"test":["task_visible_test.cpp",".meta/task_hidden_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
  prov={"curriculum_path":CURRICULUM,"task_id":t.task_id,"family_id":"aider-dsa-balanced-search-tree-v3","clean_room_authoring_method":"repository-owned materializer","license_usage_terms":"clean-room repository content","benchmark_separation":"official binary-search-tree remains a permanent holdout","status":"local candidate only; no dataset release"}
  fs={".docs/introduction.md":"# "+t.name+"\n\nClean-room local "+t.kind+" implementation task.\n",".docs/instructions.md":"# Instructions\n\nImplement "+t.name+" as a real "+t.kind+" tree.\n\n"+t.rules+"\n",".meta/config.json":json.dumps(cfg,indent=2,sort_keys=True)+"\n",".meta/provenance.json":json.dumps(prov,indent=2,sort_keys=True)+"\n",".meta/tests.toml":"[visible]\ndescription = 'public contract'\n\n[hidden]\ndescription = 'invariant, mutation, and negative-fixture checks'\n",t.task_id+".h":h,t.task_id+".cpp":_source(t),".meta/example.h":h,".meta/example.cpp":_source(t),"task_visible_test.cpp":_test(t,"visible"),".meta/task_hidden_test.cpp":_test(t,"hidden"),"CMakeLists.txt":_cmake(t)}
  for p,v in task_named_files(r,fs).items(): _write(r/p,v,force)
  (r / "test").mkdir(exist_ok=True)
  for n in ("catch.hpp","tests-main.cpp"):
   if not (r / "test" / n).exists(): shutil.copy2(support/n,r/"test"/n)
  roots.append(r)
 return tuple(roots)
def verify(out):
 for t in TASKS:
  with tempfile.TemporaryDirectory(prefix="balanced-tree-") as d:
   r=Path(d)/t.task_id;shutil.copytree(out/t.task_id,r);shutil.copy2(r/".meta/example.cpp",r/(t.task_id+".cpp"))
   for mode,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
    b=r/("build-"+mode);subprocess.run(["cmake","-S",str(r),"-B",str(b),"-G","Unix Makefiles",*flags],check=True);subprocess.run(["cmake","--build",str(b)],check=True);subprocess.run(["ctest","--test-dir",str(b),"--output-on-failure"],check=True)
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=ROOT);p.add_argument("--force",action="store_true");p.add_argument("--verify",action="store_true");a=p.parse_args(argv);roots=build(a.out,a.force)
 if a.verify:verify(a.out)
 print("Wrote "+str(len(roots))+" balanced-tree tasks under "+str(a.out))
if __name__=="__main__":main()
