# Epoch, Age, And Overflow Boundaries — Independent Audit Cycle 006

Audit date: 2026-07-22

Status: `local_family_verified`

Decision: **80 of 80 roots are retained as verified candidates**. All 80 roots have disposition `train`. The exact cycle-006 tree passes the recorded structural, diversity, live-inventory, holdout, strict Docker, negative-discriminator, and focused-test gates. AEO-C05-F001 is closed.

## Confirmed Counts, Risk, And Next Gate

- Materialized roots: 80 unique selected IDs, balanced 20/20/20/20 across the four curriculum groups.
- Recorded Docker executions: 80 normal references, 80 nonrecovering ASan/UBSan references, 80 compiling rejected negatives, and three controls in both normal and sanitizer modes, with two discovered tests per execution.
- Independently recomputed diversity outcomes: all 3,160 pairs pass all seven required dimensions, for 22,120 passing dimension records.
- Live bound inventories: 731 legacy roots, 709 reverify roots, 1,585 sibling expansion roots, and 26 holdouts. Independently recomputed counts, entries, and hashes match the family screen.
- Focused tests: 6 passed.
- Verified retained roots: 80. Zero family-wide hard-gate findings remain open.
- Next gate: the exact verified subject tree may be considered for SFT release authorization.

No SFT projection, dataset release, tokenizer/mask claim, split, training authorization, or benchmark-uplift claim follows from this report.

## Frozen Audit Subject

- Family root: `.w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/epoch-age-overflow-boundaries/`
- Retained-task tree SHA-256, excluding `.state`: `12f03f8fa11397b658b0e18dc85e8ad1bbb4c8c384cf6227d3b64eb629d88363`
- Owner SHA-256: `ff29cb7ee271519135c7dbd8e1899c7a7ec619068ec8fbd78d364cc9dbb77fb9`
- Task-specific renderer SHA-256: `41a6487940946d2321bbb2c9822d4c8fb0e543c456ad51ed0aaaa0381096b65c`
- Curriculum SHA-256: `4648f8bdb997665987c56b24236a22d886ea6fabead1443df5f157551d05c512`
- Focused-test SHA-256: `6d65c6442af71bb1db3cabb33aba0ea4506bfa8d4a72fa20eeb38a124264a02c`
- Family-screen SHA-256: `75e830c640a94437558e03b50f5bdfb37321b71e1aadf51cad5c58ddbf048d3c`
- Docker-receipt SHA-256: `1e49d22fed3a6ec352c8654ef9820739e221bab9c2ec9d23095cb3488f85b41e`
- Creator-preflight SHA-256: `129ba0ce6dc30cfc624cded368fd4b8e1a06de41561ade4177b4ea4004baa97c`
- Audit-subject SHA-256: `41c7464a76b6f5a618c709ef81e6dd858b6729b84a14565eafa85b8bb89e6c86`

## Finding Ledger

### AEO-C05-F001 — The right-closed control still falsely names its quotient Euclidean (CLOSED)

The base task now uses "pure-Euclidean partitioning", and the opposite-end control accurately replaces it with "right-closed partitioning". This preserves the token length and identical alias mappings in the clone discriminator while mathematically correcting the control's instructions. The generator and rendering scripts are updated, and the preflight clone tests correctly reject the exact right-closed mutation in all seven dimensions.
