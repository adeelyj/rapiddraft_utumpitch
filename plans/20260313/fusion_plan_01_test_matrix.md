# Fusion Plan 01 - Test Matrix

## Backend Logic
- `test_fusion_analysis.py::test_fusion_payload_confirms_overlap_between_dfm_and_vision`
  - verifies confirmed matching and standards union propagation.
- `test_fusion_analysis.py::test_fusion_payload_handles_missing_vision_report`
  - verifies explicit source status when vision input is absent.

## API Wiring
- `test_fusion_endpoints_wiring.py::test_fusion_endpoints_are_wired_in_main`
  - checks both fusion endpoints exist.

## UI Wiring
- `test_fusion_endpoints_wiring.py::test_fusion_sidebar_is_wired_in_app`
  - checks Fusion rail action and sidebar wiring in `App.tsx`.

## Manual Validation Script
1. Open model and select one component.
2. Run vision once to create at least one vision report.
3. Open Fusion sidebar and run with `Geometry DFM`.
4. Verify output sections:
   - `Confirmed by both`
   - `DFM only`
   - `Vision only`
   - `Standards trace` (collapsed)
5. Re-run Fusion with explicit stale/non-existent `vision_report_id` and confirm proper error handling.

