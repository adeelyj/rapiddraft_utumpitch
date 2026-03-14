# DFM Benchmark Plan

## Summary
This plan turns the current experimental `DFM Benchmark Bar` into the long-term issue-first DFM workspace, while keeping `Simple DFM Review` untouched as the fallback baseline until the new workflow is proven.

The first milestone is intentionally simple:
- make the benchmark bar focus on DFM issues
- move feature recognition into one collapsed section
- hide standards and heavy metadata from this workspace for now
- validate the GUI with the real benchmark parts already used in this branch

After that, the roadmap adds feature anchors, DFM blame-map callouts, candidate-model comparison, AI-assisted editing, and finally accept/promote workflows.

## Phase 1 - Simplify the Existing DFM Benchmark Bar
Use the current `DFM Benchmark Bar` as the experimental surface and simplify it in place.

Target layout:
- selected part
- minimal review controls
- primary `DFM issues` section
- collapsed `Feature recognition` section
- optional empty-state guidance

What stays visible:
- generate review
- issue title, severity, description, recommended action, and impact
- route label only when multiple routes exist

What is removed or hidden from this bar:
- standards list
- effective analysis context
- heavy process-signal presentation
- cost block by default
- detailed geometry dumps outside the collapsed feature section

Acceptance for this phase:
- `Simple DFM Review` remains untouched
- the benchmark bar becomes issue-first
- feature recognition is collapsed by default
- `sample 2` and `sample 6` are both readable in the GUI

## Phase 2 - Add Clickable Feature Recognition Anchors
Extend feature recognition so the user can click a detected feature and focus the model near the relevant geometry.

Add an anchor contract for localizable feature items:
- `anchor_id`
- `component_node_name`
- `anchor_kind`
- `position_mm`
- `normal`
- `bbox_bounds_mm`
- `label`
- optional `face_indices`

Populate these anchors from the existing CAD feature outputs where practical:
- hole and bore groups
- pocket groups
- groove groups
- boss groups
- milled-face groups
- turning clusters

Frontend goal:
- clicking a feature-recognition item should show a 3D callout near the right region
- if no precise anchor exists, fall back to component-centered focus

## Phase 3 - Add DFM Blame Map
Add a blame-map layer to localizable DFM findings so clicking an issue focuses the geometry that most likely caused it.

The first implementation should use anchored callouts, not exact face highlighting.

Add a finding-level `blame_map` shape with:
- localization status
- primary anchor
- optional secondary anchors
- source fact keys
- source feature references
- short explanation

Start only with findings that have strong provenance:
- pocket depth and corner-radius issues
- hole depth and diameter issues
- groove and bore-related issues
- other local geometry issues where source features can be traced reliably

Do not force blame mapping for:
- process mismatch
- whole-part heuristics
- evidence gaps
- findings whose facts are currently aggregated without recoverable source geometry

## Phase 4 - Add Candidate Variant Comparison
Turn the compare flow into a real original-versus-candidate workflow.

Target flow:
1. user reviews the original model
2. user clicks an issue or localized feature
3. user requests a change
4. backend creates or updates a candidate variant
5. the candidate is rebuilt, previewed, and re-reviewed
6. user compares original and candidate before accepting

Backend concepts to introduce:
- edit session
- model variant
- proposed operation
- rebuilt preview
- regenerated Part Facts
- regenerated DFM review

The original part must not be overwritten during proposal generation.

## Phase 5 - Add AI-Assisted Editing
Implement AI editing as a structured operation layer, not as free-form arbitrary CAD mutation.

Supported first operations should be bounded and DFM-safe, for example:
- increase local radius or fillet
- enlarge pocket corner radius
- reduce pocket depth
- adjust hole diameter or depth
- suppress a selected groove, bore, boss, or rib candidate when localization confidence is strong

The AI layer should:
- interpret the user request
- bind it to a localized issue or feature
- produce a structured operation request
- refuse or ask for clarification when the request is unsafe or unsupported

The AI should not directly execute arbitrary kernel commands against imported STEP geometry.

## Phase 6 - Accept and Promote
Once candidate editing is working, add an explicit accept/promote workflow.

Acceptance should:
- promote the candidate variant to the active revision
- preserve the prior revision for rollback
- refresh preview, Part Facts, and DFM outputs
- record the applied operations

This should behave like revision promotion, not destructive overwrite.

## Contracts and Backend Direction
The long-term backend should keep `review-v2` backward-compatible and additive.

Planned additions:
- compact `geometry_evidence` for the simplified benchmark bar
- optional geometry anchors on evidence items
- optional `blame_map` on localizable findings
- explicit edit-session and variant APIs for remediation workflows

The CAD stack should continue to be used as:
- solid import and access through FreeCAD
- topology and feature reasoning through OCC
- browser visualization through generated preview meshes

The architecture should treat the current stack as a strong analysis foundation and a bounded editing foundation, not as a fully general parametric CAD agent from day one.

## Validation Strategy
For each phase, prefer a mix of automated checks and real GUI validation.

Phase 1:
- `npm run build`
- review-v2 regression checks
- manual smoke on `sample 2` and `sample 6`

Phase 2:
- anchor-generation tests
- manual feature-click focus checks

Phase 3:
- provenance tests for early blame-mapped rules
- manual issue-click callout checks

Phase 4:
- candidate variant creation and rebuild checks
- manual original-versus-candidate compare checks

Phase 5:
- natural-language-to-operation tests
- safety checks for unsupported requests

Phase 6:
- revision promotion and rollback checks

## Guiding Product Principle
The benchmark bar should become an issue-first DFM workspace:
- issues first
- feature recognition second
- standards and internal metadata hidden unless later proven useful

That keeps the UI understandable now, while still aligning with the long-term vision of blame mapping, AI-assisted correction, and candidate-model acceptance.
