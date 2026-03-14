# DFM Plan 04 UI Manual Test Script

## Preconditions
1. Backend running on `http://localhost:8000`.
2. Frontend dependencies installed in `web/`.
3. At least one model imported and one component selectable in UI.

## A. V2 Flow Enabled
1. Set v2 flag on:
```powershell
cd web
$env:VITE_DFM_V2_ENABLED = "true"
npm run dev
```
2. Open the right-rail `DFM (AI)` panel.
3. Confirm flow controls appear in this order:
- manufacturing process
- industry overlay
- role lens
- report template
- advanced model selector
- run-both toggle
- generate review
4. Confirm options load dynamically (processes/overlays/roles/templates are not hardcoded).
5. Paste a screenshot in the screenshot field (optional).
6. Click `Generate review`.
7. Verify:
- plan summary appears
- review output appears with route cards
- standards section is read-only and populated from findings refs only
8. Set a manual process override different from likely AI recommendation and keep run-both enabled.
9. Generate again and verify mismatch banner appears and route count is `2`.

## B. Legacy Fallback
1. Stop dev server, then disable v2:
```powershell
cd web
$env:VITE_DFM_V2_ENABLED = "false"
npm run dev
```
2. Open the `DFM (AI)` panel.
3. Verify legacy UI appears with `Standards template` selector and legacy submit button.
4. Generate review and verify legacy markdown report renders.

## C. Build Gate
Run:
```powershell
cd web
npm run build
```
Expected:
- build completes successfully
- no TypeScript compile errors
