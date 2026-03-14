# DFM Plan 01 Loader Contract

## Implemented Module
- `server/dfm_bundle.py`

## Public Contract
### `load_dfm_bundle(bundle_dir: Path | None = None, repo_root: Path | None = None) -> DfmBundle`
Loads the canonical DFM bundle, validates schema-backed files, and runs cross-file integrity checks.

Defaults:
- `bundle_dir`: `server/dfm`
- `repo_root`: repository root (used for manifest file path resolution)

Behavior:
- Fails immediately if required files are missing.
- Fails immediately on invalid JSON.
- Fails on JSON Schema violations for schema-backed bundle files.
- Fails on cross-file integrity mismatches.
- Returns immutable `DfmBundle` dataclass on success.

## Error Contract
### `DfmBundleValidationError`
Raised for all bundle validation failures with actionable messages, including:
- missing required file path
- invalid JSON source file
- schema validation file pairing and reason
- cross-file mismatch details

## Cross-File Validation Rules
Implemented checks:
1. Every manifest `files[]` entry resolves to an existing repo file.
2. Every rule `pack_id` exists in rule pack catalog.
3. Every rule `refs[]` id exists in references catalog.
4. Every process classifier `default_packs[]` entry exists in rule pack catalog.
5. Every role `emphasize_packs[]` entry exists in rule pack catalog.
6. Every template section `overlay_required` exists in overlay catalog.
7. Manifest count integrity:
- `expected_rule_count`
- `pack_counts`
- `reference_count`
- `roles_count`
- `templates_count`

## Startup Integration
- `server/main.py` now validates bundle during app startup import path:
- imports `load_dfm_bundle`
- loads `server/dfm`
- raises `RuntimeError` with validation details when invalid

This is fail-fast behavior by design so invalid DFM bundle state cannot run silently in production.

## Dependency Contract
- Added `jsonschema` to `server/requirements.txt`.
- Required for schema validation in loader.
