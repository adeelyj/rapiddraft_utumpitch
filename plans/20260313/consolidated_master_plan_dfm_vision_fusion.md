# Consolidated Master Plan (Updated After Code Deep Dive)

## Summary
DFM is already implemented as a production baseline. Vision and Fusion are also implemented end-to-end.  
The plan should now shift from "build DFM" to "stabilize + increase evaluator coverage + harden Fusion quality + add cross-system run traceability."

## Verified Current Status (Code + Tests)
DFM backend is implemented:
- `POST /api/models/{model_id}/dfm/review-v2` is live.
- Effective context resolution is backend-owned.
- PartFacts auto-load + PartFacts->DFM fact bridge is wired.
- Analysis modes (`geometry_dfm`, `drawing_spec`, `full`) are active.
- Cost estimation is integrated in review-v2 output.

DFM pilot DeepResearch integration is implemented:
- Compiler exists and outputs source/compiled/mapping artifacts.
- `PSTD-*` rules are present in runtime bundle.

Vision backend/UI is implemented:
- View-set generation, provider selection, report generation, report retrieval, and image serving are live.

Fusion backend/UI is implemented:
- `POST /api/models/{model_id}/fusion/reviews` and report retrieval are live.
- Matching and ranking logic is implemented and persisted.

Validation snapshot from this audit:
- Focused DFM/Vision/Fusion suites: passing.
- Full DFM+Vision+Fusion suite run: 80 passed, 1 failed.
- Single failure is golden snapshot drift in `test_dfm_review_v2_golden_payloads` caused by updated standards metadata (titles/notes/URLs), not core runtime logic.
- Frontend build passes.

## What This Means for Scope
DFM implementation is complete as baseline, not pending.  
Remaining DFM work is quality/capability expansion, not first-time feature delivery.  
Fusion is implemented but heuristic; next work is precision and traceability hardening.  
Vision is implemented but needs richer structured evidence for stronger fusion matching.

## Important API/Interface Changes (Planned, Additive)
No breaking changes.

Additive response fields planned:
- DFM route/overall: `unresolved_rule_count`, optional `evaluation_coverage`.
- Vision finding: optional `refs`, optional `geometry_anchor`, optional `evidence_quality`.
- Fusion finding: `match_signals`, `match_rationale`, optional `analysis_run_id`.

Add one new optional cross-system endpoint:
- `GET /api/models/{model_id}/analysis-runs/{analysis_run_id}` for run manifest linkage (DFM/Vision/Fusion report IDs and timestamps).

## Updated Implementation Phases
### Phase 1: Stabilization and Contract Hygiene
Refresh or re-baseline DFM golden payload artifact to match current canonical standards metadata.  
Keep strict golden test for contract shape; add explicit note that standards catalog updates can require golden refresh.  
Add CI gate for DFM/Vision/Fusion suites.

Acceptance:
- 0 failing tests in targeted DFM/Vision/Fusion matrix.
- Golden mismatch resolved without runtime regression.

### Phase 2: DFM Coverage Expansion (High ROI)
Expand evaluator registry for highest-impact geometry-capable rules.  
Prioritize CNC + pilot rules already backed by available PartFacts metrics.  
Keep unresolved checks tracked in standards trace; expose compact coverage summary in output.

Acceptance:
- Evaluator coverage increases materially from current baseline (19/170).
- Pilot evaluator coverage increases from current baseline (6/28).
- Geometry-mode output shows higher design-risk signal with lower unresolved/no-evaluator proportion.

### Phase 3: Vision Evidence Enrichment
Extend normalized vision finding model with optional standards refs and geometry anchors.  
Preserve existing provider contracts; new fields are optional and additive.

Acceptance:
- Existing clients keep working unchanged.
- Fusion gets richer structured inputs without fallback-only semantic matching.

### Phase 4: Fusion Matching and Ranking Hardening
Upgrade matching to weighted multi-signal model:
- semantic overlap
- standards ref overlap
- geometry anchor overlap (when present)

Add `match_signals` and `match_rationale` to fused outputs.  
Tune ranking for confirmed findings first, then high-risk single-source findings.

Acceptance:
- Deterministic tests for match/no-match/partial-match scenarios.
- Confirmed-by-both precision improves on regression fixtures.
- Fusion selects/resolves Vision reports with component scope (not model-only latest), with deterministic tests covering same-component vs cross-component cases.

### Phase 5: Unified Analysis Run Traceability + Modularization
Introduce `analysis_run_id` manifest that links DFM/Vision/Fusion artifacts.  
Add retrieval endpoint for run manifest.  
Refactor `main.py` into routers after run-manifest contract is stable.

Acceptance:
- One run ID reconstructs full analysis chain.
- No endpoint compatibility break during router split.

## Test Cases and Scenarios
DFM:
- review-v2 contract, effective context, analysis-mode gating, cost outputs, standards trace integrity.

Pilot compiler:
- ID mapping, input alias mapping, sanitization, executable/deferred classification.

Vision:
- provider listing, view-set creation, report generation/retrieval, pasted image handling, criteria filters.

Fusion:
- available/missing vision paths, confirmed/dfm-only/vision-only partitioning, ranking determinism.

End-to-end:
- single component run producing DFM + Vision + Fusion and linked artifacts.

## Assumptions and Defaults
Baseline DFM/Vision/Fusion implementation is retained; no redesign.  
Backward compatibility is mandatory; all schema changes are additive.  
`geometry_dfm` remains default demo mode.  
Golden artifacts are treated as contract snapshots and refreshed when canonical standards metadata changes.  
Prioritized order is: stabilize -> expand DFM evaluators -> enrich vision evidence -> harden fusion -> add run manifest.
