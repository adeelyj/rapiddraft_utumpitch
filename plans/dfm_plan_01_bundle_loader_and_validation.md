# DFM Plan 01 - Bundle Loader and Validation

## Purpose
Introduce a single backend loader for `server/dfm` so runtime uses one canonical bundle source with strict validation.

## Scope
- Add bundle loading module.
- Add schema validation and cross-file consistency checks.
- Add startup validation hook with clear error messaging.

## Inputs
- `server/dfm/manifest.json`
- `server/dfm/references.json`
- `server/dfm/rule_library.json`
- `server/dfm/process_classifier.json`
- `server/dfm/overlays.json`
- `server/dfm/roles.json`
- `server/dfm/report_templates.json`
- `server/dfm/ui_bindings.json`
- `server/dfm/accounts_pilot_targets.json`
- `server/dfm/supplier_profile_template.json`
- `server/dfm/cost_model.json`
- `server/dfm/schemas/*.schema.json`

## Out of Scope
- No new DFM API contracts yet.
- No UI changes.

## Implementation Tasks
1. Add `server/dfm_bundle.py` (or equivalent) with:
- strongly typed bundle structures
- loader function
- schema validator
- cross-file validator

2. Validate schema-backed files:
- `rule_library`
- `overlays`
- `roles`
- `report_templates`
- `ui_bindings`
- `accounts_pilot_targets`
- `cost_model`
- `supplier_profile_template` (if schema present)

3. Add cross-file checks:
- every `rule.refs[]` exists in `references`
- every process default pack exists in rule packs
- overlay pack references are valid
- template `overlay_required` IDs exist in overlays
- role emphasized packs exist in packs
- manifest count fields match actual payload counts

4. Integrate startup guard in backend app initialization:
- fail fast with actionable diagnostics
- include failing file and reason

5. Add focused tests under `server/tests` for:
- happy path load
- schema mismatch
- missing refs
- count mismatch

## Acceptance Checks
- App starts when bundle is valid.
- App fails predictably when bundle is invalid.
- Validation errors identify exact file and rule.
- Tests cover at least one synthetic invalid dataset per cross-file rule.

## Intermediate Test Gate
Run:
```powershell
python -m pytest -q server/tests/test_dfm_bundle_loader.py
python -m pytest -q server/tests/test_dfm_bundle_cross_validation.py
```

## Exit Artifacts
- `plans/dfm_plan_01_loader_contract.md`
- `plans/dfm_plan_01_validation_results.md`

## Rollback
- Keep bundle files intact.
- Disable startup hard-fail hook temporarily if rollout blocks unrelated work, but keep validator tests.
