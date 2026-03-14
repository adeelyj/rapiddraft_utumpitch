# Visual Modernization Plan (Modular, Low-Risk)

## Goal
Modernize the UI to feel like a contemporary CAE tool while minimizing functional risk.
All changes are front-end only and default to CSS-first.

## Principles
- Prefer CSS-only changes first.
- Avoid altering component logic unless needed for layout.
- Keep the viewer and interaction handlers untouched in early phases.

---

# Plan A: Foundation (CSS Tokens + Typography) — lowest risk
**Goal:** Establish a neutral CAE palette + typography without changing layout.

**Changes**
- Define CSS variables for neutrals, accents, text, and elevations.
- Replace current blue-heavy palette with neutral surfaces + single accent.
- Update font family and typographic scale (base size, headings, meta).
- Normalize button styles (radius, padding, hover).

**Files**
- `web/src/styles.css`

**Risk**
- Low. Visual only; no DOM changes.

**Verify**
- UI renders, no layout shifts.
- Buttons/labels remain legible on all panels.

---

# Plan B: Panels + Toolbar Restyle (CSS-only) — low risk
**Goal:** Make top bar and right panel feel modern and subdued.

**Changes**
- Flatten gradients; use solid neutral backgrounds.
- Reduce padding and pill-shapes; tighten button sizing.
- Add subtle separators between workspace and sidebar.
- Update panel headers, table rows, chips for clean CAE look.

**Files**
- `web/src/styles.css`

**Risk**
- Low. Visual only.

**Verify**
- Toolbar still usable, all buttons visible.
- Sidebar lists and tables remain readable.

---

# Plan C: Pins + Cards Visual Refresh (CSS-only) — low risk
**Goal:** Make pins and comment cards compact, CAD-like, and unobtrusive.

**Changes**
- Smaller pin size with crisp halo.
- Card sizing, typography, shadows softened.
- Status colors tuned to muted CAE palette.

**Files**
- `web/src/styles.css`

**Risk**
- Low. Visual only.

**Verify**
- Pins visible on model.
- Card content still readable.

---

# Plan D: Layout Tweaks (Minimal DOM change) — medium risk
**Goal:** Improve spatial rhythm and modern layout density.

**Changes**
- Optional: adjust sidebar width ratio and panel padding.
- Optional: compact toolbar button labels or group actions.
- Optional: tweak table column spacing.

**Files**
- `web/src/styles.css`
- Possibly `web/src/App.tsx` (only if structural changes needed)

**Risk**
- Medium (light layout shifts).

**Verify**
- No overlap with viewer controls.
- No broken alignments on small screens.

---

# Plan E: Interaction Polish (Optional) — medium risk
**Goal:** Subtle motion and focus cues (no behavioral change).

**Changes**
- Add hover/active states and soft transitions.
- Focus-visible outlines for accessibility.
- Slight entrance animation on side panels/cards.

**Files**
- `web/src/styles.css`

**Risk**
- Medium (visual behavior only).

**Verify**
- No jarring motion; no new focus traps.

---

## Suggested Order
1) Plan A (tokens + typography)
2) Plan B (toolbar/panels)
3) Plan C (pins/cards)
4) Plan D (layout tweaks, if desired)
5) Plan E (polish, optional)

## Notes
- Each plan is reversible by reverting `styles.css` changes.
- If you want a darker CAE viewport or theme, apply in Plan A.
