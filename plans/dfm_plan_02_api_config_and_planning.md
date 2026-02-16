# DFM Plan 02 - API Config and Planning

## Purpose
Add new primary planning APIs powered by the bundle without breaking existing DFM API consumers.

## Scope
- Add `GET /api/dfm/config`.
- Add `POST /api/dfm/plan`.
- Keep existing DFM endpoints functional during migration.

## Inputs
- Bundle loader from Plan 01.
- Existing backend routes in `server/main.py`.

## Out of Scope
- No review execution output yet.
- No frontend cutover yet.

## Implementation Tasks
1. Add `GET /api/dfm/config`:
- Return processes from classifier.
- Return overlays, roles, report templates, and UI bindings.
- Return manifest version and bundle metadata.

2. Add `POST /api/dfm/plan` request contract:
- extracted part facts
- selected process override (optional)
- selected overlay (optional)
- selected role
- selected template
- `run_both_if_mismatch`

3. Add `POST /api/dfm/plan` response contract:
- `ai_recommendation`
- `selected_packs`
- `mismatch` metadata
- `execution_plans` (one or two)

4. Planning logic:
- process is primary trigger
- always include base drawing checks where required
- add overlay pack only when overlay selected
- run-both only on mismatch and toggle enabled

5. Backward compatibility:
- keep `/api/dfm/profile-options` and `/api/dfm/rule-sets`
- keep `/api/models/{model_id}/dfm/review` unchanged
- no breaking response shape changes in legacy endpoints

## Acceptance Checks
- Config endpoint returns all required option sets from bundle.
- Plan endpoint returns deterministic plans for same inputs.
- Run-both behavior works for mismatch true and false cases.
- Legacy endpoints still respond as before.

## Intermediate Test Gate
Run:
```powershell
python -m pytest -q server/tests/test_dfm_api_config.py
python -m pytest -q server/tests/test_dfm_plan_endpoint.py
```
Manual probe:
```powershell
curl http://localhost:8000/api/dfm/config
```

## Exit Artifacts
- `plans/dfm_plan_02_api_contract_examples.md`
- `plans/dfm_plan_02_plan_endpoint_examples.json`

## Rollback
- Disable new endpoints only if needed.
- Keep legacy endpoints untouched and running.

## Execution Status
- Status: **completed**
- Validation summary: `plans/dfm_plan_02_validation_results.md`
- Migration note: legacy endpoints listed above were removed in Plan 06 N+2.
