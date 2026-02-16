# DFM Plan 06 - Deprecation and Cleanup

## Execution Status
- Status: Completed (Milestone N+2 executed on 2026-02-16).
- Completed:
  - Removed backend legacy endpoints:
    - `GET /api/dfm/profile-options`
    - `GET /api/dfm/rule-sets`
    - `POST /api/dfm/review`
    - `POST /api/models/{model_id}/dfm/review`
  - Removed frontend fallback flow and legacy endpoint calls.
  - Removed runtime dependency on `server/data/dfm_profile_options.json`.
  - Removed temporary deprecation/telemetry compatibility layer after cutover.
  - Added bundle-derived component profile options into `GET /api/dfm/config` (`profile_options`).
- Current artifacts:
  - `plans/dfm_plan_06_deprecation_checklist.md`
  - `plans/dfm_plan_06_cleanup_diff_summary.md`
  - `plans/dfm_plan_06_validation_results.md`

## Purpose
Complete migration to the new DFM procedure and safely remove legacy profile-options flow after a two-milestone compatibility window.

## Scope
- Deprecate old endpoints and old data path.
- Add usage telemetry and deprecation warnings.
- Remove legacy wiring only after readiness criteria pass.

## Inputs
- Legacy endpoints:
- `/api/dfm/profile-options`
- `/api/dfm/rule-sets`
- `/api/models/{model_id}/dfm/review`
- Legacy data path:
- `server/data/dfm_profile_options.json`

## Out of Scope
- New feature additions.
- Rule-library content updates.

## Deprecation Timeline
1. Milestone N:
- new flow is default
- old flow available
- log warning when old endpoints are called

2. Milestone N+1:
- continue old flow
- add explicit deprecation metadata in response headers/body
- track endpoint usage counts by day

3. Milestone N+2:
- remove old endpoint logic and old data dependency
- keep migration notes in changelog and handoff

## Implementation Tasks
1. Add telemetry counters for old endpoint usage.
2. Add deprecation warnings for old endpoints.
3. Add readiness threshold:
- old endpoint usage near zero over agreed observation window
4. Remove legacy code paths and tests tied only to old flow.
5. Update docs and handoff templates to reflect completed migration.

## Acceptance Checks
- Telemetry confirms low or zero old endpoint usage before removal.
- Removal PR passes backend and frontend regression suites.
- No runtime references remain to `server/data/dfm_profile_options.json`.
- No frontend calls remain to deprecated endpoints.

## Intermediate Test Gate
Run before removal:
```powershell
python -m pytest -q server/tests
cd web
npm run build
```
Run after removal:
```powershell
python -m pytest -q server/tests -k dfm
```

## Exit Artifacts
- `plans/dfm_plan_06_deprecation_checklist.md`
- `plans/dfm_plan_06_cleanup_diff_summary.md`

## Rollback
- Reintroduce legacy endpoints in a temporary patch only if a hard blocker is found in production clients.
