# RapidDraft DFM Source-Data Bundle

## What This Bundle Is
This folder is a backend-ready source-data bundle for RapidDraft DFM execution. It defines rule packs, references, process classification, overlays, role lenses, report templates, UI bindings, pilot account targets, and strict schemas.

Core logic implemented:
- Manufacturing process is the primary trigger for pack selection.
- Standards are not selected manually; they are attached to fired rules and overlays.
- Roles are presentation/weighting lenses, not separate rulebooks.
- Report templates control section layout only.
- `standards_references_auto` is generated from fired `refs`.
- If user override conflicts with AI recommendation, the system can run both and show mismatch context.

## How Process, Roles, Overlays, and Templates Interact
1. Process classifier proposes route(s) with confidence from CAD/drawing facts.
2. Plan builder selects base packs from process + always-on drawing checks.
3. Optional overlay adds `F_OVERLAY` constraints and domain references.
4. Role lens reweights severity and controls emphasis/sort/wording.
5. Template defines report sections; standards section is auto-populated from findings refs.

## Adding Rules, Suppliers, and Overlays
### Add a rule
1. Add a new rule object in `rule_library.json` with stable `rule_id` and valid `pack_id`.
2. Attach at least one `refs` ID from `references.json`.
3. Add any new input enum keys to `schemas/rule_library.schema.json` if needed.

### Add supplier capability constraints
1. Copy `supplier_profile_template.json` to tenant-specific config.
2. Fill numeric thresholds based on supplier capability docs.
3. Keep null for unknown values; runtime should use defaults/fallbacks.

### Add an overlay
1. Add overlay metadata in `overlays.json`.
2. Map relevant refs in `adds_refs`.
3. Ensure overlay-specific section requirements are reflected in `report_templates.json`.

## Versioning and Change Policy
- `rule_id` values are immutable once published.
- Breaking changes: increment major version.
- Backward-compatible additions: increment minor version.
- Reference URL/title fixes only: increment patch version.
- Deprecation policy:
  - Keep deprecated rules with `severity: info` + migration note for at least one minor release.
  - Never silently reuse old IDs for different logic.
