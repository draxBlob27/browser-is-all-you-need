"""Materialize newly-authored LFU cache Aider curriculum tasks."""
from __future__ import annotations

import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/lfu-cache")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_LFU_CACHE_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; store: str; lookup: str; purge: str; noun: str; policy: str

_RAW = (
 ("lfu-product-catalog","ProductCatalog","record_product","find_product","retire_product","products","slot"),("lfu-search-results","SearchResultCache","remember_search","revisit_search","forget_search","normalized queries","slot"),("lfu-translation-memory","TranslationMemory","store_translation","translate","invalidate_language_pair","translations","namespace"),("lfu-dns-answers","DnsAnswerCache","record_answer","resolve_host","invalidate_host","host answers","expiry"),("lfu-thumbnail-store","ThumbnailStore","store_thumbnail","load_thumbnail","remove_thumbnail","thumbnails","byte"),("lfu-weather-forecast","WeatherForecastCache","publish_forecast","forecast_for","expire_location","forecasts","expiry"),("lfu-route-planner","RoutePlanCache","save_route","route_for","close_station","routes","namespace"),("lfu-compiler-artifacts","CompilerArtifactCache","save_artifact","load_artifact","discard_artifact","artifacts","slot"),("lfu-document-pages","DocumentPageCache","store_page","read_page","remove_page","document pages","snapshot"),("lfu-feature-config","FeatureConfigCache","publish_config","config_for","invalidate_tenant","tenant configs","namespace"),("lfu-pricing-quotes","PricingQuoteCache","quote","find_quote","withdraw_quote","quotes","slot"),("lfu-recommendations","RecommendationCache","save_recommendations","recommendations_for","delete_account","recommendations","namespace"),("lfu-map-tiles","MapTileCache","store_tile","tile_at","remove_tile","map tiles","slot"),("lfu-package-manifests","PackageManifestCache","publish_manifest","manifest_for","invalidate_package","package manifests","namespace"),("lfu-audio-waveforms","AudioWaveformCache","store_waveform","waveform_for","remove_waveform","waveforms","byte"),("lfu-tax-estimates","TaxEstimateCache","save_estimate","estimate_for","reset_jurisdiction","tax estimates","namespace"),("lfu-schema-metadata","SchemaMetadataCache","store_schema","schema_for","refresh_table","schemas","slot"),("lfu-session-attributes","SessionAttributeCache","store_attributes","attributes_for","revoke_session","session attributes","namespace"),("lfu-image-transform","ImageTransformCache","store_transform","transform_for","remove_transform","image transforms","byte"),("lfu-support-answers","SupportAnswerCache","store_answer","answer_for","remove_answer","support answers","snapshot"),
)
TASKS = tuple(TaskSpec(*row) for row in _RAW)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)

def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
namespace curriculum {{ class {s.class_name} {{ public: explicit {s.class_name}(std::size_t capacity); bool {s.store}(const std::string& key, const std::string& value, std::size_t cost = 1); std::optional<std::string> {s.lookup}(const std::string& key); bool {s.purge}(const std::string& selector); std::vector<std::string> retained_keys() const; std::size_t size() const; private: struct Entry {{ std::string value; std::size_t frequency; std::size_t touched; std::size_t cost; }}; std::size_t capacity_; std::size_t used_ = 0; std::size_t clock_ = 0; std::unordered_map<std::string, Entry> entries_; void evict_one(); }}; }}
#endif
'''

def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{ if (!capacity) throw std::invalid_argument("capacity must be positive"); }}
void {s.class_name}::evict_one() {{ auto victim = entries_.end(); for (auto it = entries_.begin(); it != entries_.end(); ++it) if (victim == entries_.end() || it->second.frequency < victim->second.frequency || (it->second.frequency == victim->second.frequency && it->second.touched < victim->second.touched)) victim = it; if (victim != entries_.end()) {{ used_ -= victim->second.cost; entries_.erase(victim); }} }}
bool {s.class_name}::{s.store}(const std::string& key, const std::string& value, std::size_t cost) {{ if (key.empty() || value.empty() || !cost || cost > capacity_) return false; auto it = entries_.find(key); if (it != entries_.end()) {{ const std::size_t frequency = it->second.frequency + 1; used_ -= it->second.cost; entries_.erase(it); while (used_ + cost > capacity_) evict_one(); entries_.emplace(key, Entry{{value, frequency, ++clock_, cost}}); used_ += cost; return true; }} while (used_ + cost > capacity_) evict_one(); entries_.emplace(key, Entry{{value, 1, ++clock_, cost}}); used_ += cost; return true; }}
std::optional<std::string> {s.class_name}::{s.lookup}(const std::string& key) {{ auto it = entries_.find(key); if (it == entries_.end()) return std::nullopt; ++it->second.frequency; it->second.touched = ++clock_; return it->second.value; }}
bool {s.class_name}::{s.purge}(const std::string& selector) {{ bool removed = false; for (auto it = entries_.begin(); it != entries_.end();) {{ if (it->first == selector || it->first.rfind(selector + ":", 0) == 0) {{ used_ -= it->second.cost; it = entries_.erase(it); removed = true; }} else ++it; }} return removed; }}
std::vector<std::string> {s.class_name}::retained_keys() const {{ std::vector<std::string> out; for (const auto& pair : entries_) out.push_back(pair.first); std::sort(out.begin(), out.end()); return out; }} std::size_t {s.class_name}::size() const {{ return entries_.size(); }} }}
'''

def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{ {s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}} void {s.class_name}::evict_one() {{}} bool {s.class_name}::{s.store}(const std::string&, const std::string&, std::size_t) {{ return false; }} std::optional<std::string> {s.class_name}::{s.lookup}(const std::string&) {{ return std::nullopt; }} bool {s.class_name}::{s.purge}(const std::string&) {{ return false; }} std::vector<std::string> {s.class_name}::retained_keys() const {{ return {{}}; }} std::size_t {s.class_name}::size() const {{ return 0; }} }}
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    body = f'''try {{ curriculum::{s.class_name} invalid(0); check(false); }} catch (const std::invalid_argument&) {{}} curriculum::{s.class_name} cache(2); check(!cache.{s.store}("", "x")); check(cache.{s.store}("old", "one")); check(cache.{s.store}("hot", "two")); check(cache.{s.lookup}("hot").value_or("") == "two"); check(cache.{s.store}("new", "three")); check(!cache.{s.lookup}("old")); check(cache.{s.lookup}("hot").value_or("") == "two"); check(cache.{s.purge}("hot")); check(cache.size() == 1U);'''
    if hidden: body += f''' curriculum::{s.class_name} weighted(4); check(weighted.{s.store}("big", "B", 4)); check(!weighted.{s.store}("too", "T", 5)); check(weighted.{s.store}("small", "S", 1)); check(weighted.size() == 1U); for (int i = 0; i < 200; ++i) {{ const std::string key = "k" + std::to_string(i % 7); check(cache.{s.store}(key, key)); if (i % 3 == 0) cache.{s.lookup}(key); check(cache.size() <= 2U); }} const auto keys = cache.retained_keys(); check(std::is_sorted(keys.begin(), keys.end()));'''
    includes = '#include <algorithm>\n#include <string>\n' if hidden else ''
    return f'''#include "task.h"
#include <stdexcept>
{includes}int main() {{ int failures = 0; auto check = [&](bool ok) {{ if (!ok) ++failures; }}; {body} return failures ? 1 : 0; }}
'''

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(lfu_cache_curriculum LANGUAGES CXX)
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
        root = out / s.task_id; config = {"authors": ["w8-biayn"], "blurb": f"An LFU cache for {s.noun} with deterministic recency ties.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Newly authored task-specific LFU API; not derived from an official Aider Polyglot benchmark task or its tests."}
        policy = {"slot": "Capacity is measured in entries.", "byte": "Capacity is a caller-supplied weighted byte budget.", "namespace": "The purge operation invalidates an exact key or colon-delimited namespace.", "expiry": "The purge operation models explicit logical expiry before LFU eviction.", "snapshot": "retained_keys reports a deterministic diagnostic snapshot."}[s.policy]
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local LFU-cache diagnostic for {s.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}`. `{s.store}` records a nonempty key and value; `{s.lookup}` returns and promotes a retained value. On pressure, evict the lowest-frequency entry, breaking ties by oldest touch. Replacing a retained key promotes it and updates its cost. `{s.purge}` removes its exact selector or keys in its `selector:` namespace. {policy} Empty keys/values, zero cost, and entries larger than capacity are rejected.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API, validation, LFU eviction, recency tie break, and purge\"\n\n[hidden]\ndescription = \"frequency promotion, weighted pressure, deterministic snapshot, randomized bounded traces, and sanitizer execution\"\n", "task.h": _header(s), "task.cpp": _starter(s), ".meta/example.h": _header(s), ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="lfu-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format LFU-cache curriculum tasks."); parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} LFU-cache curriculum tasks under {args.out}"); return 0

if __name__ == "__main__": raise SystemExit(main())
