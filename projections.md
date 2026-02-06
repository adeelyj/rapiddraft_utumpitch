# Projection Pipelines

## FreeCAD Tessellation Views (Top/Bottom/Left/Right)

**File**: `server/cad_service.py` → `CADService` class

Generates blueprint-style wireframe projections by tessellating the 3D mesh and projecting triangle edges onto orthographic planes.

### Workflow

1. **Load STEP**  
   `_load_shape()` reads the uploaded `.step` file via `Part.read()`, creates a temporary FreeCAD document, and exposes the `Part::Feature` shape object.

2. **Tessellate geometry**  
   `_tessellate()` calls `shape.tessellate(linear_deflection)` and builds two numpy arrays:
   - `points: np.ndarray` shape `(N, 3)` – X/Y/Z coordinates
   - `triangles: np.ndarray` shape `(M, 3)` – triangle vertex indices

3. **Project to 2D**  
   For each configuration (Top/Bottom/Left/Right), `_project_points()` selects the appropriate axis pair (e.g., (X,Y) for Top), applies sign flips for drafting conventions, and normalizes to a unit square.

4. **Rasterize**  
   `_render_projection()` iterates over every triangle, converts its edges into a `LineCollection`, and renders with Matplotlib (`Agg` backend) into transparent PNGs saved under `<model>/views/<view>.png`.

### Entry Points
- `CADService.import_model()` – Called during upload; generates glTF preview via trimesh
- `CADService.generate_views()` – Called by `/api/models/{id}/views` endpoint
- Output: Dictionary `{ view_name: Path }` → `/api/models/{id}/views/{view_name}` URLs

---

## FreeCAD Shape2D Views (Top/Side/Bottom)

**File**: `server/cad_service.py` → `CADService` class

Generates outline-style views using FreeCAD's `Draft.makeShape2DView`, which produces 2D projections with reduced visual complexity.

### Workflow

1. **Create Shape2D**  
   For each projection direction (Top, Side, Bottom), `generate_shape2d_views()` calls `Draft.makeShape2DView(obj, direction)` to create a 2D representation.

2. **Discretize edges**  
   `_render_shape2d()` iterates over all edges in the resulting shape and discretizes them with `edge.discretize(50)`.

3. **Project & normalize**  
   Projected 2D edge segments are normalized to a unit square to ensure consistent framing.

4. **Rasterize**  
   Renders with Matplotlib into transparent PNGs saved under `<model>/shape2d/<view>.png`.

### Entry Points
- `CADService.generate_shape2d_views()` – Called by `/api/models/{id}/shape2d` endpoint
- Output: Dictionary `{ view_name: Path }` → `/api/models/{id}/shape2d/{view_name}` URLs

---

## OCC HLR Views (X/Y/Z Silhouettes)

**File**: `server/cad_service_occ.py` → `CADServiceOCC` class

Uses pythonocc-core's hidden-line removal (HLR) algorithm to generate clean silhouette views without tessellation artifacts.

### Workflow

1. **Load STEP**  
   `_load_shape()` reads the STEP file via `STEPControl_Reader` and transfers the shape.

2. **Run HLR projection**  
   For each direction (X, Y, Z), `_run_hlr()` sets up an `HLRAlgo_Projector` and executes `HLRBRep_Algo` to extract only visible edges.

3. **Discretize edges**  
   `_discretize_edge()` samples each edge using `GCPnts_QuasiUniformAbscissa` (~80 points); falls back to endpoints if sampling fails.

4. **Project to 2D**  
   `_project_points()` maps 3D edge points to 2D using per-view basis vectors (e.g., X view → YZ plane).

5. **Rasterize**  
   `_render_segments()` normalizes segments and renders with Matplotlib into transparent PNGs under `<model>/occ_views/<view>.png`.

### Entry Points
- `CADServiceOCC.generate_occ_views()` – Called by `/api/models/{id}/occ_views` endpoint
- Output: Dictionary `{ x, y, z }` → `/api/models/{id}/occ_views/{view}` URLs

---

## OCC Mid-Plane Section Views

**File**: `server/cad_service_occ.py` → `CADServiceOCC` class

Creates cross-section views by slicing the part at bounding-box midpoints along each axis.

### Workflow

1. **Compute bounding box**  
   Find min/max extents and calculate midpoints along X, Y, Z axes.

2. **Create mid-plane**  
   `_midplane_section_shape()` builds a plane through the midpoint with normal aligned to the axis.

3. **Section the part**  
   `BRepAlgoAPI_Section` intersects the part with the plane, returning only the intersection curves.

4. **Discretize & project**  
   Same as OCC HLR: sample edges and project to 2D using per-axis basis vectors.

5. **Rasterize**  
   Renders into transparent PNGs under `<model>/mid_views/mid_<axis>.png`.

### Entry Points
- `CADServiceOCC.generate_mid_views()` – Called by `/api/models/{id}/mid_views` endpoint
- Output: Dictionary `{ mid_x, mid_y, mid_z }` → `/api/models/{id}/mid_views/{view}` URLs

---

## Summary

| Type | Method | Views | API Endpoint |
| --- | --- | --- | --- |
| **Tessellation** | FreeCAD mesh + triangle projection | top, bottom, left, right | `/api/models/{id}/views` |
| **Shape2D** | FreeCAD Draft outlines | top, side, bottom | `/api/models/{id}/shape2d` |
| **OCC HLR** | Hidden-line removal silhouettes | x, y, z | `/api/models/{id}/occ_views` |
| **Mid-Plane** | Section curves at midpoints | mid_x, mid_y, mid_z | `/api/models/{id}/mid_views` |
