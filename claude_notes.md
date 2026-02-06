# Claude Notes - TextCAD Drafting Service

## Architecture Overview

Two-tier application: **Python/FastAPI backend** (port 8000) + **React/Vite frontend** (port 5173).
The backend processes STEP CAD files into 3D previews and 2D projection PNGs.
The frontend displays them in a 3D viewer and an interactive drawing page.

---

## Backend

### Entry Point: `server/main.py`

FastAPI app with CORS open to all origins. Instantiates three service objects:

- `CADService` (FreeCAD-based) - workspace at `server/data/processing/`
- `CADServiceOCC` (pythonocc-based) - workspace at `server/data/processing/occ/`
- `ModelStore` - persistence at `server/data/models/`

### REST API Endpoints

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/template/drawing` | Serves the A4 ISO drawing template PNG from `/template/` |
| POST | `/api/models` | Upload STEP file, generate GLB preview via FreeCAD+Trimesh |
| GET | `/api/models/{id}/preview` | Stream the GLB file |
| POST | `/api/models/{id}/views` | Generate 4 orthographic wireframe PNGs (FreeCAD tessellation) |
| GET | `/api/models/{id}/views/{name}` | Fetch a wireframe PNG |
| GET | `/api/models/{id}/views/{name}/metadata` | Fetch wireframe JSON metadata (vertices, edges, bounds) |
| POST | `/api/models/{id}/shape2d` | Generate 3 Shape2D outline PNGs (FreeCAD Draft module) |
| GET | `/api/models/{id}/shape2d/{name}` | Fetch a Shape2D PNG |
| GET | `/api/models/{id}/shape2d/{name}/metadata` | Fetch Shape2D JSON metadata (segments, bounds) |
| POST | `/api/models/{id}/occ_views` | Generate 3 HLR silhouette PNGs (pythonocc hidden-line removal) |
| GET | `/api/models/{id}/occ_views/{name}` | Fetch an OCC view PNG |
| POST | `/api/models/{id}/mid_views` | Generate 3 mid-plane cross-section PNGs (pythonocc) |
| GET | `/api/models/{id}/mid_views/{name}` | Fetch a mid-view PNG |
| POST | `/api/models/{id}/isometric_shape2d` | Generate isometric view via FreeCAD Shape2D with direction (1,1,1) |
| GET | `/api/models/{id}/isometric_shape2d/{name}` | Fetch isometric Shape2D PNG |
| POST | `/api/models/{id}/isometric_matplotlib` | Generate isometric view via tessellation + matrix projection |
| GET | `/api/models/{id}/isometric_matplotlib/{name}` | Fetch isometric matplotlib PNG |
| POST | `/api/models/{id}/export` | Download all wireframe views as a ZIP |

### `server/model_store.py` - Persistence Layer

- `ModelMetadata` dataclass: holds model_id, original_name, step_path, preview_path, and dicts of Path objects for every view type (views, shape_views, occ_views, mid_views, isometric variants, plus metadata JSON paths).
- `ModelStore` class: creates UUID-based directories under `server/data/models/`, reads/writes `metadata.json` per model.
- Flow: `create()` generates UUID dir + writes initial metadata -> `get()` reads it back -> `update()` saves after views are generated.

### `server/cad_service.py` - FreeCAD Processing (the main CAD engine)

**Libraries used:**
- **FreeCAD** (`import FreeCAD, Part, Draft`): Loads STEP files, tessellates shapes, creates Shape2DView projections.
- **NumPy**: All point/triangle data as arrays, projection math, normalization.
- **Matplotlib** (Agg backend): Renders wireframes to PNG using `LineCollection`. All figures are 5x5 inches at 300 DPI with transparent background.
- **Trimesh**: Converts tessellated mesh (vertices + faces) to GLB format for browser 3D preview.

**Key methods:**

1. `_load_shape(step_path)` - Opens STEP via `Part.read()`, creates a FreeCAD document with the shape.

2. `_tessellate(shape_obj)` - Calls `shape.tessellate(linear_deflection=0.25)` to get vertices and triangle indices as numpy arrays.

3. `_project_points(points, axis_pair, invert_x, invert_y)` - Projects 3D points to 2D by selecting two axes (e.g., axes 0,1 for top view = XY plane). Normalizes to [0,1] unit box. Returns normalized points + min/max bounds for metadata.

4. `_render_projection(projected, triangles, out_path)` - Draws triangle edges as `LineCollection` on matplotlib, saves PNG. Color: `#102542`, linewidth 0.6.

5. `_render_shape2d(shape, out_path)` - Discretizes FreeCAD Shape2DView edges (50 samples per edge), normalizes, draws with `LineCollection`. Color: `#0f223a`, linewidth 0.7.

6. `import_model(step_path, gltf_path)` - Full pipeline: load STEP -> tessellate -> export GLB via Trimesh.

7. `generate_views(step_path, output_dir)` - Produces 4 views using the projection table:
   - **top**: axes (0,1) = XY plane
   - **bottom**: axes (0,1), Y inverted
   - **left**: axes (2,1) = ZY plane, X inverted
   - **right**: axes (2,1) = ZY plane
   - Also writes JSON metadata per view with: projected_vertices (normalized), edges (index pairs), bounds (min/max in model units).

8. `generate_shape2d_views(step_path, output_dir)` - Uses FreeCAD's `Draft.makeShape2DView()` with 3 direction vectors:
   - **top**: (0,0,1)
   - **side**: (1,0,0)
   - **bottom**: (0,0,-1)
   - Writes JSON metadata with normalized segments and bounds.

9. `generate_isometric_shape2d_view()` - Same as Shape2D but with direction (1,1,1).

10. `generate_isometric_matplotlib_view()` - Projects tessellated mesh using isometric basis vectors:
    - X-basis: `(1,-1,0)/sqrt(2)`
    - Y-basis: `(1,1,-2)/sqrt(6)`
    - Then renders the projected wireframe.

### `server/cad_service_occ.py` - pythonocc Processing

**Libraries used:**
- **pythonocc-core** (`OCC.Core.*`): STEP reading, Hidden-Line Removal (HLR), edge discretization, bounding box, mid-plane sectioning.
- **NumPy**: Point projection math.
- **Matplotlib**: Same rendering pattern as cad_service.

**Key methods:**

1. `_load_shape(step_path)` - Reads STEP via `STEPControl_Reader`.

2. `_run_hlr(shape, direction)` - Runs OCC's Hidden-Line Removal algorithm:
   - Creates `HLRAlgo_Projector` with view direction
   - Feeds shape to `HLRBRep_Algo`
   - Calls `Update()` then `Hide()` to compute visibility
   - Returns `VCompound()` (visible edges only)

3. `_discretize_edge(edge)` - Samples each edge curve at 80 points using `GCPnts_QuasiUniformAbscissa`. Falls back to just endpoints if sampling fails.

4. `_project_points(points, basis_x, basis_y)` - Dot-product projection onto 2D plane using basis vectors.

5. `_render_segments(segments, out_path)` - Normalizes all segments to [0,1] box, renders with matplotlib. Color: `#0e1e2f`, linewidth 0.7.

6. `_midplane_section_shape(shape, axis, normal, origin, span)` - Creates a cutting plane at the bounding box midpoint, intersects it with the shape using `BRepAlgoAPI_Section`.

7. `generate_occ_views(step_path, output_dir)` - HLR views for 3 axes:
   - **x**: direction (1,0,0), projects onto YZ plane
   - **y**: direction (0,1,0), projects onto XZ plane
   - **z**: direction (0,0,1), projects onto XY plane

8. `generate_mid_views(step_path, output_dir)` - Computes bounding box, finds midpoints, creates section cuts for each axis, then discretizes and renders the intersection curves.

### `server/freecad_setup.py` - FreeCAD Path Discovery

- `discover_freecad_libs()`: Checks `FREECAD_LIB` env var, then scans `Program Files/FreeCAD*` for lib dirs.
- `discover_freecad_bins()`: Checks `FREECAD_BIN` env var, then scans for bin dirs.
- `ensure_freecad_in_path()`: Injects discovered paths into `sys.path` and `os.environ["PATH"]`.
- Important: FreeCAD 1.0 ships `FreeCAD.pyd` in the `bin/` directory, not `lib/`.

---

## Frontend

### `web/src/App.tsx` - Root Component & State Manager

Central state management using React `useState`. Manages:

- **model**: current uploaded model (id, previewUrl, originalName)
- **views/shapeViews/occViews/midViews/isometric variants**: Record<string, string> of view name -> API URL
- **viewMetadata/shapeViewMetadata/isometric metadata**: same pattern for JSON metadata URLs
- **busyAction/statusMessage/logMessage**: UI feedback state
- **drawingZones**: array of `DrawingZone` objects (id, src, layout as {x,y,w,h in 0-1 normalized}, viewName, metadataUrl)
- **dimensions**: array of `Dimension` objects (id, zoneId, two endpoints with norm+world coords, distance, label)
- **isDrawingOpen**: toggles between 3D viewer and drawing page

**Data flow for each action:**
1. `importModel(file)` -> POST `/api/models` with FormData -> receives modelId + previewUrl -> stores in state, clears all views
2. `generateViews()` -> POST `/api/models/{id}/views` -> receives view URLs -> stores in state
3. Same pattern for Shape2D, OCC, Mid, Isometric views
4. `exportViews()` -> POST `/api/models/{id}/export` -> downloads ZIP blob

**Drawing state persistence:** Saves zones + dimensions to `localStorage` under key `drawingState`.

**Thumbnail assignment flow:** When a zone is pending (user clicked a zone), clicking a thumbnail in ViewsPanel calls `handleSelectThumbnailForAssignment()` which sets the zone's `src` and `metadataUrl`.

### `web/src/components/Toolbar.tsx` - Action Bar

Renders toolbar with:
- Brand name + status message
- Hidden file input (`.step/.stp` only) triggered by "Import STEP" button
- 7 generation buttons (Mesh Views, Shape2D, OCC, Mid, Iso Shape2D, Iso Matplotlib, Export)
- All buttons disabled during busy state; generation buttons disabled until a model is loaded
- Uses `clsx` for conditional CSS classes

### `web/src/components/ModelViewer.tsx` - 3D Preview

- Uses **React Three Fiber** (`@react-three/fiber`) + **drei** utilities
- Loads GLB via `GLTFLoader` from Three.js
- `FitCamera` component: computes bounding box of loaded model, positions camera at 1.5x the bounding distance along (1,1,1) direction
- Scene: ambient light (0.7) + directional light + "city" environment preset
- `OrbitControls` for mouse interaction
- "Create Drawing" button transitions to DrawingPage
- "Fit to screen" button re-triggers camera fit

### `web/src/components/ViewsPanel.tsx` - Thumbnail Sidebar

Right-side panel displaying all generated views in categorized grids:
- Isometric Views, Mesh Views, Shape2D Views, OCC Views, Mid Views
- Each view shown as a `ViewCard` (label + image or "Awaiting generation" placeholder)
- Clicking a thumbnail calls `onSelectThumbnail(name, src, metadataUrl)` to assign it to the pending drawing zone
- Views with metadata are labeled "(with md)"

### `web/src/components/DrawingPage.tsx` - Interactive Drawing Canvas

The most complex frontend component. Provides an engineering drawing workspace:

**Template:** Background image is the A4 ISO 5457 template fetched from `/api/template/drawing`.

**Zone System (normalized 0-1 coordinates):**
- Users create zones by clicking "Insert Zone" then dragging a rectangle on the canvas
- Zones can be moved/resized in "Edit Zones" mode (pointer drag with move/resize handles)
- Each zone can display an assigned projection image (from ViewsPanel thumbnails)
- Zones persist in App state and localStorage

**Measurement/Dimension System:**
- "Measure" mode enables click-to-measure on zones that have metadata
- `ensureMetadata(zone)` fetches the JSON metadata URL and caches parsed snap points
- `parseMetadata(raw)` extracts snap points from two formats:
  - `projected_vertices` + `edges` format: creates vertex points + edge midpoints
  - `segments` format: creates vertex + midpoint per segment
- `findNearestSnap()`: finds closest snap point within 0.08 normalized threshold
- Two clicks create a dimension: first click sets point A, second click sets point B
- Dimensions displayed as SVG overlay lines with distance labels
- Dimensions can be selected (click) and deleted (Delete/Backspace key)

**Coordinate System:**
- All zone layouts stored as normalized (0-1) percentages of the canvas
- `toPx()`: converts normalized coords to pixel coords, accounting for aspect-ratio letterboxing of images
- `fromClientToNorm()`: converts mouse client coords back to normalized coords
- World coordinates derived from metadata bounds: `world = min + norm * span`

**Export:** "Export PNG" composites everything onto a canvas:
1. Draws the template background at full resolution
2. For each zone: loads its image, computes letterboxed position, draws it
3. For each dimension: draws line, endpoint circles, and labeled distance box
4. Triggers browser download of the final PNG

**Keyboard shortcuts:** Delete/Backspace deletes selected dimension or zone.

---

## Data Flow Summary

```
User uploads .step file
        |
        v
POST /api/models
        |
        v
FreeCAD loads STEP -> tessellates -> Trimesh exports GLB
        |
        v
Frontend shows 3D preview (Three.js)
        |
        v
User clicks generation buttons
        |
        +---> "Gen Mesh View"     -> FreeCAD tessellation -> project onto 4 planes -> matplotlib PNGs + JSON metadata
        +---> "Gen Shape2D Views" -> FreeCAD Draft.makeShape2DView -> 3 outline PNGs + JSON metadata
        +---> "Gen OCC Views"     -> pythonocc HLR -> 3 silhouette PNGs (no metadata)
        +---> "Gen Mid View"      -> pythonocc BRepAlgoAPI_Section at bbox midpoints -> 3 section PNGs (no metadata)
        +---> "Gen Iso Shape2D"   -> FreeCAD Draft.makeShape2DView with (1,1,1) -> 1 PNG + JSON metadata
        +---> "Gen Iso Matplotlib"-> tessellation + isometric matrix projection -> 1 PNG + JSON metadata
        |
        v
ViewsPanel shows thumbnails
        |
        v
User creates drawing zones on A4 template
        |
        v
User assigns thumbnails to zones (click zone, click thumbnail)
        |
        v
User measures dimensions (snap to vertices/midpoints from metadata)
        |
        v
Export PNG composites template + views + dimensions
```

## Library Responsibility Map

| Library | What it does in this project |
|---------|------------------------------|
| **FreeCAD** (Part, Draft) | Loads STEP files, tessellates to triangles, generates Shape2DView outlines |
| **pythonocc-core** (OCC) | Loads STEP files independently, runs HLR for clean silhouettes, creates mid-plane section cuts |
| **Trimesh** | Converts FreeCAD tessellation (vertices+faces) to GLB for browser 3D preview |
| **Matplotlib** (Agg) | Renders all 2D views as PNG images using LineCollection |
| **NumPy** | Array operations for vertices/triangles, projection math, normalization |
| **FastAPI** | REST API framework, file upload handling, CORS |
| **Uvicorn** | ASGI server running FastAPI |
| **React Three Fiber** | React wrapper for Three.js, renders GLB 3D preview |
| **Three.js** (GLTFLoader) | Loads GLB files, provides 3D scene graph |
| **@react-three/drei** | OrbitControls, Center, Environment helpers for 3D scene |

## Key Design Decisions

1. **Two separate CAD engines**: FreeCAD for tessellation/Shape2D, pythonocc for HLR/sections. They load STEP files independently.
2. **All 2D views are pre-rendered PNGs**: No real-time SVG generation. Matplotlib runs server-side.
3. **Metadata JSON enables client-side measurement**: Vertex/segment data with bounds allows the frontend to snap to geometry points and compute world-space distances.
4. **Normalized coordinate system**: Everything (zone layouts, snap points, dimension endpoints) uses 0-1 normalized coordinates relative to their container, making the system resolution-independent.
5. **No database**: Pure filesystem storage with JSON metadata files. Models identified by UUID directory names.
6. **Stateless API**: Each request loads the STEP file fresh. No in-memory model cache between requests.
