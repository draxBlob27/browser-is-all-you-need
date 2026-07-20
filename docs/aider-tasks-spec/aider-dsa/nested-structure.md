# Nested Structure V2 Reverification Audit

## Scope

This report accounts for every root in the legacy `aider-dsa/nested-structure`
family and the generator-owned v2 replacements. The selected workflow is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with user inputs
`FAMILY_NAME=nested-structure` and `FAMILY_TYPE=aider-dsa`. The legacy tree was
not modified. The terminal claim is local-family verification only; dataset
handoff is `not_requested`.

## Audit finding

### NS-F1-TEMPLATE-DUPLICATE — one renamed scanner across every legacy root

**Severity:** major

**Scope:** all 20 legacy roots

**Observed evidence:** the legacy owner generated every reference through one
`_reference` function. The only per-root inputs were class/method/noun plus an
opening and closing token. Every public and private test used the same valid,
escaped, quoted, orphan, unclosed, repeated, and depth traces.

**Why it matters:** the references did not implement the advertised config,
tag, fence, query, expression, link, comment, JSON streaming, regex, binary
frame, formula, indentation, clause, diagram, policy, or build-directive
contracts. Renaming the common delimiter scan supplied no independent learning
value.

**Root cause:** the original materializer treated curriculum nouns as token
parameters instead of implementation contracts.

**Remedy:** `replace` every legacy root. The v2 owner uses 20 hand-authored
APIs and 20 different state/algorithm implementations. Each replacement has a
named executed negative fixture for its easiest false substitute.

**Verification after remedy:** `--verify-core` validates generator equality,
prompt/roles, reference mapping, normalized family uniqueness, and all 26
bound C++ holdouts. `--verify` runs each reference and negative fixture in the
locked network-disabled image.

**Status:** resolved and reverified

## Commands and exact outcomes

```text
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q \
  tests/test_moonlight_nested_structure_aider_tasks.py \
  tests/test_aider_sft_scope_docs.py
# 10 passed

PYTHONPATH=src python3 -m \
  w8_biayn.integrations.moonlight_nested_structure_aider_tasks \
  --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/nested-structure \
  --force --verify-core
# wrote 20 roots; all core screens passed

W8_NESTED_STRUCTURE_GRADER_IMAGE=sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991 \
PYTHONPATH=src python3 -m \
  w8_biayn.integrations.moonlight_nested_structure_aider_tasks \
  --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/nested-structure \
  --force --verify-core --verify
# 20/20 roots passed normal and fresh sanitizer verification
```

The locked runtime was immutable image
`sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
network `none`, GCC 13.4.0, and CMake 3.25.1. Each root discovered and passed
two normal tests and two fresh ASan/UBSan tests. Each named negative source
compiled, executed, and failed the same test suite. Owner and mount hashes
matched before receipts were accepted.

The `aider-cleanroom-family-v2` normalized five-gram screen compared docs,
APIs, references, and tests for every candidate pair, all 26 bound official C++
holdouts, and the separately excluded Exercism `matching-brackets` source. The
strongest candidate-pair similarity was `0.312076` (below the `0.72` rejection
threshold); the strongest external-source similarity remained below `0.55`.
Whole-slug screening also passed.

## Per-root disposition and evidence

| Legacy root | Replacement | Distinct primary mechanism | Legacy tree hash | V2 tree hash | Disposition/status |
| --- | --- | --- | --- | --- | --- |
| nest-access-policies | nest-access-policies-v2 | inherited policy-event interpreter | cdb70286663f564a | 0aedf8d0b0bc7145 | replace / local_family_verified |
| nest-build-directives | nest-build-directives-v2 | conditional frame evaluator | 12519e8babe25974 | 408788aee999d9f7 | replace / local_family_verified |
| nest-chat-quotes | nest-chat-quotes-v2 | quote-depth/fence line machine | a64b69ce56cb2f60 | c5db75ac45822318 | replace / local_family_verified |
| nest-code-fences | nest-code-fences-v2 | marker-length/language block extractor | 08de97d7eb95a5a3 | 529c7198a4fb1e7d | replace / local_family_verified |
| nest-command-blocks | nest-command-blocks-v2 | labeled transaction events | 460bc486848ff2ac | 416090d1b3e5694a | replace / local_family_verified |
| nest-config-sections | nest-config-sections-v2 | per-path key record parser | 9eacd1f5789004cd | a005733e5024bd1e | replace / local_family_verified |
| nest-diagram-groups | nest-diagram-groups-v2 | current-ancestor reference resolver | 83708dcc6d1968ac | 71071987fd147ec7 | replace / local_family_verified |
| nest-json-stream | nest-json-stream-v2 | persistent incremental JSON lexical state | f62a3b28d2734cb9 | c886bd474accdc5f | replace / local_family_verified |
| nest-legal-clauses | nest-legal-clauses-v2 | numeric parent/sibling automaton | bc74cc60c7f0eb7b | 3c66b403b40f5773 | replace / local_family_verified |
| nest-markdown-links | nest-markdown-links-v2 | escaped nested-destination span scanner | fec1dda1d2494799 | 174346be9bfee4d7 | replace / local_family_verified |
| nest-math-expressions | nest-math-expressions-v2 | lexer, shunting yard, checked evaluator | 76a78582eed478e0 | a540b4436b960866 | replace / local_family_verified |
| nest-protocol-frames | nest-protocol-frames-v2 | binary TLV boundary decoder | f85c81850101a085 | 2d90e1d8257b7050 | replace / local_family_verified |
| nest-query-groups | nest-query-groups-v2 | boolean unary/binary precedence parser | 2faed5663c3831b0 | 9ac2769ab50402fb | replace / local_family_verified |
| nest-recipe-steps | nest-recipe-steps-v2 | indentation lifecycle/path parser | 1fb89ed420627978 | 46009439c6595c0b | replace / local_family_verified |
| nest-regex-groups | nest-regex-groups-v2 | escape/class-aware group classifier | b367153a31bd0e1d | db39b6a8dcbe701d | replace / local_family_verified |
| nest-rich-text-tags | nest-rich-text-tags-v2 | tag/quoted-attribute coordinate lexer | a552ce7edb66baf4 | d0fe6aecb96429ea | replace / local_family_verified |
| nest-script-comments | nest-script-comments-v2 | position-preserving nested comment machine | 6728cb18f27900d1 | e1ba711563354fd3 | replace / local_family_verified |
| nest-spreadsheet-formulas | nest-spreadsheet-formulas-v2 | locale-specific call/arity frames | 70f2a32941ed06bf | 5171f4bea9e7cf92 | replace / local_family_verified |
| nest-template-placeholders | nest-template-placeholders-v2 | parent-linked placeholder/span parser | 863af9edcc80f4e2 | 491159f8fc768490 | replace / local_family_verified |
| nest-workflow-scopes | nest-workflow-scopes-v2 | parent/task lifecycle interpreter | b8917e0cf3096caa | 6aac32e1b39ef918 | replace / local_family_verified |

Full `sha256:` before/after hashes, remedy-spec hashes, prompt hashes, runtime
identity, commands, test counts, and screening results are retained in the 20
`.state/remedy` records, `.state/materialization-manifest.json`, and
`.state/oracle-receipt.json` beneath the reverify family root.

## Changed owner paths and conclusion

The changed owner surfaces are the nested-structure curriculum, generator,
hand-authored case module, focused regression test, preparation wrapper, this
audit, and the materialization guide. Generated v2 output was regenerated only
through that owner; the legacy output was reused only as immutable audit input.

Primary core objective: **achieved** for every v2 root. Structural validity,
prompt boundaries, locked oracle proof, executed negative fixtures, family
independence, and benchmark separation all pass. Therefore every replacement
reached **`local_family_verified`**. No SFT admission, release, training, or
benchmark-uplift claim is made.
