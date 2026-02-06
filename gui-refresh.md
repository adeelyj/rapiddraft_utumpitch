# GUI Refresh Workflow (macOS + VS Code + Codex)

Starting point: You are logged into GitHub in Chrome and have VS Code open (Codex chat available).

## Goal
Make GUI changes safely without touching `master`, then open a Pull Request (PR) for review.

## One-Time Setup (first time on this machine)
1. Open Terminal in VS Code (Terminal menu -> New Terminal).
2. Verify Git is installed:
```bash
git --version
```
3. Set your Git identity if needed (only once):
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Repo Setup (if not already cloned)
1. Clone the repo:
```bash
git clone https://github.com/adeelyj/rapiddraft_utumpitch.git
```
2. Open the repo in VS Code:
```bash
cd rapiddraft_utumpitch
code .
```

## Create and Use a Feature Branch
If you already ran these commands, jump to the next section.
1. Create the branch:
```bash
git checkout -b gui-refresh
```
2. Confirm you are on the branch:
```bash
git branch --show-current
```
You should see `gui-refresh`.

## Install Frontend Dependencies (GUI work)
1. Go to the web app folder:
```bash
cd web
```
2. Install dependencies:
```bash
npm install
```
3. Run the dev server:
```bash
npm run dev
```
4. Open the dev URL shown in the terminal (usually `http://localhost:5173`).

## Make GUI Changes
1. Edit files under `web/` (for example `web/src/`).
2. Use Codex chat to help with edits, but keep changes focused on the GUI.
3. Check changes:
```bash
git status
```

## Commit Your Work (still on `gui-refresh`)
1. Stage only GUI changes:
```bash
git add web
```
2. Commit with a clear message:
```bash
git commit -m "GUI refresh"
```

## Keep Your Branch Up to Date
Run this before opening a PR if the repo is active.
1. Fetch the latest changes:
```bash
git fetch origin
```
2. Rebase your branch on top of `master`:
```bash
git rebase origin/master
```
If conflicts appear, resolve them, then:
```bash
git add <resolved-files>
git rebase --continue
```

## Push Your Branch
1. Push the branch to GitHub:
```bash
git push -u origin gui-refresh
```

## Open a Pull Request (PR)
1. Go to the repo in Chrome.
2. You will see a prompt to open a PR for `gui-refresh`. Click it.
3. Set base branch to `master` and compare branch to `gui-refresh`.
4. Add a clear title and summary, then create the PR.

## Review Checklist (before PR)
1. `git status` is clean (no uncommitted changes).
2. Only GUI files under `web/` were changed.
3. No large assets were added (avoid `.mp4`, huge binaries, or `node_modules`).

## Never Do These
1. Do not commit to `master`.
2. Do not run `git push origin master`.
3. Do not add `web/node_modules` or other build artifacts.

## If You Get Stuck
1. Run:
```bash
git status
git log --oneline -5
```
2. Send the output in Codex chat for help.

## Recommendations for macOS
If you are only changing the GUI, you can skip FreeCAD and backend setup and just run the frontend (`npm install`, `npm run dev` in `web/`).

**VS Code extensions (required)**
- `Python` (ms-python.python) for backend editing and interpreter selection.
- `Pylance` (ms-python.vscode-pylance) for Python IntelliSense and type hints.

**VS Code extensions (suggested)**
- `ESLint` (dbaeumer.vscode-eslint) if you add or use linting.
- `Prettier` (esbenp.prettier-vscode) for formatting.
- `GitLens` for easier Git history and diffs.
- `Docker` if you plan to use the Dockerfile.

**FreeCAD setup on macOS (backend only)**
The backend runs `ensure_freecad_in_path()` at import time (`server/cad_service.py`), so FreeCAD paths must be available before the server starts.
1. If FreeCAD is installed in `/Applications/FreeCAD.app`, no env vars are required.
2. If FreeCAD is installed elsewhere, set these before starting the backend:
```bash
export FREECAD_LIB="/Applications/FreeCAD.app/Contents/lib"
export FREECAD_BIN="/Applications/FreeCAD.app/Contents/MacOS"
```
3. If you use conda, run the exports after `conda activate <env>` in the same terminal.
4. These env vars must be set in the same terminal session that launches the backend.

## Recommendations for Windows
If you are only changing the GUI, you can skip FreeCAD and backend setup and just run the frontend (`npm install`, `npm run dev` in `web/`).

**VS Code extensions (required)**
- `Python` (ms-python.python) for backend editing and interpreter selection.
- `Pylance` (ms-python.vscode-pylance) for Python IntelliSense and type hints.

**VS Code extensions (suggested)**
- `ESLint` (dbaeumer.vscode-eslint) if you add or use linting.
- `Prettier` (esbenp.prettier-vscode) for formatting.
- `GitLens` for easier Git history and diffs.
- `Docker` if you plan to use the Dockerfile.

**FreeCAD setup on Windows (backend only)**
The backend runs `ensure_freecad_in_path()` at import time (`server/cad_service.py`), so FreeCAD paths must be available before the server starts.
1. FreeCAD is usually installed under `C:\Program Files\FreeCAD *` or `C:\Program Files (x86)\FreeCAD *`.
2. If auto-discovery fails or multiple versions are installed, set these in PowerShell before starting the backend:
```powershell
$env:FREECAD_LIB="C:\Program Files\FreeCAD 0.21\lib"
$env:FREECAD_BIN="C:\Program Files\FreeCAD 0.21\bin"
```
3. If you use conda, run the exports after `conda activate <env>` in the same terminal.
4. These env vars must be set in the same terminal session that launches the backend.
