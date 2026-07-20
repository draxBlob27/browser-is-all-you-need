"""Remediate and locally reverify the text-justification Aider task family."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_text_justification_cases import (
    CASES,
    NEGATIVE_MUTATIONS,
    TextCase,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/text-justification")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/text-justification")
CURRICULUM = ("docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
              "GLM47_FLASH_AIDER_POLYGLOT_CPP_WORD_WRAP_TEXT_JUSTIFY_CURRICULUM.md")
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/text-justification.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-text-justification-v2"
FAMILY_ID_BEFORE = "aider-text-grid-reshaping-text-justification-v1-template"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_word_wrap_text_justify_aider_tasks.py"
CASE_PATH = "src/w8_biayn/integrations/moonlight_text_justification_cases.py"
SEMANTIC_NORMALIZER = "text-layout-control-flow-v2"
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = ("w8-biayn-polyglot-cpp@sha256:"
                "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991")
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)
OFFICIAL_HOLDOUTS = frozenset((
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
    "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
    "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name",
    "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
))
TASKS = CASES

HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_RULE_THRESHOLDS = {
    "public_api": 0.99,
    "owned_state_or_algorithm": 0.90,
    "mutation_or_selection_rules": 0.90,
    "invalid_and_boundary_behavior": 0.90,
    "reference_control_flow": 0.90,
    "deterministic_oracle": 0.95,
    "topic_specific_negative_fixture": 0.90,
}
CONTROL_NAMES = (
    "domain-identifier-renamed-clone",
    "constants-policy-clone",
    "opposite-end-selection-clone",
)
CONTROL_BASE_TASK = "justify-assembly-agenda"


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(
        p for p in root.rglob("*")
        if p.is_file() and ".state" not in p.relative_to(root).parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _source_hash(path: Path) -> str:
    return _sha(path.read_bytes())


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(text_justification_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
"""


def _negative_source(case: TextCase) -> tuple[str, str]:
    old, new, reason = NEGATIVE_MUTATIONS[case.task_id]
    if case.reference.count(old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    return case.reference.replace(old, new, 1), reason


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {case.task_id for case in CASES}
    records = {path.stem: path for path in remedy.glob("*.json")}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per legacy root is required")
    for case in CASES:
        record = json.loads(records[case.task_id].read_text(encoding="utf-8"))
        spec = remedy / f"{case.task_id}.md"
        disposition = "repair-in-place" if case.task_id == case.legacy_id else "replace"
        if record.get("disposition") != disposition:
            _fail("remedy_disposition_conflict", case.task_id)
        if record.get("legacy_task_id") != case.legacy_id or not spec.is_file():
            _fail("remedy_spec_incomplete", case.task_id)
        text = spec.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", case.task_id)
        if record.get("remedy_spec_hash") != _sha(text.encode()):
            _fail("remedy_spec_incomplete", f"hash mismatch: {case.task_id}")


def _sync_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = out / ".state" / "remedy" / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _source_hash(Path(GENERATOR_PATH))
        record["changed_owner_paths"] = [
            CURRICULUM, FAMILY_SPEC, "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            GENERATOR_PATH, CASE_PATH,
            "tests/test_moonlight_text_justification_aider_tasks.py",
            "examples/slime/moonlight_cpp_perf/prepare_text_justification_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _invalidate_stale_evidence(out: Path, reason: str) -> None:
    """Withdraw owner-produced verification before changing family artifacts."""
    state = out / ".state"
    invalidation_path = state / "evidence-invalidations.json"
    if invalidation_path.is_file():
        ledger = json.loads(invalidation_path.read_text(encoding="utf-8"))
    else:
        ledger = {
            "schema_version": "text-justification-evidence-invalidations-v1",
            "invalidations": [],
        }
    claims: list[dict[str, object]] = []
    for name in ("materialization-manifest.json", "docker-sanity.json"):
        path = state / name
        if not path.is_file():
            continue
        raw = path.read_bytes()
        payload = json.loads(raw)
        claims.append({
            "path": str(path),
            "evidence_hash": _sha(raw),
            "status": payload.get("status", "not_recorded"),
            "schema_version": payload.get("schema_version", "not_recorded"),
            "generator_hash": payload.get("generator_hash", "not_recorded"),
        })
        path.unlink()
    if claims:
        entry = {
            "reason": reason,
            "withdrawn_strongest_status": "local_family_verified",
            "replacement_status": "pending_execution",
            "claims": claims,
        }
        known = {
            tuple(claim["evidence_hash"] for claim in item.get("claims", []))
            for item in ledger["invalidations"]
        }
        identity = tuple(claim["evidence_hash"] for claim in claims)
        if identity not in known:
            ledger["invalidations"].append(entry)
        _write(invalidation_path, json.dumps(ledger, indent=2, sort_keys=True) + "\n", True)
    controls = state / "hard-rule-controls"
    if controls.is_dir():
        shutil.rmtree(controls)
    _sync_remedies(
        out,
        status="pending_execution",
        strongest_local_status="pending_execution",
        prior_verification_invalidated=bool(claims),
        invalidation_reason=reason,
        hard_rule_status="not_completed",
        oracle_evidence="not_completed",
    )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _verify_remedies(out)
    _invalidate_stale_evidence(
        out,
        "Owner, emitted artifacts, hard-rule screen, controls, tests, or receipt "
        "acceptance changed; prior proof does not bind the regenerated tree.",
    )
    roots: list[Path] = []
    for case in CASES:
        negative, reason = _negative_source(case)
        config = {
            "authors": ["w8-biayn"], "blurb": case.objective,
            "files": {"solution": ["task.h", "task.cpp"],
                      "test": ["task_visible_test.cpp"],
                      "example": [".meta/example.h", ".meta/example.cpp"]},
        }
        provenance = {
            "curriculum_document": CURRICULUM,
            "family_specification": FAMILY_SPEC,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id": FAMILY_ID,
            "semantic_profile": case.profile,
            "origin": "repository-authored clean-room remediation",
            "license": "repository-authored",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "benchmark_separation": (
                "Independent text-layout API, algorithm, and tests; all official "
                "Aider C++ roots remain permanent holdouts."),
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": (
                f'[visible]\ndescription = "{case.profile} public behavior"\n\n'
                '[hidden]\ndescription = "invalid, boundary, tie, and mechanism oracle"\n\n'
                f'[negative]\ndescription = "{reason}"\n'),
            "task.h": case.header, "task.cpp": case.starter,
            ".meta/example.h": case.header, ".meta/example.cpp": case.reference,
            ".meta/negative_false_substitute.cpp": negative,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        root = out / case.task_id
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _sync_remedies(
        out, status="pending_execution", strongest_local_status="pending_execution",
        primary_core_objective="achieved", prompt_boundary="pending",
        family_screen="pending", benchmark_screen="pending",
        oracle_evidence="not_completed",
    )
    return tuple(roots)


def _normalized_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b',
                     " LIT ", content)
    tokens = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content)
    keywords = {"if", "else", "for", "while", "return", "class", "struct",
                "const", "auto", "bool", "int", "long", "void", "true",
                "false", "public", "private", "namespace", "std", "vector",
                "deque", "string", "size_t"}
    return [token if token in keywords or not re.match(r"[A-Za-z_]", token)
            else "ID" for token in tokens]


def _ngrams(tokens: list[str], width: int = 8) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + width])
            for i in range(max(0, len(tokens) - width + 1))}


def _containment(left: str, right: str) -> float:
    a, b = _ngrams(_normalized_tokens(left)), _ngrams(_normalized_tokens(right))
    denominator = min(len(a), len(b))
    return len(a & b) / denominator if denominator else 1.0


def _artifact(root: Path) -> dict[str, str]:
    """Read the seven hard-rule dimensions from one actual emitted root."""
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = config["files"]["solution"]
    if len(solution) != 2:
        _fail("target_reference_mismatch", str(root))
    header = (root / solution[0]).read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_false_substitute.cpp").read_text(
        encoding="utf-8"
    )
    return {
        "public_api": header,
        "owned_state_or_algorithm": header + "\n" + reference,
        "mutation_or_selection_rules": instructions + "\n" + reference,
        "invalid_and_boundary_behavior": instructions + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_specific_negative_fixture": negative,
    }


def _evaluate_pair(
    left_id: str,
    left: dict[str, str],
    right_id: str,
    right: dict[str, str],
) -> dict[str, object]:
    if tuple(left) != HARD_RULE_DIMENSIONS or tuple(right) != HARD_RULE_DIMENSIONS:
        _fail("duplicate_family", "hard-rule dimension drift")
    dimensions: dict[str, dict[str, object]] = {}
    for dimension in HARD_RULE_DIMENSIONS:
        left_tokens = _normalized_tokens(left[dimension])
        right_tokens = _normalized_tokens(right[dimension])
        left_ngrams = _ngrams(left_tokens)
        right_ngrams = _ngrams(right_tokens)
        denominator = min(len(left_ngrams), len(right_ngrams))
        shared = len(left_ngrams & right_ngrams)
        score = shared / denominator if denominator else 1.0
        threshold = HARD_RULE_THRESHOLDS[dimension]
        dimensions[dimension] = {
            "materially_distinct": score < threshold,
            "normalized_containment": round(score, 6),
            "threshold_exclusive": threshold,
            "left_token_count": len(left_tokens),
            "right_token_count": len(right_tokens),
            "left_ngram_count": len(left_ngrams),
            "right_ngram_count": len(right_ngrams),
            "shared_ngram_count": shared,
        }
    passed = all(
        bool(decision["materially_distinct"])
        for decision in dimensions.values()
    )
    return {
        "left": left_id,
        "right": right_id,
        "dimension_set": list(HARD_RULE_DIMENSIONS),
        "dimensions": dimensions,
        "all_dimensions_materially_distinct": passed,
        "decision": "pass" if passed else "rejected:duplicate_family",
        "failed_dimensions": [
            name for name, decision in dimensions.items()
            if not decision["materially_distinct"]
        ],
    }


def _hard_rule_matrix(out: Path) -> dict[str, object]:
    artifacts = {case.task_id: _artifact(out / case.task_id) for case in CASES}
    pairs: list[dict[str, object]] = []
    ids = sorted(artifacts)
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1:]:
            row = _evaluate_pair(
                left_id, artifacts[left_id], right_id, artifacts[right_id]
            )
            if not row["all_dimensions_materially_distinct"]:
                _fail(
                    "duplicate_family",
                    f"{left_id} / {right_id}: {row['failed_dimensions']}",
                )
            pairs.append(row)
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"incomplete all-pairs: {len(pairs)}")
    return {"status": "pass", "normalizer": SEMANTIC_NORMALIZER,
            "dimension_set": list(HARD_RULE_DIMENSIONS),
            "decision_rule": "all seven dimensions must be materially distinct",
            "pair_count": len(pairs), "expected_pair_count": expected,
            "comparison_scope": ("actual emitted docs, public APIs, owned state, "
                                 "references, visible/private tests, and topic negatives"),
            "pairs": pairs}


def _transform_control_root(
    source: Path,
    target: Path,
    *,
    path_replacements: tuple[tuple[str, str], ...] = (),
    content_replacements: tuple[tuple[str, str], ...],
) -> list[dict[str, str]]:
    changed: list[dict[str, str]] = []
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        source_relative = path.relative_to(source).as_posix()
        target_relative = source_relative
        for old, new in path_replacements:
            target_relative = target_relative.replace(old, new)
        content = path.read_text(encoding="utf-8")
        transformed = content
        for old, new in content_replacements:
            transformed = transformed.replace(old, new)
        _write(target / target_relative, transformed, True)
        if target_relative != source_relative or transformed != content:
            changed.append({"source": source_relative, "control": target_relative})
    return changed


def _validate_control_root(root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    expected = [f"{root.name}.h", f"{root.name}.cpp"]
    if config["files"]["solution"] != expected:
        _fail("control_not_coherent", f"solution filenames: {root}")
    if not all((root / relative).is_file() for relative in expected):
        _fail("control_not_coherent", f"missing solution file: {root}")
    task = load_task(root)
    build_prompt(task)
    build_assistant_response(task, load_example_files_from_config(root))
    for relative in (
        ".docs/instructions.md", ".meta/example.cpp",
        ".meta/negative_false_substitute.cpp", "task_visible_test.cpp",
        ".meta/task_hidden_test.cpp", "CMakeLists.txt",
    ):
        if not (root / relative).is_file():
            _fail("control_not_coherent", f"missing {relative}: {root}")


def _materialize_controls(out: Path) -> dict[str, dict[str, object]]:
    source = out / CONTROL_BASE_TASK
    controls_root = out / ".state" / "hard-rule-controls"
    if controls_root.is_dir():
        shutil.rmtree(controls_root)

    domain_id = "schedule-meeting-notes"
    definitions = {
        "domain-identifier-renamed-clone": {
            "root": controls_root / "domain-identifier-renamed-clone" / domain_id,
            "path_replacements": ((CONTROL_BASE_TASK, domain_id),),
            "content_replacements": (
                (CONTROL_BASE_TASK, domain_id),
                ("AgendaItem", "MeetingItem"),
                ("AgendaLayout", "MeetingLayout"),
                ("layout_agenda", "layout_meeting"),
                ("agenda", "meeting"),
                ("Agenda", "Meeting"),
            ),
            "required_changed": {
                ".docs/instructions.md", ".meta/example.cpp", ".meta/example.h",
                ".meta/negative_false_substitute.cpp", "task_visible_test.cpp",
                ".meta/task_hidden_test.cpp", f"{CONTROL_BASE_TASK}.h",
                f"{CONTROL_BASE_TASK}.cpp", "CMakeLists.txt",
            },
        },
        "constants-policy-clone": {
            "root": controls_root / "constants-policy-clone" / CONTROL_BASE_TASK,
            "path_replacements": (),
            "content_replacements": (
                ("Width is 4..80", "Width is 4..79"),
                ("width>80U", "width>79U"),
                ("return f;}",
                 'f+=layout_agenda({{"A","x"}},80).valid;return f;}'),
            ),
            "required_changed": {
                ".docs/instructions.md", ".meta/example.cpp",
                ".meta/negative_false_substitute.cpp", ".meta/task_hidden_test.cpp",
            },
        },
        "opposite-end-selection-clone": {
            "root": controls_root / "opposite-end-selection-clone" / CONTROL_BASE_TASK,
            "path_replacements": (),
            "content_replacements": (
                ("Preserve item order.", "Render agenda items in reverse input order."),
                ("for(const AgendaItem& item:items){",
                 "for(auto it=items.rbegin();it!=items.rend();++it){const AgendaItem& item=*it;"),
                ('return x.valid&&x.lines==std::vector<std::string>{"1. alpha","   beta","   gamma"}?0:1;}',
                 'auto y=layout_agenda({{"A","one"},{"B","two"}},8);return x.valid&&x.lines==std::vector<std::string>{"1. alpha","   beta","   gamma"}&&y.valid&&y.lines==std::vector<std::string>{"B two","A one"}?0:1;}'),
                ("return f;}",
                 'auto y=layout_agenda({{"A","one"},{"B","two"}},8);f+=!y.valid||y.lines!=std::vector<std::string>{"B two","A one"};return f;}'),
            ),
            "required_changed": {
                ".docs/instructions.md", ".meta/example.cpp",
                ".meta/negative_false_substitute.cpp", "task_visible_test.cpp",
                ".meta/task_hidden_test.cpp",
            },
        },
    }
    base_artifact = _artifact(source)
    records: dict[str, dict[str, object]] = {}
    for name in CONTROL_NAMES:
        definition = definitions[name]
        root = definition["root"]
        changed = _transform_control_root(
            source,
            root,
            path_replacements=definition["path_replacements"],
            content_replacements=definition["content_replacements"],
        )
        changed_sources = {row["source"] for row in changed}
        required = definition["required_changed"]
        if not changed or not required.issubset(changed_sources):
            _fail(
                "control_noop",
                f"{name}: missing intended changes {sorted(required - changed_sources)}",
            )
        _validate_control_root(root)
        evaluation = _evaluate_pair(
            CONTROL_BASE_TASK, base_artifact, name, _artifact(root)
        )
        if evaluation["decision"] != "rejected:duplicate_family":
            _fail("duplicate_family", f"clone control escaped: {name}")
        records[name] = {
            "base_task_id": CONTROL_BASE_TASK,
            "root": root.relative_to(out).as_posix(),
            "base_tree_hash": _tree_hash(source),
            "tree_hash": _tree_hash(root),
            "changed_files": changed,
            "intended_files_changed": True,
            "structurally_coherent": True,
            "docker_build_status": "not_completed",
            "production_evaluator": evaluation,
        }
    return records


def _holdout_screen() -> dict[str, object]:
    if not DEFAULT_HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(DEFAULT_HOLDOUT_ROOT))
    holdouts: dict[str, str] = {}
    inventory = hashlib.sha256()
    for root in sorted(p for p in DEFAULT_HOLDOUT_ROOT.iterdir() if p.is_dir()):
        chunks: list[str] = []
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if path.suffix not in {".h", ".hpp", ".cpp", ".md"}:
                continue
            inventory.update(path.relative_to(DEFAULT_HOLDOUT_ROOT).as_posix().encode())
            inventory.update(path.read_bytes())
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        holdouts[root.name] = "\n".join(chunks)
    if set(holdouts) != OFFICIAL_HOLDOUTS:
        _fail("benchmark_screen_not_completed", "official holdout inventory drift")
    strongest = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = case.instructions + case.header + case.reference
        for slug, content in holdouts.items():
            score = _containment(candidate, content)
            if score > float(strongest["containment"]):
                strongest = {"candidate": case.task_id, "holdout": slug,
                             "containment": round(score, 6)}
            if score >= 0.60:
                _fail("benchmark_content_overlap",
                      f"{case.task_id} resembles {slug}: {score:.3f}")
    return {"status": "pass", "holdout_root_count": len(holdouts),
            "source_inventory": "sha256:" + inventory.hexdigest(),
            "strongest": strongest}


def _prompt_and_roles(case: TextCase, root: Path) -> None:
    task = load_task(root)
    if tuple(task.editable_files) != (f"{case.task_id}.h", f"{case.task_id}.cpp"):
        _fail("target_reference_mismatch", case.task_id)
    prompt = build_prompt(task)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    forbidden = (".meta/example", "task_hidden_test", "CMakeLists",
                 "provenance", "negative_false_substitute")
    if any(value in prompt for value in forbidden):
        _fail("prompt_contract_incomplete", case.task_id)
    if ".meta/example" in answer:
        _fail("target_reference_mismatch", case.task_id)
    config = json.loads((root / ".meta/config.json").read_text())
    if config["files"]["test"] != ["task_visible_test.cpp"]:
        _fail("unsafe_path", case.task_id)


def verify_core(out: Path, *, require_remedy: bool = True) -> dict[str, object]:
    expected = {case.task_id for case in CASES}
    actual = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"{sorted(expected ^ actual)}")
    if require_remedy:
        _verify_remedies(out)
    if len({case.profile for case in CASES}) != len(CASES):
        _fail("duplicate_family", "semantic profiles are not one-to-one")
    if len({case.public_api for case in CASES}) != len(CASES):
        _fail("duplicate_family", "public APIs are not one-to-one")
    for case in CASES:
        _prompt_and_roles(case, out / case.task_id)
        if case.marker not in case.reference:
            _fail("invariant_not_enforced", case.task_id)
    matrix = _hard_rule_matrix(out)
    controls = _materialize_controls(out)
    holdouts = _holdout_screen()
    manifest = {
        "schema_version": "text-justification-materialization-v2",
        "family_id": FAMILY_ID, "task_count": len(CASES),
        "generator_hash": _source_hash(Path(GENERATOR_PATH)),
        "case_hash": _source_hash(Path(CASE_PATH)),
        "tasks": [{"task_id": case.task_id, "legacy_task_id": case.legacy_id,
                   "profile": case.profile, "tree_hash": _tree_hash(out / case.task_id),
                   "reference_hash": _source_hash(
                       out / case.task_id / ".meta/example.cpp")}
                  for case in CASES],
        "screen": {"prompt_boundary": "pass", "reference_mapping": "pass",
                   "hard_rule": matrix, "adversarial_controls": controls,
                   "semantic_holdout": holdouts},
    }
    _write(out / ".state" / "materialization-manifest.json",
           json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out, status="pending_execution",
        strongest_local_status="pending_execution",
        primary_core_objective="achieved", prompt_boundary="pass",
        reference_mapping="pass", family_screen="pass", benchmark_screen="pass",
        hard_rule_status="pass", family_pair_count=190, holdout_root_count=26,
        hard_rule_dimension_count=7,
        hard_rule_dimensions=list(HARD_RULE_DIMENSIONS),
        adversarial_controls_status="rejected_by_production_evaluator_pending_docker",
        oracle_evidence="not_completed",
    )
    return manifest


DOCKER_RUNNER = r"""import hashlib,json,os,pathlib,shutil,subprocess,tarfile
archive=pathlib.Path("/input/family.tar")
root=pathlib.Path("/tmp/family")
if root.exists(): shutil.rmtree(root)
root.mkdir()
with tarfile.open(archive) as tar: tar.extractall(root)
expected=json.loads(pathlib.Path("/input/expected.json").read_text())
def tree_hash(path):
    d=hashlib.sha256()
    for p in sorted(x for x in path.rglob("*") if x.is_file() and ".state" not in x.parts):
        d.update(p.relative_to(path).as_posix().encode());d.update(b"\0")
        d.update(p.read_bytes());d.update(b"\0")
    return "sha256:"+d.hexdigest()
results=[];issues=[]
env=dict(os.environ);env["ASAN_OPTIONS"]="detect_leaks=0"
def quiet(args,env=None):
    return subprocess.run(args,text=True,capture_output=True,env=env)
for subject in expected["subjects"]:
    subject_id=subject["subject_id"];kind=subject["kind"]
    task=root/subject["archive_root"];want=subject["tree_hash"]
    got=tree_hash(task)
    if got!=want: raise SystemExit("grader_mount_hash_mismatch:"+subject_id+":"+got+":"+want)
    for mode in ("normal","sanitizer"):
        build=pathlib.Path("/tmp/build")/kind/subject_id/mode
        if build.exists(): shutil.rmtree(build)
        args=["cmake","-S",str(task),"-B",str(build),"-G","Unix Makefiles",
              "-DCMAKE_CXX_COMPILER=/usr/local/bin/g++",
              "-DTASK_SOURCE="+str(task/".meta/example.cpp")]
        if mode=="sanitizer":
            args+=["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                   "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
        configured=quiet(args)
        if configured.returncode:
            issues.append("reference_configure_failed:"+subject_id+":"+mode+":"+configured.stderr[-300:]);continue
        built=quiet(["cmake","--build",str(build),"--parallel","2"])
        if built.returncode:
            issues.append("reference_compile_failed:"+subject_id+":"+mode+":"+built.stderr[-300:]);continue
        shown=quiet(["ctest","--test-dir",str(build),"--show-only=json-v1"])
        if shown.returncode:
            issues.append("test_discovery_failed:"+subject_id+":"+mode);continue
        count=len(json.loads(shown.stdout)["tests"])
        if count!=2: raise SystemExit("test_discovery_failed:"+subject_id+":"+mode)
        reference_run=quiet(["ctest","--test-dir",str(build),"--output-on-failure"],env=env)
        if reference_run.returncode:
            issues.append("reference_tests_failed:"+subject_id+":"+mode+":"+reference_run.stdout[-300:])
        negative=pathlib.Path("/tmp/build")/kind/subject_id/(mode+"-negative")
        if negative.exists(): shutil.rmtree(negative)
        n_args=[x for x in args if not x.startswith("-DTASK_SOURCE=")]
        n_args[4]=str(negative)
        n_args.append("-DTASK_SOURCE="+str(task/".meta/negative_false_substitute.cpp"))
        nconfigured=quiet(n_args)
        if nconfigured.returncode:
            issues.append("negative_configure_failed:"+subject_id+":"+mode);continue
        nbuilt=quiet(["cmake","--build",str(negative),"--parallel","2"])
        if nbuilt.returncode:
            issues.append("negative_compile_failed:"+subject_id+":"+mode+":"+nbuilt.stderr[-300:]);continue
        nshown=quiet(["ctest","--test-dir",str(negative),"--show-only=json-v1"])
        if nshown.returncode:
            issues.append("negative_discovery_failed:"+subject_id+":"+mode);continue
        ncount=len(json.loads(nshown.stdout)["tests"])
        run=quiet(["ctest","--test-dir",str(negative),"--output-on-failure"],env=env)
        if ncount!=2 or run.returncode==0:
            issues.append("negative_fixture_not_rejected:"+subject_id+":"+mode)
        results.append({"subject_id":subject_id,"kind":kind,
                        "task_id":subject.get("task_id"),
                        "control_name":subject.get("control_name"),
                        "mode":mode,"test_count":count,
                        "negative_test_count":ncount,"negative_rejected":True,
                        "mounted_tree_hash":got})
toolchain={
 "compiler_path":"/usr/local/bin/g++",
 "compiler_version":subprocess.run(["/usr/local/bin/g++","--version"],text=True,
     check=True,capture_output=True).stdout.splitlines()[0],
 "compiler_hash":"sha256:"+hashlib.sha256(pathlib.Path("/usr/local/bin/g++").read_bytes()).hexdigest(),
 "cmake_version":subprocess.run(["cmake","--version"],text=True,check=True,
     capture_output=True).stdout.splitlines()[0],
}
pathlib.Path("/output/result.json").write_text(json.dumps(
 {"results":results,"toolchain":toolchain,"issues":issues},sort_keys=True))
"""


def _archive_family(
    out: Path, archive: Path, controls: dict[str, dict[str, object]]
) -> str:
    with tarfile.open(archive, "w") as tar:
        for case in sorted(CASES, key=lambda item: item.task_id):
            root = out / case.task_id
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                relative = Path(case.task_id) / path.relative_to(root)
                info = tarfile.TarInfo(relative.as_posix())
                content = path.read_bytes()
                info.size = len(content); info.mode = 0o644; info.mtime = 0
                info.uid = info.gid = 0; info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(content))
        for name in CONTROL_NAMES:
            root = out / str(controls[name]["root"])
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                relative = Path("controls") / name / root.name / path.relative_to(root)
                info = tarfile.TarInfo(relative.as_posix())
                content = path.read_bytes()
                info.size = len(content); info.mode = 0o644; info.mtime = 0
                info.uid = info.gid = 0; info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(content))
    return _source_hash(archive)


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out)
    controls = manifest["screen"]["adversarial_controls"]
    if image != SANITY_IMAGE:
        _fail("grader_image_mismatch", image)
    inspected = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        check=True, text=True, capture_output=True)
    image_id = inspected.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="text-justification-docker-") as tmp:
        temp = Path(tmp); archive = temp / "family.tar"
        archive_hash = _archive_family(out, archive, controls)
        subjects = [
            {"subject_id": row["task_id"], "kind": "task",
             "task_id": row["task_id"], "control_name": None,
             "archive_root": row["task_id"], "tree_hash": row["tree_hash"]}
            for row in manifest["tasks"]
        ]
        subjects.extend(
            {"subject_id": name, "kind": "control", "task_id": CONTROL_BASE_TASK,
             "control_name": name,
             "archive_root": f"controls/{name}/{Path(controls[name]['root']).name}",
             "tree_hash": controls[name]["tree_hash"]}
            for name in CONTROL_NAMES
        )
        expected = {"subjects": subjects}
        (temp / "expected.json").write_text(json.dumps(expected))
        (temp / "runner.py").write_text(DOCKER_RUNNER)
        output = temp / "output"; output.mkdir()
        command = ["docker", "run", "--rm", "--network", "none",
                   "-v", f"{temp}:/input:ro", "-v", f"{output}:/output",
                   image, "python3", "/input/runner.py"]
        subprocess.run(command, check=True)
        result = json.loads((output / "result.json").read_text())
    rows = result["results"]
    if result.get("issues"):
        _fail("docker_sanity_failed", ", ".join(result["issues"]))
    if len(rows) != (len(CASES) + len(CONTROL_NAMES)) * 2:
        _fail("test_discovery_failed", f"result rows: {len(rows)}")
    by_subject: dict[str, dict[str, int]] = {}
    for row in rows:
        if row["test_count"] != 2 or row["negative_test_count"] != 2:
            _fail("test_discovery_failed", row["subject_id"])
        if not row["negative_rejected"]:
            _fail("negative_fixture_not_rejected", row["subject_id"])
        by_subject.setdefault(row["subject_id"], {})[row["mode"]] = row["test_count"]
    expected_subjects = {case.task_id for case in CASES} | set(CONTROL_NAMES)
    if set(by_subject) != expected_subjects:
        _fail("test_discovery_failed", "Docker subject inventory drift")
    for subject_id, counts in by_subject.items():
        if counts != {"normal": 2, "sanitizer": 2}:
            _fail("sanitizer_test_count_mismatch", subject_id)

    for name in CONTROL_NAMES:
        controls[name]["docker_build_status"] = "pass"
        controls[name]["normal_test_count"] = 2
        controls[name]["sanitizer_test_count"] = 2
        controls[name]["negative_fixture_status"] = (
            "compiled_and_rejected_normal_and_sanitizer"
        )
    manifest_path = out / ".state" / "materialization-manifest.json"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    receipt = {
        "schema_version": "text-justification-docker-sanity-v2",
        "status": "pass", "evidence_class": "docker_sanity",
        "locked_oracle": False, "network_policy": "none",
        "image": image, "image_id": image_id, "archive_hash": archive_hash,
        "generator_hash": _source_hash(Path(GENERATOR_PATH)),
        "case_hash": _source_hash(Path(CASE_PATH)),
        "materialization_manifest_hash": _source_hash(manifest_path),
        "toolchain": result["toolchain"], "task_count": len(CASES),
        "control_count": len(CONTROL_NAMES),
        "verified_subject_count": len(expected_subjects),
        "normal_test_count_per_task": 2, "sanitizer_test_count_per_task": 2,
        "topic_negatives_compiled_and_rejected": len(CASES),
        "coherent_controls_compiled_and_rejected": len(CONTROL_NAMES),
        "results": rows, "command": command,
    }
    receipt_path = out / ".state" / "docker-sanity.json"
    _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out, status="verified", strongest_local_status="local_family_verified",
        primary_core_objective="achieved", prompt_boundary="pass",
        reference_mapping="pass", family_screen="pass", benchmark_screen="pass",
        hard_rule_status="pass", oracle_evidence="docker_sanity",
        hard_rule_dimension_count=7,
        hard_rule_dimensions=list(HARD_RULE_DIMENSIONS),
        adversarial_controls_status=(
            "coherent_buildable_and_rejected_by_production_evaluator"
        ),
        oracle_receipt=str(receipt_path), normal_test_count=2,
        sanitizer_test_count=2,
        negative_fixture_status="compiled_and_rejected_normal_and_sanitizer",
        image=image, image_id=image_id, network_policy="none",
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core and not args.docker_sanity:
        verify_core(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    print(f"Wrote {len(roots)} text-justification tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
