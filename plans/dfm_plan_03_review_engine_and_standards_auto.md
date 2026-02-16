# DFM Plan 03 - Review Engine and Standards Auto

## Purpose
Implement v2 review generation using selected rule packs and enforce standards derivation from findings refs only.

## Scope
- Add v2 review endpoint.
- Execute selected plan packs and produce findings.
- Derive `standards_used_auto` only from finding refs.

## Inputs
- Planning output from Plan 02.
- Bundle loader and validators from Plan 01.

## Out of Scope
- Cost output (handled in Plan 05).
- Full frontend migration (handled in Plan 04).

## Implementation Tasks
1. Add `POST /api/models/{model_id}/dfm/review-v2`.

2. Input contract should include:
- selected component context
- planning inputs or selected execution plan
- optional screenshot/context payload

3. Execution behavior:
- evaluate selected packs
- emit structured findings:
- `rule_id`
- `pack_id`
- `severity`
- `refs`
- `evidence` (if available)
- include empty findings case with stable response shape

4. Standards derivation:
- build `standards_used_auto` from `findings.refs`
- deduplicate and sort
- resolve to references catalog entries
- block manual standards injection

5. Add report composition skeleton:
- template sections
- role lens formatting hooks
- mismatch context when run-both used

## Acceptance Checks
- All returned refs resolve against references catalog.
- `standards_used_auto` changes only when findings refs change.
- Empty findings response is valid and explicit.
- Run-both returns two route outputs when required.

## Intermediate Test Gate
Run:
```powershell
python -m pytest -q server/tests/test_dfm_review_v2.py
python -m pytest -q server/tests/test_dfm_standards_auto.py
```
Golden payload validation:
```powershell
python -m pytest -q server/tests/test_dfm_review_v2_golden_payloads.py
```

## Exit Artifacts
- `plans/dfm_plan_03_review_golden_examples.json`
- `plans/dfm_plan_03_standards_traceability.md`

## Rollback
- Keep new endpoint behind feature flag if issues arise.
- Preserve legacy review endpoint behavior unchanged.

## Execution Status
- Status: **completed**
- Validation summary: `plans/dfm_plan_03_validation_results.md`
