# DFM Plan 07 - Pilot DeepResearch Integration

## Objective
Integrate pilot standards/rules authored in DeepResearch into the existing DFM v2 runtime without breaking current API or UI contracts.

## Runtime Strategy
- Keep DeepResearch as authoring source.
- Compile into current `rule_library` schema (`PSTD-###` IDs, canonical `inputs_required`).
- Preserve rich source metadata in rule `thresholds` for traceability.
- Keep customer output concise: findings-first, standards trace collapsible.

## Implemented Components
- Compiler module: `server/dfm_pilot_deep_research.py`
- Compiler entrypoint: `scripts/compile_pilot_deep_research.py`
- Source artifacts:
  - `server/dfm/pilot_deep_research_source.json`
  - `server/dfm/pilot_deep_research_compiled.json`
  - `plans/dfm_plan_07_pilot_deep_research_mapping_contract.json`

## Bundle Updates
- `server/dfm/references.json` patched with pilot refs (including `REF-GPS-6`, `REF-GPS-7`).
- `server/dfm/overlays.json` pilot overlay patched to include pilot refs and `PSTD-` prefix.
- `server/dfm/rule_library.json` includes compiled `PSTD-001..PSTD-028`.
- `server/dfm/manifest.json` counts updated.

## Finding Traceability
DFM findings now carry additive trace fields when available:
- `standard_clause`
- `source_rule_id`
- `evidence_quality`

These are sourced from compiled metadata and shown in the DFM sidebar finding details.

## Safety/Compatibility
- No breaking change to `POST /api/models/{model_id}/dfm/review-v2`.
- Existing response shape remains compatible; new fields are additive.
- Existing DFM sidebar behavior preserved.

## Next Increment (optional)
- Add CI gate that verifies each geometry-relevant pilot standard has at least one geometry-active rule.
- Add compiler summary export grouped by standard with `executable_now` vs `deferred`.

