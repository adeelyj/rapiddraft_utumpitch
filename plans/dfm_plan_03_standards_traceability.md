# DFM Plan 03 Standards Traceability

## Rule-to-Standard Trace Contract
`standards_used_auto` is derived only from `findings[].refs` produced by review execution.

Algorithm:
1. Execute selected packs and emit findings.
2. Collect all `refs` from emitted findings.
3. Deduplicate and sort `ref_id` values alphabetically.
4. Resolve each `ref_id` against `server/dfm/references.json`.
5. Return resolved entries as `standards_used_auto`.

Blocked path:
- Manual standards injection is rejected:
  - Request models use `extra = forbid`.
  - `context_payload` keys like `manual_standards` are blocked by runtime validation.

## Why This Is Traceable
- Each standards entry is tied to at least one fired finding reference.
- If findings change, standards list changes deterministically.
- If no findings fire, standards list is explicitly empty.

## Golden Scenario Evidence
Source: `plans/dfm_plan_03_review_golden_examples.json`

| Scenario | Routes | Finding Count | Standards Count |
| --- | --- | --- | --- |
| `single_route_planned` | 1 | 63 | 20 |
| `run_both_planned_mismatch` | 2 | 132 | 24 |
| `empty_findings_selected_plan` | 1 | 0 | 0 |

`empty_findings_selected_plan` demonstrates the explicit empty output case:
- `findings`: `[]`
- `standards_used_auto`: `[]`
- `standards_used_auto_union`: `[]`
