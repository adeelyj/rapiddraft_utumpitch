# DFM MTK Benchmark Dataset Template

This folder is the local template for benchmark cases that compare RapidDraft DFM results against Cadex outputs.

Use one folder per case inside `cases/`. Each case should contain exactly one STEP file, one Cadex features JSON file, and one Cadex DFM output JSON file.

Recommended structure:

```text
benchmark_data/
  dfm_mtk/
    cases/
      case_001/
        part.step
        cadex_features.json
        cadex_dfm.json
      case_002/
        part.step
        cadex_features.json
        cadex_dfm.json
```

The manifest template that references these files is at:

`plans/dfm_mtk_benchmark_manifest.template.json`

Copy that file to a working manifest (for example `plans/dfm_mtk_benchmark_manifest.local.json`) and fill the case paths.

This workspace already includes a populated working manifest at:

`plans/dfm_mtk_benchmark_manifest.local.json`

At the moment, that populated manifest contains seven real Cadex-labeled cases already in this workspace: `sample 2`, `sample 3`, `sample 4`, `sample 5`, `sample 6`, `sample 7`, and `sample 8`. Geometry regression coverage is also stronger because the turning detector has reduced real-data fixtures under `server/tests/fixtures/cnc_turning/`, but those fixtures are still a complement to, not a replacement for, real labeled benchmark cases.

For `sample 5`, `sample 6`, and `sample 7`, the files have now been normalized into the same one-folder-per-case structure as the earlier samples. `sample 7` only arrived with one Cadex JSON, but that export already includes both `featureRecognition` and `dfm`, so `sample7_features.json` mirrors the same combined payload to keep the dataset contract consistent.

Feature-detection hardening is now broader than turning. The repo also keeps reduced real-data feature fixtures under `server/tests/fixtures/cnc_feature_detection/`, and the focused gate can be run locally with:

`python scripts/run_dfm_feature_detection_gate.py`

When you add a new real Cadex-labeled case, the intended workflow is:

1. Add the case folder under `benchmark_data/dfm_mtk/cases/` and wire it into `plans/dfm_mtk_benchmark_manifest.local.json`.
2. Run the parity report so it emits a fresh `sample_X_feature_inspection.json`.
3. Generate a reduced regression fixture with `python scripts/regenerate_cnc_feature_fixture.py --inspection <inspection_json> --out server/tests/fixtures/cnc_feature_detection/<fixture_name>.json --case-id <case_id>`.
4. Rerun `python scripts/run_dfm_feature_detection_gate.py` so the new case is immediately covered by the exact-count geometry regression path.

The current runner can be invoked from the repo root with:

`python scripts/run_dfm_mtk_benchmark.py --manifest plans/dfm_mtk_benchmark_manifest.local.json`

If you want the benchmark philosophy, current dataset status, backend touchpoints, and a copy-paste opening brief for a fresh Codex Windows app session, read `benchmark_data/dfm_mtk/CODEX_HANDOFF.md`.
