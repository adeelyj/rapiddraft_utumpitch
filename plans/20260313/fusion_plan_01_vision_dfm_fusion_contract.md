# Fusion Plan 01 - Vision + DFM Fusion Contract

## Objective
Provide one additive fusion endpoint that ranks issues from DFM and Vision together, highlighting cross-confirmed risks first.

## API
- `POST /api/models/{model_id}/fusion/reviews`
- `GET /api/models/{model_id}/fusion/reports/{report_id}`

## Request (POST)
```json
{
  "component_node_name": "component_1",
  "vision_report_id": null,
  "dfm_review_request": {
    "component_node_name": "component_1",
    "planning_inputs": {
      "extracted_part_facts": {},
      "analysis_mode": "geometry_dfm",
      "selected_process_override": null,
      "selected_overlay": "pilot_prototype",
      "process_selection_mode": "auto",
      "overlay_selection_mode": "override",
      "selected_role": "general_dfm",
      "selected_template": "executive_1page",
      "run_both_if_mismatch": true
    },
    "context_payload": {}
  }
}
```

## Response Sections
- `confirmed_by_both`
- `dfm_only`
- `vision_only`
- `standards_trace_union`
- `priority_summary`

Additional status fields:
- `source_reports` (IDs/counts)
- `source_status` (`dfm`, `vision`)

## Matching Logic (current)
- semantic text overlap (token + keyword boost)
- optional standards-ref overlap boost when vision finding includes refs

## Ranking Logic (current)
- severity-weighted scoring across DFM/Vision
- confidence contribution for vision findings
- confirmation bonus when matched by both sources

## Persistence
Fusion artifacts stored under:
- `server/data/models/{model_id}/fusion_reports/{report_id}/request.json`
- `server/data/models/{model_id}/fusion_reports/{report_id}/result.json`

## UI Contract
Fusion sidebar shows:
- summary chips
- top actions
- collapsible sections for confirmed/dfm-only/vision-only
- standards trace collapsed by default

