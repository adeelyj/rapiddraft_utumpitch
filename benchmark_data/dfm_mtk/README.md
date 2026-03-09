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

At the moment, that populated manifest contains four real Cadex-labeled cases already in this workspace: `sample 2`, `sample 3`, `sample 4`, and `sample 8`. Geometry regression coverage is also stronger because the turning detector has reduced real-data fixtures under `server/tests/fixtures/cnc_turning/`, but those fixtures are still a complement to, not a replacement for, real labeled benchmark cases.

The current runner can be invoked from the repo root with:

`python scripts/run_dfm_mtk_benchmark.py --manifest plans/dfm_mtk_benchmark_manifest.local.json`

If you want the benchmark philosophy, current dataset status, backend touchpoints, and a copy-paste opening brief for a fresh Codex Windows app session, read `benchmark_data/dfm_mtk/CODEX_HANDOFF.md`.
