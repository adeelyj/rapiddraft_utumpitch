# DFM Plan 02 API Contract Examples

## New Primary Endpoints
- `GET /api/dfm/config`
- `POST /api/dfm/plan`

Legacy endpoints retained at Plan 02 time (later removed in Plan 06 N+2):
- `GET /api/dfm/profile-options`
- `GET /api/dfm/rule-sets`
- `POST /api/models/{model_id}/dfm/review`

## `GET /api/dfm/config` Example Response Shape
```json
{
  "bundle": {
    "version": "1.0.1",
    "generated_at": "2026-02-16T18:20:00+00:00",
    "source_dir": "server/dfm"
  },
  "manifest": {
    "expected_rule_count": 130,
    "pack_counts": {
      "A_DRAWING": 25,
      "B_CNC": 25,
      "C_SHEET": 20,
      "D_WELD": 15,
      "E_ASSEMBLY": 15,
      "F_OVERLAY": 30
    },
    "reference_count": 34,
    "roles_count": 5,
    "templates_count": 5
  },
  "processes": [
    { "process_id": "cnc_milling", "label": "CNC Milling", "default_packs": ["A_DRAWING", "B_CNC", "E_ASSEMBLY"] }
  ],
  "overlays": [
    { "overlay_id": "medical", "label": "Medical Devices", "adds_rules_pack": "F_OVERLAY" }
  ],
  "roles": [
    { "role_id": "quality_engineer", "label": "Quality Engineer" }
  ],
  "templates": [
    { "template_id": "medical_design_review", "label": "Medical Design Review" }
  ],
  "packs": [
    { "pack_id": "A_DRAWING", "label": "Drawing and Specification Completeness" }
  ],
  "ui_bindings": { "...": "..." },
  "interaction_rules": {
    "primary_trigger": "manufacturing_process",
    "overlay_adds_pack": "F_OVERLAY",
    "role_is_lens_only": true,
    "template_controls_layout_only": true,
    "mismatch_banner_enabled": true
  }
}
```

## `POST /api/dfm/plan` Request Example
```json
{
  "extracted_part_facts": {
    "bends_present": true,
    "constant_thickness": true,
    "sheet_thickness": 2.0
  },
  "selected_process_override": null,
  "selected_overlay": "medical",
  "selected_role": "quality_engineer",
  "selected_template": "medical_design_review",
  "run_both_if_mismatch": true
}
```

## `POST /api/dfm/plan` Response Notes
- `ai_recommendation` is classifier-driven and deterministic for the same input facts.
- `selected_packs` is the primary execution route pack list.
- `mismatch` reports override-vs-AI differences and run-both execution state.
- `execution_plans` returns one or two routes depending on mismatch and toggle/policy.

Concrete payload examples are stored in:
- `plans/dfm_plan_02_plan_endpoint_examples.json`
