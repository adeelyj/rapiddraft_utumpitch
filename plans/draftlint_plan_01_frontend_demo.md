# DraftLint Frontend Demo Plan for Recording-Ready Customer Walkthrough

## Summary

This plan translates the backend architecture described in `plans/plan_draftlint.md` into a convincing, production-looking frontend demo flow. The goal is a recording-ready customer experience where the product appears to scan drawings end to end, including staged processing feedback, localized issue highlights, and downloadable outputs, while using deterministic mock behavior for now.

The first release intentionally focuses on one polished scenario that behaves consistently across repeated demo runs.

## Implementation Design

### Phase 1: DraftLint UX Entry and Workspace Integration

Add a new right-rail tab named DraftLint and extend the existing `rightTab` state to support it. When DraftLint is active, the UI should switch to a dedicated drawing-analysis workspace so the user sees a clear scanning flow without interference from STEP-centric model overlays.

Introduce two frontend components:

`DraftLintSidebar.tsx` will own drawing upload (`PDF/PNG/JPG`), profile selection, scan trigger, stage timeline, summary metrics, and findings list/filter controls.

`DraftLintWorkspace.tsx` will render the drawing canvas, zoom/pan, and overlay layers for regions, OCR text boxes, detected symbols, and compliance issue bounding boxes. Selecting a finding in the sidebar should focus and pulse the corresponding area in the workspace and display rule metadata.

### Phase 2: Dummy Backend Contract with Realistic Behavior

Add temporary API routes under `/api/draftlint/*` and drive frontend with asynchronous polling so the behavior looks backend-driven, not static.

The dummy backend should not execute OCR or AI. It should load deterministic fixtures and simulate pipeline stage progression over time:

1. Load drawing  
2. Preprocess  
3. Layout analysis  
4. OCR extraction  
5. Symbol detection  
6. AI validation  
7. Rule validation  
8. Report generation

Each stage should expose status, timestamp, and progress updates so the scan feels authentic in video.

### Phase 3: Deterministic Demo Fixture

Create one fixture package at `server/fixtures/draftlint/demo_case_01/` containing:

1. Input drawing preview  
2. Annotated output image  
3. Final report JSON  
4. Optional HTML report  
5. Optional CSV extracts

Each run should generate new session/report IDs but reuse the same deterministic content, including coordinates, confidence values, severities, rule IDs, and recommended actions.

### Phase 4: Frontend Demo Fidelity

The scan trigger should run a staged timeline with realistic delay pacing and disabled controls while processing. After completion, the panel should transition into findings mode with severity chips, summary counts, and a filterable list.

The drawing workspace should support layer toggles, confidence display, and clear issue-to-overlay linking so the user can see where each issue is on the drawing immediately.

Customer-facing labels should avoid words such as “mock,” “dummy,” or “simulated.”

### Phase 5: Swap-Ready Adapter Boundary

Keep all network interaction in `web/src/services/draftlintClient.ts` and keep UI components bound to typed DTOs only. This makes real-backend replacement straightforward and minimizes refactor when the colleague implementation is connected.

Optionally add an environment flag to switch between demo fixtures and real backend later.

## Public API, Interface, and Type Changes

The planned additions are non-breaking:

1. `POST /api/draftlint/sessions` accepts drawing upload and returns session metadata with initial stage state.
2. `GET /api/draftlint/sessions/{session_id}` returns live session status, stage progression, progress percentage, and `report_id` when complete.
3. `GET /api/draftlint/reports/{report_id}` returns normalized report payload including summary, findings, AI analysis blocks, and artifact links.
4. `GET /api/draftlint/reports/{report_id}/artifacts/{artifact_name}` serves annotated image and report artifacts (`json/html/csv`).

Frontend type additions should live in `web/src/types/draftlint.ts` and include `DraftLintSession`, `DraftLintStage`, `DraftLintRegion`, `DraftLintTextElement`, `DraftLintDetectedSymbol`, `DraftLintIssue`, `DraftLintValidationReport`, and `DraftLintArtifacts`.

## Test Cases and Scenarios

Backend contract checks should verify upload validation, deterministic stage progression, completion-state transitions, report retrieval, and artifact availability.

Frontend checks should verify upload-to-scan flow, timeline rendering, control disable/enable states, completion transition, findings filtering, and correct issue-to-overlay focus behavior.

Recording acceptance criteria is one uninterrupted flow: upload drawing, run scan, observe staged processing, inspect highlighted issue, and open/download artifacts.

## Assumptions and Defaults

This first DraftLint release is standalone drawing workflow and is not tied to loaded STEP models.

The feature is integrated as a new right-rail tab in the current app shell.

The demo scope is one polished deterministic scenario.

The dummy backend contract is temporary but stable and intentionally aligned to the canonical data model in `plans/plan_draftlint.md` to reduce integration risk later.

Existing DFM, Vision, Fusion, CNC, and review flows remain unchanged.
