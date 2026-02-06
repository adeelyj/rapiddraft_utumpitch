"""
Utility helpers for processing CAD data with FreeCAD.

All heavy lifting is intentionally isolated from the API layer so that the FastAPI
application can stay responsive and FreeCAD specific imports remain optional until
the first CAD task is executed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
import json
import logging

import numpy as np
import trimesh

import matplotlib

# Force a headless friendly backend before pyplot is imported.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from .freecad_setup import ensure_freecad_in_path

ensure_freecad_in_path()

logger = logging.getLogger(__name__)


class CADProcessingError(RuntimeError):
    """Raised when the FreeCAD pipeline fails."""


@dataclass
class ProjectionConfig:
    """Configuration for a single orthographic projection."""

    axis_pair: Tuple[int, int]
    invert_x: bool = False
    invert_y: bool = False
    label: str = ""


class CADService:
    """
    Coordinates CAD imports, preview mesh generation, and 2D projections.

    Parameters
    ----------
    workspace : Path
        Root directory where intermediate files are written.
    linear_deflection : float
        Controls tessellation resolution passed to FreeCAD. Smaller values produce
        higher quality meshes at the cost of longer runtime.
    """

    def __init__(self, workspace: Path, linear_deflection: float = 0.25) -> None:
        self.workspace = workspace
        self.linear_deflection = linear_deflection
        self.workspace.mkdir(parents=True, exist_ok=True)

        self._projection_table: Dict[str, ProjectionConfig] = {
            "top": ProjectionConfig(axis_pair=(0, 1), label="Top"),
            "bottom": ProjectionConfig(axis_pair=(0, 1), invert_y=True, label="Bottom"),
            "left": ProjectionConfig(axis_pair=(2, 1), invert_x=True, label="Left"),
            "right": ProjectionConfig(axis_pair=(2, 1), label="Right"),
        }

    # ------------------------------------------------------------------ helpers
    def _load_shape(self, step_path: Path):
        """
        Uses FreeCAD to load a STEP file and returns the document + shape object.
        """
        try:
            import FreeCAD  # type: ignore
            import Part  # type: ignore
        except ImportError as exc:  # pragma: no cover - requires FreeCAD
            raise CADProcessingError(
                "The FreeCAD Python modules are required. Please install FreeCAD "
                "and ensure its site-packages directory is on PYTHONPATH."
            ) from exc

        logger.info("Loading STEP file from %s", step_path)
        doc = FreeCAD.newDocument("ImportDoc")
        shape = Part.read(str(step_path))
        obj = doc.addObject("Part::Feature", "ImportedShape")
        obj.Shape = shape
        doc.recompute()
        return doc, obj

    def _tessellate(self, shape_obj) -> Tuple[np.ndarray, np.ndarray]:
        """Extract triangle mesh data from the FreeCAD shape."""
        shape = shape_obj.Shape
        pts, tri = shape.tessellate(self.linear_deflection)

        points = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64)
        triangles = np.array(tri, dtype=np.int32)
        logger.debug("Tessellated mesh with %s points and %s triangles", points.shape[0], triangles.shape[0])
        return points, triangles

    def _project_points(
        self,
        points: np.ndarray,
        axis_pair: Tuple[int, int],
        invert_x: bool,
        invert_y: bool,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Project a 3D point cloud onto a 2D plane."""
        projected = np.stack([points[:, axis_pair[0]], points[:, axis_pair[1]]], axis=1)
        if invert_x:
            projected[:, 0] *= -1
        if invert_y:
            projected[:, 1] *= -1
        # Normalize to unit box for consistent framing.
        min_vals = projected.min(axis=0)
        max_vals = projected.max(axis=0)
        span = np.clip(max_vals - min_vals, 1e-5, None)
        normalized = (projected - min_vals) / span
        return normalized, min_vals, max_vals

    def _render_projection(self, projected: np.ndarray, triangles: np.ndarray, out_path: Path) -> None:
        """Create a blueprint style PNG from projected wireframe data."""
        fig, ax = plt.subplots(figsize=(5, 5), dpi=300)
        lines = []
        for tri in triangles:
            tri_pts = projected[tri]
            lines.append([tri_pts[0], tri_pts[1]])
            lines.append([tri_pts[1], tri_pts[2]])
            lines.append([tri_pts[2], tri_pts[0]])

        collection = LineCollection(lines, colors="#102542", linewidths=0.6)
        ax.add_collection(collection)
        ax.set_aspect("equal", "box")
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        fig.tight_layout(pad=0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, transparent=True, bbox_inches="tight", pad_inches=0)
        plt.close(fig)

    def _collect_edges(self, triangles: np.ndarray) -> List[Tuple[int, int]]:
        edges = set()
        for a, b, c in triangles:
            edges.add(tuple(sorted((int(a), int(b)))))
            edges.add(tuple(sorted((int(b), int(c)))))
            edges.add(tuple(sorted((int(c), int(a)))))
        return sorted(edges)

    def _render_shape2d(self, shape, out_path: Path) -> None:
        """
        Render a 2D Draft/Shape2DView result to PNG by discretizing all edges.
        """
        segments: List[List[List[float]]] = []
        all_points: List[List[float]] = []

        for edge in getattr(shape, "Edges", []):
            pts = edge.discretize(50)
            for a, b in zip(pts, pts[1:]):
                pair = [[a.x, a.y], [b.x, b.y]]
                segments.append(pair)
                all_points.extend(pair)

        if not all_points:  # nothing to draw
            return

        coords = np.array(all_points, dtype=np.float64)
        min_vals = coords.min(axis=0)
        max_vals = coords.max(axis=0)
        span = np.clip(max_vals - min_vals, 1e-5, None)

        norm_segments = []
        for a, b in segments:
            a_norm = (np.array(a) - min_vals) / span
            b_norm = (np.array(b) - min_vals) / span
            norm_segments.append([a_norm, b_norm])

        fig, ax = plt.subplots(figsize=(5, 5), dpi=300)
        collection = LineCollection(norm_segments, colors="#0f223a", linewidths=0.7)
        ax.add_collection(collection)
        ax.set_aspect("equal", "box")
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        fig.tight_layout(pad=0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, transparent=True, bbox_inches="tight", pad_inches=0)
        plt.close(fig)

    # ------------------------------------------------------------------ public API
    def import_model(self, step_path: Path, gltf_path: Path) -> Path:
        """
        Loads a STEP file and exports a glTF mesh for browser consumption.

        The exported file is returned so FastAPI can stream it directly.
        """
        doc, obj = self._load_shape(step_path)
        try:
            points, triangles = self._tessellate(obj)
        finally:
            try:
                import FreeCAD  # type: ignore

                FreeCAD.closeDocument(doc.Name)
            except Exception:  # pragma: no cover
                pass

        gltf_path.parent.mkdir(parents=True, exist_ok=True)
        mesh = trimesh.Trimesh(vertices=points, faces=triangles, process=False)
        try:
            mesh.export(gltf_path, file_type="glb")
        except Exception as exc:
            raise CADProcessingError(f"Failed to export preview glTF: {exc}") from exc

        return gltf_path

    def generate_views(self, step_path: Path, output_dir: Path) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        """
        Create orthographic projections for drafting style previews.
        """
        doc, obj = self._load_shape(step_path)
        try:
            points, triangles = self._tessellate(obj)
        finally:
            try:
                import FreeCAD  # type: ignore

                FreeCAD.closeDocument(doc.Name)
            except Exception:  # pragma: no cover
                pass

        results: Dict[str, Path] = {}
        meta: Dict[str, Path] = {}
        for key, config in self._projection_table.items():
            projected, min_vals, max_vals = self._project_points(points, config.axis_pair, config.invert_x, config.invert_y)
            out_path = output_dir / f"{key}.png"
            self._render_projection(projected, triangles, out_path)
            results[key] = out_path
            edges = self._collect_edges(triangles)
            meta_payload = {
                "type": "orthographic",
                "axis_pair": config.axis_pair,
                "invert_x": config.invert_x,
                "invert_y": config.invert_y,
                "bounds": {"min": min_vals.tolist(), "max": max_vals.tolist()},
                "projected_vertices": projected.tolist(),
                "edges": edges,
            }
            meta_path = output_dir / f"{key}.json"
            meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
            meta[key] = meta_path
        return results, meta

    def serialize_view_metadata(self, views: Dict[str, Path]) -> Dict[str, str]:
        """Convert raw paths to metadata payloads for HTTP responses."""
        payload = {name: str(path) for name, path in views.items()}
        return payload

    def generate_shape2d_views(self, step_path: Path, output_dir: Path) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        """
        Use FreeCAD's Draft Shape2DView to derive plan/side/bottom outlines.
        """
        try:
            import FreeCAD  # type: ignore
            import Draft  # type: ignore
        except ImportError as exc:  # pragma: no cover - requires FreeCAD
            raise CADProcessingError(
                "The FreeCAD Python modules are required. Please install FreeCAD "
                "and ensure its site-packages directory is on PYTHONPATH."
            ) from exc

        doc, obj = self._load_shape(step_path)
        results: Dict[str, Path] = {}
        meta: Dict[str, Path] = {}
        try:
            axis_map = {
                "top": FreeCAD.Vector(0, 0, 1),
                "side": FreeCAD.Vector(1, 0, 0),
                "bottom": FreeCAD.Vector(0, 0, -1),
            }
            for name, direction in axis_map.items():
                view_obj = Draft.makeShape2DView(obj, direction)
                doc.recompute()
                out_path = output_dir / f"{name}.png"
                self._render_shape2d(view_obj.Shape, out_path)
                results[name] = out_path
                # collect normalized segments by recomputing discretization similar to _render_shape2d
                segments: List[List[List[float]]] = []
                all_points: List[List[float]] = []
                for edge in getattr(view_obj.Shape, "Edges", []):
                    pts = edge.discretize(50)
                    for a, b in zip(pts, pts[1:]):
                        pair = [[a.x, a.y], [b.x, b.y]]
                        segments.append(pair)
                        all_points.extend(pair)
                if all_points:
                    coords = np.array(all_points, dtype=np.float64)
                    min_vals = coords.min(axis=0)
                    max_vals = coords.max(axis=0)
                    span = np.clip(max_vals - min_vals, 1e-5, None)
                    norm_segments = []
                    for a, b in segments:
                        a_norm = (np.array(a) - min_vals) / span
                        b_norm = (np.array(b) - min_vals) / span
                        norm_segments.append([a_norm.tolist(), b_norm.tolist()])
                    meta_payload = {
                        "type": "shape2d",
                        "direction": [direction.x, direction.y, direction.z],
                        "bounds": {"min": min_vals.tolist(), "max": max_vals.tolist()},
                        "segments": norm_segments,
                    }
                    meta_path = output_dir / f"{name}.json"
                    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
                    meta[name] = meta_path
                doc.removeObject(view_obj.Name)
        finally:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:  # pragma: no cover
                pass

        return results, meta

    def generate_isometric_shape2d_view(self, step_path: Path, output_dir: Path) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        """
        Generate isometric view using FreeCAD's Draft Shape2DView with custom direction.
        Isometric direction: (1, 1, 1) normalized.
        """
        try:
            import FreeCAD  # type: ignore
            import Draft  # type: ignore
        except ImportError as exc:  # pragma: no cover - requires FreeCAD
            raise CADProcessingError(
                "The FreeCAD Python modules are required. Please install FreeCAD "
                "and ensure its site-packages directory is on PYTHONPATH."
            ) from exc

        doc, obj = self._load_shape(step_path)
        results: Dict[str, Path] = {}
        meta: Dict[str, Path] = {}
        try:
            # Isometric direction (normalized)
            iso_direction = FreeCAD.Vector(1, 1, 1)
            view_obj = Draft.makeShape2DView(obj, iso_direction)
            doc.recompute()
            out_path = output_dir / "isometric_shape2d.png"
            self._render_shape2d(view_obj.Shape, out_path)
            results["isometric_shape2d"] = out_path
            segments: List[List[List[float]]] = []
            all_points: List[List[float]] = []
            for edge in getattr(view_obj.Shape, "Edges", []):
                pts = edge.discretize(50)
                for a, b in zip(pts, pts[1:]):
                    pair = [[a.x, a.y], [b.x, b.y]]
                    segments.append(pair)
                    all_points.extend(pair)
            if all_points:
                coords = np.array(all_points, dtype=np.float64)
                min_vals = coords.min(axis=0)
                max_vals = coords.max(axis=0)
                span = np.clip(max_vals - min_vals, 1e-5, None)
                norm_segments = []
                for a, b in segments:
                    a_norm = (np.array(a) - min_vals) / span
                    b_norm = (np.array(b) - min_vals) / span
                    norm_segments.append([a_norm.tolist(), b_norm.tolist()])
                meta_payload = {
                    "type": "shape2d_isometric",
                    "direction": [iso_direction.x, iso_direction.y, iso_direction.z],
                    "bounds": {"min": min_vals.tolist(), "max": max_vals.tolist()},
                    "segments": norm_segments,
                }
                meta_path = output_dir / "isometric_shape2d.json"
                meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
                meta["isometric_shape2d"] = meta_path
            doc.removeObject(view_obj.Name)
        finally:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:  # pragma: no cover
                pass

        return results, meta

    def generate_isometric_matplotlib_view(self, step_path: Path, output_dir: Path) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        """
        Generate isometric view by projecting tessellated mesh onto isometric plane.
        Uses an isometric projection matrix: (1, 1, 1) direction normalized to create
        a 3D-like 2D view of the geometry.
        """
        doc, obj = self._load_shape(step_path)
        try:
            points, triangles = self._tessellate(obj)
        finally:
            try:
                import FreeCAD  # type: ignore
                FreeCAD.closeDocument(doc.Name)
            except Exception:  # pragma: no cover
                pass

        # Isometric projection: use all three axes with equal weight
        # Standard isometric: project onto plane perpendicular to (1, 1, 1)
        # We'll use a 2D projection by rotating to isometric view
        iso_basis_x = np.array([1, -1, 0], dtype=np.float64) / np.sqrt(2)  # X in isometric
        iso_basis_y = np.array([1, 1, -2], dtype=np.float64) / np.sqrt(6)   # Y in isometric
        
        # Project points
        projected = np.stack([
            points @ iso_basis_x,
            points @ iso_basis_y
        ], axis=1)
        
        # Normalize to unit box
        min_vals = projected.min(axis=0)
        max_vals = projected.max(axis=0)
        span = np.clip(max_vals - min_vals, 1e-5, None)
        normalized = (projected - min_vals) / span

        out_path = output_dir / "isometric_matplotlib.png"
        self._render_projection(normalized, triangles, out_path)
        
        results: Dict[str, Path] = {}
        results["isometric_matplotlib"] = out_path
        meta_payload = {
            "type": "isometric_matplotlib",
            "bounds": {"min": min_vals.tolist(), "max": max_vals.tolist()},
            "projected_vertices": normalized.tolist(),
            "edges": [[int(a), int(b)] for a, b in self._collect_edges(triangles)],
        }
        meta_path = output_dir / "isometric_matplotlib.json"
        meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
        meta: Dict[str, Path] = {"isometric_matplotlib": meta_path}
        return results, meta


def write_metadata(metadata_path: Path, payload: Dict) -> None:
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_metadata(metadata_path: Path) -> Dict:
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))
