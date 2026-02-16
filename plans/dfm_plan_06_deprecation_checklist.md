# DFM Plan 06 Deprecation Checklist

## Milestone N (Completed)
- [x] New flow remains primary (`/api/dfm/config`, `/api/dfm/plan`, `/api/models/{model_id}/dfm/review-v2`).
- [x] Legacy endpoints remained available during compatibility window.
- [x] Legacy endpoint calls emitted deprecation response headers.
- [x] Legacy endpoint calls were logged server-side.

## Milestone N+1 (Completed)
- [x] Legacy endpoint usage telemetry stored by day and total count.
- [x] Deprecation metadata added in legacy response body where contract allows object payloads.
- [x] Telemetry inspection endpoint added during compatibility window (`GET /api/dfm/deprecation/telemetry`) and removed at N+2 cleanup.
- [x] Compatibility controls were validated before removal.

## Milestone N+2 (Completed)
- [x] Observe telemetry window and confirm legacy usage is near zero.
- [x] Remove frontend fallback wiring that depends on legacy DFM endpoints.
- [x] Remove backend legacy endpoints:
  - `/api/dfm/profile-options`
  - `/api/dfm/rule-sets`
  - `/api/models/{model_id}/dfm/review`
  - `/api/dfm/review`
- [x] Remove runtime dependency on `server/data/dfm_profile_options.json` by moving component profile options to bundle-backed config.
- [x] Run full regression after removal:
  - `python -m pytest -q server/tests`
  - `cd web && npm run build`
