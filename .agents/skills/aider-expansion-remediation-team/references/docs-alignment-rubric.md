# Docs-Alignment Rubric: generated `.docs` vs official Aider Polyglot C++ benchmark

Reference corpus (READ-ONLY, style reference only — never copy its text):
`.w8-biayn/data/polyglot-benchmark/cpp/exercises/practice/<task>/.docs/`

The benchmark is the permanent holdout. Align **format, register, and
completeness** — never wording, examples, or semantic contracts. After any
docs rewrite, the family's benchmark/cross-tree contamination screens must be
re-run and must still pass.

## What the official docs look like

- `introduction.md` (optional; some official tasks omit it): a `# <Title>`
  header followed by narrative motivation — a story, domain context, or
  intuition for why the problem exists. It never states the contract.
- `instructions.md`: starts with `# Instructions`. Concise behavioral task
  statement in plain declarative/second-person prose, with concrete worked
  examples (input → output) and, where needed, short tables or notes.
  Constraints are stated as natural task requirements ("without using the
  built-in sort function"), not as meta-commentary about the task itself.

## Violations to find in generated `.docs`

Severity: **major** = model-facing prompt materially off-distribution or
contract-wrong; **moderate** = missing element the benchmark would have;
**minor** = style.

1. **Meta/audit vocabulary (major).** Any of: "clean-room", "task" used
   self-referentially ("this task"), "SFT", "benchmark", "campaign",
   "remediation", "oracle", "negative fixture", "reference implementation",
   "generator", "adversarial", "hard rule", "forbidden substitute",
   "do not substitute", "grader", "hidden test", "local_family_verified",
   "prompt", "model". Official docs never talk about the evaluation harness.
2. **Placeholder introduction (moderate).** One-line non-introductions
   ("A clean-room C++17 temporal-boundary task.", "A deterministic modular
   normalization task."). Either write a real 1–3 paragraph domain-motivating
   introduction or, if the family prefers, match the official tasks that omit
   `introduction.md` — but be consistent within the family.
3. **Missing `# Instructions` header or wrong header (major).**
4. **Guardrail-framed constraints (major).** Contract limits phrased as
   anti-cheat scaffolding ("The required core mechanism is X. Do not
   substitute Y.") must be rephrased as natural requirements that teach the
   *why* ("Use Euclidean (floor) division: truncating division gives the
   wrong remainder for negative inputs"). The constraint itself MUST stay —
   hidden tests still enforce it.
5. **No worked example (moderate).** Every official task shows concrete
   input → output. Generated instructions must include at least one concrete
   worked example (values, not just types) unless the operation genuinely
   admits none.
6. **Contract incompleteness (blocker).** The rewrite must not drop any rule
   the hidden tests enforce: valid/invalid inputs, boundary values, error or
   empty results, ordering/tie rules, overflow policy. Removing a rule to
   sound nicer is a regression, not a fix.
7. **Leakage (blocker).** Docs must not contain reference code, hidden-test
   values beyond what the contract examples need, CMake/test file contents.
8. **Benchmark text reuse (blocker).** No sentence or example copied from the
   official corpus.
9. **Broken consistency (major).** Filenames, type names, and signatures in
   the docs must match the starter header and `.meta/config.json`.
10. **Length/register drift (minor).** Instructions should be in the same
    register and rough length class as official ones — not a 2-line stub, not
    a 5-page spec sheet.

## Fix rules

- Fix docs in the owning generator/case renderer templates; NEVER hand-edit
  generated `.docs`. Update the family's focused test (docs-shape assertions)
  and curriculum/spec in the same change.
- Regenerate through the owner, then rerun the owner's verify-core AND
  host-verify (docs changes change the tree hash; all receipts must rebind).
- Re-audit fresh after every regeneration; loop until an audit pass finds
  zero blocker/major/moderate docs findings.
