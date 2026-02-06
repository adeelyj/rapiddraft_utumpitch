# Projection Pipeline: OCC Hidden-Line Removal

**File**: `server/cad_service_occ.py`

This document details `CADServiceOCC`, which generates X/Y/Z drafting-style views using pythonocc-core's HLR (hidden-line removal) algorithm, plus mid-plane section views.

## Core Libraries

- **STEP import**: `STEPControl_Reader` reads `.step` files into OpenCascade `TopoDS_Shape` objects.
- **Hidden-Line Removal**: `HLRBRep_Algo` + `HLRBRep_HLRToShape` run projection along a given direction and return only visible edges.
- **Edge sampling**: `BRepAdaptor_Curve` + `GCPnts_QuasiUniformAbscissa` discretize edges into 3D points (~80 samples per edge; fallback to endpoints if sampling fails).
- **Projection & rasterizing**: Numpy projects sampled points onto view basis vectors; `matplotlib` + `LineCollection` render normalized line segments into PNGs.

## Orthographic Projections (generate_occ_views)

### Workflow

1. **Load STEP**  
   `_load_shape()` reads the STEP file via `STEPControl_Reader` and transfers roots into a single `TopoDS_Shape`.

2. **Run HLR for each view direction (X, Y, Z)**  
   - For each configured view (`x`, `y`, `z` in `_projection_table`):
     - `_run_hlr()` sets up an `HLRAlgo_Projector` with the view direction as the normal vector
     - Executes `HLRBRep_Algo` to run the hidden-line removal algorithm
     - `HLRBRep_HLRToShape(algo).VCompound()` extracts only the visible edges

3. **Discretize edges**  
   `_iter_edge_points()` walks every edge in the visible compound:
   - `_discretize_edge()` samples the curve using `GCPnts_QuasiUniformAbscissa` (aiming for ~80 points)
   - On failure, falls back to sampling just the start and end points
   - Edges with fewer than 2 points are skipped

4. **Project to 2D**  
   `_project_points()` maps 3D edge samples to 2D using per-view basis vectors:
   - X view: projects to YZ plane (basis_x=(0,1,0), basis_y=(0,0,1))
   - Y view: projects to XZ plane (basis_x=(1,0,0), basis_y=(0,0,1))
   - Z view: projects to XY plane (basis_x=(1,0,0), basis_y=(0,1,0))

5. **Rasterize linework**  
   `_render_segments()` normalizes all projected coordinates to a unit square, then renders segments with `LineCollection` into transparent PNGs under `<model>/occ_views/<view>.png`.

### Entry Point
- `CADServiceOCC.generate_occ_views(step_path, output_dir)` – Called by `/api/models/{id}/occ_views` endpoint
- **Output**: Dictionary `{x: Path, y: Path, z: Path}` mapping view names to PNG files

---

## Mid-Plane Section Views (generate_mid_views)

Creates cross-sectional views by slicing the part at its bounding-box midpoints.

### Workflow

1. **Compute bounding box**  
   `_bounding_box()` calculates the part's min/max extents (6 floats: xmin, ymin, zmin, xmax, ymax, zmax).

2. **Calculate midpoints**  
   For each axis (X, Y, Z), compute the midpoint: `mid = (min + max) / 2`.

3. **For each axis**:
   - **Create mid-plane**: `_midplane_section_shape()` builds a plane through the midpoint with normal aligned to the axis
   - **Section the part**: `BRepAlgoAPI_Section` intersects the part with the plane
   - **Extract intersection**: The result contains all curves where the part crosses the plane
   - **Discretize edges**: Same as HLR—sample edges using `GCPnts_QuasiUniformAbscissa`
   - **Project to 2D**: Using per-axis basis vectors (same as HLR projection tables)
   - **Rasterize**: Render into transparent PNG under `<model>/mid_views/mid_<axis>.png`

### Entry Point
- `CADServiceOCC.generate_mid_views(step_path, output_dir)` – Called by `/api/models/{id}/mid_views` endpoint
- **Output**: Dictionary `{mid_x: Path, mid_y: Path, mid_z: Path}` mapping view names to PNG files

---

## View Mapping

| View | Direction | Projection Plane | Basis X | Basis Y |
| --- | --- | --- | --- | --- |
| **x** | (1, 0, 0) | YZ | (0, 1, 0) | (0, 0, 1) |
| **y** | (0, 1, 0) | XZ | (1, 0, 0) | (0, 0, 1) |
| **z** | (0, 0, 1) | XY | (1, 0, 0) | (0, 1, 0) |

---

## Error Handling

- **Empty HLR output**: If the HLR algorithm produces no visible edges, `CADProcessingError` is raised.
- **Edge sampling failure**: If `GCPnts_QuasiUniformAbscissa` fails, the code falls back to extracting start/end points only.
- **No segments to render**: If after discretization no line segments remain, `CADProcessingError` is raised.

---

## Input / Output

- **Input**: Absolute path to the uploaded STEP file (`Path`)
- **Output (HLR)**: Dictionary `{ x: Path, y: Path, z: Path }` → FastAPI exposes at `/api/models/{id}/occ_views/{view}`
- **Output (Mid-Plane)**: Dictionary `{ mid_x: Path, mid_y: Path, mid_z: Path }` → FastAPI exposes at `/api/models/{id}/mid_views/{view}`

All logic is encapsulated in `server/cad_service_occ.py` and reusable independently of FreeCAD tessellation methods.
