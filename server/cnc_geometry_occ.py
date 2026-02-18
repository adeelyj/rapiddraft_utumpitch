from __future__ import annotations

from dataclasses import dataclass
import math
import re
from pathlib import Path
from typing import Any

CRITICAL_EPS_MM = 0.0001
WARNING_MAX_MM = 1.5
CAUTION_MAX_MM = 3.0
AGGRAVATING_RATIO_THRESHOLD = 5.0


class CncGeometryError(RuntimeError):
    pass


@dataclass
class CncCriteria:
    critical_enabled: bool = True
    critical_max_mm: float = CRITICAL_EPS_MM
    warning_enabled: bool = True
    warning_max_mm: float = WARNING_MAX_MM
    caution_enabled: bool = True
    caution_max_mm: float = CAUTION_MAX_MM
    ok_enabled: bool = True
    ok_min_mm: float = CAUTION_MAX_MM
    concave_internal_edges_only: bool = True
    pocket_internal_cavity_heuristic: bool = True
    exclude_bbox_exterior_edges: bool = True
    aggravating_factor_ratio_threshold: float = AGGRAVATING_RATIO_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "thresholds": {
                "critical_enabled": self.critical_enabled,
                "critical_max_mm": self.critical_max_mm,
                "warning_enabled": self.warning_enabled,
                "warning_max_mm": self.warning_max_mm,
                "caution_enabled": self.caution_enabled,
                "caution_max_mm": self.caution_max_mm,
                "ok_enabled": self.ok_enabled,
                "ok_min_mm": self.ok_min_mm,
            },
            "filters": {
                "concave_internal_edges_only": self.concave_internal_edges_only,
                "pocket_internal_cavity_heuristic": self.pocket_internal_cavity_heuristic,
                "exclude_bbox_exterior_edges": self.exclude_bbox_exterior_edges,
            },
            "aggravating_factor_ratio_threshold": self.aggravating_factor_ratio_threshold,
        }


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return default


def parse_criteria(criteria_payload: dict[str, Any] | None) -> CncCriteria:
    if not isinstance(criteria_payload, dict):
        return CncCriteria()

    thresholds = criteria_payload.get("thresholds", {})
    if not isinstance(thresholds, dict):
        thresholds = {}
    filters = criteria_payload.get("filters", {})
    if not isinstance(filters, dict):
        filters = {}

    critical_max = max(0.0, _as_float(thresholds.get("critical_max_mm"), CRITICAL_EPS_MM))
    warning_max = max(critical_max + 1e-9, _as_float(thresholds.get("warning_max_mm"), WARNING_MAX_MM))
    caution_max = max(warning_max + 1e-9, _as_float(thresholds.get("caution_max_mm"), CAUTION_MAX_MM))
    ok_min = max(0.0, _as_float(thresholds.get("ok_min_mm"), CAUTION_MAX_MM))
    ratio_threshold = max(0.0, _as_float(criteria_payload.get("aggravating_factor_ratio_threshold"), AGGRAVATING_RATIO_THRESHOLD))

    return CncCriteria(
        critical_enabled=_as_bool(thresholds.get("critical_enabled"), True),
        critical_max_mm=critical_max,
        warning_enabled=_as_bool(thresholds.get("warning_enabled"), True),
        warning_max_mm=warning_max,
        caution_enabled=_as_bool(thresholds.get("caution_enabled"), True),
        caution_max_mm=caution_max,
        ok_enabled=_as_bool(thresholds.get("ok_enabled"), True),
        ok_min_mm=ok_min,
        concave_internal_edges_only=_as_bool(filters.get("concave_internal_edges_only"), True),
        pocket_internal_cavity_heuristic=_as_bool(filters.get("pocket_internal_cavity_heuristic"), True),
        exclude_bbox_exterior_edges=_as_bool(filters.get("exclude_bbox_exterior_edges"), True),
        aggravating_factor_ratio_threshold=ratio_threshold,
    )


def parse_component_index(component_node_name: str | None) -> int | None:
    if not isinstance(component_node_name, str):
        return None
    match = re.match(r"^component_(\d+)$", component_node_name.strip())
    if not match:
        return None
    index = int(match.group(1))
    return index if index >= 1 else None


def classify_radius_status(radius_mm: float | None) -> str | None:
    if radius_mm is None or not math.isfinite(radius_mm):
        return None
    if radius_mm <= CRITICAL_EPS_MM:
        return "CRITICAL"
    if radius_mm < WARNING_MAX_MM:
        return "WARNING"
    if radius_mm < CAUTION_MAX_MM:
        return "CAUTION"
    return "OK"


def classify_radius_status_with_criteria(
    radius_mm: float | None,
    *,
    criteria: CncCriteria,
) -> str | None:
    if radius_mm is None or not math.isfinite(radius_mm):
        return None
    if radius_mm <= criteria.critical_max_mm:
        return "CRITICAL" if criteria.critical_enabled else None
    if criteria.critical_max_mm < radius_mm < criteria.warning_max_mm:
        return "WARNING" if criteria.warning_enabled else None
    if criteria.warning_max_mm <= radius_mm < criteria.caution_max_mm:
        return "CAUTION" if criteria.caution_enabled else None
    if radius_mm >= criteria.ok_min_mm:
        return "OK" if criteria.ok_enabled else None
    return None


def compute_machinability_score(*, critical_count: int, warning_count: int, caution_count: int) -> int:
    penalty = critical_count * 25 + warning_count * 12 + caution_count * 6
    return max(0, min(100, 100 - penalty))


def compute_cost_impact(*, critical_count: int, warning_count: int, caution_count: int) -> str:
    weighted_penalty = critical_count * 25 + warning_count * 12 + caution_count * 6
    if weighted_penalty >= 60:
        return "HIGH"
    if weighted_penalty >= 25:
        return "MODERATE"
    return "LOW"


def minimum_tool_required(*, radius_mm: float | None, status: str) -> str:
    if status == "CRITICAL":
        return "Not machinable (rotary tool)"
    if radius_mm is None or radius_mm <= 0:
        return "Unknown"
    diameter = radius_mm * 2.0
    if status == "WARNING":
        return f"Dia {diameter:.1f} mm specialist small end mill"
    if status == "CAUTION":
        return f"Dia {diameter:.1f} mm small end mill"
    return f"Dia {diameter:.1f} mm standard end mill"


def recommendation_for_status(status: str) -> str:
    if status in {"CRITICAL", "WARNING", "CAUTION"}:
        return "Increase internal radius to >= R3.0 mm"
    return "No action needed"


def _normalize(vec: tuple[float, float, float]) -> tuple[float, float, float] | None:
    mag = math.sqrt(vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2])
    if mag <= 1e-12:
        return None
    return (vec[0] / mag, vec[1] / mag, vec[2] / mag)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
    return (a[0] * scalar, a[1] * scalar, a[2] * scalar)


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _axis_bucket(value: float, min_v: float, max_v: float, low: str, high: str) -> str:
    span = max(max_v - min_v, 1e-9)
    norm = (value - min_v) / span
    if norm < 0.33:
        return low
    if norm > 0.67:
        return high
    return "mid"


def describe_location(
    midpoint: tuple[float, float, float],
    bounds: tuple[float, float, float, float, float, float],
) -> str:
    x_min, y_min, z_min, x_max, y_max, z_max = bounds
    x_label = _axis_bucket(midpoint[0], x_min, x_max, "left", "right")
    y_label = _axis_bucket(midpoint[1], y_min, y_max, "front", "rear")
    z_label = _axis_bucket(midpoint[2], z_min, z_max, "bottom", "top")
    return f"{z_label}-{x_label}-{y_label} pocket corner"


class CncGeometryAnalyzer:
    def analyze(
        self,
        *,
        step_path: Path,
        component_node_name: str | None = None,
        component_display_name: str | None = None,
        include_ok_rows: bool = False,
        criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        occ = self._import_occ()
        shape = self._load_shape(occ, step_path)
        criteria_cfg = parse_criteria(criteria)

        assumptions = [
            "Units assumed mm",
            "Pocket depth computed only when determinable",
        ]
        assumptions.append(
            (
                "Criteria applied: "
                f"critical<=R{criteria_cfg.critical_max_mm:g}({criteria_cfg.critical_enabled}), "
                f"warning<R{criteria_cfg.warning_max_mm:g}({criteria_cfg.warning_enabled}), "
                f"caution<R{criteria_cfg.caution_max_mm:g}({criteria_cfg.caution_enabled}), "
                f"ok>=R{criteria_cfg.ok_min_mm:g}({criteria_cfg.ok_enabled}), "
                f"aggravating_ratio>{criteria_cfg.aggravating_factor_ratio_threshold:g}"
            )
        )

        analysis_shape, component_fallback = self._resolve_analysis_shape(
            occ, shape, component_node_name
        )
        if component_fallback:
            assumptions.append(
                "Component-to-solid mapping fallback applied; full model analyzed."
            )

        bounds = self._shape_bounds(occ, analysis_shape)
        classifier_shape = (
            analysis_shape
            if analysis_shape.ShapeType() == occ["TopAbs_SOLID"]
            else None
        )

        records = self._edge_face_records(occ, analysis_shape)

        corners: list[dict[str, Any]] = []
        status_counts = {"CRITICAL": 0, "WARNING": 0, "CAUTION": 0, "OK": 0}
        uncertain_internal_count = 0
        corner_num = 1

        for edge_index, record in enumerate(records, start=1):
            faces = record["faces"]
            if len(faces) != 2:
                continue
            midpoint, tangent, normals = self._edge_frame(occ, record["edge"], faces)
            if midpoint is None or tangent is None or len(normals) != 2:
                continue

            signed = _dot(_cross(normals[0], normals[1]), tangent)
            if criteria_cfg.concave_internal_edges_only and signed >= 0:
                continue

            radius_mm = self._measure_radius_mm(occ, record["edge"])
            status = classify_radius_status_with_criteria(
                radius_mm,
                criteria=criteria_cfg,
            )
            if not status:
                continue

            if criteria_cfg.pocket_internal_cavity_heuristic:
                cavity = self._cavity_test(
                    occ=occ,
                    classifier_shape=classifier_shape,
                    midpoint=midpoint,
                    normal_a=normals[0],
                    normal_b=normals[1],
                    bounds=bounds,
                )
            else:
                cavity = {
                    "is_internal_like": True,
                    "uncertain": False,
                    "cavity_direction": _normalize(_add(normals[0], normals[1])),
                }

            near_exterior = self._is_near_bbox_exterior(midpoint, bounds)
            if criteria_cfg.exclude_bbox_exterior_edges:
                if criteria_cfg.pocket_internal_cavity_heuristic:
                    if near_exterior and not cavity["is_internal_like"] and not cavity["uncertain"]:
                        continue
                elif near_exterior:
                    continue
            if criteria_cfg.pocket_internal_cavity_heuristic and cavity["uncertain"]:
                uncertain_internal_count += 1

            pocket_depth_mm = self._estimate_depth_mm(
                midpoint=midpoint,
                cavity_direction=cavity.get("cavity_direction"),
                bounds=bounds,
            )
            depth_to_radius_ratio = None
            aggravating_factor = False
            if (
                pocket_depth_mm is not None
                and radius_mm is not None
                and radius_mm > CRITICAL_EPS_MM
            ):
                depth_to_radius_ratio = pocket_depth_mm / radius_mm
                aggravating_factor = (
                    depth_to_radius_ratio
                    > criteria_cfg.aggravating_factor_ratio_threshold
                )

            status_counts[status] += 1
            if status == "OK" and not include_ok_rows:
                continue

            corners.append(
                {
                    "corner_id": f"C{corner_num}",
                    "edge_index": edge_index,
                    "location_description": describe_location(midpoint, bounds),
                    "radius_mm": None if radius_mm is None else round(radius_mm, 4),
                    "status": status,
                    "minimum_tool_required": minimum_tool_required(
                        radius_mm=radius_mm, status=status
                    ),
                    "recommendation": recommendation_for_status(status),
                    "pocket_depth_mm": None
                    if pocket_depth_mm is None
                    else round(pocket_depth_mm, 4),
                    "depth_to_radius_ratio": None
                    if depth_to_radius_ratio is None
                    else round(depth_to_radius_ratio, 4),
                    "aggravating_factor": aggravating_factor,
                }
            )
            corner_num += 1

        if uncertain_internal_count:
            assumptions.append(
                f"{uncertain_internal_count} internal-edge classifications were uncertain and retained."
            )

        summary = {
            "critical_count": status_counts["CRITICAL"],
            "warning_count": status_counts["WARNING"],
            "caution_count": status_counts["CAUTION"],
            "ok_count": status_counts["OK"],
            "machinability_score": compute_machinability_score(
                critical_count=status_counts["CRITICAL"],
                warning_count=status_counts["WARNING"],
                caution_count=status_counts["CAUTION"],
            ),
            "cost_impact": compute_cost_impact(
                critical_count=status_counts["CRITICAL"],
                warning_count=status_counts["WARNING"],
                caution_count=status_counts["CAUTION"],
            ),
        }

        return {
            "component_node_name": component_node_name,
            "component_display_name": component_display_name
            or component_node_name
            or "Global Context",
            "part_filename": step_path.name,
            "criteria_applied": criteria_cfg.to_dict(),
            "summary": summary,
            "corners": corners,
            "assumptions": assumptions,
        }

    def _import_occ(self) -> dict[str, Any]:
        try:
            from OCC.Core.Bnd import Bnd_Box
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            from OCC.Core.BRepBndLib import brepbndlib_Add
            from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
            from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
            from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Line
            from OCC.Core.GeomLProp import GeomLProp_CLProps, GeomLProp_SLProps
            from OCC.Core.IFSelect import IFSelect_RetDone
            from OCC.Core.STEPControl import STEPControl_Reader
            from OCC.Core.TopAbs import (
                TopAbs_EDGE,
                TopAbs_FACE,
                TopAbs_IN,
                TopAbs_OUT,
                TopAbs_SOLID,
            )
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopoDS import topods
            from OCC.Core.gp import gp_Pnt
        except Exception as exc:  # pragma: no cover - environment dependent
            raise CncGeometryError(
                "pythonOCC is required for CNC geometry analysis. Install pythonocc-core."
            ) from exc

        return {
            "Bnd_Box": Bnd_Box,
            "BRep_Tool": BRep_Tool,
            "BRepAdaptor_Curve": BRepAdaptor_Curve,
            "brepbndlib_Add": brepbndlib_Add,
            "BRepClass3d_SolidClassifier": BRepClass3d_SolidClassifier,
            "GeomAPI_ProjectPointOnSurf": GeomAPI_ProjectPointOnSurf,
            "GeomAbs_Circle": GeomAbs_Circle,
            "GeomAbs_Line": GeomAbs_Line,
            "GeomLProp_CLProps": GeomLProp_CLProps,
            "GeomLProp_SLProps": GeomLProp_SLProps,
            "IFSelect_RetDone": IFSelect_RetDone,
            "STEPControl_Reader": STEPControl_Reader,
            "TopAbs_EDGE": TopAbs_EDGE,
            "TopAbs_FACE": TopAbs_FACE,
            "TopAbs_IN": TopAbs_IN,
            "TopAbs_OUT": TopAbs_OUT,
            "TopAbs_SOLID": TopAbs_SOLID,
            "TopExp_Explorer": TopExp_Explorer,
            "topods": topods,
            "gp_Pnt": gp_Pnt,
        }

    def _load_shape(self, occ: dict[str, Any], step_path: Path):
        reader = occ["STEPControl_Reader"]()
        status = reader.ReadFile(str(step_path))
        if status != occ["IFSelect_RetDone"]:
            raise CncGeometryError(
                f"Failed to read STEP file via OCC (status={status})."
            )
        reader.TransferRoots()
        shape = reader.Shape()
        if shape.IsNull():
            raise CncGeometryError("STEP file did not produce a valid shape.")
        return shape

    def _resolve_analysis_shape(self, occ: dict[str, Any], shape, component_node_name: str | None):
        solids: list[Any] = []
        explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_SOLID"])
        while explorer.More():
            solids.append(occ["topods"].Solid(explorer.Current()))
            explorer.Next()

        component_index = parse_component_index(component_node_name)
        if component_node_name and component_index is None:
            return shape, True
        if component_index is None or not solids:
            return shape, False
        if component_index <= len(solids):
            return solids[component_index - 1], False
        return shape, True

    def _shape_bounds(self, occ: dict[str, Any], shape) -> tuple[float, float, float, float, float, float]:
        box = occ["Bnd_Box"]()
        occ["brepbndlib_Add"](shape, box)
        return box.Get()

    def _edge_face_records(self, occ: dict[str, Any], shape) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        face_explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
        while face_explorer.More():
            face = occ["topods"].Face(face_explorer.Current())
            edge_explorer = occ["TopExp_Explorer"](face, occ["TopAbs_EDGE"])
            while edge_explorer.More():
                edge = occ["topods"].Edge(edge_explorer.Current())
                matched = False
                for record in records:
                    if record["edge"].IsSame(edge):
                        record["faces"].append(face)
                        matched = True
                        break
                if not matched:
                    records.append({"edge": edge, "faces": [face]})
                edge_explorer.Next()
            face_explorer.Next()
        return records

    def _edge_frame(self, occ: dict[str, Any], edge, faces: list[Any]):
        try:
            curve = occ["BRepAdaptor_Curve"](edge)
            first = float(curve.FirstParameter())
            last = float(curve.LastParameter())
            mid = (first + last) * 0.5
            span = max(abs(last - first), 1e-6)
            delta = min(span * 0.05, 0.1)

            p_mid = curve.Value(mid)
            p_a = curve.Value(max(first, mid - delta))
            p_b = curve.Value(min(last, mid + delta))

            tangent = _normalize((p_b.X() - p_a.X(), p_b.Y() - p_a.Y(), p_b.Z() - p_a.Z()))
            if tangent is None:
                return None, None, []
            midpoint = (p_mid.X(), p_mid.Y(), p_mid.Z())
            normals: list[tuple[float, float, float]] = []
            for face in faces:
                normal = self._face_normal_at_point(occ, face, p_mid)
                if normal is None:
                    continue
                normals.append(normal)
            return midpoint, tangent, normals
        except Exception:
            return None, None, []

    def _face_normal_at_point(self, occ: dict[str, Any], face, point) -> tuple[float, float, float] | None:
        try:
            surface = occ["BRep_Tool"].Surface(face)
            projector = occ["GeomAPI_ProjectPointOnSurf"](point, surface)
            if projector.NbPoints() < 1:
                return None
            u, v = projector.LowerDistanceParameters()
            props = occ["GeomLProp_SLProps"](surface, u, v, 1, 1e-6)
            if not props.IsNormalDefined():
                return None
            n = props.Normal()
            return _normalize((n.X(), n.Y(), n.Z()))
        except Exception:
            return None

    def _measure_radius_mm(self, occ: dict[str, Any], edge) -> float | None:
        try:
            curve = occ["BRepAdaptor_Curve"](edge)
            curve_type = curve.GetType()
            if curve_type == occ["GeomAbs_Line"]:
                return 0.0
            if curve_type == occ["GeomAbs_Circle"]:
                return abs(float(curve.Circle().Radius()))

            curve_handle, first, last = occ["BRep_Tool"].Curve(edge)
            if curve_handle is None:
                return None
            mid = (float(first) + float(last)) * 0.5
            props = occ["GeomLProp_CLProps"](curve_handle, mid, 2, 1e-6)
            curvature = abs(float(props.Curvature()))
            if curvature <= 1e-9:
                return None
            radius = 1.0 / curvature
            return radius if math.isfinite(radius) else None
        except Exception:
            return None

    def _cavity_test(
        self,
        *,
        occ: dict[str, Any],
        classifier_shape,
        midpoint: tuple[float, float, float],
        normal_a: tuple[float, float, float],
        normal_b: tuple[float, float, float],
        bounds: tuple[float, float, float, float, float, float],
    ) -> dict[str, Any]:
        bisector = _normalize(_add(normal_a, normal_b))
        if bisector is None:
            return {
                "is_internal_like": True,
                "uncertain": True,
                "cavity_direction": None,
            }

        max_span = max(
            bounds[3] - bounds[0],
            bounds[4] - bounds[1],
            bounds[5] - bounds[2],
        )
        probe = max(0.25, max_span * 0.005)
        p_plus = _add(midpoint, _mul(bisector, probe))
        p_minus = _sub(midpoint, _mul(bisector, probe))

        if classifier_shape is None:
            return {
                "is_internal_like": True,
                "uncertain": True,
                "cavity_direction": bisector,
            }

        s_plus = self._solid_state(occ, classifier_shape, p_plus)
        s_minus = self._solid_state(occ, classifier_shape, p_minus)
        if s_plus == "outside" and s_minus == "inside":
            return {
                "is_internal_like": True,
                "uncertain": False,
                "cavity_direction": bisector,
            }
        if s_plus == "inside" and s_minus == "outside":
            return {
                "is_internal_like": True,
                "uncertain": False,
                "cavity_direction": _mul(bisector, -1.0),
            }
        if s_plus == "outside" and s_minus == "outside":
            return {
                "is_internal_like": False,
                "uncertain": False,
                "cavity_direction": bisector,
            }
        if s_plus == "inside" and s_minus == "inside":
            return {
                "is_internal_like": False,
                "uncertain": False,
                "cavity_direction": bisector,
            }
        return {
            "is_internal_like": True,
            "uncertain": True,
            "cavity_direction": bisector,
        }

    def _solid_state(self, occ: dict[str, Any], solid_shape, point: tuple[float, float, float]) -> str:
        try:
            classifier = occ["BRepClass3d_SolidClassifier"](
                solid_shape,
                occ["gp_Pnt"](*point),
                1e-6,
            )
            state = classifier.State()
            if state == occ["TopAbs_IN"]:
                return "inside"
            if state == occ["TopAbs_OUT"]:
                return "outside"
            return "on"
        except Exception:
            return "unknown"

    def _is_near_bbox_exterior(
        self,
        midpoint: tuple[float, float, float],
        bounds: tuple[float, float, float, float, float, float],
    ) -> bool:
        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        span_x = max(x_max - x_min, 1e-9)
        span_y = max(y_max - y_min, 1e-9)
        span_z = max(z_max - z_min, 1e-9)
        tol_x = max(0.5, span_x * 0.02)
        tol_y = max(0.5, span_y * 0.02)
        tol_z = max(0.5, span_z * 0.02)
        x, y, z = midpoint
        return (
            abs(x - x_min) <= tol_x
            or abs(x - x_max) <= tol_x
            or abs(y - y_min) <= tol_y
            or abs(y - y_max) <= tol_y
            or abs(z - z_min) <= tol_z
            or abs(z - z_max) <= tol_z
        )

    def _estimate_depth_mm(
        self,
        *,
        midpoint: tuple[float, float, float],
        cavity_direction: tuple[float, float, float] | None,
        bounds: tuple[float, float, float, float, float, float],
    ) -> float | None:
        if cavity_direction is None:
            return None
        direction = _normalize(cavity_direction)
        if direction is None:
            return None

        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        max_diag = math.sqrt(
            (x_max - x_min) ** 2 + (y_max - y_min) ** 2 + (z_max - z_min) ** 2
        )
        candidates: list[float] = []
        for axis, (low, high, coord, d_comp) in enumerate(
            (
                (x_min, x_max, midpoint[0], direction[0]),
                (y_min, y_max, midpoint[1], direction[1]),
                (z_min, z_max, midpoint[2], direction[2]),
            )
        ):
            del axis
            if d_comp > 1e-9:
                t = (high - coord) / d_comp
                if t > 0:
                    candidates.append(t)
            elif d_comp < -1e-9:
                t = (low - coord) / d_comp
                if t > 0:
                    candidates.append(t)

        if not candidates:
            return None
        depth = min(candidates)
        if not math.isfinite(depth) or depth <= 0 or depth > max_diag * 1.5:
            return None
        return depth
