# RapidDraft Startup Mode Launcher

## Summary

Make RapidDraft open on a new startup mode screen instead of dropping directly into the current workspace. The first screen should stay quiet and precise: a mostly white surface, very light drafting-grid detail, and four mode cards. Expert mode should open the current full workspace. Batch, Drawing Analysis, and Collaboration should open lightweight placeholder shells for now so the front end already has a clear structure before backend work lands.

## Key Changes

- Add an app-level mode host above the current workspace.
- Use a small `mode` query parameter instead of adding a router.
- Keep the current workspace as Expert mode with no major behavioral changes.
- Add a clear in-app path back to the mode picker from the existing global pane.
- Build one real launcher component and one shared placeholder-shell component.

## Interfaces

- Support `launcher`, `expert`, `batch`, `drawing`, and `collaboration` as frontend modes.
- Default to `launcher` when no `mode` query parameter is present.
- Preserve existing Expert-only query behavior such as `panel=draftlint`.

## Verification

- No query parameter opens the launcher.
- Expert mode opens the current workspace.
- Batch, Drawing Analysis, and Collaboration open their own placeholder shells.
- The in-app chooser returns Expert mode back to the launcher.
- `?mode=expert&panel=draftlint` still opens the DraftLint-capable workspace behavior.
- The frontend still passes a production build.

## Assumptions

- The launcher is the default first screen on every app open.
- Non-expert modes are placeholder front-end shells for now.
- The standalone HTML template stays as inspiration rather than the runtime entrypoint.
