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
TURN_AXIS_ANGLE_TOLERANCE_DEG = 5.0
TURN_AXIS_MIN_AREA_RATIO = 0.35
TURN_AXIS_MIN_SPAN_RATIO = 0.6
TURN_AXIS_DOMINANT_DIMENSION_RATIO = 0.8
TURN_AXIS_MIN_REVOLVED_FRACTION = 0.75
TURN_END_FACE_POSITION_TOLERANCE_RATIO = 0.03
TURN_END_FACE_POSITION_TOLERANCE_MM = 1.0
TURN_DIAMETER_RADIUS_TOLERANCE_MM = 1.5
TURN_DIAMETER_AXIAL_GAP_TOLERANCE_MM = 1.0
TURN_SHORT_AXIS_CENTER_OFFSET_RATIO = 0.2
TURN_SHORT_AXIS_CENTER_OFFSET_MM = 8.0
TURN_SHORT_END_CLUSTER_GAP_MM = 2.25
TURN_SHORT_END_MIN_RADIUS_RATIO = 0.75
TURN_SHORT_PROFILE_MIN_RADIUS_RATIO = 0.78
TURN_SHORT_PROFILE_MIN_SPAN_MM = 1.0
TURN_SHORT_TORUS_MIN_SPAN_MM = 1.5
TURN_SHORT_GROOVE_MAX_SPAN_MM = 3.0
TURN_SHORT_GROOVE_MIN_DEPTH_MM = 0.6
TURN_SHORT_END_GROOVE_MAX_SPAN_MM = 1.5
TURN_SHORT_RADIUS_TOLERANCE_MM = 0.25
TURN_SHORT_BORE_MIN_SPAN_MM = 3.0
TURN_SHORT_BORE_MIN_RADIUS_RATIO = 0.5
TURN_SHORT_BORE_MAX_RADIUS_RATIO = 0.75
TURN_SHORT_SMALL_HOLE_RADIUS_MAX_MM = 3.0
TURN_SHORT_CIRCULAR_MILLED_MAX_RADIUS_RATIO = 0.7
HOLE_THROUGH_COMPLETENESS_MIN = 0.7
HOLE_PARTIAL_COMPLETENESS_MIN = 0.35
HOLE_MIN_DEPTH_TO_DIAMETER_RATIO = 0.45
HOLE_BORE_DEPTH_RATIO = 0.7
HOLE_BORE_DIAMETER_RATIO = 0.2
HOLE_DIAMETER_BAND_TOLERANCE_MM = 1.5
HOLE_COMPONENT_AXIAL_GAP_TOLERANCE_MM = 1.0
HOLE_INTERIOR_MULTI_SEGMENT_THROUGH_COMPLETENESS_MIN = 0.3
HOLE_INTERIOR_MULTI_SEGMENT_MAX_DIAMETER_MM = 12.0
HOLE_STEPPED_MIN_DEPTH_TO_DIAMETER_RATIO = 1.0
HOLE_STEPPED_OUTER_DEPTH_RATIO = 1.2
HOLE_STEPPED_FULL_DEPTH_RATIO = 0.9
HOLE_SINGLE_RECESS_MAX_COMPLETENESS = 0.5
HOLE_SINGLE_RECESS_MIN_NEIGHBOR_COUNT = 4
HOLE_CAP_EXCLUDED_MAX_AREA_MM2 = 150.0
POCKET_MIN_RECESS_RATIO = 0.3
POCKET_MIN_RECESS_MM = 2.0
POCKET_MIN_AREA_MM2 = 20.0
POCKET_OPEN_WALL_COUNT_MIN = 4
POCKET_OPEN_EXTERIOR_WALL_COUNT_MAX = 5
POCKET_OPEN_EXTERIOR_RECESS_RATIO = 0.18
POCKET_OPEN_EXTERIOR_RECESS_RATIO_RELAXED = 0.17
POCKET_OPEN_EXTERIOR_RECESS_MM = 8.0
POCKET_OPEN_EXTERIOR_INTERIOR_PLANE_MIN = 2
POCKET_OPEN_EXTERIOR_INTERIOR_CURVED_MIN = 1
POCKET_CLOSED_WALL_COUNT_MIN = 5
POCKET_CLOSED_WALL_COUNT_MAX = 12
POCKET_CURVED_ENCLOSED_RECESS_RATIO = 0.35
POCKET_CURVED_ENCLOSED_RECESS_MM = 10.0
POCKET_AXIS_ALIGNMENT_MIN = 0.98
BOSS_MIN_SPAN_RATIO = 0.6
BOSS_MIN_DIAMETER_RATIO = 0.25
BOSS_MIN_END_CAP_COUNT = 2
MILLED_FACE_AXIS_ALIGNMENT_MIN = 0.92
CONVEX_PROFILE_MIN_DIAMETER_MM = 12.0
CONVEX_PROFILE_MAX_DIAMETER_MM = 40.0
CONVEX_PROFILE_AXIS_SPAN_RATIO_MIN = 0.45
CONCAVE_FILLET_SHORT_CYLINDER_MIN_DIAMETER_MM = 15.0
CONCAVE_FILLET_SHORT_CYLINDER_MAX_DIAMETER_MM = 25.0
CONCAVE_FILLET_SHORT_CYLINDER_SPAN_RATIO_MAX = 0.3
CURVED_HALF_CYLINDER_MIN_COMPLETENESS = 0.4
CURVED_HALF_CYLINDER_MAX_DIAMETER_MM = 5.0
CURVED_CONE_GROUP_SPLIT_AREA_RATIO = 8.0
FLAT_TWIN_FACE_MAX_AREA_MM2 = 400.0
FLAT_TWIN_FACE_POSITION_GAP_MM = 6.0
FLAT_TWIN_FACE_SPAN_TOLERANCE_MM = 1.0


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


def _canonical_axis(vec: tuple[float, float, float]) -> tuple[float, float, float] | None:
    normalized = _normalize(vec)
    if normalized is None:
        return None
    for value in normalized:
        if abs(value) <= 1e-9:
            continue
        if value < 0:
            return _mul(normalized, -1.0)
        break
    return normalized


def _bbox_corners(
    bounds: tuple[float, float, float, float, float, float],
) -> list[tuple[float, float, float]]:
    x_min, y_min, z_min, x_max, y_max, z_max = bounds
    return [
        (x, y, z)
        for x in (x_min, x_max)
        for y in (y_min, y_max)
        for z in (z_min, z_max)
    ]


def _project_scalar(point: tuple[float, float, float], axis: tuple[float, float, float]) -> float:
    return _dot(point, axis)


def _project_bounds_range(
    bounds: tuple[float, float, float, float, float, float],
    axis: tuple[float, float, float],
) -> tuple[float, float]:
    projections = [_project_scalar(point, axis) for point in _bbox_corners(bounds)]
    return min(projections), max(projections)


def _project_bounds_span(
    bounds: tuple[float, float, float, float, float, float],
    axis: tuple[float, float, float],
) -> float:
    projected_min, projected_max = _project_bounds_range(bounds, axis)
    return max(0.0, projected_max - projected_min)


def _bbox_center_point(
    bounds: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float]:
    return (
        (bounds[0] + bounds[3]) * 0.5,
        (bounds[1] + bounds[4]) * 0.5,
        (bounds[2] + bounds[5]) * 0.5,
    )


def _box_payload_from_center(
    center: tuple[float, float, float],
    *,
    half_extent_mm: float,
) -> list[float]:
    half_extent = max(float(half_extent_mm), 0.05)
    return [
        round(float(center[0]) - half_extent, 4),
        round(float(center[1]) - half_extent, 4),
        round(float(center[2]) - half_extent, 4),
        round(float(center[0]) + half_extent, 4),
        round(float(center[1]) + half_extent, 4),
        round(float(center[2]) + half_extent, 4),
    ]


def detect_turning_from_face_inventory(
    face_inventory: list[dict[str, Any]],
    *,
    bbox_bounds: tuple[float, float, float, float, float, float],
    axis_angle_tolerance_deg: float = TURN_AXIS_ANGLE_TOLERANCE_DEG,
    min_area_ratio: float = TURN_AXIS_MIN_AREA_RATIO,
    min_span_ratio: float = TURN_AXIS_MIN_SPAN_RATIO,
    min_dominant_axis_ratio: float = TURN_AXIS_DOMINANT_DIMENSION_RATIO,
    min_revolved_fraction: float = TURN_AXIS_MIN_REVOLVED_FRACTION,
) -> dict[str, Any]:
    axis_tolerance_cos = math.cos(math.radians(max(0.0, axis_angle_tolerance_deg)))
    max_part_dimension = max(
        bbox_bounds[3] - bbox_bounds[0],
        bbox_bounds[4] - bbox_bounds[1],
        bbox_bounds[5] - bbox_bounds[2],
        0.0,
    )

    candidate_faces: list[dict[str, Any]] = []
    total_exterior_area = 0.0
    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        area = float(face.get("area_mm2") or 0.0)
        if math.isfinite(area) and area > 0 and face.get("is_exterior") is True:
            total_exterior_area += area
        surface_type = str(face.get("surface_type") or "").strip().lower()
        if surface_type not in {"cylinder", "cone", "surface_of_revolution", "torus"}:
            continue
        if face.get("is_exterior") is not True:
            continue
        axis_direction = face.get("axis_direction")
        if not isinstance(axis_direction, (list, tuple)) or len(axis_direction) != 3:
            continue
        axis = _canonical_axis(
            (float(axis_direction[0]), float(axis_direction[1]), float(axis_direction[2]))
        )
        if axis is None:
            continue
        if not math.isfinite(area) or area <= 0:
            continue
        candidate_face = dict(face)
        candidate_face["axis_direction"] = axis
        candidate_face["area_mm2"] = area
        candidate_faces.append(candidate_face)

    total_revolved_area = sum(face["area_mm2"] for face in candidate_faces)
    clusters: list[dict[str, Any]] = []
    for face in candidate_faces:
        axis = face["axis_direction"]
        area = face["area_mm2"]
        for cluster in clusters:
            alignment = _dot(cluster["axis_direction"], axis)
            if abs(alignment) < axis_tolerance_cos:
                continue
            signed_axis = axis if alignment >= 0 else _mul(axis, -1.0)
            cluster["axis_weighted_sum"] = _add(
                cluster["axis_weighted_sum"],
                _mul(signed_axis, area),
            )
            cluster["axis_direction"] = _canonical_axis(
                _normalize(cluster["axis_weighted_sum"]) or cluster["axis_direction"]
            ) or cluster["axis_direction"]
            cluster["area_mm2"] += area
            cluster["faces"].append(face)
            break
        else:
            clusters.append(
                {
                    "axis_direction": axis,
                    "axis_weighted_sum": _mul(axis, area),
                    "area_mm2": area,
                    "faces": [face],
                }
            )

    cluster_summaries: list[dict[str, Any]] = []
    accepted_cluster: dict[str, Any] | None = None
    for index, cluster in enumerate(
        sorted(clusters, key=lambda item: (-item["area_mm2"], -len(item["faces"]))),
        start=1,
    ):
        axis = cluster["axis_direction"]
        cluster_min: float | None = None
        cluster_max: float | None = None
        for face in cluster["faces"]:
            face_bounds = face.get("bbox_bounds")
            if isinstance(face_bounds, list) and len(face_bounds) == 6:
                bounds = tuple(float(value) for value in face_bounds)
                face_min, face_max = _project_bounds_range(bounds, axis)
            else:
                centroid = face.get("centroid_mm")
                if not isinstance(centroid, (list, tuple)) or len(centroid) != 3:
                    continue
                projection = _project_scalar(
                    (float(centroid[0]), float(centroid[1]), float(centroid[2])),
                    axis,
                )
                face_min = projection
                face_max = projection
            cluster_min = face_min if cluster_min is None else min(cluster_min, face_min)
            cluster_max = face_max if cluster_max is None else max(cluster_max, face_max)

        cluster_span = (
            max(0.0, cluster_max - cluster_min)
            if cluster_min is not None and cluster_max is not None
            else 0.0
        )
        part_axis_span = _project_bounds_span(bbox_bounds, axis)
        area_ratio = (cluster["area_mm2"] / total_revolved_area) if total_revolved_area > 0 else 0.0
        span_ratio = (cluster_span / part_axis_span) if part_axis_span > 0 else 0.0
        dominant_axis_ratio = (
            part_axis_span / max_part_dimension if max_part_dimension > 0 else 0.0
        )
        revolved_fraction = (
            cluster["area_mm2"] / total_exterior_area if total_exterior_area > 0 else 0.0
        )
        axis_normal_exterior_plane_count = 0
        for face in face_inventory:
            if not isinstance(face, dict):
                continue
            if face.get("is_exterior") is not True:
                continue
            if str(face.get("surface_type") or "").strip().lower() != "plane":
                continue
            normal = _normalized_face_vector(face)
            if normal is None:
                continue
            if abs(_dot(normal, axis)) >= axis_tolerance_cos:
                axis_normal_exterior_plane_count += 1
        accepted = (
            area_ratio >= min_area_ratio
            and span_ratio >= min_span_ratio
            and (
                dominant_axis_ratio >= min_dominant_axis_ratio
                or (
                    revolved_fraction >= min_revolved_fraction
                    and axis_normal_exterior_plane_count >= 1
                )
            )
        )

        summary = {
            "cluster_index": index,
            "axis_direction": axis,
            "candidate_face_count": len(cluster["faces"]),
            "area_mm2": round(cluster["area_mm2"], 4),
            "area_ratio": round(area_ratio, 4),
            "cluster_span_mm": round(cluster_span, 4),
            "part_axis_span_mm": round(part_axis_span, 4),
            "span_ratio": round(span_ratio, 4),
            "dominant_axis_ratio": round(dominant_axis_ratio, 4),
            "exterior_revolved_area_ratio": round(revolved_fraction, 4),
            "axis_normal_exterior_plane_count": axis_normal_exterior_plane_count,
            "accepted": accepted,
            "surface_types": sorted(
                {
                    str(face.get("surface_type") or "").strip().lower()
                    for face in cluster["faces"]
                }
            ),
            "face_indices": [
                int(face.get("face_index"))
                for face in cluster["faces"]
                if isinstance(face.get("face_index"), int)
            ],
        }
        cluster_summaries.append(summary)
        if accepted and accepted_cluster is None:
            accepted_cluster = {
                **summary,
                "faces": cluster["faces"],
                "cluster_min": cluster_min,
                "cluster_max": cluster_max,
            }

    if accepted_cluster is None:
        return {
            "rotational_symmetry": False,
            "turned_faces_present": False,
            "turned_face_count": 0,
            "turned_diameter_faces_count": 0,
            "turned_end_faces_count": 0,
            "turned_profile_faces_count": 0,
            "primary_axis": None,
            "candidate_face_count": len(candidate_faces),
            "total_exterior_revolved_area_mm2": round(total_revolved_area, 4),
            "total_exterior_area_mm2": round(total_exterior_area, 4),
            "max_part_dimension_mm": round(max_part_dimension, 4),
            "clusters": cluster_summaries,
            "thresholds": {
                "axis_angle_tolerance_deg": axis_angle_tolerance_deg,
                "min_area_ratio": min_area_ratio,
                "min_span_ratio": min_span_ratio,
                "min_dominant_axis_ratio": min_dominant_axis_ratio,
                "min_revolved_fraction": min_revolved_fraction,
            },
        }

    primary_axis = accepted_cluster["axis_direction"]
    turned_diameter_faces = [
        face
        for face in accepted_cluster["faces"]
        if str(face.get("surface_type") or "").strip().lower() == "cylinder"
    ]
    turned_diameter_groups = _group_turned_diameter_faces(
        turned_diameter_faces,
        primary_axis=primary_axis,
        part_axis_span_mm=accepted_cluster["part_axis_span_mm"],
    )
    turned_profile_faces = [
        face
        for face in accepted_cluster["faces"]
        if str(face.get("surface_type") or "").strip().lower() != "cylinder"
    ]
    short_turning_analysis: dict[str, Any] = _analyze_short_turning_axis_features(
        accepted_cluster=accepted_cluster,
        face_inventory=face_inventory,
        primary_axis=primary_axis,
        bbox_bounds=bbox_bounds,
        axis_tolerance_cos=axis_tolerance_cos,
    )
    is_short_turning_part = (
        float(accepted_cluster.get("dominant_axis_ratio") or 0.0) < min_dominant_axis_ratio
        and float(accepted_cluster.get("exterior_revolved_area_ratio") or 0.0) >= min_revolved_fraction
    )

    turned_end_faces: list[dict[str, Any]] = []
    end_position_tolerance = max(
        TURN_END_FACE_POSITION_TOLERANCE_MM,
        accepted_cluster["part_axis_span_mm"] * TURN_END_FACE_POSITION_TOLERANCE_RATIO,
    )
    part_axis_min, part_axis_max = _project_bounds_range(bbox_bounds, primary_axis)
    cluster_min = accepted_cluster.get("cluster_min")
    cluster_max = accepted_cluster.get("cluster_max")
    if cluster_min is not None and cluster_max is not None:
        for face in face_inventory:
            if not isinstance(face, dict):
                continue
            if str(face.get("surface_type") or "").strip().lower() != "plane":
                continue
            normal = face.get("sample_normal")
            if not isinstance(normal, (list, tuple)) or len(normal) != 3:
                continue
            normalized_normal = _normalize(
                (float(normal[0]), float(normal[1]), float(normal[2]))
            )
            if normalized_normal is None or abs(_dot(normalized_normal, primary_axis)) < axis_tolerance_cos:
                continue
            face_bounds = face.get("bbox_bounds")
            if isinstance(face_bounds, list) and len(face_bounds) == 6:
                face_min, face_max = _project_bounds_range(
                    tuple(float(value) for value in face_bounds),
                    primary_axis,
                )
                center = (face_min + face_max) * 0.5
            else:
                centroid = face.get("centroid_mm")
                if not isinstance(centroid, (list, tuple)) or len(centroid) != 3:
                    continue
                center = _project_scalar(
                    (float(centroid[0]), float(centroid[1]), float(centroid[2])),
                    primary_axis,
                )
            adjacent_face_indices = face.get("adjacent_face_indices")
            has_turning_adjacency = (
                isinstance(adjacent_face_indices, list)
                and any(index in accepted_cluster["face_indices"] for index in adjacent_face_indices)
            )
            within_cluster_span = (cluster_min - end_position_tolerance) <= center <= (
                cluster_max + end_position_tolerance
            )
            at_cluster_end = (
                abs(center - cluster_min) <= end_position_tolerance
                or abs(center - cluster_max) <= end_position_tolerance
            )
            at_part_end = (
                face.get("is_exterior") is True
                and (
                    abs(center - part_axis_min) <= end_position_tolerance
                    or abs(center - part_axis_max) <= end_position_tolerance
                )
            )
            if (has_turning_adjacency and within_cluster_span) or at_cluster_end or at_part_end:
                turned_end_faces.append(face)

    turned_diameter_faces_count = len(turned_diameter_groups)
    turned_profile_faces_count = len(turned_profile_faces)
    turned_end_faces_count = len(turned_end_faces)
    if is_short_turning_part:
        turned_diameter_faces_count = int(
            short_turning_analysis.get("turned_diameter_faces_count") or turned_diameter_faces_count
        )
        turned_profile_faces_count = int(
            short_turning_analysis.get("turned_profile_faces_count") or turned_profile_faces_count
        )
        turned_end_faces_count = int(
            short_turning_analysis.get("turned_end_faces_count") or turned_end_faces_count
        )
    turned_face_count = (
        turned_diameter_faces_count
        + turned_profile_faces_count
        + turned_end_faces_count
    )
    return {
        "rotational_symmetry": turned_face_count > 0,
        "turned_faces_present": turned_face_count > 0,
        "turned_face_count": turned_face_count,
        "turned_diameter_faces_count": turned_diameter_faces_count,
        "turned_end_faces_count": turned_end_faces_count,
        "turned_profile_faces_count": turned_profile_faces_count,
        "outer_diameter_groove_count": int(
            short_turning_analysis.get("outer_diameter_groove_count") or 0
        ),
        "end_face_groove_count": int(short_turning_analysis.get("end_face_groove_count") or 0),
        "primary_axis": primary_axis,
        "candidate_face_count": len(candidate_faces),
        "total_exterior_revolved_area_mm2": round(total_revolved_area, 4),
        "total_exterior_area_mm2": round(total_exterior_area, 4),
        "max_part_dimension_mm": round(max_part_dimension, 4),
        "primary_cluster": {
            key: value
            for key, value in accepted_cluster.items()
            if key not in {"faces"}
        },
        "clusters": cluster_summaries,
        "turned_diameter_groups": turned_diameter_groups,
        "turned_end_face_indices": [
            int(face.get("face_index"))
            for face in turned_end_faces
            if isinstance(face.get("face_index"), int)
        ],
        "axial_bore_groups": short_turning_analysis.get("bore_groups", []),
        "outer_diameter_groove_groups": short_turning_analysis.get(
            "outer_diameter_groove_groups",
            [],
        ),
        "end_face_groove_groups": short_turning_analysis.get("end_face_groove_groups", []),
        "turned_end_clusters": short_turning_analysis.get("turned_end_clusters", []),
        "thresholds": {
            "axis_angle_tolerance_deg": axis_angle_tolerance_deg,
            "min_area_ratio": min_area_ratio,
            "min_span_ratio": min_span_ratio,
            "min_dominant_axis_ratio": min_dominant_axis_ratio,
            "min_revolved_fraction": min_revolved_fraction,
        },
    }


def _distance_point_to_axis(
    point: tuple[float, float, float],
    axis_origin: tuple[float, float, float],
    axis_direction: tuple[float, float, float],
) -> float:
    delta = _sub(point, axis_origin)
    axis_projection = _mul(axis_direction, _dot(delta, axis_direction))
    perpendicular = _sub(delta, axis_projection)
    return math.sqrt(max(0.0, _dot(perpendicular, perpendicular)))


def _axis_offset_from_primary_axis(
    axis_origin: tuple[float, float, float] | None,
    primary_axis: tuple[float, float, float],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> float | None:
    if axis_origin is None:
        return None
    return _distance_point_to_axis(
        axis_origin,
        _bbox_center_point(bbox_bounds),
        primary_axis,
    )


def _turn_radius_from_face(
    face: dict[str, Any],
    axis: tuple[float, float, float],
) -> float | None:
    axis_origin = face.get("axis_origin")
    if isinstance(axis_origin, (list, tuple)) and len(axis_origin) == 3:
        axis_origin_tuple = (
            float(axis_origin[0]),
            float(axis_origin[1]),
            float(axis_origin[2]),
        )
        sample_point = face.get("sample_point_mm")
        if isinstance(sample_point, (list, tuple)) and len(sample_point) == 3:
            sample_point_tuple = (
                float(sample_point[0]),
                float(sample_point[1]),
                float(sample_point[2]),
            )
            radius = _distance_point_to_axis(sample_point_tuple, axis_origin_tuple, axis)
            if math.isfinite(radius) and radius > 0:
                return radius
        centroid = face.get("centroid_mm")
        if isinstance(centroid, (list, tuple)) and len(centroid) == 3:
            centroid_tuple = (
                float(centroid[0]),
                float(centroid[1]),
                float(centroid[2]),
            )
            radius = _distance_point_to_axis(centroid_tuple, axis_origin_tuple, axis)
            if math.isfinite(radius) and radius > 0:
                return radius
    face_bounds = face.get("bbox_bounds")
    if isinstance(face_bounds, list) and len(face_bounds) == 6:
        diameter = _estimate_cylinder_diameter_from_bounds(
            tuple(float(value) for value in face_bounds),
            axis,
        )
        if diameter is not None and math.isfinite(diameter) and diameter > 0:
            return diameter * 0.5
    return None


def _group_turned_diameter_faces(
    cylinder_faces: list[dict[str, Any]],
    *,
    primary_axis: tuple[float, float, float],
    part_axis_span_mm: float,
) -> list[dict[str, Any]]:
    axial_gap_tolerance = max(
        TURN_DIAMETER_AXIAL_GAP_TOLERANCE_MM,
        part_axis_span_mm * TURN_END_FACE_POSITION_TOLERANCE_RATIO,
    )
    candidates: list[dict[str, Any]] = []
    for face in cylinder_faces:
        if not isinstance(face, dict):
            continue
        face_bounds = face.get("bbox_bounds")
        if not isinstance(face_bounds, list) or len(face_bounds) != 6:
            continue
        axis_min, axis_max = _project_bounds_range(
            tuple(float(value) for value in face_bounds),
            primary_axis,
        )
        radius = _turn_radius_from_face(face, primary_axis)
        if radius is None or not math.isfinite(radius) or radius <= 0:
            continue
        candidates.append(
            {
                "face_index": int(face.get("face_index"))
                if isinstance(face.get("face_index"), int)
                else None,
                "radius_mm": radius,
                "axis_min": axis_min,
                "axis_max": axis_max,
            }
        )

    groups: list[dict[str, Any]] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (item["radius_mm"], item["axis_min"], item["face_index"] or 0),
    ):
        matched_group = None
        for group in groups:
            if abs(candidate["radius_mm"] - group["radius_mm"]) > TURN_DIAMETER_RADIUS_TOLERANCE_MM:
                continue
            overlaps_or_touches = (
                candidate["axis_min"] <= group["axis_max"] + axial_gap_tolerance
                and candidate["axis_max"] >= group["axis_min"] - axial_gap_tolerance
            )
            if not overlaps_or_touches:
                continue
            matched_group = group
            break
        if matched_group is None:
            groups.append(
                {
                    "radius_mm": candidate["radius_mm"],
                    "axis_min": candidate["axis_min"],
                    "axis_max": candidate["axis_max"],
                    "face_indices": [candidate["face_index"]]
                    if candidate["face_index"] is not None
                    else [],
                }
            )
            continue
        matched_group["radius_mm"] = (
            matched_group["radius_mm"] + candidate["radius_mm"]
        ) * 0.5
        matched_group["axis_min"] = min(matched_group["axis_min"], candidate["axis_min"])
        matched_group["axis_max"] = max(matched_group["axis_max"], candidate["axis_max"])
        if candidate["face_index"] is not None:
            matched_group["face_indices"].append(candidate["face_index"])

    return [
        {
            "radius_mm": round(group["radius_mm"], 4),
            "axis_min": round(group["axis_min"], 4),
            "axis_max": round(group["axis_max"], 4),
            "face_indices": sorted(group["face_indices"]),
        }
        for group in groups
    ]


def _cluster_short_turning_cylinders(
    cylinder_faces: list[dict[str, Any]],
    *,
    primary_axis: tuple[float, float, float],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> list[dict[str, Any]]:
    center_offset_limit = max(
        TURN_SHORT_AXIS_CENTER_OFFSET_MM,
        max(
            bbox_bounds[3] - bbox_bounds[0],
            bbox_bounds[4] - bbox_bounds[1],
            bbox_bounds[5] - bbox_bounds[2],
            0.0,
        )
        * TURN_SHORT_AXIS_CENTER_OFFSET_RATIO,
    )
    candidates: list[dict[str, Any]] = []
    for face in cylinder_faces:
        if not isinstance(face, dict):
            continue
        face_bounds = face.get("bbox_bounds")
        if not isinstance(face_bounds, list) or len(face_bounds) != 6:
            continue
        axis_origin_payload = face.get("axis_origin")
        axis_origin = None
        if isinstance(axis_origin_payload, (list, tuple)) and len(axis_origin_payload) == 3:
            axis_origin = (
                float(axis_origin_payload[0]),
                float(axis_origin_payload[1]),
                float(axis_origin_payload[2]),
            )
        axis_offset = _axis_offset_from_primary_axis(axis_origin, primary_axis, bbox_bounds)
        if axis_offset is None or axis_offset > center_offset_limit:
            continue
        axis_min, axis_max = _project_bounds_range(
            tuple(float(value) for value in face_bounds),
            primary_axis,
        )
        radius = _turn_radius_from_face(face, primary_axis)
        if radius is None or not math.isfinite(radius) or radius <= 0:
            continue
        candidates.append(
            {
                "face_index": int(face.get("face_index"))
                if isinstance(face.get("face_index"), int)
                else None,
                "radius_mm": radius,
                "axis_min": axis_min,
                "axis_max": axis_max,
                "span_mm": max(0.0, axis_max - axis_min),
                "is_exterior": face.get("is_exterior"),
                "surface_type": str(face.get("surface_type") or "").strip().lower(),
            }
        )

    groups: list[dict[str, Any]] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (item["axis_min"], item["radius_mm"], item["face_index"] or 0),
    ):
        matched_group = None
        for group in groups:
            if abs(candidate["radius_mm"] - group["radius_mm"]) > TURN_SHORT_RADIUS_TOLERANCE_MM:
                continue
            overlaps_or_touches = (
                candidate["axis_min"] <= group["axis_max"] + TURN_DIAMETER_AXIAL_GAP_TOLERANCE_MM
                and candidate["axis_max"] >= group["axis_min"] - TURN_DIAMETER_AXIAL_GAP_TOLERANCE_MM
            )
            if not overlaps_or_touches:
                continue
            matched_group = group
            break
        if matched_group is None:
            groups.append(
                {
                    "radius_mm": candidate["radius_mm"],
                    "axis_min": candidate["axis_min"],
                    "axis_max": candidate["axis_max"],
                    "face_indices": [candidate["face_index"]]
                    if candidate["face_index"] is not None
                    else [],
                    "has_exterior_face": candidate["is_exterior"] is True,
                    "has_interior_face": candidate["is_exterior"] is False,
                }
            )
            continue
        matched_group["radius_mm"] = (matched_group["radius_mm"] + candidate["radius_mm"]) * 0.5
        matched_group["axis_min"] = min(matched_group["axis_min"], candidate["axis_min"])
        matched_group["axis_max"] = max(matched_group["axis_max"], candidate["axis_max"])
        if candidate["face_index"] is not None:
            matched_group["face_indices"].append(candidate["face_index"])
        if candidate["is_exterior"] is True:
            matched_group["has_exterior_face"] = True
        if candidate["is_exterior"] is False:
            matched_group["has_interior_face"] = True

    return [
        {
            "radius_mm": round(group["radius_mm"], 4),
            "axis_min": round(group["axis_min"], 4),
            "axis_max": round(group["axis_max"], 4),
            "span_mm": round(max(0.0, group["axis_max"] - group["axis_min"]), 4),
            "face_indices": sorted(group["face_indices"]),
            "has_exterior_face": bool(group["has_exterior_face"]),
            "has_interior_face": bool(group["has_interior_face"]),
        }
        for group in groups
    ]


def _analyze_short_turning_axis_features(
    *,
    accepted_cluster: dict[str, Any],
    face_inventory: list[dict[str, Any]],
    primary_axis: tuple[float, float, float],
    bbox_bounds: tuple[float, float, float, float, float, float],
    axis_tolerance_cos: float,
) -> dict[str, Any]:
    turned_faces = list(accepted_cluster.get("faces", []))
    turned_cylinder_faces = [
        face
        for face in turned_faces
        if str(face.get("surface_type") or "").strip().lower() == "cylinder"
    ]
    cylinder_faces = [
        face
        for face in face_inventory
        if str(face.get("surface_type") or "").strip().lower() == "cylinder"
        and _axis_alignment_cos(_surface_axis_direction(face), primary_axis) >= axis_tolerance_cos
    ]
    revolved_profile_faces = [
        face
        for face in turned_faces
        if str(face.get("surface_type") or "").strip().lower() in {"cone", "torus"}
    ]
    short_cylinder_groups = _cluster_short_turning_cylinders(
        cylinder_faces,
        primary_axis=primary_axis,
        bbox_bounds=bbox_bounds,
    )
    max_exterior_radius = max(
        (
            group["radius_mm"]
            for group in short_cylinder_groups
            if group.get("has_exterior_face")
        ),
        default=0.0,
    )
    if max_exterior_radius <= 0:
        return {}

    radius_floor = max(
        TURN_SHORT_SMALL_HOLE_RADIUS_MAX_MM,
        max_exterior_radius * 0.05,
    )
    turned_diameter_faces = [
        face
        for face in turned_cylinder_faces
        if face.get("is_exterior") is True
        and (_turn_radius_from_face(face, primary_axis) or 0.0) >= radius_floor
        and (
            _axis_offset_from_primary_axis(
                (
                    float(face["axis_origin"][0]),
                    float(face["axis_origin"][1]),
                    float(face["axis_origin"][2]),
                )
                if isinstance(face.get("axis_origin"), (list, tuple))
                and len(face.get("axis_origin", [])) == 3
                else None,
                primary_axis,
                bbox_bounds,
            )
            or 0.0
        )
        <= max(TURN_SHORT_AXIS_CENTER_OFFSET_MM, max_exterior_radius * TURN_SHORT_AXIS_CENTER_OFFSET_RATIO)
    ]

    profile_radius_threshold = max_exterior_radius * TURN_SHORT_PROFILE_MIN_RADIUS_RATIO
    turned_profile_faces = []
    for face in revolved_profile_faces:
        surface_type = str(face.get("surface_type") or "").strip().lower()
        radius = _turn_radius_from_face(face, primary_axis) or 0.0
        face_bounds = face.get("bbox_bounds")
        axis_span = 0.0
        if isinstance(face_bounds, list) and len(face_bounds) == 6:
            face_min, face_max = _project_bounds_range(
                tuple(float(value) for value in face_bounds),
                primary_axis,
            )
            axis_span = max(0.0, face_max - face_min)
        min_span = (
            TURN_SHORT_TORUS_MIN_SPAN_MM
            if surface_type == "torus"
            else TURN_SHORT_PROFILE_MIN_SPAN_MM
        )
        if radius >= profile_radius_threshold and axis_span >= min_span:
            turned_profile_faces.append(face)

    part_axis_min, part_axis_max = _project_bounds_range(bbox_bounds, primary_axis)
    outer_diameter_groove_groups: list[dict[str, Any]] = []
    end_face_groove_groups: list[dict[str, Any]] = []
    exterior_bore_groups: list[dict[str, Any]] = []
    interior_bore_groups_by_radius: dict[float, dict[str, Any]] = {}
    sorted_groups = sorted(short_cylinder_groups, key=lambda item: (item["axis_min"], item["radius_mm"]))
    for index, group in enumerate(sorted_groups):
        radius = float(group["radius_mm"])
        span = float(group["span_mm"])
        touches_part_start = abs(float(group["axis_min"]) - part_axis_min) <= TURN_END_FACE_POSITION_TOLERANCE_MM
        touches_part_end = abs(float(group["axis_max"]) - part_axis_max) <= TURN_END_FACE_POSITION_TOLERANCE_MM
        if group.get("has_interior_face") and radius <= max_exterior_radius * TURN_SHORT_BORE_MAX_RADIUS_RATIO:
            if span >= TURN_SHORT_BORE_MIN_SPAN_MM:
                radius_key = round(radius / TURN_SHORT_RADIUS_TOLERANCE_MM) * TURN_SHORT_RADIUS_TOLERANCE_MM
                merged = interior_bore_groups_by_radius.setdefault(
                    round(radius_key, 4),
                    {
                        "radius_mm": round(radius, 4),
                        "axis_min": float(group["axis_min"]),
                        "axis_max": float(group["axis_max"]),
                        "face_indices": [],
                    },
                )
                merged["axis_min"] = min(merged["axis_min"], float(group["axis_min"]))
                merged["axis_max"] = max(merged["axis_max"], float(group["axis_max"]))
                merged["face_indices"].extend(group.get("face_indices", []))

        if not group.get("has_exterior_face"):
            if (
                span <= TURN_SHORT_END_GROOVE_MAX_SPAN_MM
                and (touches_part_start or touches_part_end)
                and radius >= max_exterior_radius * TURN_SHORT_BORE_MIN_RADIUS_RATIO
            ):
                end_face_groove_groups.append(group)
            continue

        left_neighbor = next(
            (
                candidate
                for candidate in reversed(sorted_groups[:index])
                if candidate.get("has_exterior_face")
            ),
            None,
        )
        right_neighbor = next(
            (
                candidate
                for candidate in sorted_groups[index + 1 :]
                if candidate.get("has_exterior_face")
            ),
            None,
        )
        left_radius = float(left_neighbor["radius_mm"]) if isinstance(left_neighbor, dict) else None
        right_radius = float(right_neighbor["radius_mm"]) if isinstance(right_neighbor, dict) else None

        if (
            span <= TURN_SHORT_GROOVE_MAX_SPAN_MM
            and not touches_part_start
            and not touches_part_end
            and left_radius is not None
            and right_radius is not None
            and left_radius >= radius + TURN_SHORT_GROOVE_MIN_DEPTH_MM
            and right_radius >= radius + TURN_SHORT_GROOVE_MIN_DEPTH_MM
        ):
            outer_diameter_groove_groups.append(group)

        if (
            span >= TURN_SHORT_BORE_MIN_SPAN_MM
            and radius >= max_exterior_radius * TURN_SHORT_BORE_MIN_RADIUS_RATIO
            and radius <= max_exterior_radius * TURN_SHORT_BORE_MAX_RADIUS_RATIO
            and (touches_part_start or touches_part_end)
            and len(group.get("face_indices", [])) >= 2
        ):
            exterior_bore_groups.append(group)

    bore_groups = [
        {
            "radius_mm": round(group["radius_mm"], 4),
            "axis_min": round(group["axis_min"], 4),
            "axis_max": round(group["axis_max"], 4),
            "face_indices": sorted(
                index
                for index in group.get("face_indices", [])
                if isinstance(index, int)
            ),
        }
        for group in exterior_bore_groups
    ]
    for radius_key in sorted(interior_bore_groups_by_radius):
        group = interior_bore_groups_by_radius[radius_key]
        bore_groups.append(
            {
                "radius_mm": round(group["radius_mm"], 4),
                "axis_min": round(group["axis_min"], 4),
                "axis_max": round(group["axis_max"], 4),
                "face_indices": sorted(set(group["face_indices"])),
            }
        )

    face_lookup = {
        int(face.get("face_index")): face
        for face in face_inventory
        if isinstance(face, dict) and isinstance(face.get("face_index"), int)
    }
    plane_records: list[dict[str, Any]] = []
    end_position_tolerance = max(
        TURN_END_FACE_POSITION_TOLERANCE_MM,
        accepted_cluster["part_axis_span_mm"] * TURN_END_FACE_POSITION_TOLERANCE_RATIO,
    )
    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        if str(face.get("surface_type") or "").strip().lower() != "plane":
            continue
        normal = _normalized_face_vector(face)
        if normal is None or abs(_dot(normal, primary_axis)) < axis_tolerance_cos:
            continue
        face_bounds = face.get("bbox_bounds")
        if not isinstance(face_bounds, list) or len(face_bounds) != 6:
            continue
        axis_min, axis_max = _project_bounds_range(
            tuple(float(value) for value in face_bounds),
            primary_axis,
        )
        axis_position = (axis_min + axis_max) * 0.5
        adjacent_faces = _neighbor_surface_records(face, face_lookup)
        adjacent_radii = [
            _turn_radius_from_face(candidate, primary_axis) or 0.0
            for candidate in adjacent_faces
            if str(candidate.get("surface_type") or "").strip().lower() in {"cylinder", "cone", "torus"}
            and (
                _axis_offset_from_primary_axis(
                    (
                        float(candidate["axis_origin"][0]),
                        float(candidate["axis_origin"][1]),
                        float(candidate["axis_origin"][2]),
                    )
                    if isinstance(candidate.get("axis_origin"), (list, tuple))
                    and len(candidate.get("axis_origin", [])) == 3
                    else None,
                    primary_axis,
                    bbox_bounds,
                )
                or 0.0
            )
            <= max(TURN_SHORT_AXIS_CENTER_OFFSET_MM, max_exterior_radius * TURN_SHORT_AXIS_CENTER_OFFSET_RATIO)
        ]
        plane_records.append(
            {
                "face_index": int(face.get("face_index"))
                if isinstance(face.get("face_index"), int)
                else None,
                "axis_position": axis_position,
                "touches_part_end": (
                    abs(axis_position - part_axis_min) <= end_position_tolerance
                    or abs(axis_position - part_axis_max) <= end_position_tolerance
                ),
                "max_adjacent_radius_mm": max(adjacent_radii, default=0.0),
            }
        )

    plane_clusters: list[list[dict[str, Any]]] = []
    for plane in sorted(plane_records, key=lambda item: item["axis_position"]):
        if (
            not plane_clusters
            or plane["axis_position"] - plane_clusters[-1][-1]["axis_position"] > TURN_SHORT_END_CLUSTER_GAP_MM
        ):
            plane_clusters.append([plane])
        else:
            plane_clusters[-1].append(plane)

    turned_end_clusters = []
    min_end_radius = max_exterior_radius * TURN_SHORT_END_MIN_RADIUS_RATIO
    for cluster in plane_clusters:
        max_adjacent_radius = max(
            (record["max_adjacent_radius_mm"] for record in cluster),
            default=0.0,
        )
        if max_adjacent_radius < min_end_radius:
            continue
        turned_end_clusters.append(
            {
                "axis_position_mm": round(
                    sum(record["axis_position"] for record in cluster) / len(cluster),
                    4,
                ),
                "face_indices": sorted(
                    record["face_index"]
                    for record in cluster
                    if isinstance(record.get("face_index"), int)
                ),
                "max_adjacent_radius_mm": round(max_adjacent_radius, 4),
                "touches_part_end": any(record.get("touches_part_end") for record in cluster),
            }
        )

    return {
        "turned_diameter_faces_count": len(turned_diameter_faces),
        "turned_profile_faces_count": len(turned_profile_faces),
        "turned_end_faces_count": len(turned_end_clusters),
        "outer_diameter_groove_count": len(outer_diameter_groove_groups),
        "end_face_groove_count": len(end_face_groove_groups),
        "bore_groups": bore_groups,
        "outer_diameter_groove_groups": outer_diameter_groove_groups,
        "end_face_groove_groups": end_face_groove_groups,
        "turned_end_clusters": turned_end_clusters,
    }


def _dominant_axis_index(axis: tuple[float, float, float]) -> int:
    return max(range(3), key=lambda index: abs(axis[index]))


def _axis_alignment_cos(
    axis_a: tuple[float, float, float] | None,
    axis_b: tuple[float, float, float] | None,
) -> float:
    if axis_a is None or axis_b is None:
        return 0.0
    canonical_a = _canonical_axis(axis_a)
    canonical_b = _canonical_axis(axis_b)
    if canonical_a is None or canonical_b is None:
        return 0.0
    return abs(_dot(canonical_a, canonical_b))


def _perpendicular_spans_from_bounds(
    bounds: tuple[float, float, float, float, float, float],
    axis: tuple[float, float, float],
) -> tuple[float, float]:
    spans = (
        bounds[3] - bounds[0],
        bounds[4] - bounds[1],
        bounds[5] - bounds[2],
    )
    axis_index = _dominant_axis_index(axis)
    perpendicular_spans = [span for index, span in enumerate(spans) if index != axis_index]
    if len(perpendicular_spans) != 2:
        return 0.0, 0.0
    return float(perpendicular_spans[0]), float(perpendicular_spans[1])


def _estimate_cylinder_diameter_from_bounds(
    bounds: tuple[float, float, float, float, float, float],
    axis: tuple[float, float, float],
) -> float | None:
    perpendicular_spans = _perpendicular_spans_from_bounds(bounds, axis)
    diameter = max(perpendicular_spans, default=0.0)
    if not math.isfinite(diameter) or diameter <= 0:
        return None
    return diameter


def _cylindrical_face_metrics(face: dict[str, Any]) -> dict[str, Any] | None:
    if str(face.get("surface_type") or "").strip().lower() != "cylinder":
        return None
    axis = _surface_axis_direction(face)
    if axis is None:
        return None
    face_bounds = face.get("bbox_bounds")
    if not isinstance(face_bounds, list) or len(face_bounds) != 6:
        return None
    bounds = tuple(float(value) for value in face_bounds)
    diameter = _estimate_cylinder_diameter_from_bounds(bounds, axis)
    if diameter is None or not math.isfinite(diameter) or diameter <= 0:
        return None
    depth = float(face.get("axial_span_mm") or 0.0)
    if not math.isfinite(depth) or depth <= 0:
        depth = _project_bounds_span(bounds, axis)
    if not math.isfinite(depth) or depth <= 0:
        return None
    area = float(face.get("area_mm2") or 0.0)
    if not math.isfinite(area) or area <= 0:
        return None
    axis_origin_payload = face.get("axis_origin")
    axis_origin = None
    if isinstance(axis_origin_payload, (list, tuple)) and len(axis_origin_payload) == 3:
        axis_origin = (
            float(axis_origin_payload[0]),
            float(axis_origin_payload[1]),
            float(axis_origin_payload[2]),
        )
    return {
        "axis_direction": axis,
        "axis_origin": axis_origin,
        "bbox_bounds": bounds,
        "diameter_mm": diameter,
        "depth_mm": depth,
        "area_mm2": area,
        "completeness_ratio": area / max(math.pi * diameter * depth, 1e-9),
        "perpendicular_spans_mm": _perpendicular_spans_from_bounds(bounds, axis),
    }


def _axis_line_key(
    axis: tuple[float, float, float],
    axis_origin: tuple[float, float, float] | None,
    *,
    rounding_mm: float = 0.5,
) -> tuple[Any, ...] | None:
    canonical_axis = _canonical_axis(axis)
    if canonical_axis is None or axis_origin is None:
        return None
    projected = _dot(axis_origin, canonical_axis)
    perpendicular_anchor = _sub(axis_origin, _mul(canonical_axis, projected))
    rounded_anchor = tuple(
        round(value / rounding_mm) * rounding_mm
        for value in perpendicular_anchor
    )
    return (
        round(canonical_axis[0], 6),
        round(canonical_axis[1], 6),
        round(canonical_axis[2], 6),
        round(rounded_anchor[0], 3),
        round(rounded_anchor[1], 3),
        round(rounded_anchor[2], 3),
    )


def _split_axis_line_components(
    cylinders: list[dict[str, Any]],
    *,
    axial_gap_tolerance_mm: float = HOLE_COMPONENT_AXIAL_GAP_TOLERANCE_MM,
) -> list[list[dict[str, Any]]]:
    ordered = sorted(
        (
            cylinder
            for cylinder in cylinders
            if isinstance(cylinder, dict)
            and isinstance(cylinder.get("axis_min"), (int, float))
            and isinstance(cylinder.get("axis_max"), (int, float))
        ),
        key=lambda item: (float(item["axis_min"]), float(item["axis_max"]), item.get("face_index") or 0),
    )
    components: list[list[dict[str, Any]]] = []
    current_component: list[dict[str, Any]] = []
    current_axis_max: float | None = None
    for cylinder in ordered:
        axis_min = float(cylinder["axis_min"])
        axis_max = float(cylinder["axis_max"])
        if not current_component:
            current_component = [cylinder]
            current_axis_max = axis_max
            continue
        if current_axis_max is not None and axis_min <= current_axis_max + axial_gap_tolerance_mm:
            current_component.append(cylinder)
            current_axis_max = max(current_axis_max, axis_max)
            continue
        components.append(current_component)
        current_component = [cylinder]
        current_axis_max = axis_max
    if current_component:
        components.append(current_component)
    return components


def detect_hole_features_from_face_inventory(
    face_inventory: list[dict[str, Any]],
    *,
    bbox_bounds: tuple[float, float, float, float, float, float],
    turning_detection: dict[str, Any] | None = None,
    axis_angle_tolerance_deg: float = TURN_AXIS_ANGLE_TOLERANCE_DEG,
) -> dict[str, Any]:
    axis_tolerance_cos = math.cos(math.radians(max(0.0, axis_angle_tolerance_deg)))
    face_lookup = {
        int(face.get("face_index")): face
        for face in face_inventory
        if isinstance(face, dict) and isinstance(face.get("face_index"), int)
    }
    primary_axis = None
    if isinstance(turning_detection, dict):
        axis_payload = turning_detection.get("primary_axis")
        if isinstance(axis_payload, (list, tuple)) and len(axis_payload) == 3:
            primary_axis = _canonical_axis(
                (float(axis_payload[0]), float(axis_payload[1]), float(axis_payload[2]))
            )

    cylinders: list[dict[str, Any]] = []
    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        metrics = _cylindrical_face_metrics(face)
        if metrics is None:
            continue
        axis = metrics["axis_direction"]
        axis_origin = metrics["axis_origin"]
        axis_min, axis_max = _project_bounds_range(metrics["bbox_bounds"], axis)
        cylinders.append(
            {
                "face_index": int(face.get("face_index"))
                if isinstance(face.get("face_index"), int)
                else None,
                "axis_direction": axis,
                "axis_origin": axis_origin,
                "axis_line_key": _axis_line_key(axis, axis_origin),
                "diameter_mm": metrics["diameter_mm"],
                "depth_mm": metrics["depth_mm"],
                "area_mm2": metrics["area_mm2"],
                "completeness_ratio": metrics["completeness_ratio"],
                "depth_to_diameter_ratio": metrics["depth_mm"] / max(metrics["diameter_mm"], 1e-9),
                "is_exterior": face.get("is_exterior"),
                "bbox_bounds": metrics["bbox_bounds"],
                "axis_min": axis_min,
                "axis_max": axis_max,
                "perpendicular_spans_mm": metrics["perpendicular_spans_mm"],
                "adjacent_face_indices": list(face.get("adjacent_face_indices") or []),
            }
        )

    if not cylinders:
        return {
            "hole_count": 0,
            "through_hole_count": 0,
            "partial_hole_count": 0,
            "bore_count": 0,
            "threaded_holes_count": 0,
            "candidates": [],
            "rejected_candidates": [],
        }

    grouped_cylinders: dict[tuple[Any, ...] | None, list[dict[str, Any]]] = {}
    for cylinder in cylinders:
        grouped_cylinders.setdefault(cylinder.get("axis_line_key"), []).append(cylinder)

    hole_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    for axis_line_key, group in grouped_cylinders.items():
        ordered_group = sorted(group, key=lambda item: (item["diameter_mm"], item["face_index"] or 0))
        eligible_ordered_group: list[dict[str, Any]] = []
        for cylinder in ordered_group:
            aligned_with_turn_axis = (
                primary_axis is not None
                and _axis_alignment_cos(cylinder["axis_direction"], primary_axis) >= axis_tolerance_cos
            )
            if (
                aligned_with_turn_axis
                and cylinder.get("is_exterior") is True
                and float(cylinder.get("diameter_mm") or 0.0) > TURN_SHORT_SMALL_HOLE_RADIUS_MAX_MM * 2.0
            ):
                rejected_candidates.append(
                    {
                        **cylinder,
                        "axis_line_key": axis_line_key,
                        "selection_reason": "turning_exterior_cylinder",
                        "nested_group_size": len(ordered_group),
                    }
                )
                continue
            eligible_ordered_group.append(cylinder)

        if not eligible_ordered_group:
            continue

        group_diameters = [
            float(candidate["diameter_mm"])
            for candidate in eligible_ordered_group
            if isinstance(candidate.get("diameter_mm"), (int, float))
        ]
        same_diameter_group = (
            max(group_diameters, default=0.0) - min(group_diameters, default=0.0)
            <= HOLE_DIAMETER_BAND_TOLERANCE_MM
        )
        all_interior_group = all(
            candidate.get("is_exterior") is False for candidate in eligible_ordered_group
        )
        if len(eligible_ordered_group) <= 2:
            eligible_components = [eligible_ordered_group]
            if len(eligible_ordered_group) == 2 and same_diameter_group and all_interior_group:
                ordered_pair = sorted(
                    eligible_ordered_group,
                    key=lambda item: (
                        float(item.get("axis_min") or 0.0),
                        float(item.get("axis_max") or 0.0),
                        item.get("face_index") or 0,
                    ),
                )
                pair_is_disjoint = (
                    float(ordered_pair[1].get("axis_min") or 0.0)
                    > float(ordered_pair[0].get("axis_max") or 0.0)
                    + HOLE_COMPONENT_AXIAL_GAP_TOLERANCE_MM
                )
                if pair_is_disjoint:
                    def _supports_split_interior_pair(cylinder: dict[str, Any]) -> bool:
                        face_index = cylinder.get("face_index")
                        face = face_lookup.get(face_index) if isinstance(face_index, int) else None
                        neighbor_faces = (
                            _neighbor_surface_records(face, face_lookup)
                            if isinstance(face, dict)
                            else []
                        )
                        has_exterior_plane_neighbor = any(
                            str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                            and neighbor.get("is_exterior") is True
                            for neighbor in neighbor_faces
                        )
                        has_cylinder_neighbor = any(
                            str(neighbor.get("surface_type") or "").strip().lower() == "cylinder"
                            for neighbor in neighbor_faces
                        )
                        return has_exterior_plane_neighbor and has_cylinder_neighbor

                    if all(_supports_split_interior_pair(cylinder) for cylinder in ordered_pair):
                        eligible_components = [[cylinder] for cylinder in ordered_pair]
        else:
            eligible_components = _split_axis_line_components(eligible_ordered_group)
        for eligible_group in eligible_components:
            if not eligible_group:
                continue

            eligible_group_axis_span = max(
                (
                    float(group_candidate.get("axis_max") or 0.0)
                    for group_candidate in eligible_group
                ),
                default=0.0,
            ) - min(
                (
                    float(group_candidate.get("axis_min") or 0.0)
                    for group_candidate in eligible_group
                ),
                default=0.0,
            )

            if len(eligible_group) == 1:
                cylinder = eligible_group[0]
                face_index = cylinder.get("face_index")
                face = face_lookup.get(face_index) if isinstance(face_index, int) else None
                neighbor_faces = _neighbor_surface_records(face, face_lookup) if isinstance(face, dict) else []
                axis_aligned_plane_neighbors = 0
                orthogonal_plane_neighbors = 0
                for neighbor in neighbor_faces:
                    if str(neighbor.get("surface_type") or "").strip().lower() != "plane":
                        continue
                    alignment = _axis_alignment_cos(
                        cylinder["axis_direction"],
                        _normalized_face_vector(neighbor),
                    )
                    if alignment >= 0.98:
                        axis_aligned_plane_neighbors += 1
                    elif alignment <= 0.2:
                        orthogonal_plane_neighbors += 1
                if (
                    cylinder.get("is_exterior") is False
                    and cylinder["completeness_ratio"] <= HOLE_SINGLE_RECESS_MAX_COMPLETENESS
                    and len(neighbor_faces) >= HOLE_SINGLE_RECESS_MIN_NEIGHBOR_COUNT
                    and axis_aligned_plane_neighbors >= 1
                    and orthogonal_plane_neighbors >= 1
                ):
                    rejected_candidates.append(
                        {
                            **cylinder,
                            "axis_line_key": axis_line_key,
                            "selection_reason": "single_cylinder_recess_blend",
                            "nested_group_size": len(eligible_group),
                        }
                    )
                    continue

            if len(eligible_group) > 1:
                diameters = [candidate["diameter_mm"] for candidate in eligible_group]
                same_diameter_band = (
                    max(diameters, default=0.0) - min(diameters, default=0.0)
                    <= HOLE_DIAMETER_BAND_TOLERANCE_MM
                )
                exterior_candidates = [
                    candidate
                    for candidate in eligible_group
                    if candidate.get("is_exterior") is True
                ]
                interior_candidates = [
                    candidate
                    for candidate in eligible_group
                    if candidate.get("is_exterior") is False
                ]
                exterior_profile_band = (
                    len(eligible_group) >= 3
                    and all(candidate.get("is_exterior") is True for candidate in eligible_group)
                    and all(
                        candidate["completeness_ratio"] < HOLE_THROUGH_COMPLETENESS_MIN
                        for candidate in eligible_group
                    )
                )
                if same_diameter_band and all(candidate.get("is_exterior") is True for candidate in eligible_group):
                    exterior_profile_band = True
                if exterior_profile_band:
                    for candidate in eligible_group:
                        rejected_candidates.append(
                            {
                                **candidate,
                                "axis_line_key": axis_line_key,
                                "selection_reason": "exterior_profile_band",
                                "nested_group_size": len(eligible_group),
                            }
                        )
                    continue

                exterior_plane_neighbor_counts: list[int] = []
                for exterior_candidate in exterior_candidates:
                    face_index = exterior_candidate.get("face_index")
                    face = face_lookup.get(face_index) if isinstance(face_index, int) else None
                    neighbor_faces = (
                        _neighbor_surface_records(face, face_lookup)
                        if isinstance(face, dict)
                        else []
                    )
                    exterior_plane_neighbor_counts.append(
                        sum(
                            1
                            for neighbor in neighbor_faces
                            if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                            and neighbor.get("is_exterior") is True
                        )
                    )

                slot_profile_group = (
                    primary_axis is None
                    and not same_diameter_band
                    and len(exterior_candidates) >= 2
                    and len(interior_candidates) >= 1
                    and min(exterior_plane_neighbor_counts, default=0) >= 5
                    and max(
                        (float(candidate.get("depth_mm") or 0.0) for candidate in exterior_candidates),
                        default=0.0,
                    )
                    >= max(
                        (float(candidate.get("depth_mm") or 0.0) for candidate in interior_candidates),
                        default=0.0,
                    )
                    * 1.2
                    and eligible_group_axis_span > 0.0
                    and max(
                        (float(candidate.get("depth_mm") or 0.0) for candidate in exterior_candidates),
                        default=0.0,
                    )
                    < eligible_group_axis_span * 0.95
                )
                if slot_profile_group:
                    for candidate in eligible_group:
                        rejected_candidates.append(
                            {
                                **candidate,
                                "axis_line_key": axis_line_key,
                                "selection_reason": "slot_profile_group",
                                "nested_group_size": len(eligible_group),
                            }
                        )
                    continue

            nested = len(eligible_group) > 1
            full_span_exterior_candidate: dict[str, Any] | None = None
            if nested:
                full_span_exterior_candidates = [
                    group_candidate
                    for group_candidate in eligible_group
                    if group_candidate.get("is_exterior") is True
                    and len(exterior_candidates) >= 4
                    and len(eligible_group) >= 3
                    and float(group_candidate.get("depth_mm") or 0.0)
                    >= eligible_group_axis_span * 0.95
                    and float(group_candidate.get("completeness_ratio") or 0.0)
                    < HOLE_THROUGH_COMPLETENESS_MIN
                    and sum(
                        1
                        for neighbor in _neighbor_surface_records(
                            face_lookup.get(group_candidate.get("face_index"))
                            if isinstance(group_candidate.get("face_index"), int)
                            else None,
                            face_lookup,
                        )
                        if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                        and neighbor.get("is_exterior") is True
                    )
                    >= 4
                ]
                if full_span_exterior_candidates:
                    full_span_exterior_candidate = max(
                        full_span_exterior_candidates,
                        key=lambda item: (
                            float(item.get("diameter_mm") or 0.0),
                            item.get("face_index") or 0,
                        ),
                    )
                    candidate_pool = [full_span_exterior_candidate]
                else:
                    candidate_pool = [
                        min(
                            eligible_group,
                            key=lambda item: (float(item["diameter_mm"]), item.get("face_index") or 0),
                        )
                    ]
            else:
                candidate_pool = eligible_group
            group_completeness_ratio = min(
                1.0,
                sum(
                    float(group_candidate.get("completeness_ratio") or 0.0)
                    for group_candidate in eligible_group
                ),
            )

            for candidate in candidate_pool:
                depth_ratio = candidate["depth_to_diameter_ratio"]
                completeness = candidate["completeness_ratio"]
                is_exterior = candidate.get("is_exterior")

                accept = False
                reason = "rejected"
                if depth_ratio < HOLE_MIN_DEPTH_TO_DIAMETER_RATIO:
                    reason = "too_shallow"
                elif full_span_exterior_candidate is not None and candidate is full_span_exterior_candidate:
                    accept = True
                    reason = "full_span_exterior_partial"
                elif nested:
                    accept = True
                    reason = "smallest_nested_cylinder"
                elif is_exterior is False:
                    accept = True
                    reason = "interior_cylinder"
                elif completeness >= HOLE_THROUGH_COMPLETENESS_MIN and depth_ratio >= 0.75:
                    accept = True
                    reason = "exterior_full_cylinder"
                else:
                    reason = "exterior_segment_without_nested_support"

                payload = {
                    **candidate,
                    "axis_line_key": axis_line_key,
                    "selection_reason": reason,
                    "nested_group_size": len(eligible_group),
                    "group_face_indices": [
                        int(group_candidate["face_index"])
                        for group_candidate in eligible_group
                        if isinstance(group_candidate.get("face_index"), int)
                    ],
                    "group_diameters_mm": [
                        round(float(group_candidate["diameter_mm"]), 4)
                        for group_candidate in eligible_group
                    ],
                    "group_depths_mm": [
                        round(float(group_candidate["depth_mm"]), 4)
                        for group_candidate in eligible_group
                    ],
                    "group_completeness_ratio": round(group_completeness_ratio, 4),
                }
                if accept:
                    hole_candidates.append(payload)
                else:
                    rejected_candidates.append(payload)

    through_hole_count = 0
    partial_hole_count = 0
    bore_count = 0
    stepped_hole_count = 0
    diameters: list[float] = []
    depths: list[float] = []
    typed_candidates: list[dict[str, Any]] = []
    threaded_holes_count = 0

    for candidate in hole_candidates:
        axis = candidate["axis_direction"]
        axis_span = _project_bounds_span(bbox_bounds, axis)
        perpendicular_part_spans = _perpendicular_spans_from_bounds(bbox_bounds, axis)
        positive_perpendicular_spans = [
            span for span in perpendicular_part_spans if math.isfinite(span) and span > 0
        ]
        min_perpendicular_part_span = min(positive_perpendicular_spans, default=0.0)
        aligned_with_turn_axis = (
            primary_axis is not None
            and _axis_alignment_cos(axis, primary_axis) >= axis_tolerance_cos
        )
        group_diameters = [
            float(value)
            for value in candidate.get("group_diameters_mm", [])
            if isinstance(value, (int, float))
        ]
        group_depths = [
            float(value)
            for value in candidate.get("group_depths_mm", [])
            if isinstance(value, (int, float))
        ]
        same_diameter_band = (
            max(group_diameters, default=candidate["diameter_mm"])
            - min(group_diameters, default=candidate["diameter_mm"])
            <= HOLE_DIAMETER_BAND_TOLERANCE_MM
        )
        group_completeness_ratio = float(
            candidate.get("group_completeness_ratio", candidate["completeness_ratio"])
        )
        max_group_depth = max(group_depths, default=candidate["depth_mm"])
        max_outer_group_depth = max(
            (
                depth
                for diameter, depth in zip(group_diameters, group_depths)
                if abs(diameter - candidate["diameter_mm"]) > HOLE_DIAMETER_BAND_TOLERANCE_MM
            ),
            default=0.0,
        )
        full_depth_group = (
            axis_span > 0 and candidate["depth_mm"] >= axis_span * HOLE_STEPPED_FULL_DEPTH_RATIO
        )
        all_interior_group = (
            candidate.get("nested_group_size", 0) > 1
            and all(
                isinstance(face_index, int) and face_lookup.get(face_index, {}).get("is_exterior") is False
                for face_index in candidate.get("group_face_indices", [])
            )
        )
        max_group_diameter = max(group_diameters, default=candidate["diameter_mm"])

        subtype = "through_hole"
        if (
            aligned_with_turn_axis
            and candidate.get("is_exterior") is not True
            and axis_span > 0
            and candidate["depth_mm"] >= axis_span * HOLE_BORE_DEPTH_RATIO
            and min_perpendicular_part_span > 0
            and candidate["diameter_mm"] >= min_perpendicular_part_span * HOLE_BORE_DIAMETER_RATIO
        ):
            subtype = "bore"
            bore_count += 1
        elif candidate.get("selection_reason") == "full_span_exterior_partial":
            subtype = "partial_hole"
            partial_hole_count += 1
        elif (
            candidate.get("nested_group_size", 0) > 1
            and same_diameter_band
            and group_completeness_ratio >= HOLE_THROUGH_COMPLETENESS_MIN
            and candidate["depth_to_diameter_ratio"] >= 0.75
        ):
            subtype = "through_hole"
            through_hole_count += 1
        elif (
            candidate.get("nested_group_size", 0) > 1
            and same_diameter_band
            and all_interior_group
            and not aligned_with_turn_axis
            and max_group_diameter <= HOLE_INTERIOR_MULTI_SEGMENT_MAX_DIAMETER_MM
            and group_completeness_ratio >= HOLE_INTERIOR_MULTI_SEGMENT_THROUGH_COMPLETENESS_MIN
            and candidate["depth_to_diameter_ratio"] >= 0.75
        ):
            subtype = "through_hole"
            through_hole_count += 1
        elif (
            candidate.get("nested_group_size", 0) > 1
            and not same_diameter_band
            and full_depth_group
            and candidate["depth_to_diameter_ratio"] >= HOLE_STEPPED_MIN_DEPTH_TO_DIAMETER_RATIO
        ):
            subtype = "through_hole"
            through_hole_count += 1
        elif candidate.get("nested_group_size", 0) > 1 and not same_diameter_band:
            if (
                candidate["depth_to_diameter_ratio"] >= HOLE_STEPPED_MIN_DEPTH_TO_DIAMETER_RATIO
                and max_outer_group_depth >= candidate["depth_mm"] * HOLE_STEPPED_OUTER_DEPTH_RATIO
            ):
                subtype = "stepped_hole"
                stepped_hole_count += 1
            elif (
                candidate["depth_to_diameter_ratio"] < HOLE_STEPPED_MIN_DEPTH_TO_DIAMETER_RATIO
                and max_outer_group_depth <= candidate["depth_mm"] * 0.6
            ):
                rejected_candidates.append(
                    {
                        **candidate,
                        "selection_reason": "shallow_nested_recess",
                    }
                )
                continue
            elif candidate["completeness_ratio"] < HOLE_THROUGH_COMPLETENESS_MIN:
                subtype = "partial_hole"
                partial_hole_count += 1
            else:
                subtype = "through_hole"
                through_hole_count += 1
        elif candidate["completeness_ratio"] < HOLE_THROUGH_COMPLETENESS_MIN:
            subtype = "partial_hole"
            partial_hole_count += 1
        else:
            through_hole_count += 1

        diameter = candidate["diameter_mm"]
        depth = candidate["depth_mm"]
        if diameter > 0:
            diameters.append(diameter)
        if depth > 0:
            depths.append(depth)
        ratio = depth / max(diameter, 1e-9)
        if 2.5 <= diameter <= 20.0 and 0.8 <= ratio <= 4.0:
            threaded_holes_count += 1

        typed_candidates.append(
            {
                **candidate,
                "subtype": subtype,
            }
        )

    axial_bore_groups = []
    if isinstance(turning_detection, dict):
        raw_bore_groups = turning_detection.get("axial_bore_groups")
        if isinstance(raw_bore_groups, list):
            axial_bore_groups = [group for group in raw_bore_groups if isinstance(group, dict)]
    consumed_face_indices = {
        int(candidate["face_index"])
        for candidate in typed_candidates
        if isinstance(candidate.get("face_index"), int)
    }
    for group in axial_bore_groups:
        group_face_indices = sorted(
            {
                int(face_index)
                for face_index in group.get("face_indices", [])
                if isinstance(face_index, int)
            }
        )
        if not group_face_indices:
            continue
        if consumed_face_indices & set(group_face_indices):
            continue
        bore_count += 1
        consumed_face_indices.update(group_face_indices)
        typed_candidates.append(
            {
                "face_index": group_face_indices[0],
                "axis_direction": list(primary_axis) if primary_axis is not None else None,
                "axis_line_key": None,
                "diameter_mm": round(float(group.get("radius_mm") or 0.0) * 2.0, 4),
                "depth_mm": round(
                    max(
                        0.0,
                        float(group.get("axis_max") or 0.0) - float(group.get("axis_min") or 0.0),
                    ),
                    4,
                ),
                "area_mm2": None,
                "completeness_ratio": 1.0,
                "depth_to_diameter_ratio": None,
                "is_exterior": False,
                "bbox_bounds": None,
                "perpendicular_spans_mm": [],
                "adjacent_face_indices": [],
                "selection_reason": "short_turning_axis_bore",
                "nested_group_size": len(group_face_indices),
                "group_face_indices": group_face_indices,
                "group_diameters_mm": [round(float(group.get("radius_mm") or 0.0) * 2.0, 4)],
                "group_depths_mm": [
                    round(
                        max(
                            0.0,
                            float(group.get("axis_max") or 0.0)
                            - float(group.get("axis_min") or 0.0),
                        ),
                        4,
                    )
                ],
                "group_completeness_ratio": 1.0,
                "subtype": "bore",
            }
        )

    return {
        "hole_count": through_hole_count + partial_hole_count + bore_count + stepped_hole_count,
        "through_hole_count": through_hole_count,
        "partial_hole_count": partial_hole_count,
        "bore_count": bore_count,
        "stepped_hole_count": stepped_hole_count,
        "threaded_holes_count": threaded_holes_count,
        "min_hole_diameter_mm": min(diameters) if diameters else None,
        "max_hole_depth_mm": max(depths) if depths else None,
        "candidates": typed_candidates,
        "rejected_candidates": rejected_candidates,
        "thresholds": {
            "through_completeness_min": HOLE_THROUGH_COMPLETENESS_MIN,
            "partial_completeness_min": HOLE_PARTIAL_COMPLETENESS_MIN,
            "min_depth_to_diameter_ratio": HOLE_MIN_DEPTH_TO_DIAMETER_RATIO,
            "bore_depth_ratio": HOLE_BORE_DEPTH_RATIO,
            "bore_diameter_ratio": HOLE_BORE_DIAMETER_RATIO,
            "stepped_min_depth_to_diameter_ratio": HOLE_STEPPED_MIN_DEPTH_TO_DIAMETER_RATIO,
            "stepped_outer_depth_ratio": HOLE_STEPPED_OUTER_DEPTH_RATIO,
        },
    }


def _normalized_face_vector(face: dict[str, Any]) -> tuple[float, float, float] | None:
    sample_normal = face.get("sample_normal")
    if isinstance(sample_normal, (list, tuple)) and len(sample_normal) == 3:
        return _normalize(
            (
                float(sample_normal[0]),
                float(sample_normal[1]),
                float(sample_normal[2]),
            )
        )
    axis_direction = face.get("axis_direction")
    if isinstance(axis_direction, (list, tuple)) and len(axis_direction) == 3:
        return _canonical_axis(
            (
                float(axis_direction[0]),
                float(axis_direction[1]),
                float(axis_direction[2]),
            )
        )
    return None


def _surface_axis_direction(face: dict[str, Any]) -> tuple[float, float, float] | None:
    axis_direction = face.get("axis_direction")
    if isinstance(axis_direction, (list, tuple)) and len(axis_direction) == 3:
        return _canonical_axis(
            (
                float(axis_direction[0]),
                float(axis_direction[1]),
                float(axis_direction[2]),
            )
        )
    return None


def _face_position_metrics(
    face: dict[str, Any],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> dict[str, Any] | None:
    normal = _normalized_face_vector(face)
    if normal is None:
        return None
    alignment = max(abs(component) for component in normal)
    axis_index = _dominant_axis_index(normal)
    part_min = float(bbox_bounds[axis_index])
    part_max = float(bbox_bounds[axis_index + 3])
    part_span = max(0.0, part_max - part_min)
    face_bounds_payload = face.get("bbox_bounds")
    if not isinstance(face_bounds_payload, list) or len(face_bounds_payload) != 6:
        return None
    face_min = float(face_bounds_payload[axis_index])
    face_max = float(face_bounds_payload[axis_index + 3])
    face_center = (face_min + face_max) * 0.5
    nearest_boundary_offset = min(abs(face_center - part_min), abs(part_max - face_center))
    return {
        "normal": normal,
        "axis_index": axis_index,
        "axis_alignment": alignment,
        "part_span_mm": part_span,
        "face_center_mm": face_center,
        "nearest_boundary_offset_mm": nearest_boundary_offset,
        "recess_ratio": nearest_boundary_offset / max(part_span, 1e-9),
    }


def _neighbor_surface_records(
    face: dict[str, Any],
    face_lookup: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    adjacent_indices = face.get("adjacent_face_indices")
    if not isinstance(adjacent_indices, list):
        return []
    neighbors: list[dict[str, Any]] = []
    for index in adjacent_indices:
        if not isinstance(index, int):
            continue
        neighbor = face_lookup.get(index)
        if isinstance(neighbor, dict):
            neighbors.append(neighbor)
    return neighbors


def _connected_face_components(
    face_indices: list[int],
    face_lookup: dict[int, dict[str, Any]],
) -> list[list[int]]:
    allowed = {index for index in face_indices if isinstance(index, int)}
    components: list[list[int]] = []
    seen: set[int] = set()
    for face_index in sorted(allowed):
        if face_index in seen:
            continue
        stack = [face_index]
        component: list[int] = []
        while stack:
            current = stack.pop()
            if current in seen or current not in allowed:
                continue
            seen.add(current)
            component.append(current)
            current_face = face_lookup.get(current)
            if not isinstance(current_face, dict):
                continue
            for neighbor_index in current_face.get("adjacent_face_indices", []):
                if isinstance(neighbor_index, int) and neighbor_index in allowed and neighbor_index not in seen:
                    stack.append(neighbor_index)
        if component:
            components.append(sorted(component))
    return components


def _split_flat_feature_groups(
    groups: list[list[int]],
    face_lookup: dict[int, dict[str, Any]],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> list[list[int]]:
    split_groups: list[list[int]] = []
    for group in groups:
        if len(group) < 4:
            split_groups.append(group)
            continue

        near_boundary_faces: list[int] = []
        recessed_interior_supported_faces: list[int] = []
        for face_index in group:
            face = face_lookup.get(face_index)
            if not isinstance(face, dict):
                continue
            metrics = _face_position_metrics(face, bbox_bounds)
            if metrics is None:
                continue
            if metrics["nearest_boundary_offset_mm"] <= 1.0:
                near_boundary_faces.append(face_index)
            interior_planar_neighbors = sum(
                1
                for neighbor in _neighbor_surface_records(face, face_lookup)
                if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                and neighbor.get("is_exterior") is False
            )
            if (
                metrics["nearest_boundary_offset_mm"] >= POCKET_OPEN_EXTERIOR_RECESS_MM
                and interior_planar_neighbors >= POCKET_OPEN_EXTERIOR_INTERIOR_PLANE_MIN
            ):
                recessed_interior_supported_faces.append(face_index)

        if len(near_boundary_faces) >= 2 and len(recessed_interior_supported_faces) == 1:
            split_face = recessed_interior_supported_faces[0]
            remainder = sorted(index for index in group if index != split_face)
            if remainder:
                split_groups.append(remainder)
            split_groups.append([split_face])
            continue

        split_groups.append(group)
    return split_groups


def _plane_signature(
    face: dict[str, Any],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> tuple[int, int, float] | None:
    metrics = _face_position_metrics(face, bbox_bounds)
    if metrics is None:
        return None
    axis_index = int(metrics["axis_index"])
    sign = 1 if metrics["normal"][axis_index] >= 0.0 else -1
    position_mm = round(float(metrics["face_center_mm"]) * 2.0) / 2.0
    return axis_index, sign, position_mm


def _symmetric_plane_signature(
    face: dict[str, Any],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> tuple[int, float, float, float] | None:
    metrics = _face_position_metrics(face, bbox_bounds)
    spans = _plane_perpendicular_spans(face)
    if metrics is None or spans is None:
        return None
    axis_index = int(metrics["axis_index"])
    position_mm = round(abs(float(metrics["face_center_mm"])) * 2.0) / 2.0
    return (
        axis_index,
        position_mm,
        round(float(spans[0]), 1),
        round(float(spans[1]), 1),
    )


def _plane_perpendicular_spans(
    face: dict[str, Any],
) -> tuple[float, float] | None:
    bounds = face.get("bbox_bounds")
    normal = _normalized_face_vector(face)
    if not isinstance(bounds, list) or len(bounds) != 6 or normal is None:
        return None
    axis_index = _dominant_axis_index(normal)
    spans = [
        float(bounds[index + 3]) - float(bounds[index])
        for index in range(3)
    ]
    perpendicular = sorted(
        spans[index]
        for index in range(3)
        if index != axis_index
    )
    if len(perpendicular) != 2:
        return None
    return float(perpendicular[0]), float(perpendicular[1])


def _group_flat_planar_features_for_simple_parts(
    face_indices: list[int],
    face_lookup: dict[int, dict[str, Any]],
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> list[list[int]]:
    buckets: dict[tuple[int, int, float], list[int]] = {}
    for face_index in face_indices:
        face = face_lookup.get(face_index)
        if not isinstance(face, dict):
            continue
        signature = _plane_signature(face, bbox_bounds)
        if signature is None:
            continue
        buckets.setdefault(signature, []).append(face_index)

    grouped: list[list[int]] = []
    for bucket_indices in buckets.values():
        grouped.extend(_connected_face_components(bucket_indices, face_lookup))

    singleton_groups: list[dict[str, Any]] = []
    retained_groups: list[list[int]] = []
    for group in grouped:
        if len(group) != 1:
            retained_groups.append(sorted(group))
            continue
        face = face_lookup.get(group[0])
        if not isinstance(face, dict):
            retained_groups.append(sorted(group))
            continue
        signature = _plane_signature(face, bbox_bounds)
        spans = _plane_perpendicular_spans(face)
        area_mm2 = float(face.get("area_mm2") or 0.0)
        if signature is None or spans is None or area_mm2 > FLAT_TWIN_FACE_MAX_AREA_MM2:
            retained_groups.append(sorted(group))
            continue
        singleton_groups.append(
            {
                "face_index": group[0],
                "signature": signature,
                "area_mm2": area_mm2,
                "spans": spans,
            }
        )

    used_indices: set[int] = set()
    merged_groups: list[list[int]] = []
    for index, record in enumerate(singleton_groups):
        if index in used_indices:
            continue
        best_match_index: int | None = None
        best_match_score: tuple[float, float, float] | None = None
        for candidate_index in range(index + 1, len(singleton_groups)):
            if candidate_index in used_indices:
                continue
            candidate = singleton_groups[candidate_index]
            if record["signature"][:2] != candidate["signature"][:2]:
                continue
            if (
                abs(record["signature"][2] - candidate["signature"][2])
                > FLAT_TWIN_FACE_POSITION_GAP_MM
            ):
                continue
            if (
                abs(record["spans"][0] - candidate["spans"][0])
                > FLAT_TWIN_FACE_SPAN_TOLERANCE_MM
                or abs(record["spans"][1] - candidate["spans"][1])
                > FLAT_TWIN_FACE_SPAN_TOLERANCE_MM
            ):
                continue
            area_ratio = max(record["area_mm2"], candidate["area_mm2"]) / max(
                min(record["area_mm2"], candidate["area_mm2"]),
                1e-9,
            )
            if area_ratio > 1.15:
                continue
            score = (
                abs(record["signature"][2] - candidate["signature"][2]),
                area_ratio,
                abs(record["spans"][0] - candidate["spans"][0])
                + abs(record["spans"][1] - candidate["spans"][1]),
            )
            if best_match_score is None or score < best_match_score:
                best_match_score = score
                best_match_index = candidate_index
        if best_match_index is None:
            merged_groups.append([record["face_index"]])
            used_indices.add(index)
            continue
        used_indices.add(index)
        used_indices.add(best_match_index)
        merged_groups.append(
            sorted(
                [
                    record["face_index"],
                    singleton_groups[best_match_index]["face_index"],
                ]
            )
        )

    all_groups = retained_groups + merged_groups
    return sorted(all_groups, key=lambda group: (group[0], len(group)))


def _median_area(face_indices: list[int], face_lookup: dict[int, dict[str, Any]]) -> float | None:
    values = sorted(
        float(face_lookup[index].get("area_mm2") or 0.0)
        for index in face_indices
        if isinstance(face_lookup.get(index), dict)
        and isinstance(face_lookup[index].get("area_mm2"), (int, float))
    )
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2 == 1:
        return values[middle]
    return 0.5 * (values[middle - 1] + values[middle])


def _face_axis_line_key(face: dict[str, Any]) -> tuple[Any, ...] | None:
    axis = _surface_axis_direction(face)
    axis_origin = face.get("axis_origin")
    if axis is None or not isinstance(axis_origin, (list, tuple)) or len(axis_origin) != 3:
        return None
    return _axis_line_key(
        axis,
        (
            float(axis_origin[0]),
            float(axis_origin[1]),
            float(axis_origin[2]),
        ),
    )


def _merge_groups_by_axis_key(
    groups: list[list[int]],
    face_lookup: dict[int, dict[str, Any]],
) -> list[list[int]]:
    merged_by_key: dict[tuple[Any, ...], set[int]] = {}
    passthrough: list[list[int]] = []
    for group in groups:
        keys = {
            _face_axis_line_key(face_lookup[index])
            for index in group
            if isinstance(face_lookup.get(index), dict)
        }
        keys.discard(None)
        surface_types = {
            str(face_lookup[index].get("surface_type") or "").strip().lower()
            for index in group
            if isinstance(face_lookup.get(index), dict)
        }
        if len(keys) == 1 and surface_types <= {"cone", "cylinder", "torus", "surface_of_revolution"}:
            key = next(iter(keys))
            merged_by_key.setdefault(key, set()).update(group)
        else:
            passthrough.append(sorted(group))
    passthrough.extend(sorted(indices) for indices in merged_by_key.values())
    return sorted(passthrough, key=lambda item: (item[0], len(item)))


def _split_curved_feature_groups(
    groups: list[list[int]],
    face_lookup: dict[int, dict[str, Any]],
) -> list[list[int]]:
    split_groups: list[list[int]] = []
    for group in groups:
        if len(group) != 2:
            split_groups.append(sorted(group))
            continue

        records = [face_lookup.get(index) for index in group]
        if not all(isinstance(record, dict) for record in records):
            split_groups.append(sorted(group))
            continue
        if any(
            str(record.get("surface_type") or "").strip().lower() != "cone"
            for record in records
        ):
            split_groups.append(sorted(group))
            continue

        areas = [float(record.get("area_mm2") or 0.0) for record in records]
        min_area = min(areas)
        max_area = max(areas)
        if min_area <= 0.0 or max_area / max(min_area, 1e-9) < CURVED_CONE_GROUP_SPLIT_AREA_RATIO:
            split_groups.append(sorted(group))
            continue

        split_groups.extend([[face_index] for face_index in sorted(group)])

    return split_groups


def detect_pocket_features_from_face_inventory(
    face_inventory: list[dict[str, Any]],
    *,
    bbox_bounds: tuple[float, float, float, float, float, float],
) -> dict[str, Any]:
    face_lookup = {
        int(face.get("face_index")): face
        for face in face_inventory
        if isinstance(face, dict) and isinstance(face.get("face_index"), int)
    }
    open_candidates: list[dict[str, Any]] = []
    closed_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    simple_planar_cylinder_part = not any(
        str(face.get("surface_type") or "").strip().lower()
        in {"cone", "torus", "bspline", "surface_of_revolution"}
        for face in face_inventory
        if isinstance(face, dict)
    )

    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        if str(face.get("surface_type") or "").strip().lower() != "plane":
            continue
        metrics = _face_position_metrics(face, bbox_bounds)
        if metrics is None:
            continue
        area = float(face.get("area_mm2") or 0.0)
        if not math.isfinite(area) or area < POCKET_MIN_AREA_MM2:
            continue

        neighbors = _neighbor_surface_records(face, face_lookup)
        wall_neighbors: list[dict[str, Any]] = []
        for neighbor in neighbors:
            surface_type = str(neighbor.get("surface_type") or "").strip().lower()
            if surface_type not in {
                "plane",
                "cylinder",
                "cone",
                "torus",
                "bspline",
                "surface_of_revolution",
            }:
                continue
            if surface_type == "plane" and _axis_alignment_cos(
                _normalized_face_vector(face),
                _normalized_face_vector(neighbor),
            ) >= 0.9:
                continue
            wall_neighbors.append(neighbor)
        interior_plane_neighbors = [
            neighbor
            for neighbor in wall_neighbors
            if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
            and neighbor.get("is_exterior") is False
        ]
        interior_curved_neighbors = [
            neighbor
            for neighbor in wall_neighbors
            if str(neighbor.get("surface_type") or "").strip().lower() != "plane"
            and neighbor.get("is_exterior") is False
        ]
        planar_wall_neighbors = [
            neighbor
            for neighbor in wall_neighbors
            if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
        ]
        curved_wall_neighbors = [
            neighbor
            for neighbor in wall_neighbors
            if str(neighbor.get("surface_type") or "").strip().lower()
            in {"cone", "torus", "bspline", "surface_of_revolution"}
        ]
        all_nonplanar_wall_neighbors = (
            bool(wall_neighbors)
            and all(
                str(neighbor.get("surface_type") or "").strip().lower() != "plane"
                for neighbor in wall_neighbors
            )
        )
        candidate_payload = {
            "face_index": int(face.get("face_index")),
            "area_mm2": round(area, 4),
            "is_exterior": face.get("is_exterior"),
            "nearest_boundary_offset_mm": round(metrics["nearest_boundary_offset_mm"], 4),
            "recess_ratio": round(metrics["recess_ratio"], 4),
            "wall_neighbor_count": len(wall_neighbors),
            "adjacent_face_indices": [
                int(neighbor.get("face_index"))
                for neighbor in wall_neighbors
                if isinstance(neighbor.get("face_index"), int)
            ],
            "adjacent_surface_types": sorted(
                {
                    str(neighbor.get("surface_type") or "").strip().lower()
                    for neighbor in wall_neighbors
                }
            ),
            "interior_plane_neighbor_count": len(interior_plane_neighbors),
            "interior_curved_neighbor_count": len(interior_curved_neighbors),
        }
        supports_exterior_open_recess = (
            face.get("is_exterior") is True
            and POCKET_OPEN_WALL_COUNT_MIN
            <= len(wall_neighbors)
            <= POCKET_OPEN_EXTERIOR_WALL_COUNT_MAX
            and metrics["recess_ratio"] >= POCKET_OPEN_EXTERIOR_RECESS_RATIO
            and metrics["nearest_boundary_offset_mm"] >= POCKET_OPEN_EXTERIOR_RECESS_MM
            and len(interior_plane_neighbors) >= POCKET_OPEN_EXTERIOR_INTERIOR_PLANE_MIN
            and len(interior_curved_neighbors) >= POCKET_OPEN_EXTERIOR_INTERIOR_CURVED_MIN
        )
        supports_exterior_open_recess_relaxed = (
            simple_planar_cylinder_part
            and face.get("is_exterior") is True
            and POCKET_OPEN_WALL_COUNT_MIN
            <= len(wall_neighbors)
            <= max(8, POCKET_OPEN_EXTERIOR_WALL_COUNT_MAX)
            and metrics["recess_ratio"] >= POCKET_OPEN_EXTERIOR_RECESS_RATIO_RELAXED
            and metrics["nearest_boundary_offset_mm"] >= POCKET_OPEN_EXTERIOR_RECESS_MM
            and len(interior_plane_neighbors) == 0
            and len(interior_curved_neighbors) >= 1
            and len(planar_wall_neighbors) >= 2
        )

        if metrics["axis_alignment"] < POCKET_AXIS_ALIGNMENT_MIN:
            candidate_payload["selection_reason"] = "non_axis_aligned_plane"
            rejected_candidates.append(candidate_payload)
            continue
        if not supports_exterior_open_recess and (
            metrics["recess_ratio"] < POCKET_MIN_RECESS_RATIO or (
            metrics["nearest_boundary_offset_mm"] < POCKET_MIN_RECESS_MM
            )
        ):
            candidate_payload["selection_reason"] = "not_recessed_enough"
            rejected_candidates.append(candidate_payload)
            continue

        if (
            face.get("is_exterior") is False
            and len(wall_neighbors) >= POCKET_OPEN_WALL_COUNT_MIN
            and curved_wall_neighbors
        ):
            open_candidates.append(
                {
                    **candidate_payload,
                    "selection_reason": "interior_recessed_floor",
                    "subtype": "open_pocket",
                }
            )
            continue
        if supports_exterior_open_recess:
            open_candidates.append(
                {
                    **candidate_payload,
                    "selection_reason": "exterior_open_recessed_floor",
                    "subtype": "open_pocket",
                }
            )
            continue
        if supports_exterior_open_recess_relaxed:
            open_candidates.append(
                {
                    **candidate_payload,
                    "selection_reason": "exterior_open_recessed_floor_relaxed",
                    "subtype": "open_pocket",
                }
            )
            continue
        if (
            face.get("is_exterior") is True
            and all_nonplanar_wall_neighbors
            and len(wall_neighbors) in {2, 4}
            and metrics["recess_ratio"] >= POCKET_CURVED_ENCLOSED_RECESS_RATIO
            and metrics["nearest_boundary_offset_mm"] >= POCKET_CURVED_ENCLOSED_RECESS_MM
        ):
            closed_candidates.append(
                {
                    **candidate_payload,
                    "selection_reason": "curved_enclosed_floor",
                    "subtype": "closed_pocket",
                }
            )
            continue
        if (
            face.get("is_exterior") is True
            and POCKET_CLOSED_WALL_COUNT_MIN <= len(wall_neighbors) <= POCKET_CLOSED_WALL_COUNT_MAX
        ):
            closed_candidates.append(
                {
                    **candidate_payload,
                    "selection_reason": "enclosed_recessed_floor",
                    "subtype": "closed_pocket",
                }
            )
            continue

        candidate_payload["selection_reason"] = "insufficient_wall_support"
        rejected_candidates.append(candidate_payload)

    open_feature_groups: list[list[int]] = []
    standard_open_faces = [
        int(candidate["face_index"])
        for candidate in open_candidates
        if candidate.get("selection_reason") != "exterior_open_recessed_floor_relaxed"
        and isinstance(candidate.get("face_index"), int)
    ]
    if standard_open_faces:
        open_feature_groups.extend(_connected_face_components(standard_open_faces, face_lookup))

    relaxed_buckets: dict[tuple[Any, ...], set[int]] = {}
    for candidate in open_candidates:
        if candidate.get("selection_reason") != "exterior_open_recessed_floor_relaxed":
            continue
        face_index = candidate.get("face_index")
        face = face_lookup.get(face_index) if isinstance(face_index, int) else None
        if not isinstance(face, dict):
            continue
        signature = _symmetric_plane_signature(face, bbox_bounds)
        if signature is None:
            signature = _plane_signature(face, bbox_bounds)
        if signature is None:
            continue
        relaxed_buckets.setdefault(signature, set()).add(int(face_index))
    open_feature_groups.extend(sorted(indices) for indices in relaxed_buckets.values())
    open_feature_groups = sorted(open_feature_groups, key=lambda group: (group[0], len(group)))

    closed_feature_groups = [
        [int(candidate["face_index"])]
        for candidate in closed_candidates
        if isinstance(candidate.get("face_index"), int)
    ]

    return {
        "pocket_count": len(open_feature_groups) + len(closed_feature_groups),
        "open_pocket_count": len(open_feature_groups),
        "closed_pocket_count": len(closed_feature_groups),
        "candidates": open_candidates + closed_candidates,
        "open_pocket_feature_groups": open_feature_groups,
        "closed_pocket_feature_groups": closed_feature_groups,
        "rejected_candidates": rejected_candidates,
        "thresholds": {
            "min_recess_ratio": POCKET_MIN_RECESS_RATIO,
            "min_recess_mm": POCKET_MIN_RECESS_MM,
            "min_area_mm2": POCKET_MIN_AREA_MM2,
            "open_wall_count_min": POCKET_OPEN_WALL_COUNT_MIN,
            "open_exterior_wall_count_max": POCKET_OPEN_EXTERIOR_WALL_COUNT_MAX,
            "open_exterior_recess_ratio": POCKET_OPEN_EXTERIOR_RECESS_RATIO,
            "open_exterior_recess_ratio_relaxed": POCKET_OPEN_EXTERIOR_RECESS_RATIO_RELAXED,
            "open_exterior_recess_mm": POCKET_OPEN_EXTERIOR_RECESS_MM,
            "curved_enclosed_recess_ratio": POCKET_CURVED_ENCLOSED_RECESS_RATIO,
            "curved_enclosed_recess_mm": POCKET_CURVED_ENCLOSED_RECESS_MM,
            "closed_wall_count_min": POCKET_CLOSED_WALL_COUNT_MIN,
            "closed_wall_count_max": POCKET_CLOSED_WALL_COUNT_MAX,
        },
    }


def detect_boss_features_from_face_inventory(
    face_inventory: list[dict[str, Any]],
    *,
    bbox_bounds: tuple[float, float, float, float, float, float],
    turning_detection: dict[str, Any] | None = None,
    axis_angle_tolerance_deg: float = TURN_AXIS_ANGLE_TOLERANCE_DEG,
) -> dict[str, Any]:
    axis_tolerance_cos = math.cos(math.radians(max(0.0, axis_angle_tolerance_deg)))
    primary_axis = None
    if isinstance(turning_detection, dict):
        axis_payload = turning_detection.get("primary_axis")
        if isinstance(axis_payload, (list, tuple)) and len(axis_payload) == 3:
            primary_axis = _canonical_axis(
                (float(axis_payload[0]), float(axis_payload[1]), float(axis_payload[2]))
            )

    grouped_faces: dict[tuple[Any, ...] | None, list[dict[str, Any]]] = {}
    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        surface_type = str(face.get("surface_type") or "").strip().lower()
        if surface_type not in {"cylinder", "cone"}:
            continue
        if face.get("is_exterior") is not True:
            continue
        axis_direction = face.get("axis_direction")
        axis_origin = face.get("axis_origin")
        if not isinstance(axis_direction, (list, tuple)) or len(axis_direction) != 3:
            continue
        if not isinstance(axis_origin, (list, tuple)) or len(axis_origin) != 3:
            continue
        axis = _canonical_axis(
            (
                float(axis_direction[0]),
                float(axis_direction[1]),
                float(axis_direction[2]),
            )
        )
        if axis is None:
            continue
        if primary_axis is not None and _axis_alignment_cos(axis, primary_axis) >= axis_tolerance_cos:
            continue
        grouped_faces.setdefault(
            _axis_line_key(
                axis,
                (
                    float(axis_origin[0]),
                    float(axis_origin[1]),
                    float(axis_origin[2]),
                ),
            ),
            [],
        ).append({**face, "axis_direction": axis})

    boss_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    for axis_line_key, faces in grouped_faces.items():
        if not axis_line_key:
            continue
        cylinders = [
            face
            for face in faces
            if str(face.get("surface_type") or "").strip().lower() == "cylinder"
        ]
        if not cylinders:
            continue
        axis = cylinders[0]["axis_direction"]
        axis_span = _project_bounds_span(bbox_bounds, axis)
        group_min: float | None = None
        group_max: float | None = None
        max_diameter = 0.0
        face_indices: list[int] = []
        for face in faces:
            face_bounds_payload = face.get("bbox_bounds")
            if not isinstance(face_bounds_payload, list) or len(face_bounds_payload) != 6:
                continue
            face_bounds = tuple(float(value) for value in face_bounds_payload)
            face_min, face_max = _project_bounds_range(face_bounds, axis)
            group_min = face_min if group_min is None else min(group_min, face_min)
            group_max = face_max if group_max is None else max(group_max, face_max)
            face_indices.append(int(face.get("face_index")))
            if str(face.get("surface_type") or "").strip().lower() == "cylinder":
                diameter = _estimate_cylinder_diameter_from_bounds(face_bounds, axis) or 0.0
                max_diameter = max(max_diameter, diameter)

        if group_min is None or group_max is None or axis_span <= 0:
            continue
        group_span = max(0.0, group_max - group_min)
        part_perpendicular_spans = _perpendicular_spans_from_bounds(bbox_bounds, axis)
        positive_part_spans = [
            span for span in part_perpendicular_spans if math.isfinite(span) and span > 0
        ]
        min_part_span = min(positive_part_spans, default=0.0)

        interior_cylinders_same_axis = 0
        for face in face_inventory:
            if not isinstance(face, dict):
                continue
            if face.get("is_exterior") is not False:
                continue
            if str(face.get("surface_type") or "").strip().lower() != "cylinder":
                continue
            face_axis_direction = face.get("axis_direction")
            face_axis_origin = face.get("axis_origin")
            if not isinstance(face_axis_direction, (list, tuple)) or len(face_axis_direction) != 3:
                continue
            if not isinstance(face_axis_origin, (list, tuple)) or len(face_axis_origin) != 3:
                continue
            face_axis = _canonical_axis(
                (
                    float(face_axis_direction[0]),
                    float(face_axis_direction[1]),
                    float(face_axis_direction[2]),
                )
            )
            if face_axis is None or _axis_alignment_cos(face_axis, axis) < axis_tolerance_cos:
                continue
            interior_key = _axis_line_key(
                face_axis,
                (
                    float(face_axis_origin[0]),
                    float(face_axis_origin[1]),
                    float(face_axis_origin[2]),
                ),
            )
            if interior_key == axis_line_key:
                interior_cylinders_same_axis += 1

        end_cap_count = 0
        end_tolerance = max(1.0, axis_span * 0.03)
        for face in face_inventory:
            if not isinstance(face, dict):
                continue
            if face.get("is_exterior") is not True:
                continue
            if str(face.get("surface_type") or "").strip().lower() != "plane":
                continue
            normal = _normalized_face_vector(face)
            if normal is None or _axis_alignment_cos(normal, axis) < axis_tolerance_cos:
                continue
            face_bounds_payload = face.get("bbox_bounds")
            if not isinstance(face_bounds_payload, list) or len(face_bounds_payload) != 6:
                continue
            face_min, face_max = _project_bounds_range(
                tuple(float(value) for value in face_bounds_payload),
                axis,
            )
            face_center = (face_min + face_max) * 0.5
            if abs(face_center - group_min) <= end_tolerance or abs(face_center - group_max) <= end_tolerance:
                end_cap_count += 1

        candidate_payload = {
            "axis_line_key": axis_line_key,
            "axis_direction": axis,
            "face_indices": face_indices,
            "group_span_mm": round(group_span, 4),
            "part_axis_span_mm": round(axis_span, 4),
            "span_ratio": round(group_span / max(axis_span, 1e-9), 4),
            "max_diameter_mm": round(max_diameter, 4),
            "diameter_ratio": round(max_diameter / max(min_part_span, 1e-9), 4)
            if min_part_span > 0
            else None,
            "interior_cylinders_same_axis": interior_cylinders_same_axis,
            "end_cap_count": end_cap_count,
        }
        if interior_cylinders_same_axis > 0:
            candidate_payload["selection_reason"] = "coaxial_interior_cylinder_present"
            rejected_candidates.append(candidate_payload)
            continue
        if group_span < axis_span * BOSS_MIN_SPAN_RATIO:
            candidate_payload["selection_reason"] = "insufficient_axial_span"
            rejected_candidates.append(candidate_payload)
            continue
        if min_part_span <= 0 or max_diameter < min_part_span * BOSS_MIN_DIAMETER_RATIO:
            candidate_payload["selection_reason"] = "insufficient_diameter"
            rejected_candidates.append(candidate_payload)
            continue
        if end_cap_count < BOSS_MIN_END_CAP_COUNT:
            candidate_payload["selection_reason"] = "missing_end_caps"
            rejected_candidates.append(candidate_payload)
            continue
        candidate_payload["selection_reason"] = "exterior_revolved_protrusion"
        boss_candidates.append(candidate_payload)

    return {
        "boss_count": len(boss_candidates),
        "candidates": boss_candidates,
        "rejected_candidates": rejected_candidates,
        "thresholds": {
            "min_span_ratio": BOSS_MIN_SPAN_RATIO,
            "min_diameter_ratio": BOSS_MIN_DIAMETER_RATIO,
            "min_end_cap_count": BOSS_MIN_END_CAP_COUNT,
        },
    }


def detect_milled_faces_from_face_inventory(
    face_inventory: list[dict[str, Any]],
    *,
    bbox_bounds: tuple[float, float, float, float, float, float],
    turning_detection: dict[str, Any] | None = None,
    pocket_detection: dict[str, Any] | None = None,
    hole_detection: dict[str, Any] | None = None,
    boss_detection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    face_lookup = {
        int(face.get("face_index")): face
        for face in face_inventory
        if isinstance(face, dict) and isinstance(face.get("face_index"), int)
    }
    turned_face_indices: set[int] = set()
    primary_axis = None
    short_turning_part = False
    max_turn_radius_mm = 0.0
    if isinstance(turning_detection, dict):
        axis_payload = turning_detection.get("primary_axis")
        if isinstance(axis_payload, (list, tuple)) and len(axis_payload) == 3:
            primary_axis = _canonical_axis(
                (float(axis_payload[0]), float(axis_payload[1]), float(axis_payload[2]))
            )
        primary_cluster = turning_detection.get("primary_cluster")
        if isinstance(primary_cluster, dict):
            for face_index in primary_cluster.get("face_indices", []):
                if isinstance(face_index, int):
                    turned_face_indices.add(face_index)
            short_turning_part = (
                float(primary_cluster.get("dominant_axis_ratio") or 0.0)
                < TURN_AXIS_DOMINANT_DIMENSION_RATIO
                and float(primary_cluster.get("exterior_revolved_area_ratio") or 0.0)
                >= TURN_AXIS_MIN_REVOLVED_FRACTION
            )
        for group in turning_detection.get("turned_diameter_groups", []):
            if not isinstance(group, dict):
                continue
            max_turn_radius_mm = max(
                max_turn_radius_mm,
                float(group.get("radius_mm") or 0.0),
            )
    boss_face_indices: set[int] = set()
    if isinstance(boss_detection, dict):
        for candidate in boss_detection.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            for face_index in candidate.get("face_indices", []):
                if isinstance(face_index, int):
                    boss_face_indices.add(face_index)
    hole_face_indices: set[int] = set()
    if isinstance(hole_detection, dict):
        for candidate in hole_detection.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            face_index = candidate.get("face_index")
            if isinstance(face_index, int):
                hole_face_indices.add(face_index)
    interior_cylinder_keys: set[tuple[Any, ...]] = set()
    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        if face.get("is_exterior") is not False:
            continue
        if str(face.get("surface_type") or "").strip().lower() != "cylinder":
            continue
        key = _face_axis_line_key(face)
        if key is not None:
            interior_cylinder_keys.add(key)
    excluded_pocket_face_indices: set[int] = set()
    exterior_open_pocket_face_indices: set[int] = set()
    if isinstance(pocket_detection, dict):
        for candidate in pocket_detection.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            face_index = candidate.get("face_index")
            if isinstance(face_index, int):
                if candidate.get("subtype") == "open_pocket" and candidate.get("is_exterior") is True:
                    exterior_open_pocket_face_indices.add(face_index)
                else:
                    excluded_pocket_face_indices.add(face_index)
    simple_planar_cylinder_part = (
        primary_axis is None
        and isinstance(pocket_detection, dict)
        and int(pocket_detection.get("closed_pocket_count") or 0) == 0
        and int(pocket_detection.get("open_pocket_count") or 0) <= 2
        and not any(
            str(face.get("surface_type") or "").strip().lower()
            in {"cone", "torus", "bspline", "surface_of_revolution"}
            for face in face_inventory
            if isinstance(face, dict)
        )
    )

    bbox_spans = (
        bbox_bounds[3] - bbox_bounds[0],
        bbox_bounds[4] - bbox_bounds[1],
        bbox_bounds[5] - bbox_bounds[2],
    )
    dominant_axis_index = max(range(3), key=lambda index: bbox_spans[index])
    smallest_axis_index = min(range(3), key=lambda index: bbox_spans[index])
    smallest_axis_vector = tuple(
        1.0 if index == smallest_axis_index else 0.0 for index in range(3)
    )

    flat_face_candidates: list[int] = []
    flat_side_candidates: list[int] = []
    curved_face_candidates: list[int] = []
    circular_milled_candidates: list[int] = []
    convex_profile_edge_candidates: list[int] = []
    concave_fillet_edge_candidate_groups: dict[tuple[Any, ...], set[int]] = {}
    turning_moderate_flat_candidates: list[int] = []
    excluded_turning_deck_faces: list[int] = []

    for face in face_inventory:
        if not isinstance(face, dict):
            continue
        face_index = face.get("face_index")
        if not isinstance(face_index, int):
            continue
        surface_type = str(face.get("surface_type") or "").strip().lower()
        if face_index in turned_face_indices and not (
            short_turning_part and surface_type in {"cone", "torus"}
        ):
            continue

        if surface_type == "plane":
            metrics = _face_position_metrics(face, bbox_bounds)
            if metrics is None:
                continue
            neighbor_faces = _neighbor_surface_records(face, face_lookup)
            plane_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
            ]
            cylinder_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "cylinder"
            ]
            curved_neighbor_count = sum(
                1
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower()
                in {"bspline", "cone", "cylinder", "torus", "surface_of_revolution"}
            )
            if primary_axis is None:
                adjacent_exterior_open_pocket = any(
                    isinstance(neighbor.get("face_index"), int)
                    and int(neighbor.get("face_index")) in exterior_open_pocket_face_indices
                    for neighbor in neighbor_faces
                )
                if face.get("is_exterior") is not True:
                    if not adjacent_exterior_open_pocket:
                        continue
                    if metrics["axis_alignment"] < 0.85 or metrics["axis_alignment"] >= 0.95:
                        continue
                    flat_side_candidates.append(face_index)
                    continue
                if face_index in excluded_pocket_face_indices:
                    continue
                hole_cap_plane = (
                    float(face.get("area_mm2") or 0.0) <= HOLE_CAP_EXCLUDED_MAX_AREA_MM2
                    and
                    metrics["axis_alignment"] >= 0.98
                    and metrics["axis_index"] == smallest_axis_index
                    and len(neighbor_faces) <= 2
                    and bool(neighbor_faces)
                    and all(
                        str(neighbor.get("surface_type") or "").strip().lower()
                        in {"cylinder", "cone"}
                        for neighbor in neighbor_faces
                    )
                    and any(
                        isinstance(neighbor.get("face_index"), int)
                        and int(neighbor.get("face_index")) in hole_face_indices
                        for neighbor in neighbor_faces
                    )
                )
                if hole_cap_plane:
                    continue
                transition_profile_plane = (
                    face.get("is_exterior") is True
                    and metrics["axis_alignment"] >= 0.95
                    and metrics["axis_index"] != smallest_axis_index
                    and len(plane_neighbors) <= 2
                    and len(cylinder_neighbors) >= 2
                    and any(neighbor.get("is_exterior") is not True for neighbor in neighbor_faces)
                )
                if transition_profile_plane:
                    continue
                aligned_smallest_plane_neighbors = sum(
                    1
                    for neighbor in plane_neighbors
                    if _axis_alignment_cos(_normalized_face_vector(neighbor), smallest_axis_vector)
                    >= 0.98
                )
                small_profile_cylinder_neighbors = sum(
                    1
                    for neighbor in cylinder_neighbors
                    if (
                        (_cylindrical_face_metrics(neighbor) or {}).get("diameter_mm") is not None
                        and _dominant_axis_index(
                            (_cylindrical_face_metrics(neighbor) or {})["axis_direction"]
                        )
                        == smallest_axis_index
                        and (_cylindrical_face_metrics(neighbor) or {})["diameter_mm"] <= 10.0
                    )
                )
                bridge_side_plane = (
                    face.get("is_exterior") is True
                    and metrics["axis_alignment"] >= 0.95
                    and metrics["axis_index"] != smallest_axis_index
                    and len(plane_neighbors) == 2
                    and aligned_smallest_plane_neighbors == 2
                    and len(cylinder_neighbors) == 2
                    and small_profile_cylinder_neighbors == 2
                    and all(neighbor.get("is_exterior") is True for neighbor in neighbor_faces)
                )
                if bridge_side_plane:
                    flat_side_candidates.append(face_index)
                    continue
                if metrics["axis_alignment"] < 0.85:
                    continue
                axis_index = metrics["axis_index"]
                if axis_index == dominant_axis_index or metrics["axis_alignment"] < 0.95:
                    flat_side_candidates.append(face_index)
                else:
                    flat_face_candidates.append(face_index)
                if (
                    simple_planar_cylinder_part
                    and face.get("is_exterior") is True
                    and metrics["axis_alignment"] >= 0.95
                ):
                    if (
                        axis_index != smallest_axis_index
                        and metrics["nearest_boundary_offset_mm"] > 0.0
                        and float(face.get("area_mm2") or 0.0) <= FLAT_TWIN_FACE_MAX_AREA_MM2
                    ):
                        flat_side_candidates.append(face_index)
                    elif (
                        axis_index == smallest_axis_index
                        and metrics["nearest_boundary_offset_mm"] > 0.0
                        and float(face.get("area_mm2") or 0.0) <= FLAT_TWIN_FACE_MAX_AREA_MM2
                    ):
                        flat_side_candidates.append(face_index)
                    elif (
                        axis_index == smallest_axis_index
                        and 0.0 < metrics["nearest_boundary_offset_mm"] <= 6.0
                        and len(plane_neighbors) >= 7
                        and 3 <= len(cylinder_neighbors) <= 5
                    ):
                        flat_side_candidates.append(face_index)
            else:
                if face.get("is_exterior") is not True:
                    continue
                aligned_with_primary = (
                    _axis_alignment_cos(metrics["normal"], primary_axis) >= 0.996
                )
                if (
                    aligned_with_primary
                    and metrics["recess_ratio"] >= 0.3
                    and curved_neighbor_count >= 20
                ):
                    excluded_turning_deck_faces.append(face_index)
                    continue
                if metrics["axis_alignment"] >= MILLED_FACE_AXIS_ALIGNMENT_MIN:
                    flat_face_candidates.append(face_index)
                elif metrics["axis_alignment"] >= 0.7:
                    turning_moderate_flat_candidates.append(face_index)
            continue

        if surface_type == "bspline":
            if face.get("is_exterior") is not True:
                continue
            curved_face_candidates.append(face_index)
            continue

        if surface_type in {"cone", "torus", "surface_of_revolution"}:
            if face.get("is_exterior") is not True:
                continue
            neighbor_faces = _neighbor_surface_records(face, face_lookup)
            exterior_planar_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                and neighbor.get("is_exterior") is True
            ]
            surface_axis = _surface_axis_direction(face)
            axis_index = _dominant_axis_index(surface_axis) if surface_axis is not None else None
            if (
                short_turning_part
                and primary_axis is not None
                and surface_axis is not None
                and _axis_alignment_cos(surface_axis, primary_axis) >= 0.996
            ):
                radius = _turn_radius_from_face(face, primary_axis) or 0.0
                if (
                    surface_type == "cone"
                    and radius > 0.0
                    and radius <= max_turn_radius_mm * TURN_SHORT_CIRCULAR_MILLED_MAX_RADIUS_RATIO
                ):
                    circular_milled_candidates.append(face_index)
                    continue
                if surface_type == "torus":
                    curved_face_candidates.append(face_index)
                    continue
                continue
            if (
                primary_axis is None
                and surface_type == "torus"
                and axis_index == smallest_axis_index
                and exterior_planar_neighbors
            ):
                concave_fillet_edge_candidate_groups.setdefault(("torus", face_index), set()).add(face_index)
                continue
            if (
                primary_axis is None
                and surface_type == "cone"
                and len(neighbor_faces) <= 2
                and any(
                    isinstance(neighbor.get("face_index"), int)
                    and int(neighbor.get("face_index")) in hole_face_indices
                    for neighbor in neighbor_faces
                )
            ):
                continue
            curved_face_candidates.append(face_index)
            continue

        if surface_type == "cylinder":
            if face.get("is_exterior") is not True:
                continue
            metrics = _cylindrical_face_metrics(face)
            if metrics is None:
                continue
            axis = metrics["axis_direction"]
            if primary_axis is not None and _axis_alignment_cos(axis, primary_axis) >= 0.996:
                continue
            neighbor_faces = _neighbor_surface_records(face, face_lookup)
            exterior_planar_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                and neighbor.get("is_exterior") is True
            ]
            interior_planar_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "plane"
                and neighbor.get("is_exterior") is False
            ]
            torus_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "torus"
            ]
            exterior_cylinder_neighbors = [
                neighbor
                for neighbor in neighbor_faces
                if str(neighbor.get("surface_type") or "").strip().lower() == "cylinder"
                and neighbor.get("is_exterior") is True
            ]
            axis_index = _dominant_axis_index(axis)
            axis_span_ratio = metrics["depth_mm"] / max(bbox_spans[axis_index], 1e-9)
            principal_axis_aligned = max(abs(component) for component in axis) >= 0.98
            face_axis_key = _face_axis_line_key(face)
            large_exterior_cylinder_neighbors = [
                neighbor
                for neighbor in exterior_cylinder_neighbors
                if ((_cylindrical_face_metrics(neighbor) or {}).get("diameter_mm") or 0.0)
                >= metrics["diameter_mm"] + 5.0
            ]
            is_large_profile_edge = (
                primary_axis is None
                and principal_axis_aligned
                and CONVEX_PROFILE_MIN_DIAMETER_MM
                <= metrics["diameter_mm"]
                <= (
                    max(CONVEX_PROFILE_MAX_DIAMETER_MM, 45.0)
                    if simple_planar_cylinder_part
                    else CONVEX_PROFILE_MAX_DIAMETER_MM
                )
                and axis_span_ratio >= CONVEX_PROFILE_AXIS_SPAN_RATIO_MIN
                and (
                    (
                        not simple_planar_cylinder_part
                        and len(exterior_planar_neighbors) >= 2
                    )
                    or (
                        simple_planar_cylinder_part
                        and axis_span_ratio < 0.98
                        and len(exterior_planar_neighbors) >= 4
                    )
                )
            )
            if is_large_profile_edge:
                convex_profile_edge_candidates.append(face_index)
                if axis_span_ratio >= 0.9:
                    continue
            is_short_concave_blend = (
                primary_axis is None
                and axis_index == smallest_axis_index
                and CONCAVE_FILLET_SHORT_CYLINDER_MIN_DIAMETER_MM
                <= metrics["diameter_mm"]
                <= CONCAVE_FILLET_SHORT_CYLINDER_MAX_DIAMETER_MM
                and axis_span_ratio <= CONCAVE_FILLET_SHORT_CYLINDER_SPAN_RATIO_MAX
                and len(torus_neighbors) == 1
                and len(exterior_planar_neighbors) >= 1
            )
            if is_short_concave_blend:
                concave_fillet_edge_candidate_groups.setdefault(("short_blend", face_index), set()).add(face_index)
                continue
            if (
                simple_planar_cylinder_part
                and primary_axis is None
                and (
                    (
                        metrics["diameter_mm"] <= 10.0
                        and metrics["completeness_ratio"] >= 0.45
                        and len(exterior_planar_neighbors) >= 4
                        and axis_span_ratio >= 0.6
                    )
                    or (
                        len(large_exterior_cylinder_neighbors) >= 1
                        and len(exterior_planar_neighbors) >= 2
                        and metrics["completeness_ratio"] <= 0.55
                        and axis_span_ratio <= 0.45
                        and (
                            len(interior_planar_neighbors) >= 1
                            or face_axis_key in interior_cylinder_keys
                        )
                    )
                )
            ):
                if large_exterior_cylinder_neighbors and metrics["diameter_mm"] > 10.0:
                    largest_neighbor = max(
                        large_exterior_cylinder_neighbors,
                        key=lambda neighbor: float(
                            (_cylindrical_face_metrics(neighbor) or {}).get("diameter_mm") or 0.0
                        ),
                    )
                    merge_key = (
                        "neighbor",
                        int(largest_neighbor.get("face_index"))
                        if isinstance(largest_neighbor.get("face_index"), int)
                        else face_index,
                    )
                else:
                    merge_key = ("face", face_index)
                concave_fillet_edge_candidate_groups.setdefault(merge_key, set()).add(face_index)

            simple_partial_curved_cylinder = (
                simple_planar_cylinder_part
                and primary_axis is None
                and 0.2 <= metrics["completeness_ratio"] <= 0.6
                and len(exterior_planar_neighbors) >= 2
                and axis_index != dominant_axis_index
                and (
                    face_index in hole_face_indices
                    or face_axis_key in interior_cylinder_keys
                    or len(interior_planar_neighbors) >= 1
                    or len(exterior_cylinder_neighbors) >= 1
                    or (
                        is_large_profile_edge
                        and len(exterior_planar_neighbors) >= 6
                        and metrics["completeness_ratio"] <= 0.35
                    )
                )
            )
            if face_index in boss_face_indices:
                continue
            is_off_axis_half_cylinder = (
                primary_axis is None
                and axis_index != smallest_axis_index
                and metrics["diameter_mm"] <= CURVED_HALF_CYLINDER_MAX_DIAMETER_MM
                and metrics["completeness_ratio"] >= CURVED_HALF_CYLINDER_MIN_COMPLETENESS
                and len(torus_neighbors) >= 2
                and len(interior_planar_neighbors) >= 1
                and len(exterior_planar_neighbors) + len(interior_planar_neighbors) >= 2
            )
            if is_off_axis_half_cylinder:
                curved_face_candidates.append(face_index)
                continue
            if simple_partial_curved_cylinder:
                curved_face_candidates.append(face_index)
                continue
            if (
                primary_axis is None
                and axis_index == smallest_axis_index
                and len(exterior_planar_neighbors) >= 1
                and axis_span_ratio >= 0.9
            ):
                continue
            if (
                primary_axis is None
                and len(torus_neighbors) >= 1
                and len(exterior_planar_neighbors) >= 1
                and axis_span_ratio <= CONCAVE_FILLET_SHORT_CYLINDER_SPAN_RATIO_MAX
            ):
                continue
            if face_index in hole_face_indices:
                continue
            if face_axis_key in interior_cylinder_keys:
                continue
            if axis_index == smallest_axis_index:
                curved_face_candidates.append(face_index)

    curved_face_candidates = sorted(set(curved_face_candidates))
    circular_milled_candidates = sorted(set(circular_milled_candidates))
    if primary_axis is not None:
        bspline_candidates = [
            face_index
            for face_index in curved_face_candidates
            if str(face_lookup.get(face_index, {}).get("surface_type") or "").strip().lower() == "bspline"
        ]
        if len(bspline_candidates) >= 8:
            bspline_areas = [
                float(face_lookup[face_index].get("area_mm2") or 0.0)
                for face_index in bspline_candidates
            ]
            if bspline_areas and max(bspline_areas) / max(min(bspline_areas), 1e-9) >= 2.0:
                median_area = _median_area(bspline_candidates, face_lookup)
                if median_area is not None:
                    curved_face_candidates = [
                        face_index
                        for face_index in curved_face_candidates
                        if str(face_lookup.get(face_index, {}).get("surface_type") or "").strip().lower() != "bspline"
                        or float(face_lookup[face_index].get("area_mm2") or 0.0) >= median_area
                    ]

    flat_face_candidates = sorted(set(flat_face_candidates))
    flat_side_candidates = sorted(set(flat_side_candidates))
    turning_moderate_flat_candidates = sorted(set(turning_moderate_flat_candidates))
    curved_face_candidates = sorted(set(curved_face_candidates))
    convex_profile_edge_candidates = sorted(set(convex_profile_edge_candidates))
    concave_fillet_edge_feature_groups = sorted(
        (
            sorted(indices)
            for indices in concave_fillet_edge_candidate_groups.values()
            if indices
        ),
        key=lambda group: (group[0], len(group)),
    )
    concave_fillet_edge_candidates = sorted(
        {
            face_index
            for group in concave_fillet_edge_feature_groups
            for face_index in group
        }
    )

    if simple_planar_cylinder_part and primary_axis is None:
        flat_feature_groups = _group_flat_planar_features_for_simple_parts(
            flat_face_candidates,
            face_lookup,
            bbox_bounds,
        )
    else:
        flat_feature_groups = _split_flat_feature_groups(
            _connected_face_components(flat_face_candidates, face_lookup),
            face_lookup,
            bbox_bounds,
        )
    flat_side_feature_groups = _connected_face_components(flat_side_candidates, face_lookup)
    curved_feature_groups = _merge_groups_by_axis_key(
        _connected_face_components(curved_face_candidates, face_lookup),
        face_lookup,
    )
    curved_feature_groups = _split_curved_feature_groups(curved_feature_groups, face_lookup)
    if (
        simple_planar_cylinder_part
        and primary_axis is None
        and isinstance(pocket_detection, dict)
        and int(pocket_detection.get("open_pocket_count") or 0) > 0
    ):
        partial_hole_face_indices = {
            int(candidate["face_index"])
            for candidate in (hole_detection or {}).get("candidates", [])
            if isinstance(candidate, dict)
            and candidate.get("subtype") == "partial_hole"
            and isinstance(candidate.get("face_index"), int)
        }
        curved_feature_groups = [
            [face_index]
            for face_index in curved_face_candidates
            if face_index not in partial_hole_face_indices
        ]
    elif (
        simple_planar_cylinder_part
        and primary_axis is None
        and isinstance(pocket_detection, dict)
        and int(pocket_detection.get("open_pocket_count") or 0) == 0
    ):
        refined_curved_feature_groups: list[list[int]] = []
        for group in curved_feature_groups:
            if len(group) == 3:
                records = [
                    face_lookup.get(face_index)
                    for face_index in group
                ]
                if all(
                    isinstance(record, dict)
                    and str(record.get("surface_type") or "").strip().lower() == "cylinder"
                    for record in records
                ):
                    ordered = sorted(
                        (
                            (
                                float(record.get("area_mm2") or 0.0),
                                int(record.get("face_index")),
                            )
                            for record in records
                            if isinstance(record.get("face_index"), int)
                        ),
                        reverse=True,
                    )
                    if (
                        len(ordered) == 3
                        and ordered[0][0] > max(ordered[1][0], 1e-9) * 2.5
                    ):
                        dominant_face = ordered[0][1]
                        residual_faces = sorted(
                            face_index
                            for face_index in group
                            if face_index != dominant_face
                        )
                        refined_curved_feature_groups.append([dominant_face])
                        refined_curved_feature_groups.append(residual_faces)
                        continue
            refined_curved_feature_groups.append(group)
        curved_feature_groups = refined_curved_feature_groups
    turning_moderate_flat_groups = _connected_face_components(
        turning_moderate_flat_candidates,
        face_lookup,
    )

    if primary_axis is None:
        flat_milled_face_count = len(flat_feature_groups)
        flat_side_milled_face_count = len(flat_side_candidates)
        curved_milled_face_count = len(curved_feature_groups)
        circular_milled_face_count = len(circular_milled_candidates)
        count_strategy = {
            "flat": "connected_groups",
            "flat_side": "raw_faces",
            "curved": "connected_groups",
            "circular": "raw_faces",
        }
    else:
        flat_milled_face_count = len(flat_face_candidates) + len(turning_moderate_flat_groups)
        flat_side_milled_face_count = 0
        curved_milled_face_count = len(curved_face_candidates)
        circular_milled_face_count = len(circular_milled_candidates)
        count_strategy = {
            "flat": "raw_faces_plus_moderate_groups",
            "flat_side": "disabled_for_turning_part",
            "curved": "filtered_raw_faces",
            "circular": "raw_faces",
        }

    all_face_indices = sorted(
        set(flat_face_candidates)
        | set(flat_side_candidates)
        | set(curved_face_candidates)
        | set(circular_milled_candidates)
    )
    return {
        "milled_face_count": (
            flat_milled_face_count
            + flat_side_milled_face_count
            + curved_milled_face_count
            + circular_milled_face_count
        ),
        "flat_milled_face_count": flat_milled_face_count,
        "flat_side_milled_face_count": flat_side_milled_face_count,
        "curved_milled_face_count": curved_milled_face_count,
        "circular_milled_face_count": circular_milled_face_count,
        "convex_profile_edge_milled_face_count": len(convex_profile_edge_candidates),
        "concave_fillet_edge_milled_face_count": len(concave_fillet_edge_feature_groups),
        "face_indices": all_face_indices,
        "flat_milled_face_indices": flat_face_candidates,
        "flat_side_milled_face_indices": flat_side_candidates,
        "curved_milled_face_indices": curved_face_candidates,
        "circular_milled_face_indices": circular_milled_candidates,
        "convex_profile_edge_milled_face_indices": convex_profile_edge_candidates,
        "concave_fillet_edge_milled_face_indices": concave_fillet_edge_candidates,
        "flat_milled_feature_groups": flat_feature_groups,
        "flat_side_milled_feature_groups": flat_side_feature_groups,
        "curved_milled_feature_groups": curved_feature_groups,
        "circular_milled_feature_groups": [[face_index] for face_index in circular_milled_candidates],
        "convex_profile_edge_milled_feature_groups": [[face_index] for face_index in convex_profile_edge_candidates],
        "concave_fillet_edge_milled_feature_groups": concave_fillet_edge_feature_groups,
        "turning_moderate_flat_face_indices": turning_moderate_flat_candidates,
        "turning_moderate_flat_groups": turning_moderate_flat_groups,
        "excluded_turning_deck_faces": excluded_turning_deck_faces,
        "count_strategy": count_strategy,
        "dominant_axis_index": dominant_axis_index,
        "smallest_axis_index": smallest_axis_index,
        "simple_planar_cylinder_part": simple_planar_cylinder_part,
    }


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
                    "position_mm": [
                        round(float(midpoint[0]), 4),
                        round(float(midpoint[1]), 4),
                        round(float(midpoint[2]), 4),
                    ],
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
                    "anchor_bounds_mm": _box_payload_from_center(
                        midpoint,
                        half_extent_mm=min(
                            12.0,
                            max(
                                1.5,
                                (pocket_depth_mm or 0.0) * 0.08,
                                (radius_mm or 0.0) * 2.0,
                            ),
                        ),
                    ),
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
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
            from OCC.Core.BRepBndLib import brepbndlib
            from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
            from OCC.Core.BRepGProp import brepgprop
            from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
            from OCC.Core.GeomAbs import (
                GeomAbs_BSplineSurface,
                GeomAbs_Circle,
                GeomAbs_Cone,
                GeomAbs_Cylinder,
                GeomAbs_Line,
                GeomAbs_Plane,
                GeomAbs_Sphere,
                GeomAbs_SurfaceOfRevolution,
                GeomAbs_Torus,
            )
            from OCC.Core.GeomLProp import GeomLProp_CLProps, GeomLProp_SLProps
            from OCC.Core.GProp import GProp_GProps
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
            "BRepAdaptor_Surface": BRepAdaptor_Surface,
            "brepbndlib": brepbndlib,
            "BRepClass3d_SolidClassifier": BRepClass3d_SolidClassifier,
            "brepgprop": brepgprop,
            "GeomAPI_ProjectPointOnSurf": GeomAPI_ProjectPointOnSurf,
            "GeomAbs_BSplineSurface": GeomAbs_BSplineSurface,
            "GeomAbs_Circle": GeomAbs_Circle,
            "GeomAbs_Cone": GeomAbs_Cone,
            "GeomAbs_Cylinder": GeomAbs_Cylinder,
            "GeomAbs_Line": GeomAbs_Line,
            "GeomAbs_Plane": GeomAbs_Plane,
            "GeomAbs_Sphere": GeomAbs_Sphere,
            "GeomAbs_SurfaceOfRevolution": GeomAbs_SurfaceOfRevolution,
            "GeomAbs_Torus": GeomAbs_Torus,
            "GeomLProp_CLProps": GeomLProp_CLProps,
            "GeomLProp_SLProps": GeomLProp_SLProps,
            "GProp_GProps": GProp_GProps,
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
        occ["brepbndlib"].Add(shape, box)
        return box.Get()

    def inspect_feature_inventory(
        self,
        *,
        step_path: Path,
        component_node_name: str | None = None,
    ) -> dict[str, Any]:
        occ = self._import_occ()
        shape = self._load_shape(occ, step_path)
        analysis_shape, component_fallback = self._resolve_analysis_shape(
            occ, shape, component_node_name
        )
        bounds = self._shape_bounds(occ, analysis_shape)
        classifier_shape = (
            analysis_shape
            if analysis_shape.ShapeType() == occ["TopAbs_SOLID"]
            else None
        )
        face_inventory = self._build_face_inventory(
            occ=occ,
            shape=analysis_shape,
            bounds=bounds,
            classifier_shape=classifier_shape,
        )
        turning_detection = detect_turning_from_face_inventory(
            face_inventory,
            bbox_bounds=bounds,
        )
        hole_detection = detect_hole_features_from_face_inventory(
            face_inventory,
            bbox_bounds=bounds,
            turning_detection=turning_detection,
        )
        pocket_detection = detect_pocket_features_from_face_inventory(
            face_inventory,
            bbox_bounds=bounds,
        )
        boss_detection = detect_boss_features_from_face_inventory(
            face_inventory,
            bbox_bounds=bounds,
            turning_detection=turning_detection,
        )
        milled_face_detection = detect_milled_faces_from_face_inventory(
            face_inventory,
            bbox_bounds=bounds,
            turning_detection=turning_detection,
            pocket_detection=pocket_detection,
            hole_detection=hole_detection,
            boss_detection=boss_detection,
        )
        return {
            "part_filename": step_path.name,
            "component_node_name": component_node_name,
            "component_fallback": component_fallback,
            "bbox_bounds": bounds,
            "face_inventory": face_inventory,
            "turning_detection": turning_detection,
            "hole_detection": hole_detection,
            "pocket_detection": pocket_detection,
            "boss_detection": boss_detection,
            "milled_face_detection": milled_face_detection,
        }

    def _build_face_inventory(
        self,
        *,
        occ: dict[str, Any],
        shape,
        bounds: tuple[float, float, float, float, float, float],
        classifier_shape,
    ) -> list[dict[str, Any]]:
        faces: list[Any] = []
        inventory: list[dict[str, Any]] = []
        explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
        face_index = 1
        while explorer.More():
            face = occ["topods"].Face(explorer.Current())
            explorer.Next()
            faces.append(face)
            record = self._face_inventory_record(
                occ=occ,
                face=face,
                face_index=face_index,
                bounds=bounds,
                classifier_shape=classifier_shape,
            )
            inventory.append(record)
            face_index += 1
        self._annotate_face_adjacency(
            occ=occ,
            faces=faces,
            inventory=inventory,
        )
        return inventory

    def _face_inventory_record(
        self,
        *,
        occ: dict[str, Any],
        face,
        face_index: int,
        bounds: tuple[float, float, float, float, float, float],
        classifier_shape,
    ) -> dict[str, Any]:
        surface = occ["BRepAdaptor_Surface"](face, True)
        surface_type = self._surface_type_name(occ, int(surface.GetType()))
        face_bounds = self._shape_bounds(occ, face)
        area_mm2, centroid = self._surface_area_and_centroid(occ, face)
        sample_point = None
        sample_normal = None
        boundary_classification = {
            "is_boundary_face": None,
            "is_exterior": None,
        }
        for u, v in self._face_sample_uvs(surface):
            point, normal = self._face_point_and_normal(
                occ=occ,
                face=face,
                surface=surface,
                u=u,
                v=v,
            )
            if point is None or normal is None:
                continue
            if sample_point is None:
                sample_point = point
                sample_normal = normal
            classification = self._classify_face_boundary(
                occ=occ,
                classifier_shape=classifier_shape,
                sample_point=point,
                sample_normal=normal,
                bounds=bounds,
            )
            if classification["is_boundary_face"] is None:
                continue
            sample_point = point
            sample_normal = normal
            boundary_classification = classification
            if classification["is_boundary_face"]:
                break

        axis_direction, axis_origin = self._surface_axis_payload(surface)
        axial_span_mm = None
        if axis_direction is not None:
            axial_span_mm = _project_bounds_span(face_bounds, axis_direction)

        return {
            "face_index": face_index,
            "surface_type": surface_type,
            "area_mm2": None if area_mm2 is None else round(area_mm2, 4),
            "centroid_mm": None if centroid is None else [round(value, 4) for value in centroid],
            "bbox_bounds": [round(value, 4) for value in face_bounds],
            "sample_point_mm": None
            if sample_point is None
            else [round(value, 4) for value in sample_point],
            "sample_normal": None
            if sample_normal is None
            else [round(value, 6) for value in sample_normal],
            "is_boundary_face": boundary_classification["is_boundary_face"],
            "is_exterior": boundary_classification["is_exterior"],
            "axis_direction": None
            if axis_direction is None
            else [round(value, 6) for value in axis_direction],
            "axis_origin": None
            if axis_origin is None
            else [round(value, 4) for value in axis_origin],
            "axial_span_mm": None if axial_span_mm is None else round(axial_span_mm, 4),
            "adjacent_face_indices": [],
            "adjacent_face_count": 0,
            "edge_count": 0,
        }

    def _annotate_face_adjacency(
        self,
        *,
        occ: dict[str, Any],
        faces: list[Any],
        inventory: list[dict[str, Any]],
    ) -> None:
        edge_to_face_indices: dict[int, set[int]] = {}
        edge_keys_by_face: dict[int, list[int]] = {}

        for index, face in enumerate(faces, start=1):
            explorer = occ["TopExp_Explorer"](face, occ["TopAbs_EDGE"])
            edge_keys: list[int] = []
            seen_edge_keys: set[int] = set()
            while explorer.More():
                edge = occ["topods"].Edge(explorer.Current())
                explorer.Next()
                try:
                    edge_key = hash(edge)
                except Exception:
                    continue
                if edge_key in seen_edge_keys:
                    continue
                seen_edge_keys.add(edge_key)
                edge_keys.append(edge_key)
                edge_to_face_indices.setdefault(edge_key, set()).add(index)
            edge_keys_by_face[index] = edge_keys

        for index, record in enumerate(inventory, start=1):
            adjacent_indices: set[int] = set()
            for edge_key in edge_keys_by_face.get(index, []):
                adjacent_indices.update(edge_to_face_indices.get(edge_key, set()))
            adjacent_indices.discard(index)
            record["adjacent_face_indices"] = sorted(adjacent_indices)
            record["adjacent_face_count"] = len(adjacent_indices)
            record["edge_count"] = len(edge_keys_by_face.get(index, []))

    def _surface_type_name(self, occ: dict[str, Any], surface_type: int) -> str:
        type_map = {
            int(occ["GeomAbs_Plane"]): "plane",
            int(occ["GeomAbs_Cylinder"]): "cylinder",
            int(occ["GeomAbs_Cone"]): "cone",
            int(occ["GeomAbs_SurfaceOfRevolution"]): "surface_of_revolution",
            int(occ["GeomAbs_BSplineSurface"]): "bspline",
            int(occ["GeomAbs_Sphere"]): "sphere",
            int(occ["GeomAbs_Torus"]): "torus",
        }
        return type_map.get(surface_type, f"surface_type_{surface_type}")

    def _surface_area_and_centroid(
        self,
        occ: dict[str, Any],
        face,
    ) -> tuple[float | None, tuple[float, float, float] | None]:
        try:
            props = occ["GProp_GProps"]()
            occ["brepgprop"].SurfaceProperties(face, props)
            centre = props.CentreOfMass()
            return float(props.Mass()), (
                float(centre.X()),
                float(centre.Y()),
                float(centre.Z()),
            )
        except Exception:
            return None, None

    def _face_sample_uvs(self, surface) -> list[tuple[float, float]]:
        try:
            first_u = float(surface.FirstUParameter())
            last_u = float(surface.LastUParameter())
            first_v = float(surface.FirstVParameter())
            last_v = float(surface.LastVParameter())
        except Exception:
            return []

        if not all(math.isfinite(value) for value in (first_u, last_u, first_v, last_v)):
            return []

        u_span = last_u - first_u
        v_span = last_v - first_v
        samples: list[tuple[float, float]] = []
        for u_fraction in (0.5, 0.25, 0.75):
            for v_fraction in (0.5, 0.25, 0.75):
                samples.append(
                    (
                        first_u + u_span * u_fraction,
                        first_v + v_span * v_fraction,
                    )
                )
        return samples

    def _face_point_and_normal(
        self,
        *,
        occ: dict[str, Any],
        face,
        surface,
        u: float,
        v: float,
    ) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None]:
        try:
            point = surface.Value(u, v)
            geom_surface = occ["BRep_Tool"].Surface(face)
            props = occ["GeomLProp_SLProps"](geom_surface, u, v, 1, 1e-6)
            if not props.IsNormalDefined():
                return None, None
            normal = props.Normal()
            return (
                (float(point.X()), float(point.Y()), float(point.Z())),
                _normalize((float(normal.X()), float(normal.Y()), float(normal.Z()))),
            )
        except Exception:
            return None, None

    def _classify_face_boundary(
        self,
        *,
        occ: dict[str, Any],
        classifier_shape,
        sample_point: tuple[float, float, float],
        sample_normal: tuple[float, float, float],
        bounds: tuple[float, float, float, float, float, float],
    ) -> dict[str, bool | None]:
        if classifier_shape is None:
            return {"is_boundary_face": None, "is_exterior": None}

        max_span = max(
            bounds[3] - bounds[0],
            bounds[4] - bounds[1],
            bounds[5] - bounds[2],
            0.0,
        )
        probe = max(0.25, max_span * 0.005)
        plus_state = self._solid_state(
            occ,
            classifier_shape,
            _add(sample_point, _mul(sample_normal, probe)),
        )
        minus_state = self._solid_state(
            occ,
            classifier_shape,
            _sub(sample_point, _mul(sample_normal, probe)),
        )
        if plus_state == "outside" and minus_state == "inside":
            outside_direction = sample_normal
        elif plus_state == "inside" and minus_state == "outside":
            outside_direction = _mul(sample_normal, -1.0)
        else:
            is_boundary_face = (
                plus_state == "outside" and minus_state == "outside"
            ) or (
                plus_state == "inside" and minus_state == "inside"
            )
            return {"is_boundary_face": False if is_boundary_face else None, "is_exterior": None}

        return {
            "is_boundary_face": True,
            "is_exterior": self._outside_direction_reaches_bbox(
                occ=occ,
                classifier_shape=classifier_shape,
                sample_point=sample_point,
                outside_direction=outside_direction,
                bounds=bounds,
                probe=probe,
            ),
        }

    def _outside_direction_reaches_bbox(
        self,
        *,
        occ: dict[str, Any],
        classifier_shape,
        sample_point: tuple[float, float, float],
        outside_direction: tuple[float, float, float],
        bounds: tuple[float, float, float, float, float, float],
        probe: float,
    ) -> bool:
        escape_distance = self._distance_to_bounds_along_direction(
            sample_point=sample_point,
            direction=outside_direction,
            bounds=bounds,
        )
        max_span = max(
            bounds[3] - bounds[0],
            bounds[4] - bounds[1],
            bounds[5] - bounds[2],
            probe,
        )
        if escape_distance is None:
            escape_distance = max_span
        travel_distance = max(escape_distance, probe * 2.0)
        for fraction in (0.25, 0.5, 0.75, 1.0):
            probe_point = _add(
                sample_point,
                _mul(outside_direction, max(probe, travel_distance * fraction)),
            )
            state = self._solid_state(occ, classifier_shape, probe_point)
            if state == "inside":
                return False
        return True

    def _distance_to_bounds_along_direction(
        self,
        *,
        sample_point: tuple[float, float, float],
        direction: tuple[float, float, float],
        bounds: tuple[float, float, float, float, float, float],
    ) -> float | None:
        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        candidates: list[float] = []
        for bound_min, bound_max, coordinate, component in (
            (x_min, x_max, sample_point[0], direction[0]),
            (y_min, y_max, sample_point[1], direction[1]),
            (z_min, z_max, sample_point[2], direction[2]),
        ):
            if component > 1e-9:
                distance = (bound_max - coordinate) / component
                if distance > 0:
                    candidates.append(distance)
            elif component < -1e-9:
                distance = (bound_min - coordinate) / component
                if distance > 0:
                    candidates.append(distance)
        if not candidates:
            return None
        distance = min(candidates)
        return distance if math.isfinite(distance) and distance > 0 else None

    def _surface_axis_payload(
        self,
        surface,
    ) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None]:
        try:
            surface_type = str(surface.GetType())
        except Exception:
            surface_type = ""
        del surface_type
        try:
            cylinder = surface.Cylinder()
            axis = cylinder.Axis()
        except Exception:
            axis = None
        if axis is None:
            try:
                cone = surface.Cone()
                axis = cone.Axis()
            except Exception:
                axis = None
        if axis is None:
            try:
                torus = surface.Torus()
                axis = torus.Axis()
            except Exception:
                axis = None
        if axis is None:
            try:
                axis = surface.AxeOfRevolution()
            except Exception:
                axis = None
        if axis is None:
            return None, None
        try:
            direction = axis.Direction()
            location = axis.Location()
            return (
                _canonical_axis(
                    (
                        float(direction.X()),
                        float(direction.Y()),
                        float(direction.Z()),
                    )
                ),
                (
                    float(location.X()),
                    float(location.Y()),
                    float(location.Z()),
                ),
            )
        except Exception:
            return None, None

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
