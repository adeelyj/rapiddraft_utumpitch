# DFM Plan 04 UI Behavior Checklist

## Core Cutover
- [x] DFM sidebar supports v2 config -> plan -> review flow.
- [x] DFM sidebar calls `GET /api/dfm/config` when v2 mode is enabled.
- [x] DFM sidebar calls `POST /api/dfm/plan` before review execution.
- [x] DFM sidebar calls `POST /api/models/{model_id}/dfm/review-v2` for v2 review generation.

## Flow and Controls
- [x] Flow order is sourced from `ui_bindings.screens.dfm_review_panel.flow_order`.
- [x] Manufacturing process supports auto vs explicit override.
- [x] Overlay selection is optional.
- [x] Role lens and report template are selectable.
- [x] Advanced model selector is shown when options are present in config.
- [x] Run-both toggle is wired and sent to planning API.

## Mismatch and Standards
- [x] Mismatch banner is displayed from planning mismatch metadata.
- [x] Standards panel is read-only.
- [x] Standards entries are rendered from `standards_used_auto_union` only.
- [x] No manual standards selection control exists in v2 sidebar.

## Migration Update (Plan 06 N+2)
- [x] Legacy sidebar fallback has been removed.
- [x] Sidebar runs v2 flow only.
- [x] No frontend calls remain to legacy DFM endpoints.

## Build Validation
- [x] `cd web && npm run build` passes.
