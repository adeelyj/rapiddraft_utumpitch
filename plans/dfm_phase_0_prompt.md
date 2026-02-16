# Phase 0 Prompt - Repository Discovery and Integration Map

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
Do not implement features yet. Perform repository discovery and produce a decision-ready integration map for Phase 1.

Required outputs:
1. `docs/dfm_phase0_discovery.md`
2. `docs/dfm_phase0_discovery.json`

Discovery scope:
1. Identify backend stack and key locations:
- API framework and route files
- Service layer conventions
- Validation/schema mechanisms
- Existing rule engine execution path
- Existing report generation path

2. Identify frontend stack and key locations:
- Component architecture
- State management pattern
- API client pattern
- Existing sidebar/panel UI components
- Existing report template UI components

3. Map DFM integration points:
- Where to add config endpoint/service
- Where to add plan endpoint/service
- Where to add review generate endpoint/service
- Where to mount DFM Review panel and REP panel
- Where to add mismatch banner and standards auto list

4. Read all DFM bundle files and summarize:
- required enums/IDs used by UI
- data dependencies and joins
- potential schema mismatch risks

5. Produce a concrete Phase 1 implementation plan:
- file-by-file target changes
- exact endpoint contracts (request/response examples)
- risk list and mitigations

Constraints:
- No hardcoded option lists for process/overlay/role/template.
- Preserve existing architecture patterns.
- Keep plan incremental and easy to debug.

Execution style:
1. Inspect codebase first.
2. Produce concise integration map.
3. End with numbered "Phase 1 steps" that can be directly executed.
