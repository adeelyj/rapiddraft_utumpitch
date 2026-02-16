# Phase 1 Prompt - Vertical Slice (DFM Review Bar)

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

Task:
Implement a stable vertical slice for DFM Review Bar only. Do not implement full report-template-builder customization yet.

Before coding:
1. Read and follow Phase 0 outputs if present:
- `docs/dfm_phase0_discovery.md`
- `docs/dfm_phase0_discovery.json`

Phase 1 scope:
1. Backend config + planning + generate flow
- Add config endpoint/service returning:
  - processes
  - overlays
  - roles
  - templates
  - ui bindings
  - manifest version
- Add plan endpoint/service:
  - input: extracted part facts + user selections + `run_both_if_mismatch`
  - output: `ai_recommendation`, `selected_packs`, mismatch metadata, `execution_plans` (1 or 2)
- Add review generate endpoint/service:
  - execute selected packs (use existing rule engine if available, otherwise add adapter/stub with explicit TODO)
  - return findings (`rule_id`, `refs`, severity, evidence fields if available)
  - return `standards_used_auto` derived from findings refs joined with `references.json`

2. Frontend DFM Review panel
Implement and wire controls:
- Manufacturing process (Auto + override)
- Industry overlay
- Role lens
- Report template
- Advanced LLM model selector
- Run both if mismatch toggle
- Standards used (auto), read-only, collapsible
- Generate action

3. Required behavior
- UI options come from backend config (no hardcoded literals).
- Flow order must match:
  - process -> overlay -> role -> template -> advanced -> run both -> generate
- Show mismatch banner when user override differs from high-confidence AI recommendation.
- Standards used list must be derived from findings refs only.

4. Validation required in Phase 1
- Rule count and pack counts load correctly from bundle.
- All returned standards refs resolve to `references.json`.
- Run-both returns two plans when mismatch plus toggle is true.
- Existing app behavior is not regressed.

5. Mandatory handoff artifacts for Phase 2 context retention
Create:
- `docs/dfm_phase1_handoff.md`
- `docs/dfm_phase1_handoff.json`

Include:
- endpoints/services added
- request/response contracts with examples
- files changed
- feature flags/toggles
- known gaps and explicit TODOs for Phase 2
- test commands and results

Execution style:
1. Inspect current architecture quickly.
2. Show short implementation plan.
3. Implement fully.
4. End with:
  - changed files
  - contracts added
  - validation evidence
  - unresolved items
