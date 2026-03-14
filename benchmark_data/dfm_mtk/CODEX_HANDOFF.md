# DFM MTK Benchmark Handoff

This note exists so a fresh Codex session can understand the benchmark philosophy without having to rediscover it from scattered files and half-finished context. The benchmark is not only asking whether RapidDraft and Cadex land on the same final answer. It is trying to separate two different sources of disagreement that are easy to blur together if we only look at the finished report. One source is feature recognition: what geometry and manufacturing-relevant signals were noticed in the first place. The other source is DFM reasoning: what manufacturing conclusions were drawn from those signals once they were available.

The working copy that contained the real sample cases when this note was written was `D:\02_Code\21_RapidDraft_ProductversionFinal_DFMBenchmark`. That detail matters because an earlier sibling repo snapshot only had the scaffold. In this working copy, `benchmark_data/dfm_mtk/cases/sample 2`, `sample 3`, `sample 4`, `sample 5`, `sample 6`, `sample 7`, and `sample 8` each contain exactly one STEP file, one Cadex features JSON file, and one Cadex DFM JSON file. The manifest template at `plans/20260313/dfm_mtk_benchmark_manifest.template.json` still uses placeholder `case_001` paths, but this workspace now also includes `plans/20260313/dfm_mtk_benchmark_manifest.local.json`, which points at the real sample folders. One small implementation note: `sample 7` arrived with a single combined Cadex export, so `sample7_features.json` intentionally mirrors that same payload because it already includes both `featureRecognition` and `dfm`.

The core idea is simple once you say it plainly. The Cadex features JSON is the reference for what geometry and manufacturing signals Cadex recognized. The Cadex DFM JSON is the reference for the manufacturing conclusions Cadex reached from those signals. That gives us two benchmark modes that answer two different questions. In logic-only mode, RapidDraft should receive enough pre-existing feature context that we are mostly testing its manufacturing reasoning rather than its geometry extraction. In end-to-end mode, RapidDraft should start from the STEP alone, which is closer to real usage. If logic-only looks good and end-to-end looks bad, the likely weakness is in feature extraction or in the adapter that turns recognized signals into RapidDraft inputs. If both look bad, the reasoning layer is also part of the problem.

The manifest template is there to keep the comparison honest. It fixes defaults such as `selected_role`, `selected_template`, `selected_overlay`, `run_both_if_mismatch`, and analysis mode so two cases are not silently being compared under different review settings. It also defines severity normalization because Cadex and RapidDraft may use different words for roughly the same level of concern. In the current template, `critical`, `blocker`, and `fatal` collapse into `critical`; `major` and `high` collapse into `major`; and `minor`, `medium`, `low`, and `info` collapse into `minor`. The point is to compare normalized meaning rather than exact phrasing. Each case can also carry process, material, and industry context, and it can specify a `component_node_name` for assembly STEP files so the benchmark does not accidentally measure missing context instead of DFM quality.

The backend contracts already present in this repo are important because they show where a runner should plug in. `server/main.py` exposes `POST /api/models` to import a STEP file, `GET /api/dfm/config` to discover available DFM configuration, `POST /api/dfm/plan` and `POST /api/models/{model_id}/dfm/plan` to resolve execution plans, `GET /api/models/{model_id}/components/{node_name}/part-facts` to derive RapidDraft part facts from geometry, and `POST /api/models/{model_id}/dfm/review-v2` to generate a DFM review. `server/dfm_part_facts_bridge.py` turns part-facts sections into the extracted-facts shape that planning and review consume. `server/dfm_planning.py` decides which process, overlay, template, and packs should run. `server/dfm_review_v2.py` can generate a review either from planning inputs or from explicit execution plans. That means the missing benchmark runner should be treated as an orchestration layer around existing DFM backend contracts, not as a reason to redesign the benchmark concept.

One practical implementation question still needs careful handling. Logic-only mode will need a trustworthy way to translate the Cadex features JSON into the RapidDraft-side input shape expected by planning and review. That may end up looking like `extracted_part_facts` directly, or it may require an adapter that maps Cadex feature names into the facts RapidDraft expects. That is an implementation detail to solve deliberately, not evidence that the benchmark idea is flawed.

The current repo state should therefore be read as "benchmark scaffold plus real data," not "finished executable benchmark." The right first move for a new session is to validate that the actual dataset matches the intended contract, then propose or implement the runner using the existing DFM backend contracts, and only redesign something if a concrete blocker makes that unavoidable.

This workspace now includes a first runnable benchmark entry point at `scripts/run_dfm_mtk_benchmark.py`. The default happy-path command is `python scripts/run_dfm_mtk_benchmark.py --manifest plans/20260313/dfm_mtk_benchmark_manifest.local.json`. It writes a machine-readable summary to `output/dfm_mtk_benchmark/<run_label_or_timestamp>/summary.json` and a quick human-readable summary to the sibling `summary.md`. One important caveat is that end-to-end mode depends on the local geometry stack for part-facts extraction. If pythonOCC or related dependencies are unavailable, the runner will still emit a result, but it will mark end-to-end as completed with warnings so you do not mistake an environment limitation for a product regression.

One more practical note about the current workspace snapshot: there are now seven real Cadex-labeled benchmark cases, and the feature work now keeps reduced real-data regression fixtures under both `server/tests/fixtures/cnc_turning/` and `server/tests/fixtures/cnc_feature_detection/`. The focused local gate for that path is `python scripts/run_dfm_feature_detection_gate.py`, and new labeled cases should immediately be followed by a fresh feature inspection artifact plus a regenerated reduced fixture via `python scripts/regenerate_cnc_feature_fixture.py`.

If you want to seed a new Codex Windows app session quickly, paste the brief below.

```text
Open the exact working copy at:
D:\02_Code\21_RapidDraft_ProductversionFinal_DFMBenchmark

This repo contains a DFM benchmark scaffold for comparing RapidDraft against Cadex.

Please inspect:
- benchmark_data/dfm_mtk/
- plans/20260313/dfm_mtk_benchmark_manifest.local.json
- plans/20260313/dfm_mtk_benchmark_manifest.template.json
- scripts/run_dfm_mtk_benchmark.py
- server/main.py
- server/dfm_review_v2.py
- server/dfm_part_facts_bridge.py
- server/dfm_planning.py

Benchmark intent:
- Separate feature recognition from DFM reasoning.
- Each case has one STEP file, one Cadex features JSON, and one Cadex DFM JSON.
- We want two benchmark modes:
  1. logic-only: compare RapidDraft DFM reasoning against Cadex using pre-existing feature context
  2. end-to-end: compare RapidDraft full pipeline from STEP to DFM output against Cadex
- Normalize severities so labels from both systems map into shared buckets.
- Keep DFM context stable across runs using manifest defaults and per-case overrides.

Important:
- Do not redesign the benchmark concept unless necessary.
- First inspect the actual populated benchmarking folder and tell me whether the dataset matches the intended contract.
- Then propose or implement the runner needed to execute the benchmark using the existing DFM backend contracts.
```
