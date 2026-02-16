# DFM Plan 05 - Cost Integration

## Execution Status
- Status: Completed on 2026-02-16.
- Cost outputs are live in review-v2 and can be disabled with `DFM_COST_ENABLED=false`.
- Exit artifacts produced:
  - `plans/dfm_plan_05_cost_contract_examples.json`
  - `plans/dfm_plan_05_cost_scenario_matrix.md`
  - `plans/dfm_plan_05_validation_results.md`

## Purpose
Integrate quick should-cost into v2 review outputs and reporting with route comparison support.

## Scope
- Use `server/dfm/cost_model.json`.
- Extend review response with cost summaries.
- Add route comparison costs for run-both mode.
- Wire template and UI bindings for cost sections.

## Inputs
- `server/dfm/cost_model.json`
- `server/dfm/schemas/cost_model.schema.json`
- `server/dfm/supplier_profile_template.json`
- `server/dfm/report_templates.json`
- `server/dfm/ui_bindings.json`

## Out of Scope
- Quote-grade pricing.
- Procurement integration.

## Implementation Tasks
1. Validate cost model at startup via bundle loader.

2. Add cost input pipeline:
- geometry metrics (volume, area, bbox, counts)
- process route
- supplier cost profile defaults and overrides
- quantity

3. Add review response fields:
- `cost_estimate`
- `cost_estimate_by_route[]` when run-both active
- confidence/range metadata and assumptions

4. Update report composition:
- include `cost_summary`
- include `cost_drivers`
- include `cost_compare_routes` when applicable

5. Update UI bindings and rendering:
- show cost blocks as read-only system-derived outputs
- show route delta in mismatch run-both mode

## Acceptance Checks
- Cost model validates against schema.
- Review response includes cost output when enabled.
- Run-both includes two route costs and a delta.
- Missing cost inputs degrade confidence without hard failure.

## Intermediate Test Gate
Run:
```powershell
python -m pytest -q server/tests/test_dfm_cost_model_validation.py
python -m pytest -q server/tests/test_dfm_cost_estimation.py
```
Manual checks:
- Single-route review shows one cost summary.
- Run-both review shows route comparison and delta.
- Missing supplier rates returns assumptions and lower confidence.

## Exit Artifacts
- `plans/dfm_plan_05_cost_contract_examples.json`
- `plans/dfm_plan_05_cost_scenario_matrix.md`

## Rollback
- Keep cost feature behind server flag if needed.
- Preserve non-cost review behavior when cost disabled.
