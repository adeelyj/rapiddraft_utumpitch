# DFM Plan 07 - Test Matrix

## Compiler Contract
- `test_pilot_deep_research_compiler.py::test_compiler_maps_rule_id_and_inputs_to_runtime_contract`
  - verifies `PILOTSTD-*` -> `PSTD-*` mapping and canonical input mapping.
- `test_pilot_deep_research_compiler.py::test_compiler_sanitizes_citation_tokens_in_notes`
  - verifies citation artifact cleanup.

## Runtime DFM Behavior
- `test_dfm_review_v2.py::test_review_v2_route_is_wired_in_main`
  - route wiring check.
- `test_dfm_review_v2.py::test_review_v2_geometry_mode_filters_drawing_spec_rules`
  - geometry mode excludes drawing/spec checks.
- `test_dfm_review_v2.py::test_review_v2_zero_corner_radius_is_reported_as_violation`
  - regression for radius=0 rule-violation behavior.
- `test_dfm_review_v2.py::test_review_v2_pilot_findings_include_traceable_source_fields`
  - pilot findings include `source_rule_id` trace field.

## Standards Trace and UI
- Manual check in DFM sidebar:
  - findings show standards labels and links.
  - standards trace remains collapsible.
  - trace fields (`Clause`, `Source rule`, `Evidence basis`) render when available.

## Bundle Validation
- Startup bundle loader validation (`load_dfm_bundle`) must pass after compilation.
- Manifest/rule/reference counts must remain internally consistent.

