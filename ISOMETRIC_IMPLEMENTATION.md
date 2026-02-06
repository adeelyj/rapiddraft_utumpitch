# Isometric Views Implementation Summary

## What Was Added

### Backend Changes

#### 1. **cad_service.py** - Two new isometric view generation methods:

**`generate_isometric_shape2d_view()`**
- Uses FreeCAD's `Draft.makeShape2DView` with isometric direction vector `(1, 1, 1)`
- Creates a Shape2D projection with custom isometric perspective
- Renders via `_render_shape2d()` to PNG

**`generate_isometric_matplotlib_view()`**
- Tessellates the STEP model with FreeCAD
- Applies mathematical isometric projection using basis vectors:
  - X-basis: `(1, -1, 0) / √2` 
  - Y-basis: `(1, 1, -2) / √6`
- Projects all triangle vertices onto isometric plane
- Renders wireframe via `_render_projection()` to PNG

#### 2. **model_store.py** - Extended metadata:
- Added `isometric_shape2d: Dict[str, Path]` field
- Added `isometric_matplotlib: Dict[str, Path]` field
- Updated `to_dict()` and `from_dict()` methods to persist isometric views

#### 3. **main.py** - Four new REST endpoints:
- `POST /api/models/{id}/isometric_shape2d` - Generate Shape2D isometric view
- `GET /api/models/{id}/isometric_shape2d/{view_name}` - Fetch Shape2D PNG
- `POST /api/models/{id}/isometric_matplotlib` - Generate matplotlib isometric view
- `GET /api/models/{id}/isometric_matplotlib/{view_name}` - Fetch matplotlib PNG

### Frontend Changes

#### 1. **App.tsx** - Updated state and handlers:
- Added `isometricShape2DViews` state
- Added `isometricMatplotlibViews` state
- Added `generateIsometricShape2D()` async handler
- Added `generateIsometricMatplotlib()` async handler
- Added URL mappers for both isometric view types
- Updated Toolbar and ViewsPanel props to pass isometric data

#### 2. **Toolbar.tsx** - Two new action buttons:
- "Gen Iso Shape2D" button - Calls `generateIsometricShape2D`
- "Gen Iso Matplotlib" button - Calls `generateIsometricMatplotlib`
- Added handlers to component destructuring

#### 3. **ViewsPanel.tsx** - Isometric section at top:
- Added "Isometric Views" section **above all other view sections**
- Displays both isometric views side-by-side
- Labels: "isometric_shape2d (Shape2D)" and "isometric_matplotlib (MPL)"
- Added new state props and constants for isometric views

## File Organization

```
server/data/models/<model_id>/
├── isometric_shape2d/
│   └── isometric_shape2d.png      # Draft.makeShape2DView(1,1,1)
├── isometric_matplotlib/
│   └── isometric_matplotlib.png   # Tessellation + isometric projection
└── [other view directories...]
```

## UI Layout

The ViewsPanel now displays sections in this order:
1. **Isometric Views** ← NEW (Shape2D + Matplotlib side-by-side)
2. Mesh Views (Top, Bottom, Left, Right)
3. Shape2D Views (Top, Side, Bottom)
4. OCC Views (X, Y, Z)
5. Mid Views (Mid-X, Mid-Y, Mid-Z)

## Technical Details

### Isometric Projection Math

For the matplotlib isometric view, we use standard isometric projection basis vectors:

- **X-axis (width)**: `(1, -1, 0) / √2` - represents depth and width equally
- **Y-axis (height)**: `(1, 1, -2) / √6` - represents all three axes with emphasis on vertical

This creates a true orthographic isometric projection where the part is viewed at 30° from horizontal.

### Shape2D Isometric

Uses FreeCAD's Draft module with direction vector `FreeCAD.Vector(1, 1, 1)` which FreeCAD interprets as an isometric viewing direction.

## API Summary

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/models/{id}/isometric_shape2d` | POST | Generate isometric Shape2D view |
| `/api/models/{id}/isometric_shape2d/{view}` | GET | Fetch isometric Shape2D PNG |
| `/api/models/{id}/isometric_matplotlib` | POST | Generate isometric matplotlib view |
| `/api/models/{id}/isometric_matplotlib/{view}` | GET | Fetch isometric matplotlib PNG |

## Testing

1. Import a STEP file
2. Click "Gen Iso Shape2D" - Creates Shape2D isometric view
3. Click "Gen Iso Matplotlib" - Creates tessellation-based isometric view
4. Both views appear in the "Isometric Views" section at top of ViewsPanel
5. Export includes both isometric views in the ZIP
