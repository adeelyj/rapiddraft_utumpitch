# Phase 3 Prompt - Cost Estimation Integration (Quick Should-Cost)

Project context:
You are implementing RapidDraft DFM workflow integration using backend source-data bundle at:

- `server/schema/dfm/manifest.json`
- `server/schema/dfm/references.json`
- `server/schema/dfm/rule_library.json`
- `server/schema/dfm/process_classifier.json`
- `server/schema/dfm/overlays.json`
- `server/schema/dfm/roles.json`
- `server/schema/dfm/report_templates.json`
- `server/schema/dfm/ui_bindings.json`
- `server/schema/dfm/accounts_pilot_targets.json`
- `server/schema/dfm/supplier_profile_template.json`
- `server/schema/dfm/schemas/*.schema.json`

Core product logic that must never be violated:
1. Manufacturing process is the primary trigger for rule packs.
2. Standards are never manually selected; they are auto-derived from fired finding refs.
3. Roles are a lens (sorting/weighting/wording), not separate rulebooks.
4. Report templates control structure/sections only.
5. If user override mismatches AI process recommendation, support run-both and show mismatch banner.

Cost decisions already locked:
1. Cost model type: quick should-cost (not quote-grade).
2. Cost model location: new `server/schema/dfm/cost_model.json`.
3. Output depth: summary + cost drivers.
4. Currency strategy: single project currency.

Task:
Add cost estimation into the existing DFM workflow with minimal disruption to existing contracts and behavior.

Before coding:
1. Read and honor prior phase handoff files if present:
- `docs/dfm_phase0_discovery.md`
- `docs/dfm_phase0_discovery.json`
- `docs/dfm_phase1_handoff.md`
- `docs/dfm_phase1_handoff.json`
- `docs/dfm_phase2_release_notes.md` (optional)
2. Preserve all existing Phase 1 and Phase 2 behavior.

Phase 3 scope:
1. Add cost model files and schemas
- Create `server/schema/dfm/cost_model.json`.
- Create `server/schema/dfm/schemas/cost_model.schema.json`.
- Create `server/schema/dfm/schemas/supplier_profile_template.schema.json` if missing, or extend if present.
- Validate startup loading for these configs where practical.

2. Extend supplier profile for pricing inputs
- Update `server/schema/dfm/supplier_profile_template.json` with a `cost_profile` block including:
  - `currency_override`
  - `material_rate_per_kg`
  - `process_hourly_rates`
  - `setup_costs`
  - `scrap_factors`
  - `inspection_hourly_rate`
  - `finishing_rates`
- Keep unknown values nullable and marked configurable.

3. Add geometry-to-cost input pipeline
- Integrate STEP-derived metrics (from FreeCAD or existing geometry extractor):
  - `part_volume_mm3`
  - `surface_area_mm2`
  - `bbox_x_mm`, `bbox_y_mm`, `bbox_z_mm`
  - `bbox_volume_mm3`
  - `body_count`
  - process-relevant counts where available (`hole_count`, `bend_count`, etc.)
- Normalize units and handle missing-solid cases gracefully.

4. Add cost computation and route comparison
- Compute per-route quick should-cost using:
  - process route
  - geometry metrics
  - supplier rates/defaults
  - selected quantity
  - finding-based cost adjustments where implemented
- If mismatch run-both is enabled, compute both route costs and delta.
- Return confidence/range instead of fake precision.

5. Extend output contracts without breaking old consumers
- Add `cost_estimate` object to generate/review response.
- Add `cost_estimate_by_route[]` when run-both is active.
- Keep findings and `standards_used_auto` unchanged.

6. Extend report and UI config
- Update `server/schema/dfm/report_templates.json` to support:
  - `cost_summary`
  - `cost_drivers`
  - `cost_compare_routes`
- Update `server/schema/dfm/schemas/report_templates.schema.json` section enum accordingly.
- Update `server/schema/dfm/ui_bindings.json` with read-only cost blocks and route-compare widget.
- Update `server/schema/dfm/schemas/ui_bindings.schema.json` for added cost UI blocks.

7. Update manifest and validation metadata
- Update `server/schema/dfm/manifest.json` file list and counts for newly added cost files.
- Keep existing rule/reference/role/template counts intact.

Acceptance criteria:
1. Existing DFM behavior still passes:
- process-first pack triggering
- standards auto-only behavior
- role lens as presentation-only
- template section control
- mismatch run-both behavior
2. Cost model and supplier profile parse and validate.
3. Cost output appears in API and UI where configured, read-only.
4. Run-both returns two route cost summaries plus delta.
5. Missing geometry/rate inputs degrade confidence and produce clear assumptions.

Required deliverables:
1. Updated code and config files.
2. `docs/dfm_phase3_handoff.md`
3. `docs/dfm_phase3_handoff.json`
4. Final summary:
- files changed
- new/updated contracts
- test commands and outcomes
- known risks and deferred items

Execution style:
1. Inspect current architecture and identify integration points.
2. Provide a short plan.
3. Implement fully.
4. Finish with evidence for each acceptance criterion.
