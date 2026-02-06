# TextCAD Drafting Service

## Project Overview

This prototype delivers a Siemens NX-inspired drafting workflow made of two deployable pieces:

1. **`server/`** - FastAPI service that drives **FreeCAD** and **pythonocc-core** in headless mode to:
   - Import STEP files and generate glTF previews for 3D visualization
   - Rasterize multiple orthographic projection systems:
     - **FreeCAD tessellation views** (Top/Bottom/Left/Right wireframes)
     - **FreeCAD Shape2D views** (Top/Side/Bottom outlines)
     - **OCC HLR views** (X/Y/Z hidden-line removal silhouettes)
     - **OCC mid-plane section views** (cross-sections at model midpoints)

2. **`web/`** - React/Vite single-page application tailored for Netlify that communicates with the API for uploads, view generation, and downloads.

The backend must run on infrastructure with both **FreeCAD** and **pythonocc-core** installed (typically a Linux VM or Windows workstation). The frontend is static and ready for Netlify or any CDN host.

---

## Deploying the Backend

1. **Install FreeCAD & pythonocc-core** and ensure their Python site-packages are available:
   - **FreeCAD**: Download from https://www.freecad.org/downloads.php with Python modules enabled. Add bin/lib folders to `PATH`/`PYTHONPATH` or set `FREECAD_BIN`/`FREECAD_LIB` environment variables.
   - **pythonocc-core**: Install via `pip install pythonocc-core` (or build from source if needed for your platform).
   - Verify with:
     ```bash
     python -c "import FreeCAD, Part; print(FreeCAD.Version())"
     python -c "from OCC.Core.STEPControl import STEPControl_Reader; print('OCC OK')"
     ```

2. **Create and activate a Python environment** (pick one workflow):

   **Option A - `venv`:**
   ```bash
   cd server
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   **Option B - Conda:**
   ```bash
   cd server
   conda create -n textcad python=3.11 -y
   conda activate textcad 
   pip install -r requirements.txt  
   ```

3. **Run the API locally** for development:
   ```bash
   python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   
   **Test dependencies** (verify FreeCAD, pythonocc, and all required libraries are installed):
   ```bash
   python -m pytest tests/test_dependencies.py -s
   ```

4. **Production**: host behind a process manager (systemd, Supervisor, or Docker). Always mount a persistent volume over `server/data` so uploads survive restarts. Expose ports over HTTPS and allow CORS from the Netlify domain.

---

## Deploying the Frontend to Netlify

1. ```bash
   cd web
   npm install
   npm run build
   ```
2. Create a Netlify site and configure:
   - **Build command**: `npm run build`
   - **Publish directory**: `web/dist`
   - **Environment variable**: `VITE_API_BASE_URL=https://your-backend-domain`
3. Trigger a deploy (`netlify deploy --prod` or push to a connected Git repository). Netlify will serve the bundled SPA that calls the backend API base URL you configured.

---

## Local End-to-End Test

1. Run the backend with uvicorn (step above).
2. In another terminal:
   ```bash
   cd web
   npm run dev -- --host
   ```
3. Go to `http://localhost:5173`, import a STEP file, click any projection button, and **Export All** to download PNGs as ZIP.
