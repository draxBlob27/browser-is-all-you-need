# Circular Deque Curriculum: Distinct Logic and Implementations

Status: local curriculum-design note. This document does not claim dataset
admission, a release, training authorization, or benchmark uplift.

This curriculum contains exactly 15 roots, satisfying the requested 15–20
bound. Every root has different primary logic and implementation; names,
constants, end-selection flips, and policy toggles do not count as diversity.
The official Aider Polyglot C++ `circular-buffer` root is a permanent holdout.
Fixed-capacity FIFO read/write exercises, full-write policies, forced
overwrite, clear, and renamed semantic variants are excluded.

Use this with `docs/AIDER_SFT_SCOPE.md` and the selected remediation prompt
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`.

## Rejected legacy inventory

The 20 `cdeque-*` roots beneath
`.w8-biayn/data/aider-tasks/aider-dsa/circular-deque/` remain unchanged. They
are rejected because normalization reduces them to one bounded integer ring
template with renamed methods and three small policy toggles, and that contract
overlaps the holdout. Their dispositions are bound in the reverify family's
`.state/remedy/` directory.

## Clean-room replacement tasks

| ID | Primary logic | Required implementation |
|---|---|---|
| `deque-work-steal-scheduler` | asymmetric owner LIFO and thief FIFO removal with dynamic growth | owned optional-slot ring, wrapped head, logical-order doubling |
| `deque-window-extrema` | online min/max over the latest sample window | two monotonic index/value deques with expiry and dominance removal |
| `deque-zero-one-router` | shortest paths in a directed zero/one-toll graph | adjacency list plus deque-based 0-1 BFS front/back relaxation |
| `deque-center-sequence` | front/middle/back sequence updates | two balanced deque halves |
| `deque-prefix-expression` | checked prefix evaluation | recursive front-consuming token deque |
| `deque-run-segment-editor` | run-normalized end editing | maximal run deque with merge/split deletion |
| `deque-snake-arena` | grid-body movement and collision | body deque plus occupancy set |
| `deque-deficit-scheduler` | variable-cost fair scheduling | active flows, per-flow FIFOs, carried deficits |
| `deque-temporal-join` | greedy event-time pairing | two ordered stream deques with expiry |
| `deque-palindrome-fingerprint` | end edits and palindrome queries | reversible forward/reverse hashes |
| `deque-chunked-text` | bulk text edits | bounded nonempty string chunks |
| `deque-josephus-elimination` | directed circular elimination | live deque rotation and removal |
| `deque-lexicographic-end-picker` | minimal end-choice string | symmetric tie lookahead |
| `deque-card-war-cycle` | deck simulation | paired deques plus repeated-state detection |
| `deque-stable-radix` | stable integer sorting | per-digit deque buckets over LSD passes |

Sharing a name prefix or merely using a deque is insufficient. All 15 roots must
have a different public API, state model, failure behavior, algorithm,
reference shape, deterministic oracle, and negative fixture.

The executable hard-rule gate is artifact-derived: normalizer
`circular-deque-semantic-v4` compares normalized docs, public API, reference
source, and visible tests for all 105 pairs. It does not use task IDs, kind
labels, or raw source hashes as diversity evidence. The current strongest
family score is 0.417 against a 0.78 rejection threshold. All 15 roots are also
compared with the permanent holdout; the strongest score is 0.092 against a
0.72 threshold. Adversarial renamed-domain/identifier clones,
constant/policy-toggle clones, and opposite-end-selection clones must be
rejected by tests.

Hidden checks use root-specific deterministic examples, traces, brute-force
comparators, or independent oracles. Source-level fixtures remove a required
state/algorithm marker and inject that root's named false substitute. The owner
fails with `family_count_out_of_bounds`, `duplicate_family`, or
`invariant_not_enforced` rather than accepting a short or renamed family.

Every root needs complete visible C++17 behavior, a coherent starter,
independent private reference, visible and hidden tests, role-correct metadata,
prompt-boundary proof, normal and fresh sanitizer evidence when the designated
runtime exists, duplicate-family screening, and content-level holdout
screening. Dataset handoff is not requested.
