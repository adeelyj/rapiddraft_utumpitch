# DFM Plan 06 Cleanup Diff Summary

## Backend Changes
- Updated `server/main.py`.
  - Removed legacy endpoints:
    - `GET /api/dfm/profile-options`
    - `GET /api/dfm/rule-sets`
    - `POST /api/dfm/review`
    - `POST /api/models/{model_id}/dfm/review`
  - Removed legacy runtime path for `server/data/dfm_profile_options.json`.
  - Component profile validation now uses bundle-derived options via `build_component_profile_options(...)`.
- Updated `server/dfm_planning.py`.
  - Added `build_component_profile_options(bundle)` and included `profile_options` in `build_dfm_config(...)`.
  - Industry options now derive standards titles from overlay reference IDs.

## Test Changes
- Removed `server/tests/test_component_profile_options.py` (file-based legacy contract).
- Added `server/tests/test_dfm_component_profile_options.py` for bundle-derived profile options.
- Updated `server/tests/test_dfm_api_config.py` to assert legacy DFM routes are absent.

## Frontend Changes
- Updated `web/src/components/DfmReviewSidebar.tsx` to v2-only flow.
  - Removed legacy rule-set loading and legacy review submission.
- Updated `web/src/App.tsx` to load profile options from `GET /api/dfm/config`.
- Removed obsolete v2 feature flag declaration from `web/src/vite-env.d.ts`.

## Removed Files
- `server/dfm_deprecation.py`
- `server/tests/test_dfm_deprecation.py`
- `server/data/dfm_legacy_endpoint_usage.json`
- `server/data/dfm_profile_options.json`
