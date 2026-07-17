"""Materialize decontaminated nested-structure local Aider tasks."""
from __future__ import annotations

import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/nested-structure")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_NESTED_STRUCTURE_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; method: str; opener: str; closer: str; grammar: str

_RAW = (
 ("nest-config-sections","ConfigSectionValidator","inspect_sections","begin ","end ","named begin/end sections"),("nest-template-placeholders","TemplatePlaceholderParser","parse_template","{{","}}","nested placeholders"),("nest-rich-text-tags","RichTextTagValidator","validate_markup","<tag>","</tag>","typed rich-text tags"),("nest-code-fences","CodeFenceChecker","check_fences","```", "```", "labeled code fences"),("nest-workflow-scopes","WorkflowScopeChecker","check_workflow","open ","close ","workflow scopes"),("nest-query-groups","QueryGroupParser","parse_groups","(",")","boolean query groups"),("nest-math-expressions","MathExpressionScanner","scan_expression","(",")","math expression groups"),("nest-markdown-links","MarkdownLinkParser","inspect_links","[","]","link-label regions"),("nest-script-comments","ScriptCommentStripper","inspect_comments","/*","*/","nested block comments"),("nest-command-blocks","CommandBlockValidator","validate_commands","command ","endcommand","command blocks"),("nest-json-stream","JsonStreamChecker","consume_chunk","{","}","streamed object scopes"),("nest-regex-groups","RegexGroupInspector","inspect_groups","(",")","regex capture groups"),("nest-protocol-frames","ProtocolFrameParser","parse_frames","<frame>","</frame>","length-marked frames"),("nest-spreadsheet-formulas","SpreadsheetFormulaChecker","check_formula","(",")","function argument groups"),("nest-recipe-steps","RecipeStepStructure","validate_steps","step ","endstep","recipe preparation blocks"),("nest-legal-clauses","LegalClauseNumbering","inspect_clauses","clause ","endclause","hierarchical clauses"),("nest-diagram-groups","DiagramGroupParser","parse_groups","group ","endgroup","drawing groups"),("nest-chat-quotes","ChatQuoteFormatter","inspect_quotes",">>","<<","multiline quote markers"),("nest-access-policies","AccessPolicyValidator","validate_policy","allow ","endallow","access-policy scopes"),("nest-build-directives","BuildDirectiveParser","parse_directives","if ","endif","build conditional directives"),
)
TASKS = tuple(TaskSpec(*row) for row in _RAW)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)

def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {{
struct StructureDiagnostic {{ bool valid = false; std::size_t offset = 0; std::string reason; std::vector<std::string> remaining; }};
class {s.class_name} {{ public: StructureDiagnostic {s.method}(const std::string& source) const; }};
}}  // namespace curriculum
#endif
'''

def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <vector>
namespace curriculum {{
StructureDiagnostic {s.class_name}::{s.method}(const std::string& source) const {{
 const std::string open = "{s.opener}", close = "{s.closer}"; std::vector<std::string> stack; char quote = 0;
 for (std::size_t i = 0; i < source.size();) {{
  if (source[i] == '\\\\') {{ i += i + 1 < source.size() ? 2 : 1; continue; }}
  if (quote) {{ if (source[i] == quote) quote = 0; ++i; continue; }}
  if (source[i] == '\\'' || source[i] == '\\"') {{ quote = source[i++]; continue; }}
  if (source.compare(i, open.size(), open) == 0) {{ if (open == close && !stack.empty()) stack.pop_back(); else stack.push_back(open); i += open.size(); continue; }}
  if (source.compare(i, close.size(), close) == 0) {{ if (stack.empty()) return {{false, i, "unexpected closing token", {{}}}}; stack.pop_back(); i += close.size(); continue; }}
  ++i;
 }}
 if (quote) return {{false, source.size(), "unterminated quoted literal", stack}};
 if (!stack.empty()) return {{false, source.size(), "unclosed opening token", stack}};
 return {{true, source.size(), "", {{}}}};
}}
}}  // namespace curriculum
'''

def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{ StructureDiagnostic {s.class_name}::{s.method}(const std::string&) const {{ return {{false, 0, "not implemented", {{}}}}; }} }}
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    open_, close = s.opener, s.closer
    valid = f"{open_}body{close}" if open_ != close else f"{open_}body{close}"
    unexpected = close + "orphan"
    unclosed = open_ + "body"
    repeated = open_ + open_ + "x" + close + close if open_ != close else open_ + "x" + close
    body = f'''curriculum::{s.class_name} parser; auto valid = parser.{s.method}("{valid}"); check(valid.valid); auto escaped = parser.{s.method}("\\\\{close}"); check(escaped.valid); auto quoted = parser.{s.method}("\\\"{close}\\\""); check(quoted.valid); auto orphan = parser.{s.method}("{unexpected}"); check(!orphan.valid && orphan.offset == 0U); auto incomplete = parser.{s.method}("{unclosed}"); check(!incomplete.valid && !incomplete.remaining.empty());'''
    if hidden: body += f''' for (int depth = 1; depth <= 128; ++depth) {{ std::string source; for (int i = 0; i < depth; ++i) source += "{open_}"; source += "x"; for (int i = 0; i < depth; ++i) source += "{close}"; check(parser.{s.method}(source).valid); }} check(parser.{s.method}("{repeated}").valid);'''
    return f'''#include "task.h"
int main() {{ int failures = 0; auto check = [&](bool ok) {{ if (!ok) ++failures; }}; {body} return failures ? 1 : 0; }}
'''

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(nested_structure_curriculum LANGUAGES CXX)
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
add_custom_target(test_task ALL DEPENDS task_visible task_hidden COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure)
'''

def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots = []
    for s in TASKS:
        root = out / s.task_id
        config = {"authors": ["w8-biayn"], "blurb": f"Validate {s.grammar} with escaped/quoted token handling and diagnostics.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Independently authored structured-token API; not derived from the official Aider matching-brackets holdout or the excluded matching-brackets source family."}
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local diagnostic for {s.grammar}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}::{s.method}` for {s.grammar}. Opening token: `{s.opener}`; closing token: `{s.closer}`. Return a `StructureDiagnostic` containing success, deterministic first-error byte offset, reason, and any unclosed opening tokens. Escaped tokens and tokens inside single- or double-quoted literals are literal text. Do not use recursion; empty/literal-only input is valid. An unexpected closing token is reported at its first byte and end-of-input with open scopes retains them in order.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"task API, literal handling, unexpected closer, and unclosed diagnostic\"\n\n[hidden]\ndescription = \"escaped and quoted tokens, deterministic offset, non-recursive deep nesting, and sanitizer execution\"\n", "task.h": _header(s), "task.cpp": _starter(s), ".meta/example.h": _header(s), ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="nested-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format nested-structure curriculum tasks."); parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} nested-structure curriculum tasks under {args.out}"); return 0

if __name__ == "__main__": raise SystemExit(main())
