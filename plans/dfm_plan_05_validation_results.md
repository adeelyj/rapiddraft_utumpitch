# DFM Plan 05 Validation Results

## Scope Verified
- Cost model schema validation is enforced.
- Review-v2 responses include `cost_estimate` and `cost_estimate_by_route`.
- Run-both responses include `cost_compare_routes` with route delta.
- Missing supplier/geometry inputs degrade confidence but do not fail review generation.
- Cost sections are available in report templates and UI bindings.

## Commands Run
Plan 05 focused gate:
```powershell
python -m pytest -q server/tests/test_dfm_cost_model_validation.py server/tests/test_dfm_cost_estimation.py
```

DFM regression gate:
```powershell
python -m pytest -q server/tests/test_dfm_review_v2.py server/tests/test_dfm_standards_auto.py server/tests/test_dfm_review_v2_golden_payloads.py server/tests/test_dfm_cost_model_validation.py server/tests/test_dfm_cost_estimation.py
```

Full backend regression gate (FreeCAD runtime):
```powershell
$env:PATH = "C:\Program Files\FreeCAD 1.0\bin;$env:PATH"
python -m pytest -q server/tests
```

Frontend build gate:
```powershell
cd web
npm run build
```

## Results
- Plan 05 focused gate: `6 passed`
- DFM regression gate: `14 passed`
- Full backend suite: `40 passed, 1 warning`
- Frontend build: successful (`vite build`)

Warning detail:
- Pending deprecation warning from `python-multipart` import alias in dependency smoke test.

## Exit Artifacts
- `plans/dfm_plan_05_cost_contract_examples.json`
- `plans/dfm_plan_05_cost_scenario_matrix.md`
