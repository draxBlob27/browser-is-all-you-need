#!/usr/bin/env python3
"""Freeze the legacy calendar-family audit and write planned remedy records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


LEGACY = Path(
    ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/"
    "general-calendar-arithmetic"
)
OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/"
    "general-calendar-arithmetic"
)
OWNER = Path(
    "src/w8_biayn/integrations/moonlight_calendar_arithmetic_aider_tasks.py"
)
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "general-calendar-arithmetic.md"
)
FAMILY_BEFORE = "aider-dates-and-clocks-general-calendar-arithmetic-v1-template"
FAMILY_AFTER = "aider-dates-and-clocks-general-calendar-arithmetic-v2-hard-rule"

# Legacy id, surviving core objective, required remediated mechanism, negative.
CASES = (
    ("calendar-subscription-cycle", "select the next anchored renewal across subscriber policies", "anchor-preserving month projection plus earliest-due reduction", "clamped-day chaining instead of retaining the original anchor"),
    ("calendar-harvest-plan", "migrate crop windows while preserving their civil-day duration", "ordinal conversion plus checked duration reconstruction", "shifting both endpoints independently and changing duration"),
    ("calendar-clinic-followup", "allocate follow-ups around blackout intervals before a horizon", "ordered blackout interval merge plus forward free-day search", "dropping a blocked appointment instead of finding its first free day"),
    ("calendar-inventory-expiry", "classify inventory from manufactured, expiry, recall, and as-of events", "stable event precedence sweep with an expiring threshold", "testing expiry before an effective recall"),
    ("calendar-contract-amendment", "apply an effective-date amendment ledger atomically", "sequence/effective-date validation plus transactional period replay", "committing valid prefixes when a later amendment is rejected"),
    ("calendar-vacation-allocation", "charge a leave span across annual balances and closures", "year-partitioned inclusive span ledger with closure exclusion", "charging closure days or debiting the wrong year"),
    ("calendar-maintenance-rotation", "project recurring service dates and catch-up counts", "anchor-based recurrence search with first-due-at-or-after selection", "advancing from each clamped occurrence and drifting the anchor"),
    ("calendar-licence-grace", "classify submissions across active, grace, lapse, and reinstatement boundaries", "ordered policy-boundary construction with inclusive tier selection", "making the inclusive grace endpoint lapsed"),
    ("calendar-release-train", "propagate milestone shifts through dependency constraints", "topological dependency propagation plus deterministic collision detection", "shifting milestones independently and violating predecessor order"),
    ("calendar-lease-portfolio", "aggregate lease occupancy, gaps, and overlaps", "civil-ordinal difference sweep over valid portfolio intervals", "pairwise overlap counting that double-counts days with three leases"),
)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def tree_hash(root: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        result.update(relative)
        result.update(b"\0")
        result.update(path.read_bytes())
        result.update(b"\0")
    return "sha256:" + result.hexdigest()


def remedy_markdown(
    legacy_id: str, objective: str, mechanism: str, negative: str
) -> str:
    root = LEGACY / legacy_id
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    header_path = root / config["files"]["solution"][0]
    header = header_path.read_text(encoding="utf-8").strip()
    return f"""## Identity

Task ID: `{legacy_id}`. Task-spec revision: 2. Family ID: `{FAMILY_AFTER}/{legacy_id}`. Disposition: `repair-in-place`. Source inventory ID: `general-calendar-arithmetic-legacy-v1`. License result: pass (repository-authored clean-room material). Generator: `{OWNER}`. Benchmark screen: pending semantic screen; `clock`, `gigasecond`, and `meetup` are permanent holdouts. Selected prompt: `{PROMPT}` with corrected user inputs `FAMILY_NAME=general-calendar-arithmetic`, `FAMILY_TYPE=aider-dates-and-clocks`, and hard-rule count `8-12`.

## Objective

Implement and deterministically test one observable capability: {objective}. The task remains a domain policy API rather than a reusable date-library exercise.

## Public API

C++17 namespace `curriculum`; editable order is `{config['files']['solution']}`. The legacy declarations below are audit input; the remediated task retains the task ID but may revise its task-specific records and signatures to expose the capability completely.

```cpp
{header}
```

Caller-owned values cross the API. The implementation owns only the state or work structures declared by the remediated header.

## Behavior table

| Operation class | Valid result | Invalid, duplicate, absent, empty, ordering, tie, and overflow behavior |
| --- | --- | --- |
| primary calendar policy | returns the documented task-specific report after executing `{mechanism}` | invalid civil dates and checked-range overflow reject without partial mutation; task-specific duplicate/absent rules are explicit; empty input returns the documented neutral report; dates and diagnostics use stable civil/ID order; equality is inclusive only where stated |

Boundary example: the remediated public tests include a leap-century or month-end equality that distinguishes the required mechanism from the named negative fixture.

## Implementation invariant

Required mechanism: `{mechanism}`. The reference must own that control flow. Forbidden substitutes are the legacy shared generic `add_months` wrapper as the substantive implementation, a renamed root, a standard date/time library, host-clock access, hard-coded examples, a policy-switch template, or another root's algorithm.

## Starter and reference

The task-named header exposes the full revised API and the task-named source is coherent but incomplete. `.meta/example.*` maps one-to-one by suffix and independently implements `{mechanism}`. It imports neither benchmark assets nor generated legacy reference code.

## Tests

Visible tests cover the normal domain transition and one public boundary. Private tests cover invalid civil dates, leap-century behavior, checked range, empty/singleton inputs, duplicates or absent IDs where applicable, equality, stable ordering, and atomic failure. A deterministic hard-rule test derives expected values through an independent ordinal or direct-enumeration oracle. The topic negative is `{negative}`; it must compile under strict reference flags and be rejected by executed tests. Coherent domain/identifier-renamed, constants/policy-only, and opposite-end-selection controls must remain buildable and pass their behavior tests while the production semantic evaluator rejects them in all seven dimensions.

## Files and metadata

Solutions are `<task-id>.h` and `<task-id>.cpp`; tests are `task_visible_test.cpp`, `.meta/task_hidden_test.cpp`, and `.meta/task_hard_rule_test.cpp`; references are `.meta/example.h` and `.meta/example.cpp`; the private negative is `.meta/negative_fixture.cpp`. Config, provenance, tests metadata, docs, CMake, controls, manifests, and receipts are non-editable and prompt-private. Reference mapping follows solution order. No external support bundle is required.

## Build/oracle

C++17 with strict warnings, explicit `Unix Makefiles`, and three positive CTest targets. Run clean normal and separate fresh ASan/UBSan builds in the pinned network-disabled repository C++ sanity image. The receipt binds live/archive/mounted tree hashes, owner/reference/negative hashes, image/compiler/CMake identities, commands, network policy, and equal normal/sanitizer counts for roots and coherent controls.

## Family/contamination

Compare the actual emitted docs, public API, required state/algorithm, mutation/selection rules, invalid/boundary behavior, reference control flow, deterministic oracle, and topic negative against every other counted root. The count must remain within the user-authorized `8-12` range; ten roots require 45 unordered pairs and every pair must differ in all seven dimensions. Screen every root against all 26 official C++ holdouts with a role-aware normalizer that removes identifiers, domain nouns, literals, and endpoint direction while preserving API arity, state shape, control flow, and assertions.

## Optional dataset handoff

`not_requested`. No JSONL, renderer, token/mask evidence, split, producer verification, export, consumer verification, training, release, or uplift claim is authorized.

## Acceptance

Run the focused pytest, owner `--verify-core`, owner host verifier for iteration, and owner `--docker-sanity`. Require exact regeneration, prompt/role/reference safety, ten roots, 45 independently inspected seven-dimension decisions, three nonempty coherent clone controls rejected by the production evaluator, ten compiled and executed topic-negative rejections, 260 holdout comparisons, and three equal positive normal/fresh-sanitizer tests for every root and control. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `hard_rule_pair_not_distinct`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def main() -> int:
    if not LEGACY.is_dir():
        raise SystemExit(f"missing legacy family: {LEGACY}")
    actual = {path.name for path in LEGACY.iterdir() if path.is_dir()}
    expected = {row[0] for row in CASES}
    if actual != expected:
        raise SystemExit(f"legacy inventory mismatch: {sorted(actual ^ expected)}")
    remedy_root = OUT / ".state/remedy"
    remedy_root.mkdir(parents=True, exist_ok=True)
    owner_revision = digest(OWNER.read_bytes())
    for task_id, objective, mechanism, negative in CASES:
        markdown = remedy_markdown(task_id, objective, mechanism, negative)
        markdown_path = remedy_root / f"{task_id}.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": task_id,
            "family_id_before": f"{FAMILY_BEFORE}/{task_id}",
            "family_id_after": f"{FAMILY_AFTER}/{task_id}",
            "tree_hash_before": tree_hash(LEGACY / task_id),
            "generator_path": str(OWNER),
            "generator_revision": owner_revision,
            "finding_ids": [
                "GCA-F1-shared-calendar-template",
                "GCA-F2-nondiscriminating-private-tests",
                "GCA-F3-missing-hard-rule-controls",
                "GCA-F4-missing-docker-receipt",
            ],
            "disposition": "repair-in-place",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(markdown_path),
            "remedy_spec_hash": digest(markdown.encode()),
            "selected_prompt": PROMPT,
            "user_inputs": {
                "FAMILY_NAME": "general-calendar-arithmetic",
                "FAMILY_TYPE": "aider-dates-and-clocks",
                "hard_rule_count": "8-12",
            },
            "primary_core_objective": "not_achieved",
            "status": "planned",
        }
        markdown_path.write_text(markdown, encoding="utf-8")
        (remedy_root / f"{task_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"planned {len(CASES)} remedies under {remedy_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
