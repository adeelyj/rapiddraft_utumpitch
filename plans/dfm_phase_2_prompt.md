# Phase 2 Prompt - Hardening and Report Template Builder

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
Complete Report Template Builder and harden the full DFM flow to production-ready behavior.

Before coding:
1. Read and honor Phase 1 handoff files:
- `docs/dfm_phase1_handoff.md`
- `docs/dfm_phase1_handoff.json`
2. Preserve all Phase 1 behavior. If contract changes are needed, keep backward compatibility.

Phase 2 scope:
1. Report Template Builder end-to-end
- Implement and wire:
  - template type
  - optional overlay pack
  - default role lens
  - template name plus save
  - section tree enable/disable behavior
- Standards/References section must remain auto-generated from findings (not user-selected).
- Enforce overlay-required sections during composition.

2. Backend template/report composition
- Add or complete template persistence consistent with repo conventions.
- Compose report output from:
  - findings + selected template + overlay + role lens
- Enforce `standards_references_auto` from findings refs only.

3. Hardening
- Add startup/runtime validation against `server/schema/dfm/schemas` where practical.
- Add robust error handling for missing/malformed config and unknown IDs.
- Add telemetry/logging around:
  - plan selection
  - mismatch/run-both path
  - standards auto-derivation
- Add edge-case tests:
  - low-confidence ties
  - override mismatch
  - missing refs
  - overlay-required sections
  - empty findings

4. Acceptance criteria
- Phase 1 DFM Review panel behavior remains intact.
- Template Builder is fully wired and functional.
- Standards are always auto and read-only.
- Role lens changes presentation weighting/order, not truth set.
- Run-both mismatch works end-to-end.
- Tests pass and are documented.

Deliverables:
1. Updated code.
2. Updated `docs/dfm_phase1_handoff.md` with Phase 2 completion notes.
3. Optional `docs/dfm_phase2_release_notes.md`.
4. Final summary with:
  - files changed
  - contracts added/updated
  - tests run and outcomes
  - remaining risks
