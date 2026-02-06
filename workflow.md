# Workflow & Architecture

## Components

### Backend (FastAPI Server)
- **`server/main.py`** – FastAPI application hosting 11 REST endpoints for uploads, view generation, and exports
- **`server/cad_service.py`** – `CADService` class for FreeCAD tessellation, trimesh glTF export, Matplotlib rendering
- **`server/cad_service_occ.py`** – `CADServiceOCC` class for pythonocc HLR projections and mid-plane sections
- **`server/model_store.py`** – `ModelStore` class for on-disk metadata and model lifecycle management
- **`server/freecad_setup.py`** – Auto-detection and configuration of FreeCAD Python paths
- **`tests/test_dependencies.py`** – Pytest dependency verification

### Frontend (React/Vite UI)
- **`web/src/App.tsx`** – Root component coordinating UI state, API calls, and view panels
- **`web/src/components/Toolbar.tsx`** – Upload button, projection action buttons, status messages
- **`web/src/components/ModelViewer.tsx`** – React Three Fiber canvas for 3D glTF visualization
- **`web/src/components/ViewsPanel.tsx`** – Grid layout displaying PNG thumbnails from all projection methods
- **`web/src/styles.css`** – Siemens NX-inspired dark theme and blueprint aesthetic

### CAD Processing Layer
- **FreeCAD Headless** – Loads STEP data, tessellates shapes into triangle meshes, provides Draft Shape2D
- **pythonocc-core Headless** – Uses OpenCascade HLR algorithm for silhouette generation and mid-plane sectioning

---

## Processing Pipeline

### 1. Import STEP → Generate 3D Preview

1. User clicks toolbar **"Import"** and selects a `.step` file
2. `App.tsx` uploads to `POST /api/models` as multipart/form-data
3. Backend:
   - Saves to `server/data/models/<model_id>/source.step`
   - Calls `CADService.import_model()`:
     - Loads STEP via FreeCAD
     - Tessellates with `shape.tessellate(0.25)`
     - Exports glTF via trimesh to `preview.glb`
   - Returns `{modelId, previewUrl: /api/models/{id}/preview, originalName}`
4. Frontend loads glTF in 3D canvas via Three.js `GLTFLoader`
5. Model metadata saved to `server/data/models/<id>/metadata.json`

### 2. Generate FreeCAD Tessellation Views

1. User clicks **"Generate Views"** button
2. `POST /api/models/{id}/views`
3. Backend:
   - `CADService.generate_views()` tessellates STEP, projects onto 4 planes
   - Top: (X,Y); Bottom: (X,-Y); Left: (-Z,Y); Right: (Z,Y)
   - Renders triangle wireframes as PNGs via Matplotlib
   - Saves to `<model>/views/{top,bottom,left,right}.png`
   - Updates metadata
4. Frontend: `{views: {top: /api/.../top, bottom: /api/.../bottom, ...}}`

### 3. Generate FreeCAD Shape2D Outline Views

1. User clicks **"Shape2D Views"** button
2. `POST /api/models/{id}/shape2d`
3. Backend:
   - `CADService.generate_shape2d_views()` creates Draft Shape2D projections
   - Directions: Top, Side, Bottom
   - Discretizes and renders edges as PNGs
   - Saves to `<model>/shape2d/{top,side,bottom}.png`
4. Frontend: `{views: {top: /api/.../top, side: /api/.../side, ...}}`

### 4. Generate OCC HLR Silhouettes

1. User clicks **"OCC Silhouettes"** button
2. `POST /api/models/{id}/occ_views`
3. Backend:
   - `CADServiceOCC.generate_occ_views()` runs HLR projection along X/Y/Z
   - Extracts visible edges only (no hidden lines)
   - Discretizes edges and renders as PNGs
   - Saves to `<model>/occ_views/{x,y,z}.png`
4. Frontend: `{views: {x: /api/.../x, y: /api/.../y, z: /api/.../z}}`

### 5. Generate OCC Mid-Plane Sections

1. User clicks **"Mid-Plane Sections"** button
2. `POST /api/models/{id}/mid_views`
3. Backend:
   - `CADServiceOCC.generate_mid_views()` creates section planes at bounding-box midpoints
   - One section per axis (X, Y, Z)
   - Sections the part and extracts intersection curves
   - Discretizes and renders as PNGs
   - Saves to `<model>/mid_views/mid_{x,y,z}.png`
4. Frontend: `{views: {mid_x: /api/.../mid_x, mid_y: /api/.../mid_y, ...}}`

### 6. Export All Views as ZIP

1. User clicks **"Export All"** button
2. `POST /api/models/{id}/export`
3. Backend:
   - Collects all generated PNGs from `metadata.views`
   - Creates ZIP in memory with all PNGs
   - Streams via `StreamingResponse`
4. Browser prompts to save `views-<model_id>.zip`

---

## REST API Endpoints

| HTTP | Endpoint | Purpose | Response |
| --- | --- | --- | --- |
| GET | `/health` | Health check | `{status: ok}` |
| POST | `/api/models` | Upload STEP file | `{modelId, previewUrl, originalName, views}` |
| GET | `/api/models/{id}/preview` | Stream glTF | Binary GLB |
| POST | `/api/models/{id}/views` | Generate FreeCAD wireframes | `{modelId, views: {top, bottom, left, right}}` |
| GET | `/api/models/{id}/views/{view}` | Fetch wireframe PNG | PNG image |
| POST | `/api/models/{id}/shape2d` | Generate Shape2D outlines | `{modelId, views: {top, side, bottom}}` |
| GET | `/api/models/{id}/shape2d/{view}` | Fetch Shape2D PNG | PNG image |
| POST | `/api/models/{id}/occ_views` | Generate OCC silhouettes | `{modelId, views: {x, y, z}}` |
| GET | `/api/models/{id}/occ_views/{view}` | Fetch OCC PNG | PNG image |
| POST | `/api/models/{id}/mid_views` | Generate mid-plane sections | `{modelId, views: {mid_x, mid_y, mid_z}}` |
| GET | `/api/models/{id}/mid_views/{view}` | Fetch mid-plane PNG | PNG image |
| POST | `/api/models/{id}/export` | Export all views as ZIP | ZIP stream |

---

## Data Organization

```
server/data/models/<model_id>/
├── metadata.json              # Model metadata (paths & view references)
├── source.step                # Original STEP file
├── preview.glb                # 3D mesh for viewer
├── views/                     # FreeCAD tessellation wireframes
│   ├── top.png
│   ├── bottom.png
│   ├── left.png
│   └── right.png
├── shape2d/                   # FreeCAD Shape2D outlines
│   ├── top.png
│   ├── side.png
│   └── bottom.png
├── occ_views/                 # OCC HLR silhouettes
│   ├── x.png
│   ├── y.png
│   └── z.png
└── mid_views/                 # OCC mid-plane sections
    ├── mid_x.png
    ├── mid_y.png
    └── mid_z.png
```

---

## Frontend State Management (App.tsx)

The `App` component maintains:
- `model` – Current model ID, preview URL, original name
- `views` – FreeCAD tessellation view URLs
- `shapeViews` – FreeCAD Shape2D view URLs
- `occViews` – OCC HLR view URLs
- `midViews` – OCC mid-plane view URLs
- `busyAction` – Current operation (e.g., "Importing", "Generating Views")
- `statusMessage` – User-facing operation status
- `logMessage` – Last operation result

All API URLs are prefixed with `VITE_API_BASE_URL` (configured for Netlify deployments).

---

## Error Handling

- **CADProcessingError** (Backend) – Raised by FreeCAD or OCC operations (parsing, tessellation, HLR failures)
- **HTTPException 404** – Model not found or view not yet generated
- **HTTPException 500** – Processing failed (details in response body)
- **Frontend** – Catches errors and displays in status/log messages

---

## CORS & Deployment

- Backend enables CORS for all origins (`allow_origins=["*"]`)
- Frontend configured via `VITE_API_BASE_URL` environment variable
- For Netlify: set `VITE_API_BASE_URL=https://your-backend-domain`
- For local dev: defaults to `http://localhost:8000`
