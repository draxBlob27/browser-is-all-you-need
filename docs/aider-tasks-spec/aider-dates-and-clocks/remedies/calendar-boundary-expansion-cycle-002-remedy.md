# Calendar Boundary Expansion Cycle 002 Remedy Record

Status: owner changes implemented; regenerated evidence and fresh independent
cycle-003 audit pending.

This record responds to the immutable cycle-002 subject
`sha256:65f5b236a8318ec356901aed46b4b12e0c412d9c2ae42c73ef8e34e6e9e665e5`
and independent report digest
`sha256:0b8eeca4fce067189f692c550e456c86a03fa8470ae0aa9c3aa6d51513a2eec9`.
The cycle-001 and cycle-002 reports remain unchanged.

| Finding | Disposition | Owner-level remedy | Closure gate |
| --- | --- | --- | --- |
| `CAL-C02-001` | repair | Represent invalid constrained-series parameters as `None` in the Python oracle, preserve C++ `std::nullopt`, state the policy in every series prompt, and assert invalid lower/upper parameters. | Fresh normal and sanitizer tests reject invalid parameters for all three affected roots. |
| `CAL-C02-002` | repair | Add signed year deltas in `long long`, range-check before narrowing, and probe `INT_MIN` and `INT_MAX` in generated tests and behavior signatures. | Fresh UBSan and independent extreme-parameter probes find no signed overflow. |
| `CAL-C02-003` | repair | Archive the complete prior ledger, delete only the active receipt directory during forced owner regeneration, recreate exactly one schema-2 receipt per selected root, and fail preflight unless receipt IDs equal selected IDs. | Active receipt set is exactly the 90 selected roots and archived evidence remains append-only. |
| `CAL-C02-004` | repair | Emit the February terminal for both common and leap century checkpoints in the C++ and Python oracles, with exact 1900 and 2000 element assertions. | Prompt and both oracles agree on 1900-02-28 and 2000-02-29. |
| `CAL-C02-005` | repair | Replace four stale integer-encoding notes with date-valued endpoint and midpoint/tie rules. | Fresh prompt audit finds no contradictory length, allocation, run-encoding, or gap-encoding prose. |
| `CAL-C01-004` | continue repair | Extend executable coverage with invalid series parameters, integer extremes, and explicit century checkpoint values. | Fresh audit closes all missing-oracle counterexamples. |
| `CAL-C01-007` | continue repair | Make invalid series parameter behavior explicit and remove every stale replacement note. | Fresh audit finds all 90 public contracts internally consistent. |

All task bytes remain generator-owned. The complete 90-root family must be
regenerated and all diversity, lineage, holdout, Docker normal/sanitizer, and
fresh independent audit gates rerun. No dataset release, split, token/mask,
training, or uplift claim is part of this remedy.
