# Text Justification Family Remediation Audit

## Scope

Review date: 2026-07-18. Selected workflow:
docs/aider-tasks-spec/prompts/remediate-family-reverify.md with
FAMILY_NAME=text-justification and FAMILY_TYPE=aider-text-grid-reshaping.
The immutable input is
.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/text-justification/.
The owner-generated replacement is
.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/text-justification/.
Dataset handoff is not_requested.

The audit covered all 20 legacy roots and every visible document, editable
starter, reference, visible/private test, role declaration, provenance record,
and build recipe. The legacy tree was not modified.

## Current re-verification status

The earlier `local_family_verified` claim and schema-v1 Docker receipt were
invalidated after the hard-rule re-audit found only six recorded dimensions,
text-only controls, circular focused assertions, and no Docker control proof.
The owner-controlled invalidation ledger preserves those withdrawn evidence
hashes under `.state/evidence-invalidations.json`. The replacement
seven-dimension screen and schema-v2 Docker receipt now pass for the final tree,
so the strongest status is `local_family_verified`.

## Findings

### TJ-F1 — one semantic template under twenty domain names

Severity: major. Scope: all 20 legacy roots. Every root used the same
header/paragraph/protected-line state, whitespace tokenizer, greedy wrap,
gap distribution, overflow ledger, tests, and reference control flow. Nineteen
roots differed only through nouns and two final-line policy values. This is a
family-wide semantic duplicate, so nineteen dispositions are replace.

### TJ-F2 — advertised objectives were not implemented

Severity: major. Scope: all roots except the independently salvageable
justify-assembly-agenda objective. Curriculum claims such as duration-limited
cues, column balancing, page allocation, quote-depth parsing, hyphenation, and
tab stops were absent from the generated references and tests. The replacement
owner now implements and tests each named mechanism. The agenda root retains
its ID at task-spec revision 2 and implements measured hanging indentation.

### TJ-F3 — no executed topic-specific negative evidence

Severity: major. Scope: all legacy roots. The legacy tests could not
distinguish the advertised mechanisms from the shared formatter. Every v2 root
now has a compiling false substitute. The pinned Docker verifier builds it
under the same strict flags and requires at least one of two executed CTests to
reject it in both normal and sanitizer modes.

### TJ-F4 — legacy oracle evidence was not image-bound

Severity: moderate. Scope: all legacy roots. Host-only normal/sanitizer checks
did not bind the pinned image, mounted tree, compiler binary, or network policy.
The v2 receipt binds all of those identities and independently recomputes every
mounted task-tree hash.

All four findings are resolved and reverified for the v2 roots.

## Per-root disposition and hashes

| Legacy root | v2 root | Disposition | Before tree hash | After tree hash | Status |
| --- | --- | --- | --- | --- | --- |
| justify-assembly-agenda | justify-assembly-agenda | repair-in-place | sha256:6664de4a5e94eba1ca9137ec0bda89e12c9a6a8e8c2accf12fb427c4e4211587 | sha256:b0e0edca48c167280c269be974439c14ba729d9ffa7e64698b7656ff795159b5 | local_family_verified |
| justify-aviation-brief | segment-flight-telex | replace | sha256:402dedd58a596a0a11a0df7d407abdde0c3ebc97243670e60ee47a581cc96554 | sha256:4ffbf9b7ff61227536b67586be3312bcc0328a7d4fcf4b7b253949ade06843d7 | local_family_verified |
| justify-emergency-protocol | layout-protocol-steps | replace | sha256:ce518b108fa0e56d5e700dbf3ed862888d7bf0ec9bf543187be2f9c701e7e660 | sha256:b980a5e1d899b31f29daacb48055a9df5009fd9decca19057bcdcc344050251c | local_family_verified |
| justify-expedition-log | paginate-expedition-ledger | replace | sha256:6466b99e0b5fe5903e4e6e8a141e19b1cd168097f36e6e9de56ac7778fdf98b4 | sha256:e41df65f66ecb816f5d08e8208a2a6eb93a2afdd8d8f4db8d20ba3576f5dbb76 | local_family_verified |
| justify-field-notebook | align-field-observations | replace | sha256:62a03e301c4e73bc8871bfaebd7740e0432dcaeba3591120cf2b2cf633ba59ee | sha256:72bb235df0cde8151663df866d96b295716cbcf2be780607e4a73a2638d223c1 | local_family_verified |
| justify-game-dialogue | paginate-dialogue-boxes | replace | sha256:ab6cee9a8e90a04f4d786a582575b145263e7bff394b450df69dc1a84ede65a7 | sha256:f9a22384cee3c5238875fc7b71cb94d0325567b088adf6d7b734fce23455f4e7 | local_family_verified |
| justify-garden-catalog | balance-catalog-columns | replace | sha256:c2598d1d04c899ecc3760762e9195232bebfdbcfc6d9c39afa45d2ed1ff3bdec | sha256:a65d40b4d7746f826ffad10065deff47e9e5a1bc7d0687d427f22337d52d8ccd | local_family_verified |
| justify-helpdesk-replies | reflow-nested-quotes | replace | sha256:9c5ff71ee64212b448aad713e484c12630d54ee8db9d28f0b7b646e26dba630a | sha256:def4c068420b1e98fd087dc365181ad73c2efff60f918ae91775693b9b0bac38 | local_family_verified |
| justify-invoice-notes | align-invoice-tabstops | replace | sha256:e018dc68ea9c09587b006fa49c95b0462441d1a954a6eac4826b603cc910cfa8 | sha256:030d3d60518c897b87336b25fa0f60ab44d65aa7063eb93f37b765ffb7171bf1 | local_family_verified |
| justify-legal-notice | break-clauses-by-penalty | replace | sha256:74601cc733329f63a21aef9d7efc07d5152cbfc384f2eb3e37ba615c8adb7144 | sha256:0ae838e42f61f44aa932c1e2ab4bf5ad0fab761265586b4544d6887762e48365 | local_family_verified |
| justify-library-notices | prevent-notice-widows | replace | sha256:48393d6d6ae3e3b5c43600977e8bc79da20e40d1065bc775fb42c95ece5c607d | sha256:f8a42e8bbf9b6f0f2e20042bf2cb7d88cafbd9a5e9de24e4b033655e54217ae6 | local_family_verified |
| justify-medication-leaflet | wrap-dosage-hyphenation | replace | sha256:2fbc7fd2427a4141d59d89a47b0d8a6ec7c945245864db6eff80c8c5abe120e7 | sha256:ec0ffb80f949f81a02b9f95911e165061b18f63eb7683295963d4e82b4336b35 | local_family_verified |
| justify-museum-plaques | center-plaque-lines | replace | sha256:0db22a5d1199bf14af8acafd63b2b7cb1104f2af57b8f56352896154fb4d7185 | sha256:9a095ff1110334caaa50c3218570276aa272560c453c037dd7474c7a8ca198bb | local_family_verified |
| justify-radio-script | segment-radio-cues | replace | sha256:50b757ed90ad59f7df3865691b8702c94f72809342a32758b2058fa0edf0de8b | sha256:df53feb8c341729c7fa3a2a03d7f898db0457a81cf1a24492a587173c09a5ecc | local_family_verified |
| justify-rail-platform-board | scroll-platform-pages | replace | sha256:b2d29821a706de0bdbdf85e655d471abce77d93236eaeb650bd26629674262b0 | sha256:1acf55ee44fc6a05bef3cc0d20021adf3db12357d10fcde8eedcf4bbccf9ea9f | local_family_verified |
| justify-recipe-cards | wrap-recipe-quantities | replace | sha256:03bbc15a17eb41caf1669d93a9349116afa294bf3c04a8ac73ea21cd3e38bbd7 | sha256:c7fd159b1f222028450fe9549f72585e4d0ff4dbd7de5479b627e6f02f645312 | local_family_verified |
| justify-safety-posters | fit-poster-font-scale | replace | sha256:4a8684bffaa8003bce4ee5efa1d1ff68c23ed68ebfa9f9dd0ce264a270a33be6 | sha256:c1e87ce86b4ac34373769108fe74eca07daa58ddc2910b7f1b59c22f0943721d | local_family_verified |
| justify-school-newsletter | balance-newsletter-columns | replace | sha256:a8d36535ba9d4140a4cf13e977ecb805081a26e7999ed7c437fe78adec8f1673 | sha256:f07a5a0b11df34d3471bfccda197cc42b291599ffb01b34896eb6c48da83c83a | local_family_verified |
| justify-shipping-labels | pack-address-lines | replace | sha256:7706feb07d5b790caddb4780d79c4335058619e589d179c048b09f8a94799b06 | sha256:5ad491db64c93d6b421083ade3193dab79a7e1ee4f942fc84526aef43d7db78f | local_family_verified |
| justify-weather-bulletin | merge-bulletin-regions | replace | sha256:c5fbc4c689cc5e516963463226f5ba1af2de9423c8446b0c7b238c5282fa6af5 | sha256:abaff5b898aa9bab341f07d13ffdf6990eee6558b5309911682fd4ed85870b6f | local_family_verified |

## Structural and semantic verification

The regenerated manifest records prompt_boundary=pass, reference_mapping=pass,
and 190 of 190 unordered hard-rule comparisons. Every pair must pass
conjunctively and separately over the exact seven dimensions: public API, owned
state or algorithm, mutation or selection rules, invalid and boundary behavior,
reference control flow, deterministic oracle, and topic-specific negative
fixture. Evidence is read from the emitted docs, API, reference, visible/private
tests, and negative source using text-layout-control-flow-v2.

The owner materializes three complete controls from the emitted agenda root:
a domain/API/identifier rename with consistent filenames, a width-policy change
with matching docs/reference/negative/private test, and reverse-end selection
with matching docs/reference/visible/private tests. All change their intended
files, remain structurally coherent, and are rejected by the exact pair
evaluator. Independent focused assertions recompute every pair and control
decision. All three controls passed normal and fresh sanitizer builds with two
tests in each mode, while their false substitutes compiled and were rejected.
The bound semantic holdout inventory contains exactly 26 official C++ roots and
passed all 520 candidate/holdout comparisons.

Primary core objective: achieved for every v2 root. Evidence is the
task-specific reference control flow and the compiled/executed negative
substitute recorded in the owner-generated manifest and Docker receipt.

## Oracle receipt

The final owner command completed successfully:

    PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_word_wrap_text_justify_aider_tasks --force --docker-sanity

Receipt:
.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/text-justification/.state/docker-sanity.json

The prior schema-v1 receipt remains invalidated and cannot prove the current
tree. The replacement evidence records:

- schema: text-justification-docker-sanity-v2
- evidence class: docker_sanity; locked_oracle: false
- network policy: none
- image ID: sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991
- compiler: g++ (GCC) 13.4.0
- compiler binary hash: sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663
- CMake: 3.25.1
- deterministic archive hash: sha256:b219f65132c8efba6a7c6501b022dfaf39c0d5457d326e7e6f373c716d685ef9
- owner hash: sha256:484d966ee7cb520f7c3513fba9c6a96c31c27e38eefc493791d98237748a61b0
- case inventory hash: sha256:c0793b426c4a17e74d4794b127aee86c61bd49f830d0ca80e66afc5b21ba11fc
- verified subjects: 20 task roots plus three coherent controls
- receipt rows: 40 task rows plus six control rows
- reference discoveries: two normal and two fresh sanitizer tests per subject
- negative evidence: 23 substitutes compiled and were rejected in both modes
- mounted hashes: all 23 independently matched the live owner hashes

## Changed owner paths

- docs/aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_WORD_WRAP_TEXT_JUSTIFY_CURRICULUM.md
- docs/aider-tasks-spec/aider-text-grid-reshaping/text-justification.md
- docs/AIDER_TASK_MATERIALIZATION_GUIDE.md
- src/w8_biayn/integrations/moonlight_word_wrap_text_justify_aider_tasks.py
- src/w8_biayn/integrations/moonlight_text_justification_cases.py
- tests/test_moonlight_text_justification_aider_tasks.py
- examples/slime/moonlight_cpp_perf/prepare_text_justification_aider_tasks.sh

## Conclusion

All 20 v2 roots reached `local_family_verified`. This workflow creates no JSONL
rows, token or mask evidence, split, export, training authorization, dataset
release, official benchmark score, or uplift claim.
