# DFM Plan 05 Cost Scenario Matrix

## Scenario Coverage
| Scenario | Inputs | Expected Behavior | Validation Evidence |
| --- | --- | --- | --- |
| Single route cost | Planned route, `quantity` provided | `cost_estimate` returned, one route in `cost_estimate_by_route`, no compare block | `server/tests/test_dfm_cost_estimation.py::test_review_v2_single_route_contains_cost_estimate` |
| Run-both mismatch cost | User override mismatches AI process, run-both enabled | Two route costs returned and `cost_compare_routes` populated with deltas | `server/tests/test_dfm_cost_estimation.py::test_review_v2_run_both_includes_route_cost_delta` |
| Degraded inputs | Missing supplier overrides and sparse geometry/profile | Cost still returned, confidence reduced, assumptions populated | `server/tests/test_dfm_cost_estimation.py::test_missing_supplier_rates_and_geometry_degrade_confidence_without_failure` |
| Cost model schema gate | Cost model JSON and schema | Valid model passes; malformed fields fail validation | `server/tests/test_dfm_cost_model_validation.py` |

## Output Contracts
- Example payloads are stored in `plans/dfm_plan_05_cost_contract_examples.json`.
- Response sections enabled in templates:
  - `cost_summary`
  - `cost_drivers`
  - `cost_compare_routes`
- UI binding source of truth:
  - `server/dfm/ui_bindings.json` under `screens.dfm_review_panel.cost_outputs`.
