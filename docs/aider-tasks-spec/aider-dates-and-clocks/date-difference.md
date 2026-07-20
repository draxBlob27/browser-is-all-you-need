# Date-Difference Family Remediation and Audit

## Scope and immutable inputs

This report implements
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with:

```text
FAMILY_NAME=date-difference
FAMILY_TYPE=aider-text-grid-reshaping
hard family size=8-12
```

The supplied legacy path
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/date-difference` did not
exist. The discovered generated family is preserved unchanged at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/date-difference`; all fresh
artifacts use the supplied type at
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/date-difference`.
This taxonomy mismatch is a recorded audit finding, not permission to move or
rewrite legacy evidence.

Owner paths are:

- curriculum:
  `docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATE_DIFFERENCE_CURRICULUM.md`;
- generator:
  `src/w8_biayn/integrations/moonlight_date_difference_aider_tasks.py`;
- focused tests: `tests/test_moonlight_date_difference_aider_tasks.py`;
- wrapper:
  `examples/slime/moonlight_cpp_perf/prepare_date_difference_aider_tasks.sh`.

The family ends at `local_family_verified`. Dataset rows, masks, splits,
exports, consumer verification, training, and uplift are not requested.

## Legacy audit findings

The five legacy roots had internally mapped prompt/reference roles and distinct
domain APIs, but their prior host-oriented verification did not bind a locked
or repository-pinned Docker runtime, complete all-pairs seven-dimension hard
rule, coherent adversarial controls, or the requested 8–12 family size. They
also shared one generic date-helper template without recorded per-dimension
family evidence. That makes their prior local proof stale for this workflow;
it does not make the preserved bytes invalid historical evidence.

| Finding | Severity | Root cause | Remedy | Acceptance |
| --- | --- | --- | --- | --- |
| `DATE-FAMILY-COUNT` | blocker | Five roots are below the authorized minimum of eight. | Retain the five surviving capabilities and add three different mechanisms. | Exact owner inventory is eight. |
| `DATE-HARD-RULE` | major | No complete 10-pair seven-dimension legacy decision matrix or coherent clone controls. | Recompute all 28 fresh-family pairs from emitted artifacts and reject three required control classes. | Every pair passes all seven dimensions; all controls fail as duplicates. |
| `DATE-ORACLE-REVERIFY` | blocker | Earlier evidence does not bind the final owner/tree and mandatory Docker runtime. | Fresh network-disabled normal and ASan/UBSan builds of every reference, negative, and control. | Positive equal count three in both modes; negative exit 1; mounted hashes match. |
| `DATE-TAXONOMY-MISMATCH` | moderate | Supplied family type and discovered legacy location differ. | Preserve actual legacy input, honor supplied reverify destination, bind both paths in provenance/remedies. | Structural test and audit identify both exact paths. |

## Root inventory and dispositions

| Legacy/final root | Disposition | Primary core objective | Topic-specific negative |
| --- | --- | --- | --- |
| `dated-warranty-audit` | repair-in-place | Ordered per-claim classification with inclusive coverage threshold and duplicate-ID state. | Treat the first expired day as covered. |
| `dated-project-burnup` | repair-in-place | Weekday/holiday exclusion over `(start,end]` with duplicate holiday validation. | Count weekend dates as workdays. |
| `dated-library-loan` | repair-in-place | Closure-adjusted overdue count plus tiered integer fee calculation. | Charge closure dates as overdue. |
| `dated-experiment-window` | repair-in-place | Canonicalized half-open interval union and subtraction with ordered residual spans. | Ignore every blackout interval. |
| `dated-retention-review` | repair-in-place | Policy-category join and equality-sensitive active/review/expired classification. | Delay expiry past its equality boundary. |
| absent / `dated-maintenance-ledger` | replace/backfill | Keyed per-asset chronological state and maximum consecutive service gap. | Reuse the first asset's state for interleaved assets. |
| absent / `dated-subscription-proration` | replace/backfill | Change-point sweep allocating a half-open window across integer rate bands. | Select a future band before its effective date. |
| absent / `dated-custody-chain` | replace/backfill | Sequential transfer validation with per-handler duration and strict limit classification. | Treat equality with the holding limit as a breach. |

The three backfills are replacements for missing semantically diverse family
capacity, not renamed copies of rejected roots. Each generated root has an
`aider-task-remedy-v1` JSON record and a twelve-section Markdown specification
under the fresh sibling `.state/remedy/` directory. Those records bind the
pre-change legacy hash (or `sha256:absent` for a backfill), owner revision,
disposition, selected prompt, user inputs, after hash, screens, and receipt.

## Public contracts and primary mechanisms

All roots use C++17 in namespace `curriculum`, declare exactly one editable
task-ID header/source pair, and expose structured domain records and typed
diagnostics rather than a bare date-difference helper. Dates are deterministic
proleptic Gregorian values with year at least one. The reference owns its
substantive collection or transition mechanism:

- ordered diagnostic traversal and duplicate set for warranty claims;
- day sweep plus holiday membership for project burn-up;
- relation validation, closure set, and tiered fee accumulation for loans;
- clipping, sorting, merging, and interval difference for experiments;
- category-policy map and threshold classification for retention;
- per-key mutable last/largest/count state for maintenance;
- ordered change-point band sweep for proration; and
- consecutive transition construction plus limit classification for custody.

Host clock/calendar APIs, fixed-year/month approximations, constant answers,
precomputed cases, a generic renamed wrapper, and exposed `days_between` APIs
are forbidden. Incidental vectors, maps, and sets support the stated domain
algorithms; they are not substitutes for a claimed custom data structure.

## Prompt, roles, and reference mapping

For root `<id>`, model-visible material is `.docs/*.md`, `<id>.h`, and
`<id>.cpp`; only the latter two are editable in header/source order. Hidden
material includes `.meta/config.json`, provenance, tests metadata,
`.meta/example.*`, `.meta/task_hidden_test.cpp`, `.meta/negative.cpp`,
`CMakeLists.txt`, screens, receipts, and remedies. The two examples map by
suffix and order to the two editable files. The focused test renders the exact
whole-file reference answer and rejects oracle/build paths in the prompt.

## Seven-dimension hard rule

The count gate is 8–12; the owner emits exactly 8, so the complete unordered
comparison count is `8 * 7 / 2 = 28`.
`date-difference-artifact-materiality-v2` derives counted structural n-grams,
operation/cardinality features, boundary-rule features, control-flow features,
oracle-shape features, and reference-to-negative semantic deltas separately
from emitted public API, reference, instructions, visible/private tests, and
negative fixture. Identifiers, literals, the shared Gregorian helper, and
clean-room domain nouns are removed. A dimension passes only when its Jaccard
overlap is below that dimension's fixed threshold and its symmetric feature
difference reaches the fixed minimum. A pair passes only if every dimension
passes independently:

1. public API;
2. owned state or algorithm;
3. mutation/selection rules;
4. invalid/boundary behavior;
5. reference control flow;
6. deterministic oracle; and
7. topic-specific negative fixture.

The frozen `(maximum Jaccard overlap, minimum symmetric difference)` gates are:
public API `(0.75, 6)`, owned state/algorithm `(0.65, 12)`,
mutation/selection `(0.70, 8)`, invalid/boundary behavior `(0.50, 6)`,
reference control flow `(0.65, 12)`, deterministic oracle `(0.80, 10)`, and
topic-specific negative `(0.40, 2)`. Equality with an overlap threshold fails.

The production evaluator materializes three coherent controls from
`dated-warranty-audit`: domain/identifier rename, coverage-constant/policy
change, and reversed elapsed-date endpoint selection. Every control must change
nonempty emitted files, preserve role mapping, compile and pass its own normal
and sanitizer reference tests, retain an executing negative rejection, and be
rejected by the exact conjunctive evaluator. Focused tests independently
recompute every persisted overlap/difference decision without calling the
production feature helper, and separately require seven distinct, emitted-file
semantic witnesses for each of the eight roots.

## Invalidated first proof

The initial eight-root receipt and audit were withdrawn after re-audit because
they equated unequal normalized hashes with material difference, reused the
production feature helper in the focused assertion, and used one generic
zero-serial negative across all roots. The owner preserves those files and the
reason under
`.state/invalidated/hard-rule-fingerprint-overclaim-v1/`; no retained remedy
record may cite them as current evidence.

## Benchmark contamination

The bound checkout at `.cache/upstreams/aider-polyglot` supplies all 26 official
C++ roots. The owner compares every candidate with every holdout over normalized
docs/API/source/tests (`8 * 26 = 208` comparisons), in addition to whole-slug
screening. `clock`, `gigasecond`, and `meetup` are specifically permanent
holdouts. Any inventory gap is `not_completed`; any threshold match is
`benchmark_content_overlap` and requires rejection, never a waiver.

## Oracle and receipt contract

The repository-pinned fallback image is
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`; this is
`docker_sanity`, not a family-designated locked oracle. Docker runs with
`--network none`, mounts a deterministic archive, recomputes each mounted tree
hash independently, records the immutable image ID and compiler/CMake identity,
and uses explicit `Unix Makefiles`. Every root and coherent control receives a
clean normal build and a separate fresh `-fsanitize=address,undefined`
build. Each mode must discover exactly three CTest entries: visible, hidden,
and a `WILL_FAIL` negative. Direct negative execution must exit 1.

The receipt is accepted only when owner, tree, reference, mounted-tree, image,
network, task/control inventory, equal positive counts, and negative outcomes
all match the live final revision. Any owner or artifact-affecting edit
invalidates it and returns every record to `pending_execution`.

## Commands and evidence

```bash
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_date_difference_aider_tasks --force --verify-core
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_date_difference_aider_tasks --force --docker-sanity
uv run pytest -q tests/test_moonlight_date_difference_aider_tasks.py
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

Generated evidence lives under the fresh root's `.state/` directory:
`family-screen.json`, `docker-sanity.json`, `audit.json`, and per-root remedy
records. The strongest status is truthful only when those final-tree files say
`local_family_verified`; absent Docker access or image leaves the family at
`pending_execution` / `not_completed`.
