"""
OCC-based view generation for plan projections using pythonocc-core.

Generates X/Y/Z plane views with OCC's hidden-line removal (HLR) to avoid mesh
artifacts. Visible edges are projected onto view planes and rasterized.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple
import logging
import re

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from .freecad_setup import ensure_freecad_in_path

ensure_freecad_in_path()

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCC.Core.HLRAlgo import HLRAlgo_Projector
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pln, gp_Pnt
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_SOLID
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.GCPnts import GCPnts_QuasiUniformAbscissa
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
from OCC.Core.TopoDS import topods

from .cad_service import CADProcessingError

logger = logging.getLogger(__name__)


class CADServiceOCC:
    """
    Builds simple orthographic wireframe renderings using pythonocc-core.
    """

    def __init__(self, workspace: Path, linear_deflection: float = 0.5) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        # View direction, and basis vectors used to project 3D points to 2D.
        self._projection_table: Dict[str, Dict[str, Tuple[float, float, float] | str]] = {
            "x": {"axis": "x", "dir": (1.0, 0.0, 0.0), "basis_x": (0.0, 1.0, 0.0), "basis_y": (0.0, 0.0, 1.0)},  # YZ
            "y": {"axis": "y", "dir": (0.0, 1.0, 0.0), "basis_x": (1.0, 0.0, 0.0), "basis_y": (0.0, 0.0, 1.0)},  # XZ
            "z": {"axis": "z", "dir": (0.0, 0.0, 1.0), "basis_x": (1.0, 0.0, 0.0), "basis_y": (0.0, 1.0, 0.0)},  # XY
        }

    # ------------------------------------------------------------------ internals
    def _load_shape(self, step_path: Path):
        reader = STEPControl_Reader()
        status = reader.ReadFile(str(step_path))
        if status != IFSelect_RetDone:
            raise CADProcessingError(f"Failed to read STEP file via OCC (status={status})")

        reader.TransferRoots()
        shape = reader.Shape()
        return shape

    def _bounding_box(self, shape) -> Tuple[float, float, float, float, float, float]:
        box = Bnd_Box()
        brepbndlib_Add(shape, box)
        return box.Get()

    def _run_hlr(self, shape, direction: Tuple[float, float, float]):
        projector = HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*direction)))
        algo = HLRBRep_Algo()
        algo.Add(shape)
        algo.Projector(projector)
        algo.Update()
        algo.Hide()

        hlr_shapes = HLRBRep_HLRToShape(algo)
        visible = hlr_shapes.VCompound()
        if visible.IsNull():
            raise CADProcessingError("OCC HLR produced no visible edges")
        return visible

    def _discretize_edge(self, edge) -> List[Tuple[float, float, float]]:
        # Sample curve with a reasonable number of points; fallback to endpoints.
        curve = BRepAdaptor_Curve(edge)
        samples: List[Tuple[float, float, float]] = []
        try:
            discretizer = GCPnts_QuasiUniformAbscissa(curve, 80)
            if discretizer.IsDone():
                for i in range(1, discretizer.NbPoints() + 1):
                    param = discretizer.Parameter(i)
                    pnt = curve.Value(param)
                    samples.append((pnt.X(), pnt.Y(), pnt.Z()))
        except Exception:
            # If OCC errors on curve sampling, ignore and fallback below.
            pass

        if not samples:
            try:
                first, last = curve.FirstParameter(), curve.LastParameter()
                p1, p2 = curve.Value(first), curve.Value(last)
                samples = [(p1.X(), p1.Y(), p1.Z()), (p2.X(), p2.Y(), p2.Z())]
            except Exception as exc:
                logger.debug("Failed to sample edge: %s", exc)
                return []
        return samples

    def _iter_edge_points(self, shape) -> Iterable[List[Tuple[float, float, float]]]:
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            pts = self._discretize_edge(edge)
            if len(pts) >= 2:
                yield pts
            explorer.Next()

    def _project_points(
        self, points: List[Tuple[float, float, float]], basis_x: Tuple[float, float, float], basis_y: Tuple[float, float, float]
    ) -> np.ndarray:
        bx = np.array(basis_x, dtype=np.float64)
        by = np.array(basis_y, dtype=np.float64)
        pts = np.array(points, dtype=np.float64)
        proj = np.stack([pts @ bx, pts @ by], axis=1)
        return proj

    def _render_segments(self, segments: List[np.ndarray], out_path: Path) -> None:
        if not segments:
            raise CADProcessingError("No segments to render from OCC HLR output")

        all_points = np.concatenate(segments, axis=0)
        min_vals = all_points.min(axis=0)
        max_vals = all_points.max(axis=0)
        span = np.clip(max_vals - min_vals, 1e-5, None)

        norm_segments = [((seg - min_vals) / span) for seg in segments]

        fig, ax = plt.subplots(figsize=(5, 5), dpi=300)
        collection = LineCollection(norm_segments, colors="#0e1e2f", linewidths=0.7)
        ax.add_collection(collection)
        ax.set_aspect("equal", "box")
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        fig.tight_layout(pad=0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, transparent=True, bbox_inches="tight", pad_inches=0)
        plt.close(fig)

    def _midplane_section_shape(
        self,
        shape,
        axis: str,
        normal: Tuple[float, float, float],
        origin: Tuple[float, float, float],
        span: float,
    ):
        plane = gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))
        half = max(span * 1.5, 1.0)
        plane_face = BRepBuilderAPI_MakeFace(plane, -half, half, -half, half).Face()
        section = BRepAlgoAPI_Section(shape, plane_face, True)
        section.Build()
        if not section.IsDone():
            raise CADProcessingError(f"Mid-plane section failed for axis {axis}")
        sec_shape = section.Shape()
        if sec_shape.IsNull():
            raise CADProcessingError(f"Mid-plane section returned empty geometry for axis {axis}")
        return sec_shape

    def _parse_component_index(self, component_node_name: str | None) -> int | None:
        if not isinstance(component_node_name, str):
            return None
        match = re.match(r"^component_(\d+)$", component_node_name.strip())
        if not match:
            return None
        index = int(match.group(1))
        return index if index >= 1 else None

    def _collect_solids(self, shape) -> List[object]:
        solids: List[object] = []
        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        while explorer.More():
            solids.append(topods.Solid(explorer.Current()))
            explorer.Next()
        return solids

    def _resolve_component_shape(
        self,
        shape,
        *,
        component_node_name: str | None = None,
        component_solid_index: int | None = None,
    ):
        index = component_solid_index if isinstance(component_solid_index, int) and component_solid_index >= 1 else None
        if index is None:
            index = self._parse_component_index(component_node_name)
        if index is None:
            return shape

        solids = self._collect_solids(shape)
        if not solids:
            raise CADProcessingError("No solids found in STEP model for component view selection.")
        if index > len(solids):
            raise CADProcessingError(
                f"Component solid index {index} is out of range for this model ({len(solids)} solids)."
            )
        return solids[index - 1]

    # ------------------------------------------------------------------ public API
    def generate_occ_views(
        self,
        step_path: Path,
        output_dir: Path,
        *,
        component_node_name: str | None = None,
        component_solid_index: int | None = None,
    ) -> Dict[str, Path]:
        shape = self._load_shape(step_path)
        view_shape = self._resolve_component_shape(
            shape,
            component_node_name=component_node_name,
            component_solid_index=component_solid_index,
        )

        results: Dict[str, Path] = {}
        for name, config in self._projection_table.items():
            visible_edges = self._run_hlr(view_shape, config["dir"])

            segments: List[np.ndarray] = []
            for edge_pts in self._iter_edge_points(visible_edges):
                projected = self._project_points(edge_pts, config["basis_x"], config["basis_y"])
                segments.append(projected)

            out_path = output_dir / f"{name}.png"
            self._render_segments(segments, out_path)
            results[name] = out_path
        return results

    def generate_mid_views(self, step_path: Path, output_dir: Path) -> Dict[str, Path]:
        """
        Create mid-plane section views (one per axis) and render the intersection curves.
        """
        shape = self._load_shape(step_path)
        bbox = self._bounding_box(shape)
        mins = bbox[:3]
        maxs = bbox[3:]
        mids = tuple((lo + hi) / 2.0 for lo, hi in zip(mins, maxs))
        span = max((hi - lo) for lo, hi in zip(mins, maxs)) or 1.0

        results: Dict[str, Path] = {}
        for name, config in self._projection_table.items():
            axis = config["axis"]
            normal = config["dir"]
            origin = list(mids)
            if axis == "x":
                origin[0] = mids[0]
            elif axis == "y":
                origin[1] = mids[1]
            else:
                origin[2] = mids[2]

            section_shape = self._midplane_section_shape(shape, axis, normal, tuple(origin), span)

            segments: List[np.ndarray] = []
            for edge_pts in self._iter_edge_points(section_shape):
                projected = self._project_points(edge_pts, config["basis_x"], config["basis_y"])
                segments.append(projected)

            out_path = output_dir / f"mid_{name}.png"
            self._render_segments(segments, out_path)
            results[f"mid_{name}"] = out_path
        return results
