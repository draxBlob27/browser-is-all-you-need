"""Materialize newly-authored local LRU-cache Aider curriculum tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/lru-cache")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_LRU_CACHE_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    record: str
    find: str
    remove: str
    noun: str
    capacity_kind: str

_ROWS = (
    ("lru-thumbnail-cache", "ThumbnailCache", "store_preview", "view_preview", "discard_preview", "image previews", "entries"),
    ("lru-web-page-cache", "WebPageCache", "cache_page", "open_page", "invalidate_page", "page bodies", "entries"),
    ("lru-session-store", "SessionStore", "start_session", "read_session", "revoke_session", "user sessions", "entries"),
    ("lru-dns-answer-cache", "DnsAnswerCache", "remember_answer", "resolve_host", "invalidate_host", "host answers", "entries"),
    ("lru-query-result-cache", "QueryResultCache", "save_result", "find_result", "forget_result", "query results", "resizable"),
    ("lru-compiler-artifacts", "CompilerArtifactCache", "store_artifact", "load_artifact", "discard_artifact", "compiler artifacts", "entries"),
    ("lru-map-tile-cache", "MapTileCache", "load_tile", "touch_tile", "remove_tile", "map tiles", "entries"),
    ("lru-product-details", "ProductDetailCache", "cache_product", "product_details", "remove_product", "product details", "entries"),
    ("lru-translation-cache", "TranslationCache", "store_translation", "translate", "invalidate_language_pair", "normalized translations", "namespace"),
    ("lru-weather-snapshots", "WeatherSnapshotCache", "record_snapshot", "lookup_snapshot", "expire_location", "weather snapshots", "expiry"),
    ("lru-document-pages", "DocumentPageCache", "open_page", "read_page", "close_page", "document pages", "bytes"),
    ("lru-package-manifests", "PackageManifestCache", "cache_manifest", "resolve_manifest", "invalidate_package", "package manifests", "namespace"),
    ("lru-feature-config", "FeatureConfigCache", "publish_config", "config_for", "clear_tenant", "tenant configurations", "namespace"),
    ("lru-tax-estimate-cache", "TaxEstimateCache", "save_estimate", "estimate_for", "invalidate_jurisdiction", "tax estimates", "namespace"),
    ("lru-search-suggestions", "SearchSuggestionCache", "remember_suggestions", "suggestions_for", "forget_query", "normalized search suggestions", "entries"),
    ("lru-audio-waveforms", "AudioWaveformCache", "store_waveform", "waveform_for", "remove_waveform", "audio waveform chunks", "bytes"),
    ("lru-route-plans", "RoutePlanCache", "save_plan", "route_for", "invalidate_route", "route plans", "resizable"),
    ("lru-recommendation-cache", "RecommendationCache", "store_recommendations", "recommendations_for", "delete_user", "user recommendations", "entries"),
    ("lru-file-metadata", "FileMetadataCache", "record_metadata", "metadata_for", "forget_file", "file metadata", "entries"),
    ("lru-pricing-quote-cache", "PricingQuoteCache", "quote", "find_quote", "withdraw_quote", "pricing quotes", "entries"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

def _header(s: TaskSpec) -> str:
    guard = f"{s.class_name.upper()}_H"
    return f'''#ifndef {guard}
#define {guard}
#include <cstddef>
#include <list>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
namespace curriculum {{
class {s.class_name} {{
public:
  explicit {s.class_name}(std::size_t capacity);
  bool {s.record}(const std::string& key, const std::string& value, std::size_t cost = 1);
  std::optional<std::string> {s.find}(const std::string& key);
  bool {s.remove}(const std::string& selector);
  bool resize_capacity(std::size_t capacity);
  std::vector<std::string> recency_keys() const;
  std::size_t size() const; std::size_t used_capacity() const;
private:
  struct Entry {{ std::string value; std::size_t cost; std::list<std::string>::iterator position; }};
  bool matches_selector(const std::string& key, const std::string& selector) const;
  void touch(std::unordered_map<std::string, Entry>::iterator item); void evict_until_fits(std::size_t incoming);
  std::size_t capacity_; std::size_t used_ = 0; std::list<std::string> newest_first_; std::unordered_map<std::string, Entry> entries_;
}};
}}  // namespace curriculum
#endif
'''

def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}}
bool {s.class_name}::matches_selector(const std::string& key, const std::string& selector) const {{ return key == selector || key.rfind(selector + ":", 0) == 0; }}
void {s.class_name}::touch(std::unordered_map<std::string, Entry>::iterator item) {{ newest_first_.splice(newest_first_.begin(), newest_first_, item->second.position); item->second.position = newest_first_.begin(); }}
void {s.class_name}::evict_until_fits(std::size_t incoming) {{ while (used_ + incoming > capacity_ && !newest_first_.empty()) {{ const std::string victim = newest_first_.back(); used_ -= entries_.at(victim).cost; entries_.erase(victim); newest_first_.pop_back(); }} }}
bool {s.class_name}::{s.record}(const std::string& key, const std::string& value, std::size_t cost) {{ if (key.empty() || value.empty() || cost == 0 || cost > capacity_) return false; auto item = entries_.find(key); if (item != entries_.end()) {{ used_ -= item->second.cost; newest_first_.erase(item->second.position); entries_.erase(item); }} evict_until_fits(cost); newest_first_.push_front(key); entries_.emplace(key, Entry{{value, cost, newest_first_.begin()}}); used_ += cost; return true; }}
std::optional<std::string> {s.class_name}::{s.find}(const std::string& key) {{ auto item = entries_.find(key); if (item == entries_.end()) return std::nullopt; touch(item); return item->second.value; }}
bool {s.class_name}::{s.remove}(const std::string& selector) {{ if (selector.empty()) return false; bool removed = false; for (auto item = entries_.begin(); item != entries_.end();) {{ if (matches_selector(item->first, selector)) {{ used_ -= item->second.cost; newest_first_.erase(item->second.position); item = entries_.erase(item); removed = true; }} else ++item; }} return removed; }}
bool {s.class_name}::resize_capacity(std::size_t capacity) {{ capacity_ = capacity; evict_until_fits(0); return true; }}
std::vector<std::string> {s.class_name}::recency_keys() const {{ return {{newest_first_.begin(), newest_first_.end()}}; }} std::size_t {s.class_name}::size() const {{ return entries_.size(); }} std::size_t {s.class_name}::used_capacity() const {{ return used_; }}
}}  // namespace curriculum
'''

def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}}
bool {s.class_name}::matches_selector(const std::string&, const std::string&) const {{ return false; }} void {s.class_name}::touch(std::unordered_map<std::string, Entry>::iterator) {{}} void {s.class_name}::evict_until_fits(std::size_t) {{}}
bool {s.class_name}::{s.record}(const std::string&, const std::string&, std::size_t) {{ return false; }} std::optional<std::string> {s.class_name}::{s.find}(const std::string&) {{ return std::nullopt; }} bool {s.class_name}::{s.remove}(const std::string&) {{ return false; }} bool {s.class_name}::resize_capacity(std::size_t) {{ return false; }} std::vector<std::string> {s.class_name}::recency_keys() const {{ return {{}}; }} std::size_t {s.class_name}::size() const {{ return 0; }} std::size_t {s.class_name}::used_capacity() const {{ return 0; }}
}}  // namespace curriculum
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    trace = ""
    if hidden:
        trace = f'''\n  curriculum::{s.class_name} trace(4); std::vector<std::string> oracle;
  for (int step = 0; step < 240; ++step) {{ const std::string key = "k" + std::to_string(step % 7); if (step % 5 == 0) {{ trace.{s.find}(key); auto found = std::find(oracle.begin(), oracle.end(), key); if (found != oracle.end()) {{ oracle.erase(found); oracle.insert(oracle.begin(), key); }} }} else {{ trace.{s.record}(key, "v" + std::to_string(step)); auto found = std::find(oracle.begin(), oracle.end(), key); if (found != oracle.end()) oracle.erase(found); oracle.insert(oracle.begin(), key); if (oracle.size() > 4U) oracle.pop_back(); }} check(trace.recency_keys() == oracle); check(trace.size() == oracle.size()); }} check(trace.resize_capacity(1)); check(trace.size() <= 1U);'''
    return f'''#include "task.h"
#include <algorithm>
#include <optional>
#include <string>
#include <vector>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }};
  curriculum::{s.class_name} zero(0); check(!zero.{s.record}("x", "y")); check(!zero.{s.find}("x"));
  curriculum::{s.class_name} cache(2); check(!cache.{s.record}("", "v")); check(cache.{s.record}("old", "one")); check(cache.{s.record}("hot", "two")); check(cache.{s.find}("hot") == std::optional<std::string>("two")); check(cache.{s.record}("new", "three")); check(!cache.{s.find}("old")); check(cache.recency_keys() == std::vector<std::string>{{"new", "hot"}}); check(cache.{s.record}("hot", "updated")); check(cache.size() == 2U); check(cache.{s.find}("hot") == std::optional<std::string>("updated")); check(cache.{s.remove}("hot")); check(cache.size() == 1U);{trace}
  return failures == 0 ? 0 : 1; }}
'''

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(lru_cache_curriculum LANGUAGES CXX)
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

def _capacity_note(kind: str) -> str:
    return {"entries": "Capacity is a number of retained records.", "bytes": "Capacity is a caller-supplied byte-budget cost; oversized records are rejected.", "resizable": "resize_capacity may shrink the cache and evicts least-recent records first.", "namespace": "The removal selector removes an exact key or a selector: namespace.", "expiry": "Explicit expiration is modeled by removal before ordinary LRU pressure."}[kind]

def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots: list[Path] = []
    for s in TASKS:
        root = out / s.task_id
        config = {"authors": ["w8-biayn"], "blurb": f"An LRU cache for {s.noun} with observable recency.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Newly authored task-specific LRU API; not derived from an official Aider Polyglot benchmark task or its tests."}
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local LRU-cache diagnostic for {s.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}`. `{s.record}` stores a nonempty key/value and makes it most recent. `{s.find}` returns a retained value and promotes it. `{s.remove}` removes an exact key (and, where meaningful, its `selector:` namespace). At capacity, a new key evicts exactly the least-recent key; replacing a key does not grow the cache. `recency_keys()` returns most-recent to least-recent order. {_capacity_note(s.capacity_kind)} Empty keys/values, zero cost, and records exceeding capacity are rejected without mutation.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API, validation, promotion, overwrite, eviction, and removal\"\n\n[hidden]\ndescription = \"zero/singleton capacity, randomized map-plus-recency oracle traces, resize, namespace removal, and list/map coherence\"\n", "task.h": _header(s), "task.cpp": _starter(s), ".meta/example.h": _header(s), ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / spec.task_id for spec in TASKS):
        with tempfile.TemporaryDirectory(prefix="lru-cache-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format LRU-cache curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} LRU-cache curriculum tasks under {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
