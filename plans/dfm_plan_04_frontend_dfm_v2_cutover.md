# DFM Plan 04 - Frontend DFM v2 Cutover

## Purpose
Move DFM UI to the new config -> plan -> review flow while retaining temporary fallback to legacy backend paths.

## Scope
- Wire DFM sidebar to new backend contracts.
- Enforce flow order from `ui_bindings`.
- Add mismatch banner and read-only standards-from-findings section.

## Inputs
- `GET /api/dfm/config` from Plan 02.
- `POST /api/dfm/plan` from Plan 02.
- `POST /api/models/{model_id}/dfm/review-v2` from Plan 03.
- UI components:
- `web/src/App.tsx`
- `web/src/components/DfmReviewSidebar.tsx`
- `web/src/components/ModelViewer.tsx`

## Out of Scope
- Final legacy endpoint removal (Plan 06).
- Cost UI sections beyond baseline placeholders (Plan 05).

## Implementation Tasks
1. Add frontend feature flag for rollout control:
- Example: `VITE_DFM_V2_ENABLED=true`

2. Replace hardcoded/legacy option loading in DFM sidebar with `/api/dfm/config`.

3. Implement UI flow order:
- manufacturing process
- industry overlay
- role lens
- report template
- advanced model selector
- run-both toggle
- generate

4. Add mismatch banner:
- show when user process override differs from high-confidence AI recommendation
- include both selected and recommended route labels

5. Standards panel:
- read-only
- populated only from review findings refs resolution
- no manual standards selection controls

6. Fallback behavior:
- when v2 flag disabled, keep current legacy API path working

## Acceptance Checks
- UI options load dynamically from config endpoint.
- Flow order is enforced and visible.
- Mismatch banner appears correctly.
- Standards panel reflects findings-only behavior.
- Legacy fallback works with flag disabled.

## Intermediate Test Gate
Run:
```powershell
cd web
npm run build
```
Manual script:
- Open DFM sidebar with v2 enabled.
- Complete flow and generate review.
- Trigger mismatch route and verify banner.
- Disable v2 flag and verify legacy path still works.

## Exit Artifacts
- `plans/dfm_plan_04_ui_manual_test_script.md`
- `plans/dfm_plan_04_ui_behavior_checklist.md`

## Rollback
- Flip feature flag off to return to legacy UI behavior while backend v2 remains deployed.

## Execution Status
- Status: **completed**
- Validation summary: `plans/dfm_plan_04_validation_results.md`
