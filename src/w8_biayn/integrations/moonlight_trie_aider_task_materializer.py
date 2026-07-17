"""Reproducibly materialize the 20 local Trie Aider curriculum roots."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/trie")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_TRIE_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    noun: str
    add: str
    remove: str
    exact: str
    count: str
    suggestions: str
    policy: str


_ROWS = (
    ("trie-command-completion", "CommandCompletion", "commands", "register_command", "remove_command", "is_registered", "matching_command_count", "complete", "lower-case command names; lexical completions"),
    ("trie-product-search", "ProductSearch", "product codes", "add_product", "remove_product", "has_product", "matching_product_count", "suggest", "upper-case codes; bounded lexical suggestions"),
    ("trie-contact-directory", "ContactDirectory", "contacts", "add_contact", "delete_contact", "has_contact", "matching_contact_count", "search_contacts", "case-normalized names; lexical searches"),
    ("trie-library-call-prefixes", "LibraryCallPrefixes", "call numbers", "add_call_number", "remove_call_number", "has_call_number", "count_under_prefix", "list_under_prefix", "call-number strings; prefix counts"),
    ("trie-word-game-dictionary", "WordGameDictionary", "words", "add_word", "remove_word", "is_word", "word_count_with_prefix", "words_from_prefix", "dictionary words; terminal membership"),
    ("trie-url-router", "UrlRouter", "routes", "register_route", "remove_route", "has_route", "route_count_under", "routes_under", "slash-separated routes; registered descendants"),
    ("trie-dns-suffixes", "DnsSuffixes", "suffix rules", "add_suffix_rule", "remove_suffix_rule", "has_suffix_rule", "suffix_rule_count", "matching_suffix_rules", "domain suffix rules; deterministic candidates"),
    ("trie-dna-motifs", "DnaMotifs", "DNA motifs", "add_motif", "remove_motif", "has_motif", "motif_count_with_prefix", "motifs_from_prefix", "DNA alphabet A/C/G/T only"),
    ("trie-emoji-shortcodes", "EmojiShortcodes", "shortcode aliases", "add_alias", "remove_alias", "has_alias", "alias_count_with_prefix", "aliases_from_prefix", "shortcodes; deterministic unique-prefix candidates"),
    ("trie-spell-checker", "SpellChecker", "words", "load_word", "unload_word", "is_spelled", "spelling_count_with_prefix", "suggest_spellings", "normalized spelling words; prefix suggestions"),
    ("trie-file-path-index", "FilePathIndex", "file paths", "register_path", "remove_path", "has_path", "descendant_count", "descendants", "absolute paths; descendant queries"),
    ("trie-license-plate-index", "LicensePlateIndex", "license plates", "reserve_plate", "release_plate", "is_reserved", "reserved_count_with_prefix", "reserved_with_prefix", "normalized plates; prefix reservations"),
    ("trie-predictive-text", "PredictiveText", "terms", "record_term", "remove_term", "has_term", "term_count_with_prefix", "top_completions", "positive frequencies; frequency then lexical completions"),
    ("trie-snippet-tags", "SnippetTags", "snippet tags", "add_tag", "remove_tag", "has_tag", "tag_count_with_prefix", "tags_from_prefix", "tag prefixes; lexical IDs"),
    ("trie-log-category-filter", "LogCategoryFilter", "log categories", "register_category", "remove_category", "has_category", "category_count_under", "categories_under", "dotted categories; subtree selection"),
    ("trie-morse-codebook", "MorseCodebook", "Morse encodings", "add_encoding", "remove_encoding", "has_encoding", "encoding_count_with_prefix", "encodings_from_prefix", "dots/dashes; prefix-free insertion"),
    ("trie-access-token-prefixes", "AccessTokenPrefixes", "access tokens", "issue_token", "revoke_token", "has_token", "active_count_with_prefix", "active_from_prefix", "opaque tokens; ambiguous-prefix candidates"),
    ("trie-sku-allocator", "SkuAllocator", "SKUs", "reserve_sku", "release_sku", "is_reserved", "reserved_count_with_prefix", "reserved_from_prefix", "patterned SKUs; used suffixes"),
    ("trie-wildcard-dictionary", "WildcardDictionary", "dictionary entries", "add_entry", "remove_entry", "has_entry", "entry_count_with_prefix", "entries_from_prefix", "words; candidates for single-character wildcard matching"),
    ("trie-translation-glossary", "TranslationGlossary", "language-qualified terms", "add_term", "remove_term", "has_term", "term_count_with_prefix", "terms_from_prefix", "language-qualified terms; exact and prefix lookup"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <map>
#include <string>
#include <vector>
namespace curriculum {{
class {s.class_name} {{
 public:
  bool {s.add}(const std::string& key, int weight = 1);
  bool {s.remove}(const std::string& key);
  bool {s.exact}(const std::string& key) const;
  std::size_t {s.count}(const std::string& prefix) const;
  std::vector<std::string> {s.suggestions}(const std::string& prefix, std::size_t limit = 10) const;
 private:
  std::map<std::string, int> entries_;
}};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    predictive = s.task_id == "trie-predictive-text"
    morse = s.task_id == "trie-morse-codebook"
    valid = "return !key.empty() && key.find_first_of(\"!@#$%^&*()[]{}\\\\\") == std::string::npos;"
    if s.task_id == "trie-dna-motifs":
        valid = "return !key.empty() && key.find_first_not_of(\"ACGT\") == std::string::npos;"
    add = "if (!valid(key) || weight <= 0 || entries_.count(key)) return false; entries_[key] = weight; return true;"
    if predictive:
        add = "if (!valid(key) || weight <= 0) return false; entries_[key] += weight; return true;"
    if morse:
        add = "if (!valid(key) || weight != 1) return false; for (const auto& e : entries_) if (prefix(e.first, key) || prefix(key, e.first)) return false; entries_[key] = 1; return true;"
    order = "return a.second != b.second ? a.second > b.second : a.first < b.first;" if predictive else "return a.first < b.first;"
    return f'''#include "task.h"
#include <algorithm>
namespace curriculum {{
namespace {{
bool valid(const std::string& key) {{ {valid} }}
bool prefix(const std::string& key, const std::string& value) {{ return key.size() >= value.size() && key.compare(0, value.size(), value) == 0; }}
}}  // namespace
bool {s.class_name}::{s.add}(const std::string& key, int weight) {{ {add} }}
bool {s.class_name}::{s.remove}(const std::string& key) {{ return entries_.erase(key) == 1; }}
bool {s.class_name}::{s.exact}(const std::string& key) const {{ return entries_.count(key) != 0; }}
std::size_t {s.class_name}::{s.count}(const std::string& prefix_key) const {{ std::size_t n = 0; for (const auto& e : entries_) if (prefix(e.first, prefix_key)) ++n; return n; }}
std::vector<std::string> {s.class_name}::{s.suggestions}(const std::string& prefix_key, std::size_t limit) const {{
  std::vector<std::pair<std::string, int>> found; for (const auto& e : entries_) if (prefix(e.first, prefix_key)) found.push_back(e);
  std::sort(found.begin(), found.end(), [](const auto& a, const auto& b) {{ {order} }}); if (found.size() > limit) found.resize(limit);
  std::vector<std::string> out; for (const auto& e : found) out.push_back(e.first); return out;
}}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
bool {s.class_name}::{s.add}(const std::string&, int) {{ return false; }}
bool {s.class_name}::{s.remove}(const std::string&) {{ return false; }}
bool {s.class_name}::{s.exact}(const std::string&) const {{ return false; }}
std::size_t {s.class_name}::{s.count}(const std::string&) const {{ return 0; }}
std::vector<std::string> {s.class_name}::{s.suggestions}(const std::string&, std::size_t) const {{ return {{}}; }}
}}  // namespace curriculum
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    keys = ('".-"', '"-."', '"--"') if s.task_id == "trie-morse-codebook" else ('"al"', '"alpha"', '"alpine"')
    query_prefix = '""' if s.task_id == "trie-morse-codebook" else keys[0]
    invalid = '"AX"' if s.task_id == "trie-dna-motifs" else '"bad!"'
    randomized = ""
    if hidden:
        randomized = f'''\n  for (int i = 0; i < 160; ++i) {{ const std::string key = "trace" + std::to_string((i * 37) % 29); if (i % 3) index.{s.add}(key); else index.{s.remove}(key); check(index.{s.suggestions}("", 500).size() == index.{s.count}("")); }}'''
    return f'''#include "task.h"
#include <string>
#include <vector>
int main() {{
  curriculum::{s.class_name} index; int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }};
  check(!index.{s.add}("", 1)); check(!index.{s.add}({invalid}, 1));
  check(index.{s.add}({keys[0]}, 1)); check(index.{s.add}({keys[1]}, 1)); check(index.{s.add}({keys[2]}, 1));
  check(!index.{s.add}({keys[1]}, 1)); check(index.{s.exact}({keys[1]})); check(index.{s.count}({query_prefix}) == 3U);
  check(index.{s.suggestions}({query_prefix}, 2).size() == 2U); check(index.{s.remove}({keys[1]})); check(!index.{s.remove}({keys[1]})); check(index.{s.count}({query_prefix}) == 2U);{randomized}
  return failures ? 1 : 0;
}}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(trie_curriculum LANGUAGES CXX)
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
    roots: list[Path] = []
    for s in TASKS:
        root, header = out / s.task_id, _header(s)
        config = {"authors": ["w8-biayn"], "blurb": s.policy, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Independently authored domain API, reference, and tests; not derived from an official Aider Polyglot task."}
        instructions = f"# Instructions\n\nImplement `{s.class_name}` for {s.noun}. Its policy is: {s.policy}. Empty and invalid keys are rejected; a failed mutation leaves state unchanged. The count method counts terminal keys below a prefix and the suggestion method returns at most `limit` deterministic results. Prefixes that are also terminal keys must remain valid after mutations.\n"
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local trie diagnostic for {s.noun}.\n", ".docs/instructions.md": instructions, ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API, terminal keys, duplicate policy, prefix count, and bounded ordering\"\n\n[hidden]\ndescription = \"shared prefixes, deletion, invalid keys, repeated mutations, and randomized traces\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    for root in (out / spec.task_id for spec in TASKS):
        with tempfile.TemporaryDirectory(prefix="trie-curriculum-") as temp:
            copied = Path(temp) / root.name
            shutil.copytree(root, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={copied / '.meta' / 'example.cpp'}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format Trie curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} trie curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
