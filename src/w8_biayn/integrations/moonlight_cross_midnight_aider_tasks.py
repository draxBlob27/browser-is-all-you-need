"""Remediate and reverify clean-room cross-midnight interval tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_cross_midnight_cases import (
    CASES,
    REJECTED_CASES,
    MidnightCase,
)
from w8_biayn.integrations.moonlight_cross_midnight_hard_rule import (
    HARD_DIMENSIONS,
    analyze_root,
    compare_roots,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/cross-midnight-intervals"
)
LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/cross-midnight-intervals"
)
REQUESTED_LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/cross-midnight-intervals"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_CROSS_MIDNIGHT_INTERVALS_ARITHMETIC_CURRICULUM.md"
)
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/cross-midnight-intervals.md"
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-cross-midnight-intervals-v2"
MANIFEST_SCHEMA = "aider-cross-midnight-materialization-v2"
SEMANTIC_NORMALIZER = "cross-midnight-artifact-seven-dimension-v2"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
REMEDY_HEADINGS = (
    "Identity",
    "Objective",
    "Public API",
    "Behavior table",
    "Implementation invariant",
    "Starter and reference",
    "Tests",
    "Files and metadata",
    "Build/oracle",
    "Family/contamination",
    "Optional dataset handoff",
    "Acceptance",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
        "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
        "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
        "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age",
        "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
    }
)
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
TASKS = CASES
OWNER_SOURCE_PATHS = {
    "materializer": Path(__file__),
    "cases": Path(__file__).with_name("moonlight_cross_midnight_cases.py"),
    "hard_rule": Path(__file__).with_name("moonlight_cross_midnight_hard_rule.py"),
}


CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(cross_midnight_intervals_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _owner_source_hashes() -> dict[str, str]:
    return {name: _sha_bytes(path.read_bytes()) for name, path in OWNER_SOURCE_PATHS.items()}


def _source_hash() -> str:
    digest = hashlib.sha256()
    for name, path in sorted(OWNER_SOURCE_PATHS.items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and ".state" not in p.relative_to(root).parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _family_hash(out: Path) -> str:
    digest = hashlib.sha256()
    for case in CASES:
        digest.update(case.task_id.encode())
        digest.update(b"\0")
        digest.update(_tree_hash(out / case.task_id).encode())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_remedies(out: Path) -> None:
    remedy = out / ".state/remedy"
    if not remedy.is_dir():
        _fail(
            "remedy_spec_incomplete",
            "run python3 scripts/plan_cross_midnight_remedies.py before implementation",
        )
    for case in CASES:
        md_path = remedy / f"{case.task_id}.md"
        json_path = remedy / f"{case.task_id}.json"
        if not md_path.is_file() or not json_path.is_file():
            _fail("remedy_spec_incomplete", case.task_id)
        text = md_path.read_text(encoding="utf-8")
        found = tuple(re.findall(r"^## (.+)$", text, flags=re.M))
        if found != REMEDY_HEADINGS:
            _fail("remedy_spec_incomplete", f"{case.task_id}: {found}")
        record = json.loads(json_path.read_text(encoding="utf-8"))
        if record.get("status") not in {"planned", "implemented", "verified"}:
            _fail("remedy_disposition_conflict", case.task_id)
        if record.get("disposition") != "replace" or record.get("legacy_task_id") != case.legacy_id:
            _fail("remedy_disposition_conflict", case.task_id)
        if record.get("remedy_spec_hash") != _sha_bytes(text.encode()):
            _fail("remedy_spec_incomplete", f"stale hash: {case.task_id}")
    for case in REJECTED_CASES:
        md_path = remedy / f"{case.task_id}.md"
        json_path = remedy / f"{case.task_id}.json"
        if not md_path.is_file() or not json_path.is_file():
            _fail("remedy_spec_incomplete", f"rejected proposal: {case.task_id}")
        record = json.loads(json_path.read_text(encoding="utf-8"))
        if record.get("disposition") != "reject" or record.get("status") != "rejected":
            _fail("remedy_disposition_conflict", f"rejected proposal: {case.task_id}")
        if (out / case.task_id).is_dir() and not _owned_root(out / case.task_id):
            _fail("generator_output_drift", f"foreign rejected root: {case.task_id}")


def _negative_source(case: MidnightCase) -> str:
    count = case.reference.count(case.negative_old)
    if count != 1:
        _fail("invariant_not_enforced", f"negative mutation count {case.task_id}: {count}")
    changed = case.reference.replace(case.negative_old, case.negative_new, 1)
    if changed == case.reference:
        _fail("invariant_not_enforced", f"unchanged negative: {case.task_id}")
    return changed


def _owned_root(root: Path) -> bool:
    provenance = root / ".meta/provenance.json"
    if not provenance.is_file():
        return False
    try:
        return json.loads(provenance.read_text(encoding="utf-8")).get("family_id") == FAMILY_ID
    except json.JSONDecodeError:
        return False


def _prune_owned_obsolete(out: Path) -> None:
    selected = {case.task_id for case in CASES}
    if not out.is_dir():
        return
    for root in out.iterdir():
        if root.is_dir() and root.name != ".state" and root.name not in selected:
            if not _owned_root(root):
                _fail("generator_output_drift", f"refuse to prune foreign root: {root}")
            shutil.rmtree(root)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if not 8 <= len(CASES) <= 12:
        _fail("hard_rule_count", str(len(CASES)))
    _validate_remedies(out)
    if force:
        _prune_owned_obsolete(out)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.objective,
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "curriculum_document": CURRICULUM,
            "family_specification": FAMILY_SPEC,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "legacy_root": LEGACY_ROOT.as_posix(),
            "requested_legacy_root": REQUESTED_LEGACY_ROOT.as_posix(),
            "requested_legacy_root_status": "absent_at_planning",
            "requested_family_type": "aider-text-grid-reshaping",
            "family_id": FAMILY_ID,
            "semantic_profile": case.profile,
            "origin": "newly authored in-repository clean-room replacement",
            "license": "repository-authored",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "benchmark_separation": (
                "Independent interval API, mechanism, oracle, and tests; official Aider "
                "C++ roots remain permanent holdouts."
            ),
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": (
                f'[visible]\ndescription = "normal {case.profile} behavior and public boundary"\n\n'
                f'[hidden]\ndescription = "invalid, empty, duplicate, ordering, and endpoint behavior"\n\n'
                f'[negative]\ndescription = "{case.negative_reason}"\n'
            ),
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/negative_false_substitute.cpp": _negative_source(case),
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


def _normalized_tokens(content: str) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", content
    )
    keywords = {
        "if", "else", "for", "while", "return", "class", "struct", "const", "auto",
        "bool", "int", "long", "void", "true", "false", "public", "private",
        "namespace", "std", "vector", "array", "set", "sort", "priority_queue",
        "greater", "max", "min", "break", "continue", "template", "using",
    }
    return tuple(token if token in keywords or not token[0].isalpha() else "ID" for token in raw)


def _normalized_words(content: str) -> tuple[str, ...]:
    content = re.sub(r"`[^`]*`|\b\d+\b", " TOKEN ", content.lower())
    domain = {
        "parking", "patrol", "dock", "sleep", "wake", "radio", "quiet", "oven", "batch",
        "transit", "pass", "trip", "hospital", "handoff", "noise", "delivery", "curfew",
        "route", "tariff", "watch", "booking", "shift", "operation",
    }
    return tuple("DOMAIN" if word in domain else word for word in re.findall(r"[a-z_]+|[.,;:]", content))


def _ngrams(tokens: tuple[str, ...], width: int = 9) -> set[tuple[str, ...]]:
    return {tokens[index : index + width] for index in range(max(0, len(tokens) - width + 1))}


def _hard_rule(out: Path, roots: Sequence[Path] | None = None) -> dict[str, object]:
    selected = tuple(roots or (out / case.task_id for case in CASES))
    evidence = {root.name: analyze_root(root) for root in selected}
    pairs: list[dict[str, object]] = []
    for i, left in enumerate(selected):
        for right in selected[i + 1 :]:
            pairs.append(compare_roots(left, right))
    expected = len(selected) * (len(selected) - 1) // 2
    return {
        "dimensions": list(HARD_DIMENSIONS),
        "root_count": len(selected),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "artifact_evidence": evidence,
        "pairs": pairs,
        "pass": len(pairs) == expected and all(row["pass"] for row in pairs),
    }


def _copy_control(source: Path, destination: Path, replacements: Sequence[tuple[str, str]]) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    for path in sorted(p for p in destination.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        changed = text
        for old, new in replacements:
            changed = changed.replace(old, new)
        if changed != text:
            path.write_text(changed, encoding="utf-8")
    for path in sorted(destination.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        renamed = path.name
        for old, new in replacements:
            renamed = renamed.replace(old, new)
        if renamed != path.name:
            path.rename(path.with_name(renamed))


def _write_controls(out: Path, force: bool) -> None:
    del force
    controls = out / ".state/controls"
    controls.mkdir(parents=True, exist_ok=True)
    parking = out / CASES[0].task_id
    _copy_control(
        parking, controls / "domain-identifier-renamed-clone",
        (("Parking", "Garage"), ("parking", "garage"), ("Tariff", "Rate"), ("tariff", "rate")),
    )
    _copy_control(
        parking, controls / "constants-policy-clone",
        (("{{2,0,360,1}", "{{2,0,360,2}"), ("x.total_cents==240", "x.total_cents==300"),
         ("{2,60,60}", "{2,60,120}")),
    )
    delivery = out / CASES[-1].task_id
    _copy_control(
        delivery, controls / "opposite-end-selection-clone",
        (("smallest ID", "largest ID"), ("a.id<b.id", "a.id>b.id"), ("c.route_id==2", "c.route_id==3")),
    )


def _validate_prompt_roles(root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = config["files"]["solution"]
    expected = [f"{root.name}.h", f"{root.name}.cpp"]
    if solution != expected:
        _fail("prompt_contract_incomplete", f"solution order {root.name}: {solution}")
    if config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
        _fail("target_reference_mismatch", root.name)
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (".meta/example", "task_hidden_test", "CMakeLists.txt", "provenance.json")
    if any(item in prompt for item in forbidden):
        _fail("prompt_contract_incomplete", root.name)
    response = build_assistant_response(task, load_example_files_from_config(root))
    if not response.startswith(f"{root.name}.h\n```") or f"{root.name}.cpp\n```" not in response:
        _fail("whole_format_failed", root.name)


def _holdout_screen(out: Path, holdout_root: Path) -> dict[str, object]:
    ids = {case.task_id for case in CASES}
    overlap = sorted(ids & OFFICIAL_AIDER_CPP_HOLDOUTS)
    if overlap:
        _fail("benchmark_id_overlap", ",".join(overlap))
    if not holdout_root.is_dir():
        return {"status": "not_completed", "reason": f"missing holdout root: {holdout_root}", "root_count": 0}
    found = {p.name for p in holdout_root.iterdir() if p.is_dir()}
    missing = sorted(OFFICIAL_AIDER_CPP_HOLDOUTS - found)
    if missing:
        return {"status": "not_completed", "reason": "missing holdouts: " + ",".join(missing), "root_count": len(found)}
    candidate_tokens = {
        case.task_id: _ngrams(_normalized_tokens("\n".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in sorted((out / case.task_id).rglob("*"))
            if p.is_file()
            and (p.suffix in {".h", ".cpp", ".md"})
            and p.name != "CMakeLists.txt"
        ))) for case in CASES
    }
    comparisons = 0
    max_similarity = 0.0
    for slug in sorted(OFFICIAL_AIDER_CPP_HOLDOUTS):
        holdout = _ngrams(_normalized_tokens("\n".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in sorted((holdout_root / slug).rglob("*"))
            if p.is_file() and p.suffix in {".h", ".cpp", ".md"} and p.name != "catch.hpp"
        )))
        for task_id, candidate in candidate_tokens.items():
            comparisons += 1
            denominator = max(1, min(len(candidate), len(holdout)))
            similarity = len(candidate & holdout) / denominator
            max_similarity = max(max_similarity, similarity)
            if similarity >= 0.72:
                _fail("benchmark_content_overlap", f"{task_id}:{slug}:{similarity:.3f}")
    return {"status": "pass", "root_count": 26, "comparisons": comparisons, "max_similarity": max_similarity}


def _control_screen(out: Path) -> dict[str, object]:
    controls = out / ".state/controls"
    sources = {
        "domain-identifier-renamed-clone": out / CASES[0].task_id,
        "constants-policy-clone": out / CASES[0].task_id,
        "opposite-end-selection-clone": out / CASES[-1].task_id,
    }
    rows = []
    for name, source in sources.items():
        control = controls / name
        changed = _tree_hash(control) != _tree_hash(source)
        comparison = compare_roots(source, control)
        rejected = not comparison["pass"]
        if not changed or not rejected:
            _fail("duplicate_family", f"control not rejected: {name}")
        rows.append({"name": name, "changed": changed, "comparison": comparison, "rejected": rejected})
    return {"status": "pass", "controls": rows}


def _sync_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = out / ".state/remedy" / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _source_hash()
        record["changed_owner_paths"] = [
            CURRICULUM, FAMILY_SPEC, "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            "scripts/plan_cross_midnight_remedies.py",
            "src/w8_biayn/integrations/moonlight_cross_midnight_aider_tasks.py",
            "src/w8_biayn/integrations/moonlight_cross_midnight_cases.py",
            "src/w8_biayn/integrations/moonlight_cross_midnight_hard_rule.py",
            "tests/test_moonlight_cross_midnight_aider_tasks.py",
            "examples/slime/moonlight_cpp_perf/prepare_cross_midnight_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def invalidate_hard_rule_evidence(out: Path, reason: str) -> dict[str, object]:
    """Preserve stale receipts and return every root to the planned state."""
    state = out / ".state"
    receipt_path = state / "docker-sanity.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
    prior_path = state / "hard-rule-invalidation.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.is_file() else {}
    invalidated_generator = receipt.get(
        "generator_hash", prior.get("invalidated_generator_hash", "not_available")
    )
    evidence_id = str(invalidated_generator).replace("sha256:", "")[:16]
    archive = state / "invalidated" / f"hard-rule-{evidence_id}"
    archive.mkdir(parents=True, exist_ok=True)
    preserved: list[str] = sorted(
        {
            *prior.get("preserved_records", []),
            *(
                path.relative_to(out).as_posix()
                for path in archive.iterdir()
                if path.is_file()
            ),
        }
    )
    for name in (
        "docker-sanity.json",
        "materialization-manifest.json",
        "family-screen.json",
        "host-verification.json",
    ):
        source = state / name
        if source.is_file():
            destination = archive / name
            if not destination.exists():
                shutil.copy2(source, destination)
            relative = destination.relative_to(out).as_posix()
            if relative not in preserved:
                preserved.append(relative)
    invalidation = {
        "schema_version": "cross-midnight-hard-rule-invalidation-v1",
        "reason": reason,
        "invalidated_status": receipt.get(
            "local_family_verified", prior.get("invalidated_status", False)
        ),
        "invalidated_generator_hash": invalidated_generator,
        "invalidated_family_hash": receipt.get(
            "family_hash", prior.get("invalidated_family_hash", "not_available")
        ),
        "preserved_records": preserved,
        "replacement_gate": (
            f"material artifact-derived decisions for all "
            f"{len(CASES) * (len(CASES) - 1) // 2} pairs in all seven dimensions, "
            "independent focused assertions, coherent controls, and fresh Docker evidence"
        ),
        "strongest_local_status": "planned",
    }
    _write(state / "hard-rule-invalidation.json", json.dumps(invalidation, indent=2, sort_keys=True) + "\n", True)
    for name in ("docker-sanity.json", "family-screen.json"):
        path = state / name
        if path.exists():
            path.unlink()
    manifest_path = state / "materialization-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["strongest_local_status"] = "planned"
        manifest["hard_rule_status"] = "invalidated"
        manifest["invalidation_record"] = ".state/hard-rule-invalidation.json"
        manifest.pop("docker_receipt", None)
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="planned",
        strongest_local_status="planned",
        hard_rule_status="invalidated",
        docker_sanity="invalidated",
        invalidation_record=".state/hard-rule-invalidation.json",
        invalidation_reason=reason,
    )
    return invalidation


def verify_core(out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    roots = tuple(out / case.task_id for case in CASES)
    if any(not root.is_dir() for root in roots):
        _fail("generator_output_drift", "missing generated root")
    for root in roots:
        _validate_prompt_roles(root)
    hard = _hard_rule(out, roots)
    expected_pairs = len(roots) * (len(roots) - 1) // 2
    if hard["pair_count"] != expected_pairs or not hard["pass"]:
        failed = [f"{p['left']}:{p['right']}" for p in hard["pairs"] if not p["pass"]]
        _fail("duplicate_family", ",".join(failed))
    controls = _control_screen(out)
    holdout = _holdout_screen(out, holdout_root)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "task_count": len(roots),
        "hard_count": {"minimum": 8, "maximum": 12, "pass": 8 <= len(roots) <= 12},
        "task_ids": [root.name for root in roots],
        "family_hash": _family_hash(out),
        "generator_hash": _source_hash(),
        "owner_source_hashes": _owner_source_hashes(),
        "legacy_root": LEGACY_ROOT.as_posix(),
        "requested_legacy_root": REQUESTED_LEGACY_ROOT.as_posix(),
        "requested_legacy_root_status": "absent_at_planning",
        "screen": {
            "prompt_boundary": "pass", "reference_mapping": "pass",
            "hard_rule": hard, "adversarial_controls": controls,
            "benchmark_contamination": holdout,
        },
        "strongest_local_status": "implemented" if holdout["status"] == "pass" else "pending_execution",
        "dataset_handoff": "not_requested",
    }
    state = out / ".state"
    _write(state / "materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _write(state / "family-screen.json", json.dumps(hard, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out, status="implemented", primary_core_objective="achieved",
        prompt_boundary="pass", reference_mapping="pass", hard_rule_status="pass",
        hard_rule_pair_count=expected_pairs, benchmark_screen=holdout["status"],
        strongest_local_status=manifest["strongest_local_status"], dataset_handoff="not_requested",
    )
    return manifest


def _run(command: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def _ctest_count(build_dir: Path) -> int:
    result = _run(["ctest", "--test-dir", str(build_dir), "-N"])
    match = re.search(r"Total Tests:\s*(\d+)", result.stdout)
    if not match:
        _fail("test_discovery_failed", str(build_dir))
    return int(match.group(1))


def _configure_and_build(root: Path, source: Path, build_dir: Path, sanitizer: bool) -> int:
    command = [
        "cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles",
        f"-DTASK_SOURCE={source}",
    ]
    if sanitizer:
        command += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    _run(command)
    _run(["cmake", "--build", str(build_dir), "--parallel", "2"])
    return _ctest_count(build_dir)


def _host_root_check(root: Path, prefix: Path) -> dict[str, object]:
    normal = prefix / "normal"
    sanitizer = prefix / "sanitizer"
    normal_count = _configure_and_build(root, root / ".meta/example.cpp", normal, False)
    _run(["ctest", "--test-dir", str(normal), "--output-on-failure"])
    sanitizer_count = _configure_and_build(root, root / ".meta/example.cpp", sanitizer, True)
    env = {"ASAN_OPTIONS": "detect_leaks=0", "UBSAN_OPTIONS": "halt_on_error=1"}
    _run(["ctest", "--test-dir", str(sanitizer), "--output-on-failure"], env={**__import__("os").environ, **env})
    if normal_count <= 0 or sanitizer_count != normal_count:
        _fail("sanitizer_test_count_mismatch", root.name)
    negative = prefix / "negative"
    negative_count = _configure_and_build(root, root / ".meta/negative_false_substitute.cpp", negative, False)
    rejected = subprocess.run(["ctest", "--test-dir", str(negative), "--output-on-failure"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode != 0
    if negative_count != normal_count or not rejected:
        _fail("negative_fixture_not_rejected", root.name)
    return {"normal_tests": normal_count, "sanitizer_tests": sanitizer_count, "negative_tests": negative_count, "negative_rejected": rejected}


def verify(out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        missing = [name for name in ("cmake", "c++") if shutil.which(name) is None]
        receipt = {
            "schema_version": "cross-midnight-host-verification-v2",
            "evidence_class": "host_diagnostic",
            "status": "not_completed",
            "blocked_command": (
                "PYTHONPATH=src python3 -m "
                "w8_biayn.integrations.moonlight_cross_midnight_aider_tasks --force --verify"
            ),
            "missing_prerequisite": missing,
            "local_family_verified": False,
        }
        _write(
            out / ".state/host-verification.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
        _sync_remedies(
            out,
            host_verification="not_completed",
            host_missing_prerequisite=missing,
            strongest_local_status="pending_docker_sanity",
        )
        return receipt
    verify_core(out)
    tasks: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="cross-midnight-host-") as temporary:
        scratch = Path(temporary)
        for case in CASES:
            tasks[case.task_id] = _host_root_check(out / case.task_id, scratch / case.task_id)
        controls: dict[str, object] = {}
        for control in sorted((out / ".state/controls").iterdir()):
            controls[control.name] = _host_root_check(control, scratch / f"control-{control.name}")
    receipt = {
        "schema_version": "cross-midnight-host-verification-v2", "evidence_class": "host_diagnostic",
        "family_hash": _family_hash(out), "generator_hash": _source_hash(),
        "owner_source_hashes": _owner_source_hashes(), "tasks": tasks,
        "controls": controls, "status": "pass", "local_family_verified": False,
    }
    _write(out / ".state/host-verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(out, status="implemented", host_verification="pass", strongest_local_status="pending_docker_sanity")
    return receipt


DOCKER_SCRIPT = r'''set -eu
root=/family
work=/tmp/cross-midnight
mkdir -p "$work"
: > /tmp/results.tsv
trap 'status=$?; trap - 0; if [ "$status" -ne 0 ]; then cat /tmp/results.tsv 2>/dev/null || true; for log in /tmp/configure.log /tmp/build.log /tmp/ctest.log /tmp/neg-configure.log /tmp/neg-build.log /tmp/neg-test.log; do [ ! -f "$log" ] || { echo "== $log =="; tail -80 "$log"; }; done; fi; exit "$status"' 0
run_root() {
  name="$1"; source_root="$2"; target="$work/$name"; cp -R "$source_root" "$target"
  for mode in normal sanitizer; do
    build="$target/build-$mode"
    if [ "$mode" = sanitizer ]; then
      cmake -S "$target" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$target/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined" >/tmp/configure.log 2>&1
    else
      cmake -S "$target" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$target/.meta/example.cpp" >/tmp/configure.log 2>&1
    fi
    cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *\([0-9][0-9]*\).*/\1/p')
    [ "$count" = 2 ]
    ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$build" --output-on-failure >/tmp/ctest.log 2>&1
    printf '%s\t%s\t%s\tpass\n' "$name" "$mode" "$count" >> /tmp/results.tsv
  done
  neg="$target/build-negative"
  cmake -S "$target" -B "$neg" -G "Unix Makefiles" -DTASK_SOURCE="$target/.meta/negative_false_substitute.cpp" >/tmp/neg-configure.log 2>&1
  cmake --build "$neg" --parallel 2 >/tmp/neg-build.log 2>&1
  count=$(ctest --test-dir "$neg" -N | sed -n 's/.*Total Tests: *\([0-9][0-9]*\).*/\1/p')
  [ "$count" = 2 ]
  if ctest --test-dir "$neg" --output-on-failure >/tmp/neg-test.log 2>&1; then exit 71; fi
  printf '%s\tnegative\t%s\trejected\n' "$name" "$count" >> /tmp/results.tsv
}
for path in "$root"/*; do [ -d "$path" ] || continue; run_root "$(basename "$path")" "$path"; done
for path in "$root/.state/controls"/*; do run_root "control-$(basename "$path")" "$path"; done
python3 - "$root" <<'PY' > /tmp/treehash.tsv
import hashlib
import pathlib
import sys

family = pathlib.Path(sys.argv[1])
roots = [(path.name, path) for path in sorted(family.iterdir()) if path.is_dir() and path.name != ".state"]
controls = family / ".state/controls"
roots.extend((f"control-{path.name}", path) for path in sorted(controls.iterdir()) if path.is_dir())
for name, root in roots:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".state" not in item.relative_to(root).parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    print(f"TREEHASH\t{name}\tsha256:{digest.hexdigest()}")
PY
compiler=$(command -v c++)
printf 'TOOL\tcompiler_path\t%s\n' "$compiler" > /tmp/tools.tsv
printf 'TOOL\tcompiler_sha256\tsha256:%s\n' "$(sha256sum "$compiler" | cut -d' ' -f1)" >> /tmp/tools.tsv
printf 'TOOL\tcompiler_version\t%s\n' "$(c++ --version | head -1)" >> /tmp/tools.tsv
printf 'TOOL\tcmake_version\t%s\n' "$(cmake --version | head -1)" >> /tmp/tools.tsv
cat /tmp/tools.tsv /tmp/treehash.tsv /tmp/results.tsv
'''


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out)
    if manifest["screen"]["benchmark_contamination"]["status"] != "pass":
        _fail("not_completed", "benchmark semantic holdout screen is unavailable")
    if shutil.which("docker") is None:
        receipt = {"status": "not_completed", "blocked_command": f"docker run --network none {image}", "missing_prerequisite": "docker CLI/socket", "local_family_verified": False}
        _write(out / ".state/docker-sanity.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        return receipt
    command = ["docker", "run", "--rm", "--network", "none", "-v", f"{out.resolve()}:/family:ro", image, "sh", "-c", DOCKER_SCRIPT]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        receipt = {"status": "failed", "command": command, "returncode": result.returncode, "stdout_tail": result.stdout[-4000:], "stderr_tail": result.stderr[-4000:], "local_family_verified": False}
        _write(out / ".state/docker-sanity.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        _fail("docker_sanity_failed", str(result.returncode))
    rows = []
    mount_hashes: dict[str, str] = {}
    toolchain: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == "TREEHASH":
            mount_hashes[parts[1]] = parts[2]
        elif len(parts) == 3 and parts[0] == "TOOL":
            toolchain[parts[1]] = parts[2]
        elif len(parts) == 4:
            rows.append({"root": parts[0], "mode": parts[1], "test_count": int(parts[2]), "result": parts[3]})
    expected_rows = (len(CASES) + 3) * 3
    if len(rows) != expected_rows or any(row["test_count"] != 2 for row in rows):
        _fail("sanitizer_test_count_mismatch", f"rows={len(rows)} expected={expected_rows}")
    live_hashes = {case.task_id: _tree_hash(out / case.task_id) for case in CASES}
    live_control_hashes = {
        f"control-{path.name}": _tree_hash(path)
        for path in sorted((out / ".state/controls").iterdir())
        if path.is_dir()
    }
    if mount_hashes != {**live_hashes, **live_control_hashes}:
        _fail("grader_mount_hash_mismatch", json.dumps(mount_hashes, sort_keys=True))
    required_tools = {"compiler_path", "compiler_sha256", "compiler_version", "cmake_version"}
    if set(toolchain) != required_tools:
        _fail("docker_sanity_failed", f"missing toolchain fields: {required_tools - set(toolchain)}")
    receipt = {
        "schema_version": "cross-midnight-docker-sanity-v2", "status": "pass",
        "evidence_class": "docker_sanity", "locked_oracle": False, "network_policy": "none",
        "image": image, "command": command, "family_hash": _family_hash(out),
        "live_tree_hashes": live_hashes, "docker_mount_tree_hashes": mount_hashes,
        "live_control_hashes": live_control_hashes,
        "generator_hash": _source_hash(),
        "owner_source_hashes": _owner_source_hashes(),
        "reference_hashes": {
            case.task_id: _sha_bytes((out / case.task_id / ".meta/example.cpp").read_bytes())
            for case in CASES
        },
        "rows": rows, "toolchain": toolchain,
        "hard_rule_pair_count": len(CASES) * (len(CASES) - 1) // 2,
        "hard_rule_dimensions": list(HARD_DIMENSIONS),
        "controls_compiled_and_tested": 3, "topic_negatives_compiled_and_rejected": len(CASES),
        "local_family_verified": True, "dataset_handoff": "not_requested",
    }
    _write(out / ".state/docker-sanity.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out, status="verified", strongest_local_status="local_family_verified",
        docker_sanity="pass", receipt_path=".state/docker-sanity.json",
        normal_test_count=2, sanitizer_test_count=2, topic_negative_rejected=True,
        coherent_controls_rejected=True, benchmark_screen="pass", family_screen="pass",
    )
    final_manifest = json.loads((out / ".state/materialization-manifest.json").read_text(encoding="utf-8"))
    final_manifest["strongest_local_status"] = "local_family_verified"
    final_manifest["docker_receipt"] = ".state/docker-sanity.json"
    _write(out / ".state/materialization-manifest.json", json.dumps(final_manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remediate cross-midnight interval Aider tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--holdout-root", type=Path, default=DEFAULT_HOLDOUT_ROOT)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out, args.holdout_root)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out)
    print(f"Wrote {len(roots)} cross-midnight interval replacements under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
