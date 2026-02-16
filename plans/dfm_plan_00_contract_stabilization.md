# DFM Plan 00 - Contract Stabilization

## Purpose
Fix file and contract integrity before runtime changes so later phases do not fail due to path or schema drift.

## Scope
- Ensure bundle and schema paths are repo-correct.
- Add missing `supplier_profile_template` schema.
- Align `server/dfm/manifest.json` file list and counts with actual repo files.
- Clean duplicate prompt lines and normalize prompt path style.

## Inputs
- `server/dfm/*.json`
- `server/dfm/schemas/*.json`
- `plans/handoff_template.md`

## Out of Scope
- No API or UI behavior changes.
- No rule execution logic changes.

## Implementation Tasks
1. Verify required bundle files exist:
- `manifest.json`
- `references.json`
- `rule_library.json`
- `process_classifier.json`
- `overlays.json`
- `roles.json`
- `report_templates.json`
- `ui_bindings.json`
- `accounts_pilot_targets.json`
- `supplier_profile_template.json`
- `cost_model.json`

2. Verify required schemas exist under `server/dfm/schemas`:
- `rule_library.schema.json`
- `roles.schema.json`
- `overlays.schema.json`
- `report_templates.schema.json`
- `ui_bindings.schema.json`
- `accounts_pilot_targets.schema.json`
- `cost_model.schema.json`
- `supplier_profile_template.schema.json` (create if missing)

3. Align `server/dfm/manifest.json`:
- Update `files` entries to repo paths (`server/dfm/...`), not foreign workspace paths.
- Include cost artifacts if they are part of active bundle.
- Ensure count fields match actual data:
- `expected_rule_count`
- `pack_counts`
- `reference_count`
- `roles_count`
- `templates_count`

4. Prompt cleanup:
- Remove duplicated lines in legacy phase prompt files if they still exist.
- Convert prompt references from leading slash style to workspace-relative style where possible:
- `server/...`
- `plans/...`

5. Produce an integrity report with pass/fail table and corrective notes.

## Acceptance Checks
- All referenced bundle and schema files exist.
- Manifest file entries resolve to real files in this repo.
- All `server/dfm/*.json` parse as valid JSON.
- All `server/dfm/schemas/*.json` parse as valid JSON.
- Prompt files have no duplicate critical instruction lines.
- Only expected unresolved paths are future handoff/discovery outputs.

## Intermediate Test Gate
Run:
```powershell
python -m pytest -q server/tests
```
And:
```powershell
@'
import json
from pathlib import Path
base = Path("server/dfm")
for p in base.glob("*.json"):
    json.loads(p.read_text(encoding="utf-8"))
for p in (base / "schemas").glob("*.json"):
    json.loads(p.read_text(encoding="utf-8"))
print("json-parse-ok")
'@ | python -
```

## Exit Artifacts
- `plans/dfm_plan_00_integrity_report.md`
- `plans/dfm_plan_00_integrity_report.json`

## Rollback
- Revert only manifest/prompt/schema edits from this phase if any integrity check fails.
