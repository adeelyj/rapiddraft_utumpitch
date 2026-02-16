# DFM Plan 00 Integrity Report

- Generated at (UTC): 2026-02-16T17:24:35.782008+00:00
- Overall status: **pass_with_warnings**

## Pass/Fail Matrix

| Check | Status | Notes |
| --- | --- | --- |
| `required_bundle_files_exist` | `pass` | OK |
| `required_schema_files_exist` | `pass` | OK |
| `manifest_file_entries_resolve` | `pass` | OK |
| `bundle_json_parse` | `pass` | OK |
| `schema_json_parse` | `pass` | OK |
| `manifest_counts_match_actual` | `pass` | OK |
| `schema_validation_jsonschema` | `pass` | OK |
| `prompt_refs_unresolved_only_expected_outputs` | `pass` | OK |
| `phase2_duplicate_hardening_line_removed` | `pass` | OK |
| `pytest_server_tests_gate` | `warn` | E   AssertionError: Missing dependencies: aiofiles, FreeCAD |

## Key Findings

- Manifest file entries now resolve to existing repo paths.
- Missing supplier profile schema was added and validates against current supplier template JSON.
- Phase 2 duplicate hardening line is reduced to one occurrence.
- Prompt path style is normalized to workspace-relative `server/...` and `plans/...`.
- Full `server/tests` gate has environment dependency warnings (see JSON report for tail output).

## Artifact Links

- `plans/dfm_plan_00_integrity_report.json`
