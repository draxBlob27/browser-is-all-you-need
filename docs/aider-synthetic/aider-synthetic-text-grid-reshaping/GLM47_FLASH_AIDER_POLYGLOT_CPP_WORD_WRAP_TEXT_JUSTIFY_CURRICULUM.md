# Word Wrap And Text Justification Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops tokenization, width-constrained reflow, gap
distribution, paragraph preservation, and declared byte-layout policies.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official Aider holdouts are excluded. Do not paraphrase a holdout or online
formatter. Each candidate must use domain records, a result beyond plain text,
and distinct normalization, overlong-token, and final-line policies.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `justify-shipping-labels` | Shipping labels | Reflow addresses and report overflow parcels. |
| `justify-weather-bulletin` | Weather bulletin | Justify notices while preserving station headers. |
| `justify-museum-plaques` | Museum plaques | Fit exhibit text while protecting artifact identifiers. |
| `justify-medication-leaflet` | Medication leaflet | Wrap dosage paragraphs and retain warning indents. |
| `justify-rail-platform-board` | Rail platform board | Reflow delay messages with fixed route prefixes. |
| `justify-field-notebook` | Field notebook | Format observations while preserving timestamps. |
| `justify-legal-notice` | Legal notice | Distribute spaces in numbered clauses. |
| `justify-radio-script` | Radio script | Wrap spoken cues and calculate reading duration. |
| `justify-recipe-cards` | Recipe cards | Reflow instructions while keeping quantities intact. |
| `justify-helpdesk-replies` | Helpdesk replies | Format replies with quoted lines verbatim. |
| `justify-school-newsletter` | School newsletter | Justify articles and preserve headings/bylines. |
| `justify-safety-posters` | Safety posters | Fit steps in panels with mandatory emphasis words. |
| `justify-aviation-brief` | Aviation brief | Reflow notices with indivisible code groups. |
| `justify-game-dialogue` | Game dialogue | Wrap dialogue boxes and report overflow speakers. |
| `justify-invoice-notes` | Invoice notes | Align narrative notes beneath invoice metadata. |
| `justify-library-notices` | Library notices | Reflow overdue notices while retaining dates. |
| `justify-assembly-agenda` | Assembly agenda | Format items with hanging indents. |
| `justify-emergency-protocol` | Emergency protocol | Wrap explanations without splitting step IDs. |
| `justify-garden-catalog` | Garden catalog | Fit descriptions into columns preserving botanical names. |
| `justify-expedition-log` | Expedition log | Reflow entries and calculate line counts. |

## Materialization Requirements

Use ASCII or an explicit byte-width model. Hidden tests cover empty input,
multiple spaces, paragraph breaks, exact-width/one-word lines, overlong-token
policy, gap remainders, final lines, protected spans, and a line-width oracle.

## Admission Boundary

Every candidate needs original C++17 assets, provenance, normal/sanitizer
proof, contamination/family checks, and primary-pipeline release verification.
