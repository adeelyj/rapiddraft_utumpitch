# RapidDraft Product Requirements Documents

Document version: 1.0  
Last updated: 2026-03-02  
Prepared from current repository implementation in `server/`, `web/`, and `plans/`.

## Product Narrative

RapidDraft is an engineering workspace that starts with a STEP model and turns that model into a practical review and decision flow. The product combines geometry ingestion, generated drawing views, threaded review collaboration, and AI-assisted manufacturability analysis in one shell. The experience is organized around two sidebars: the left rail controls workspace creation and review context, while the right rail runs analysis systems such as Vision, DraftLint, CNC, DFM, Fusion, and report workflows.

The current codebase already contains most of this product surface. This PRD set therefore defines the next stable product contract by describing what must continue to work, what quality bar each module must meet, and what acceptance evidence engineering and product should require before each release.

## PRD-A: Core Workspace and Collaboration

### Product Intent

This document defines the foundation workflow where a user uploads a model, explores generated views, captures contextual comments or formal review items, and preserves work sessions. The objective is to make technical review repeatable and traceable without requiring users to leave the product for screenshots, spreadsheets, or ad hoc notes.

### Users and Jobs

The primary user is a design engineer who needs to validate a part quickly before manufacturing review. A secondary user is a reviewer or lead who needs to comment on exact geometry locations, convert comments into tracked review items, and verify closure status with history.

### Functional Requirements

| ID         | Requirement                                                                                                                                                  | Acceptance Signal                                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| RD-CORE-01 | The system shall ingest STEP files through the web client and create a persistent model record with stable `modelId`, source filename, and preview asset.    | `POST /api/models` returns model metadata and the model can be reopened by ID in subsequent API calls.              |
| RD-CORE-02 | The system shall generate and serve a 3D preview for interactive model viewing.                                                                              | `GET /api/models/{model_id}/preview` streams a valid preview file and the viewer renders without manual conversion. |
| RD-CORE-03 | The system shall generate multi-family 2D outputs, including tessellation views, Shape2D views, OCC silhouettes, mid-plane sections, and isometric variants. | Each generation endpoint returns non-empty view maps and each corresponding asset endpoint serves an image.         |
| RD-CORE-04 | The workspace shall support per-component visibility and component-scoped manufacturing profile metadata.                                                    | Component selections persist during a session and profile updates round-trip through `/component-profiles` APIs.    |
| RD-CORE-05 | The workspace shall support pinned model comments and design review records with lifecycle operations including create, update, reply, and delete.           | Ticket and design-review endpoints reflect UI actions and state stays consistent after refresh.                     |
| RD-CORE-06 | The workspace shall allow session export and import, including cached analysis references and drawing-state payloads.                                        | A saved session file reloads model, views, component context, and cached report references in one operation.        |
| RD-CORE-07 | The user shall be able to export generated views as a downloadable archive.                                                                                  | `POST /api/models/{model_id}/export` returns a downloadable ZIP with generated image assets.                        |

### Quality Requirements

Core workspace operations must be deterministic for the same input model and must fail with clear actionable messages when dependencies are unavailable. The product must preserve user-created review context even when analysis modules are not used.

## PRD-B: Manufacturing Intelligence Suite (DFM, CNC, Vision, Fusion)

### Product Intent

This document defines the analysis systems that convert geometry and drawing evidence into manufacturability risk signals. The intended outcome is not raw data volume but decision confidence: users should understand what is risky, why it is risky, and what to do next.

### Functional Requirements

| ID       | Requirement                                                                                                                                    | Acceptance Signal                                                                                                                |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| RD-AI-01 | The DFM system shall expose configuration and planning contracts and execute review-v2 analysis with selected mode and context resolution.     | `/api/dfm/config`, `/api/dfm/plan`, and `/api/models/{model_id}/dfm/review-v2` remain compatible and return structured findings. |
| RD-AI-02 | DFM shall support analysis modes `geometry_dfm`, `drawing_spec`, and `full`, and must report effective context in outputs.                     | Returned payload includes mode context and findings reflect mode gating behavior.                                                |
| RD-AI-03 | DFM shall integrate standards provenance through auto-generated standards references and standards trace outputs.                              | Review payload includes `standards_used_auto` and standards trace records attributable to fired rules.                           |
| RD-AI-04 | The system shall support component-level PartFacts retrieval and refresh to strengthen geometry-based decisions.                               | PartFacts endpoints produce/refresh fact payloads and DFM inputs consume those facts in analysis runs.                           |
| RD-AI-05 | CNC geometry analysis shall classify corner risks using configurable criteria and provide a downloadable PDF report.                           | `/api/models/{model_id}/cnc/geometry-report` returns summary and `pdf_url`; PDF endpoint serves the artifact.                    |
| RD-AI-06 | Vision analysis shall allow view-set creation, provider routing, criteria control, and report retrieval for model or component scope.          | Vision provider, view-set, report create, and report fetch endpoints execute end-to-end from the sidebar.                        |
| RD-AI-07 | Fusion shall combine DFM and Vision outputs into ranked confirmed and single-source findings with explicit match rationale and signal weights. | `/api/models/{model_id}/fusion/reviews` returns priority partitions, tuning-applied values, and match-signal fields.             |
| RD-AI-08 | Cross-system traceability shall be available through analysis run manifests that link DFM, Vision, and Fusion artifacts.                       | `/api/models/{model_id}/analysis-runs/{analysis_run_id}` reconstructs run lineage for report IDs and timestamps.                 |

### Quality Requirements

The analysis suite must preserve backward compatibility by adding fields rather than breaking existing keys. Every reported finding must remain attributable to either a rule, a vision observation, or a fusion rationale so that reviewers can audit conclusions rather than trust opaque scoring alone.

## PRD-C: DraftLint Drawing Compliance Experience

### Product Intent

This document defines the drawing-first scan workflow represented by the DraftLint rail tab. DraftLint is intended to feel production-grade in user interaction while maintaining deterministic behavior for demo and integration stability.

### Functional Requirements

| ID       | Requirement                                                                                                              | Acceptance Signal                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| RD-DL-01 | DraftLint shall create scan sessions from uploaded drawing files and return immediate session state.                     | `POST /api/draftlint/sessions` accepts drawing input and returns `session_id`, status, and progression metadata.       |
| RD-DL-02 | DraftLint shall provide polling endpoints with staged progress suitable for timeline rendering.                          | `GET /api/draftlint/sessions/{session_id}` advances through stages and returns progress and poll hints.                |
| RD-DL-03 | Completed sessions shall resolve to a normalized report contract with summary, issues, and customer-facing summary text. | `GET /api/draftlint/reports/{report_id}` returns structured report payload consumed directly by the sidebar/workspace. |
| RD-DL-04 | DraftLint shall expose report artifacts including annotated visual output and machine-readable exports.                  | Artifact endpoints return accessible URLs for annotated image, HTML/JSON report, and issue CSV.                        |
| RD-DL-05 | The workspace shall support issue-focused navigation from sidebar to canvas overlays.                                    | Selecting an issue highlights corresponding regions in the DraftLint workspace with stable coordinates.                |

### Quality Requirements

DraftLint demo behavior must stay deterministic across repeated runs so customer recordings and internal QA do not drift unexpectedly. The adapter boundary in frontend services must remain thin so the deterministic backend can later be replaced by a live inference service with minimal UI rewrite.

## Cross-Cutting Product Requirements

### User Experience and Interaction

The two sidebar model is the primary interaction grammar and must remain consistent. Left rail modules should set context and review artifacts, while right rail modules should execute analysis and reporting flows. Actions that trigger expensive processing should provide explicit running state, clear completion status, and persistent result recall within the same model session.

### Data and Persistence

Model-scoped artifacts, reports, and derived views must remain addressable by model ID and report ID so that generated outputs can be reopened reliably. Session import and export must preserve enough metadata to restore analysis continuity without hidden dependencies on browser-only memory.

### Reliability and Operations

The backend should return explicit error details for missing inputs, unavailable dependencies, and invalid analysis requests. The system should support redeploy-safe operation by keeping generated artifacts in persistent storage rather than process memory.

### Security and Configuration

Provider integrations for Vision and related services must allow per-run overrides without forcing secrets into repository files. Any API key override entered in UI should be treated as runtime input and not persisted to shared source-controlled assets.

## Release Readiness Criteria

Release readiness requires passing targeted backend test suites for DFM, Vision, Fusion, DraftLint, and wiring assertions that verify UI integration in `App.tsx`. Frontend build stability and static asset loading must be verified in the same CI run so deploys cannot ship with analysis endpoints passing while UI contracts are broken.

## Traceability to Existing Code

This PRD set maps directly to currently implemented surfaces in `server/main.py`, `web/src/App.tsx`, and analysis sidebars under `web/src/components/`. Planning references already present in `plans/` were treated as directional constraints and aligned with current runtime behavior before writing requirements.

## Non-Goals in This Revision

This revision does not propose a redesign of the shell navigation pattern, does not replace the current API surface with router-versioned contracts, and does not require immediate migration away from deterministic DraftLint fixtures. The current objective is product contract clarity and predictable delivery, not architectural churn.


