from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cnc_geometry_occ import CncGeometryAnalyzer, CncGeometryError

KNOWN_METRIC_STATES = {"measured", "inferred", "declared"}
NOT_APPLICABLE_STATE = "not_applicable"


class PartFactsError(RuntimeError):
    pass


class PartFactsNotFoundError(PartFactsError):
    pass


def _metric(
    *,
    label: str,
    value: Any = None,
    unit: str | None = None,
    state: str = "unknown",
    confidence: float = 0.0,
    source: str = "",
    reason: str | None = None,
) -> dict[str, Any]:
    payload = {
        "label": label,
        "value": value,
        "unit": unit,
        "state": state,
        "confidence": round(float(max(0.0, min(1.0, confidence))), 4),
        "source": source,
    }
    if reason:
        payload["reason"] = reason
    return payload


def _state_known(state: Any) -> bool:
    return isinstance(state, str) and state in KNOWN_METRIC_STATES


def _state_not_applicable(state: Any) -> bool:
    return isinstance(state, str) and state == NOT_APPLICABLE_STATE


def _safe_optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _safe_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and float(value).is_integer():
        return int(value)
    return None


class PartFactsService:
    SCHEMA_VERSION = "1.2.0"

    def __init__(
        self,
        *,
        root: Path,
        bundle: Any,
        geometry_analyzer: CncGeometryAnalyzer | None = None,
    ) -> None:
        self.root = root
        self.bundle = bundle
        self.geometry_analyzer = geometry_analyzer or CncGeometryAnalyzer()
        self.rule_input_frequency = self._collect_rule_input_frequency(bundle)
        self.process_input_keys = self._collect_process_input_keys(bundle)
        self.high_priority_rule_inputs = [
            key
            for key, count in sorted(
                self.rule_input_frequency.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if count >= 3
        ]

    def get(self, *, model_id: str, component_node_name: str) -> dict[str, Any]:
        payload_path = self._facts_path(
            model_id=model_id,
            component_node_name=component_node_name,
        )
        if not payload_path.exists():
            raise PartFactsNotFoundError("Part facts not found for component.")
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PartFactsError(f"Failed to read part facts: {exc}") from exc
        if not isinstance(payload, dict):
            raise PartFactsError("Invalid part facts payload format.")
        return payload

    def get_or_create(
        self,
        *,
        model_id: str,
        step_path: Path,
        component_node_name: str,
        component_display_name: str,
        component_profile: dict[str, Any] | None,
        triangle_count: int | None,
        assembly_component_count: int,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        if not force_refresh:
            try:
                payload = self.get(model_id=model_id, component_node_name=component_node_name)
                if payload.get("schema_version") == self.SCHEMA_VERSION:
                    return payload
            except PartFactsNotFoundError:
                pass

        payload = self._build_payload(
            model_id=model_id,
            step_path=step_path,
            component_node_name=component_node_name,
            component_display_name=component_display_name,
            component_profile=component_profile or {},
            triangle_count=triangle_count,
            assembly_component_count=assembly_component_count,
        )

        payload_path = self._facts_path(
            model_id=model_id,
            component_node_name=component_node_name,
        )
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            raise PartFactsError(f"Failed to persist part facts: {exc}") from exc
        return payload

    def _build_payload(
        self,
        *,
        model_id: str,
        step_path: Path,
        component_node_name: str,
        component_display_name: str,
        component_profile: dict[str, Any],
        triangle_count: int | None,
        assembly_component_count: int,
    ) -> dict[str, Any]:
        assumptions = [
            "Units assumed mm from CAD kernel context.",
            "STEP contains no native drawing-note semantics; drawing-derived fields can remain unknown.",
        ]
        errors: list[str] = []

        sections = {
            "geometry": self._geometry_section_defaults(),
            "manufacturing_signals": self._manufacturing_section_defaults(),
            "declared_context": self._declared_context_defaults(component_profile),
            "process_inputs": self._process_input_defaults(),
            "rule_inputs": self._rule_input_defaults(),
        }

        declared_material = sections["declared_context"]["material_spec"]
        if _state_known(declared_material.get("state")):
            sections["rule_inputs"]["material_spec"] = _metric(
                label="Material specification available",
                value=True,
                unit=None,
                state="declared",
                confidence=1.0,
                source="component_profile.material",
            )

        if triangle_count is not None:
            sections["geometry"]["triangle_count"] = _metric(
                label="Triangle count",
                value=int(triangle_count),
                unit=None,
                state="measured",
                confidence=1.0,
                source="model.components.triangleCount",
            )

        try:
            self._apply_geometry_metrics(
                sections=sections,
                step_path=step_path,
                component_node_name=component_node_name,
            )
        except PartFactsError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"Unexpected geometry extraction error: {exc.__class__.__name__}: {exc}")

        # Assembly-aware input signal.
        sections["rule_inputs"]["assembly_model"] = _metric(
            label="Assembly model context available",
            value=assembly_component_count > 1,
            unit=None,
            state="inferred",
            confidence=0.7,
            source="model.components",
        )

        # Context-derived process hints.
        process_label = str(component_profile.get("manufacturingProcess") or "").strip().lower()
        process_context = self._process_context(process_label)
        if process_label:
            sections["process_inputs"]["manufacturing_process"] = _metric(
                label="Manufacturing process selected",
                value=component_profile.get("manufacturingProcess"),
                unit=None,
                state="declared",
                confidence=1.0,
                source="component_profile.manufacturingProcess",
            )
            if process_context["is_sheet"]:
                assumptions.append("Sheet process selected; sheet-specific facts remain unknown until extracted.")
            if process_context["is_weld"]:
                assumptions.append("Weld process selected; weld-symbol/note fields require drawing or annotations.")
        self._apply_not_applicable_rules(
            sections=sections,
            process_context=process_context,
            assembly_component_count=assembly_component_count,
        )
        self._apply_standards_context_hints(
            sections=sections,
            component_profile=component_profile,
            component_display_name=component_display_name,
            process_context=process_context,
        )
        core_extraction_coverage = self._coverage_snapshot(
            sections=sections,
            include_sections=["geometry", "manufacturing_signals"],
        )
        full_rule_readiness_coverage = self._coverage_snapshot(
            sections=sections,
            include_sections=["declared_context", "process_inputs", "rule_inputs"],
        )
        weighted_coverage_percent = (
            core_extraction_coverage["percent"] * 0.35
            + full_rule_readiness_coverage["percent"] * 0.65
        )
        overall_confidence = self._overall_confidence(
            coverage_percent=weighted_coverage_percent,
            error_count=len(errors),
        )
        missing_inputs = self._missing_inputs(sections)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "model_id": model_id,
            "component_node_name": component_node_name,
            "component_display_name": component_display_name,
            "generated_at": self._now_iso(),
            "coverage": {
                "core_extraction_coverage": core_extraction_coverage,
                "full_rule_readiness_coverage": full_rule_readiness_coverage,
            },
            "overall_confidence": overall_confidence,
            "missing_inputs": missing_inputs,
            "assumptions": assumptions,
            "errors": errors,
            "sections": sections,
        }

    def _apply_geometry_metrics(
        self,
        *,
        sections: dict[str, dict[str, dict[str, Any]]],
        step_path: Path,
        component_node_name: str,
    ) -> None:
        if not step_path.exists():
            raise PartFactsError("STEP file not found for part facts extraction.")

        analyzer = self.geometry_analyzer
        try:
            occ = analyzer._import_occ()
            shape = analyzer._load_shape(occ, step_path)
            analysis_shape, _ = analyzer._resolve_analysis_shape(occ, shape, component_node_name)
            bounds = analyzer._shape_bounds(occ, analysis_shape)
        except CncGeometryError as exc:
            raise PartFactsError(str(exc)) from exc
        except Exception as exc:
            raise PartFactsError(
                f"Failed to load geometry for part facts: {exc.__class__.__name__}: {exc}"
            ) from exc

        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        dx = max(0.0, x_max - x_min)
        dy = max(0.0, y_max - y_min)
        dz = max(0.0, z_max - z_min)
        bbox_volume = dx * dy * dz
        diagonal = math.sqrt(dx * dx + dy * dy + dz * dz)

        sections["geometry"]["bbox_x_mm"] = _metric(
            label="Bounding box X",
            value=round(dx, 4),
            unit="mm",
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )
        sections["geometry"]["bbox_y_mm"] = _metric(
            label="Bounding box Y",
            value=round(dy, 4),
            unit="mm",
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )
        sections["geometry"]["bbox_z_mm"] = _metric(
            label="Bounding box Z",
            value=round(dz, 4),
            unit="mm",
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )
        sections["geometry"]["bbox_volume_mm3"] = _metric(
            label="Bounding box volume",
            value=round(bbox_volume, 4),
            unit="mm3",
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )
        sections["geometry"]["bbox_diagonal_mm"] = _metric(
            label="Bounding box diagonal",
            value=round(diagonal, 4),
            unit="mm",
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )

        body_count = self._count_solids(occ=occ, shape=analysis_shape)
        sections["geometry"]["body_count"] = _metric(
            label="Solid body count",
            value=body_count,
            unit=None,
            state="measured",
            confidence=1.0,
            source="occ.topology",
        )

        volume, surface_area = self._mass_properties(analysis_shape)
        if volume is not None:
            sections["geometry"]["part_volume_mm3"] = _metric(
                label="Part volume",
                value=round(volume, 4),
                unit="mm3",
                state="measured",
                confidence=0.95,
                source="occ.mass_properties",
            )
        if surface_area is not None:
            sections["geometry"]["surface_area_mm2"] = _metric(
                label="Surface area",
                value=round(surface_area, 4),
                unit="mm2",
                state="measured",
                confidence=0.95,
                source="occ.mass_properties",
            )

        try:
            cnc_payload = analyzer.analyze(
                step_path=step_path,
                component_node_name=component_node_name,
                component_display_name=component_node_name,
                include_ok_rows=True,
                criteria=None,
            )
        except Exception:
            cnc_payload = {}

        corners = cnc_payload.get("corners") if isinstance(cnc_payload, dict) else None
        summary = cnc_payload.get("summary") if isinstance(cnc_payload, dict) else None
        corners = corners if isinstance(corners, list) else []
        summary = summary if isinstance(summary, dict) else {}

        radii = [
            value
            for value in (_safe_optional_float(item.get("radius_mm")) for item in corners if isinstance(item, dict))
            if value is not None
        ]
        depths = [
            value
            for value in (_safe_optional_float(item.get("pocket_depth_mm")) for item in corners if isinstance(item, dict))
            if value is not None
        ]
        ratios = [
            value
            for value in (
                _safe_optional_float(item.get("depth_to_radius_ratio")) for item in corners if isinstance(item, dict)
            )
            if value is not None
        ]
        aggravating_count = sum(
            1
            for item in corners
            if isinstance(item, dict) and bool(item.get("aggravating_factor"))
        )

        critical_count = _safe_optional_int(summary.get("critical_count")) or 0
        warning_count = _safe_optional_int(summary.get("warning_count")) or 0
        caution_count = _safe_optional_int(summary.get("caution_count")) or 0
        ok_count = _safe_optional_int(summary.get("ok_count")) or 0
        corner_count = len(corners)
        feature_complexity = min(100, critical_count * 3 + warning_count * 2 + caution_count)

        sections["manufacturing_signals"]["corner_count"] = _metric(
            label="Detected corner count",
            value=corner_count,
            unit=None,
            state="measured",
            confidence=0.85,
            source="cnc_geometry_occ",
        )
        sections["manufacturing_signals"]["critical_corner_count"] = _metric(
            label="Critical corners",
            value=critical_count,
            unit=None,
            state="measured",
            confidence=0.85,
            source="cnc_geometry_occ.summary",
        )
        sections["manufacturing_signals"]["warning_corner_count"] = _metric(
            label="Warning corners",
            value=warning_count,
            unit=None,
            state="measured",
            confidence=0.85,
            source="cnc_geometry_occ.summary",
        )
        sections["manufacturing_signals"]["caution_corner_count"] = _metric(
            label="Caution corners",
            value=caution_count,
            unit=None,
            state="measured",
            confidence=0.85,
            source="cnc_geometry_occ.summary",
        )
        sections["manufacturing_signals"]["ok_corner_count"] = _metric(
            label="OK corners",
            value=ok_count,
            unit=None,
            state="measured",
            confidence=0.85,
            source="cnc_geometry_occ.summary",
        )
        sections["manufacturing_signals"]["long_reach_tool_risk_count"] = _metric(
            label="Long-reach risk count",
            value=aggravating_count,
            unit=None,
            state="inferred",
            confidence=0.75,
            source="cnc_geometry_occ.aggravating_factor",
        )
        sections["manufacturing_signals"]["pockets_present"] = _metric(
            label="Pockets/slotted corners detected",
            value=corner_count > 0,
            unit=None,
            state="inferred",
            confidence=0.7,
            source="cnc_geometry_occ",
        )
        sections["manufacturing_signals"]["feature_complexity_score"] = _metric(
            label="Feature complexity score",
            value=feature_complexity,
            unit=None,
            state="inferred",
            confidence=0.65,
            source="cnc_geometry_occ.summary",
        )

        if radii:
            min_radius = min(radii)
            max_radius = max(radii)
            rounded_unique_radii = {round(value, 3) for value in radii if value >= 0.0}
            sections["manufacturing_signals"]["min_internal_radius_mm"] = _metric(
                label="Minimum internal radius",
                value=round(min_radius, 4),
                unit="mm",
                state="measured",
                confidence=0.85,
                source="cnc_geometry_occ.radius",
            )
            sections["manufacturing_signals"]["count_radius_below_1_5_mm"] = _metric(
                label="Count radius < 1.5 mm",
                value=sum(1 for value in radii if value < 1.5),
                unit=None,
                state="inferred",
                confidence=0.8,
                source="cnc_geometry_occ.radius",
            )
            sections["manufacturing_signals"]["count_radius_below_3_0_mm"] = _metric(
                label="Count radius < 3.0 mm",
                value=sum(1 for value in radii if value < 3.0),
                unit=None,
                state="inferred",
                confidence=0.8,
                source="cnc_geometry_occ.radius",
            )
            sections["manufacturing_signals"]["unique_internal_radius_count"] = _metric(
                label="Unique internal radius count",
                value=len(rounded_unique_radii),
                unit=None,
                state="inferred",
                confidence=0.75,
                source="cnc_geometry_occ.radius",
            )
            if min_radius > 0:
                sections["manufacturing_signals"]["radius_variation_ratio"] = _metric(
                    label="Internal radius variation ratio",
                    value=round(max_radius / min_radius, 4),
                    unit=None,
                    state="inferred",
                    confidence=0.75,
                    source="cnc_geometry_occ.radius",
                )
            sections["rule_inputs"]["radii_set"] = _metric(
                label="Radii set available",
                value=True,
                unit=None,
                state="measured",
                confidence=0.85,
                source="cnc_geometry_occ.radius",
            )
            sections["rule_inputs"]["pocket_corner_radius"] = _metric(
                label="Pocket corner radius available",
                value=True,
                unit=None,
                state="measured",
                confidence=0.85,
                source="cnc_geometry_occ.radius",
            )

        if depths:
            sections["manufacturing_signals"]["max_pocket_depth_mm"] = _metric(
                label="Maximum pocket depth",
                value=round(max(depths), 4),
                unit="mm",
                state="measured",
                confidence=0.75,
                source="cnc_geometry_occ.depth",
            )
            sections["rule_inputs"]["pocket_depth"] = _metric(
                label="Pocket depth data available",
                value=True,
                unit=None,
                state="measured",
                confidence=0.75,
                source="cnc_geometry_occ.depth",
            )

        if ratios:
            sections["manufacturing_signals"]["max_depth_to_radius_ratio"] = _metric(
                label="Maximum depth/radius ratio",
                value=round(max(ratios), 4),
                unit=None,
                state="inferred",
                confidence=0.75,
                source="cnc_geometry_occ.depth_to_radius",
            )

        sections["rule_inputs"]["geometry_features"] = _metric(
            label="Geometry feature map available",
            value=corner_count > 0,
            unit=None,
            state="inferred",
            confidence=0.7,
            source="cnc_geometry_occ",
        )
        sections["rule_inputs"]["part_bounding_box"] = _metric(
            label="Part bounding box available",
            value=True,
            unit=None,
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )

        sections["process_inputs"]["pockets_present"] = _metric(
            label="Pockets present",
            value=corner_count > 0,
            unit=None,
            state="inferred",
            confidence=0.7,
            source="cnc_geometry_occ",
        )
        sections["process_inputs"]["bbox_dimensions"] = _metric(
            label="Bounding-box dimensions available",
            value=True,
            unit=None,
            state="measured",
            confidence=1.0,
            source="occ.bbox",
        )
        sections["process_inputs"]["feature_complexity_score"] = _metric(
            label="Feature complexity score available",
            value=True,
            unit=None,
            state="inferred",
            confidence=0.65,
            source="cnc_geometry_occ.summary",
        )

        cylindrical_metrics = self._extract_cylindrical_feature_metrics(
            occ=occ,
            shape=analysis_shape,
            bbox_dims=(dx, dy, dz),
        )
        if cylindrical_metrics:
            hole_count = cylindrical_metrics.get("hole_count")
            if isinstance(hole_count, int):
                sections["manufacturing_signals"]["hole_count"] = _metric(
                    label="Hole count",
                    value=hole_count,
                    unit=None,
                    state="measured",
                    confidence=0.65,
                    source="occ.cylindrical_faces",
                )
                sections["rule_inputs"]["hole_features"] = _metric(
                    label="Hole features available",
                    value=hole_count > 0,
                    unit=None,
                    state="measured",
                    confidence=0.65,
                    source="occ.cylindrical_faces",
                )

            min_hole_diameter = cylindrical_metrics.get("min_hole_diameter_mm")
            if isinstance(min_hole_diameter, (int, float)) and min_hole_diameter > 0:
                sections["manufacturing_signals"]["min_hole_diameter_mm"] = _metric(
                    label="Minimum hole diameter",
                    value=round(float(min_hole_diameter), 4),
                    unit="mm",
                    state="measured",
                    confidence=0.65,
                    source="occ.cylindrical_faces",
                )
                sections["rule_inputs"]["hole_diameter"] = _metric(
                    label="Hole diameter",
                    value=round(float(min_hole_diameter), 4),
                    unit="mm",
                    state="measured",
                    confidence=0.65,
                    source="occ.cylindrical_faces",
                )

            max_hole_depth = cylindrical_metrics.get("max_hole_depth_mm")
            if isinstance(max_hole_depth, (int, float)) and max_hole_depth > 0:
                sections["manufacturing_signals"]["max_hole_depth_mm"] = _metric(
                    label="Maximum hole depth",
                    value=round(float(max_hole_depth), 4),
                    unit="mm",
                    state="measured",
                    confidence=0.6,
                    source="occ.cylindrical_faces",
                )
                sections["rule_inputs"]["hole_depth"] = _metric(
                    label="Hole depth",
                    value=round(float(max_hole_depth), 4),
                    unit="mm",
                    state="measured",
                    confidence=0.6,
                    source="occ.cylindrical_faces",
                )

            threaded_holes_count = cylindrical_metrics.get("threaded_holes_count")
            if isinstance(threaded_holes_count, int) and threaded_holes_count >= 0:
                sections["manufacturing_signals"]["threaded_holes_count"] = _metric(
                    label="Threaded hole count",
                    value=threaded_holes_count,
                    unit=None,
                    state="inferred",
                    confidence=0.45,
                    source="occ.cylindrical_faces.heuristic",
                    reason="heuristic from hole geometry; validate via drawing callouts for release.",
                )
                sections["process_inputs"]["threaded_holes_count"] = _metric(
                    label="Threaded holes count",
                    value=threaded_holes_count,
                    unit=None,
                    state="inferred",
                    confidence=0.45,
                    source="occ.cylindrical_faces.heuristic",
                )

        wall_thickness = self._estimate_min_wall_thickness_mm(
            occ=occ,
            shape=analysis_shape,
        )
        if isinstance(wall_thickness, (int, float)) and wall_thickness > 0:
            wall_thickness = float(wall_thickness)
            sections["manufacturing_signals"]["min_wall_thickness_mm"] = _metric(
                label="Minimum wall thickness",
                value=round(wall_thickness, 4),
                unit="mm",
                state="inferred",
                confidence=0.55,
                source="occ.opposed_planar_faces",
            )
            sections["process_inputs"]["min_wall_thickness"] = _metric(
                label="Minimum wall thickness",
                value=round(wall_thickness, 4),
                unit="mm",
                state="inferred",
                confidence=0.55,
                source="occ.opposed_planar_faces",
            )
            sections["rule_inputs"]["wall_thickness_map"] = _metric(
                label="Wall thickness map available",
                value=True,
                unit=None,
                state="inferred",
                confidence=0.55,
                source="occ.opposed_planar_faces",
            )

    def _mass_properties(self, shape) -> tuple[float | None, float | None]:
        try:
            from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
            from OCC.Core.GProp import GProp_GProps

            volume_props = GProp_GProps()
            brepgprop_VolumeProperties(shape, volume_props)
            volume = float(volume_props.Mass())

            surface_props = GProp_GProps()
            brepgprop_SurfaceProperties(shape, surface_props)
            surface_area = float(surface_props.Mass())
            return volume, surface_area
        except Exception:
            return None, None

    def _count_solids(self, *, occ: dict[str, Any], shape) -> int:
        try:
            explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_SOLID"])
            count = 0
            while explorer.More():
                count += 1
                explorer.Next()
            return max(1, count)
        except Exception:
            return 1

    def _extract_cylindrical_feature_metrics(
        self,
        *,
        occ: dict[str, Any],
        shape,
        bbox_dims: tuple[float, float, float],
    ) -> dict[str, Any]:
        try:
            from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
            from OCC.Core.GeomAbs import GeomAbs_Cylinder
        except Exception:
            return {}

        min_bbox_dim = min((dim for dim in bbox_dims if dim > 0), default=0.0)
        cylindrical_candidates: list[tuple[float, float | None]] = []

        try:
            explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
            while explorer.More():
                face = occ["topods"].Face(explorer.Current())
                explorer.Next()
                try:
                    surface = BRepAdaptor_Surface(face, True)
                except Exception:
                    continue
                if surface.GetType() != GeomAbs_Cylinder:
                    continue

                try:
                    radius = abs(float(surface.Cylinder().Radius()))
                except Exception:
                    continue
                if not math.isfinite(radius) or radius <= 0:
                    continue

                diameter = radius * 2.0
                if min_bbox_dim > 0 and diameter > (min_bbox_dim * 0.7):
                    # Likely an exterior cylindrical body, not a hole feature.
                    continue

                depth_mm: float | None = None
                try:
                    v_first = float(surface.FirstVParameter())
                    v_last = float(surface.LastVParameter())
                    depth_candidate = abs(v_last - v_first)
                    if math.isfinite(depth_candidate) and depth_candidate > 0:
                        depth_mm = depth_candidate
                except Exception:
                    depth_mm = None

                if depth_mm is not None and depth_mm < (diameter * 0.15):
                    # Very shallow cylindrical patches are usually blends/chamfers.
                    continue

                cylindrical_candidates.append((diameter, depth_mm))
        except Exception:
            return {}

        if not cylindrical_candidates:
            return {"hole_count": 0, "threaded_holes_count": 0}

        diameters = [diameter for diameter, _ in cylindrical_candidates if diameter > 0]
        depths = [depth for _, depth in cylindrical_candidates if isinstance(depth, (int, float)) and depth > 0]

        threaded_holes_count = 0
        for diameter, depth in cylindrical_candidates:
            if not isinstance(depth, (int, float)) or depth <= 0:
                continue
            ratio = depth / max(diameter, 1e-9)
            if 2.5 <= diameter <= 20.0 and 0.8 <= ratio <= 4.0:
                threaded_holes_count += 1

        payload: dict[str, Any] = {
            "hole_count": len(cylindrical_candidates),
            "threaded_holes_count": threaded_holes_count,
        }
        if diameters:
            payload["min_hole_diameter_mm"] = min(diameters)
        if depths:
            payload["max_hole_depth_mm"] = max(depths)
        return payload

    def _estimate_min_wall_thickness_mm(self, *, occ: dict[str, Any], shape) -> float | None:
        try:
            from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
            from OCC.Core.GeomAbs import GeomAbs_Plane
        except Exception:
            return None

        plane_equations: list[tuple[tuple[float, float, float], float]] = []
        try:
            explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
            while explorer.More():
                face = occ["topods"].Face(explorer.Current())
                explorer.Next()
                try:
                    surface = BRepAdaptor_Surface(face, True)
                except Exception:
                    continue
                if surface.GetType() != GeomAbs_Plane:
                    continue
                try:
                    plane = surface.Plane()
                    normal_dir = plane.Axis().Direction()
                    point = plane.Location()
                    normal = (
                        float(normal_dir.X()),
                        float(normal_dir.Y()),
                        float(normal_dir.Z()),
                    )
                    length = math.sqrt(
                        normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2]
                    )
                    if length <= 1e-9:
                        continue
                    unit_normal = (normal[0] / length, normal[1] / length, normal[2] / length)
                    d = -(
                        unit_normal[0] * float(point.X())
                        + unit_normal[1] * float(point.Y())
                        + unit_normal[2] * float(point.Z())
                    )
                except Exception:
                    continue
                plane_equations.append((unit_normal, d))
        except Exception:
            return None

        if len(plane_equations) < 2:
            return None

        min_distance: float | None = None
        for idx, (n1, d1) in enumerate(plane_equations):
            for n2, d2 in plane_equations[idx + 1 :]:
                dot = n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]
                if dot > -0.97:
                    continue
                candidate = abs(d1 - d2)
                if not math.isfinite(candidate) or candidate <= 1e-4:
                    continue
                if min_distance is None or candidate < min_distance:
                    min_distance = candidate

        return min_distance

    def _geometry_section_defaults(self) -> dict[str, dict[str, Any]]:
        return {
            "bbox_x_mm": _metric(label="Bounding box X", unit="mm"),
            "bbox_y_mm": _metric(label="Bounding box Y", unit="mm"),
            "bbox_z_mm": _metric(label="Bounding box Z", unit="mm"),
            "bbox_volume_mm3": _metric(label="Bounding box volume", unit="mm3"),
            "bbox_diagonal_mm": _metric(label="Bounding box diagonal", unit="mm"),
            "part_volume_mm3": _metric(label="Part volume", unit="mm3"),
            "surface_area_mm2": _metric(label="Surface area", unit="mm2"),
            "body_count": _metric(label="Solid body count"),
            "triangle_count": _metric(label="Triangle count"),
        }

    def _manufacturing_section_defaults(self) -> dict[str, dict[str, Any]]:
        return {
            "corner_count": _metric(label="Detected corner count"),
            "critical_corner_count": _metric(label="Critical corners"),
            "warning_corner_count": _metric(label="Warning corners"),
            "caution_corner_count": _metric(label="Caution corners"),
            "ok_corner_count": _metric(label="OK corners"),
            "min_internal_radius_mm": _metric(label="Minimum internal radius", unit="mm"),
            "count_radius_below_1_5_mm": _metric(label="Count radius < 1.5 mm"),
            "count_radius_below_3_0_mm": _metric(label="Count radius < 3.0 mm"),
            "max_pocket_depth_mm": _metric(label="Maximum pocket depth", unit="mm"),
            "max_depth_to_radius_ratio": _metric(label="Maximum depth/radius ratio"),
            "long_reach_tool_risk_count": _metric(label="Long-reach risk count"),
            "pockets_present": _metric(label="Pockets/slotted corners detected"),
            "feature_complexity_score": _metric(label="Feature complexity score"),
            "min_wall_thickness_mm": _metric(label="Minimum wall thickness", unit="mm"),
            "hole_count": _metric(label="Hole count"),
            "threaded_holes_count": _metric(label="Threaded hole count"),
            "min_hole_diameter_mm": _metric(label="Minimum hole diameter", unit="mm"),
            "max_hole_depth_mm": _metric(label="Maximum hole depth", unit="mm"),
            "unique_internal_radius_count": _metric(label="Unique internal radius count"),
            "radius_variation_ratio": _metric(label="Internal radius variation ratio"),
        }

    def _declared_context_defaults(self, component_profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
        material = str(component_profile.get("material") or "").strip()
        process = str(component_profile.get("manufacturingProcess") or "").strip()
        industry = str(component_profile.get("industry") or "").strip()
        return {
            "material_spec": _metric(
                label="Material",
                value=material or None,
                state="declared" if material else "unknown",
                confidence=1.0 if material else 0.0,
                source="component_profile.material" if material else "",
            ),
            "manufacturing_process": _metric(
                label="Manufacturing process",
                value=process or None,
                state="declared" if process else "unknown",
                confidence=1.0 if process else 0.0,
                source="component_profile.manufacturingProcess" if process else "",
            ),
            "industry": _metric(
                label="Industry",
                value=industry or None,
                state="declared" if industry else "unknown",
                confidence=1.0 if industry else 0.0,
                source="component_profile.industry" if industry else "",
            ),
        }

    def _process_input_defaults(self) -> dict[str, dict[str, Any]]:
        defaults: dict[str, dict[str, Any]] = {}
        for key in self.process_input_keys:
            defaults[key] = _metric(
                label=key.replace("_", " "),
                value=None,
                state="unknown",
                confidence=0.0,
                source="",
                reason="not extracted yet",
            )
        defaults.setdefault(
            "manufacturing_process",
            _metric(
                label="manufacturing process",
                value=None,
                state="unknown",
                confidence=0.0,
                source="",
            ),
        )
        return defaults

    def _rule_input_defaults(self) -> dict[str, dict[str, Any]]:
        defaults: dict[str, dict[str, Any]] = {}
        for key in sorted(self.rule_input_frequency.keys()):
            defaults[key] = _metric(
                label=key.replace("_", " "),
                value=None,
                state="unknown",
                confidence=0.0,
                source="",
                reason="not extracted yet",
            )
        return defaults

    def _process_context(self, process_label: str) -> dict[str, bool]:
        normalized = process_label.lower().strip()
        return {
            "has_process": bool(normalized),
            "is_sheet": "sheet" in normalized,
            "is_weld": "weld" in normalized,
            "is_turning": any(token in normalized for token in ("turn", "lathe")),
        }

    def _apply_not_applicable_rules(
        self,
        *,
        sections: dict[str, dict[str, dict[str, Any]]],
        process_context: dict[str, bool],
        assembly_component_count: int,
    ) -> None:
        process_inputs = sections.get("process_inputs", {})
        rule_inputs = sections.get("rule_inputs", {})
        manufacturing_signals = sections.get("manufacturing_signals", {})

        has_process = bool(process_context.get("has_process"))
        is_sheet = bool(process_context.get("is_sheet"))
        is_weld = bool(process_context.get("is_weld"))
        is_turning = bool(process_context.get("is_turning"))
        is_assembly = assembly_component_count > 1

        if has_process and not is_sheet:
            for key in ("bends_present", "constant_thickness", "sheet_thickness"):
                self._mark_not_applicable(
                    process_inputs,
                    key,
                    "Not applicable for non-sheet manufacturing process.",
                )
            for key in ("bend_features", "flange_length"):
                self._mark_not_applicable(
                    rule_inputs,
                    key,
                    "Not applicable for non-sheet manufacturing process.",
                )

        if has_process and not is_turning:
            for key in ("turned_faces_present", "rotational_symmetry"):
                self._mark_not_applicable(
                    process_inputs,
                    key,
                    "Not applicable for non-turning manufacturing process.",
                )

        if has_process and not is_weld:
            for key in ("weld_symbols_detected",):
                self._mark_not_applicable(
                    process_inputs,
                    key,
                    "Not applicable when weld process is not selected.",
                )
            self._mark_not_applicable(
                rule_inputs,
                "weld_data",
                "Not applicable when weld process is not selected.",
            )

        if not is_assembly:
            self._mark_not_applicable(
                process_inputs,
                "multi_part_joined",
                "Not applicable for single-part context.",
            )
            self._mark_not_applicable(
                rule_inputs,
                "bom_items",
                "Not applicable for single-part context.",
            )

        pockets_metric = manufacturing_signals.get("pockets_present")
        if (
            isinstance(pockets_metric, dict)
            and _state_known(pockets_metric.get("state"))
            and not bool(pockets_metric.get("value"))
        ):
            for key in ("pocket_corner_radius", "pocket_depth", "radii_set"):
                self._mark_not_applicable(
                    rule_inputs,
                    key,
                    "No pocket/slotted-corner features detected.",
                )

        hole_count_metric = manufacturing_signals.get("hole_count")
        if (
            isinstance(hole_count_metric, dict)
            and _state_known(hole_count_metric.get("state"))
            and isinstance(hole_count_metric.get("value"), (int, float))
            and float(hole_count_metric.get("value")) <= 0
        ):
            for key in ("hole_features", "hole_diameter", "hole_depth", "thread_callouts"):
                self._mark_not_applicable(
                    rule_inputs,
                    key,
                    "No hole features detected in solid geometry.",
                )

    def _apply_standards_context_hints(
        self,
        *,
        sections: dict[str, dict[str, dict[str, Any]]],
        component_profile: dict[str, Any],
        component_display_name: str,
        process_context: dict[str, bool],
    ) -> None:
        declared_context = sections.get("declared_context", {})
        manufacturing = sections.get("manufacturing_signals", {})
        material_label = str(component_profile.get("material") or "").strip()
        process_label = str(component_profile.get("manufacturingProcess") or "").strip()
        industry_label = str(component_profile.get("industry") or "").strip()
        display_name = component_display_name.strip()

        normalized_material = material_label.lower()
        normalized_process = process_label.lower()
        normalized_industry = industry_label.lower()
        normalized_name = display_name.lower()

        if (
            "food" in normalized_industry
            or "hygien" in normalized_industry
            or "portion" in normalized_industry
            or "combicut" in normalized_name
        ):
            declared_context["pilot_food_overlay_candidate"] = _metric(
                label="Pilot food/portioning overlay candidate",
                value="pilot_prototype",
                unit=None,
                state="inferred",
                confidence=0.8,
                source="component_profile.industry",
            )

        if any(token in normalized_material for token in ("1.4404", "316l", "stainless")):
            declared_context["en10088_3_material_candidate"] = _metric(
                label="EN 10088-3 material reference candidate",
                value=True,
                unit=None,
                state="inferred",
                confidence=0.75,
                source="component_profile.material",
            )

        if any(token in normalized_material for token in ("aluminum", "aluminium")):
            declared_context["iso7599_coating_candidate"] = _metric(
                label="ISO 7599 anodizing reference candidate",
                value=True,
                unit=None,
                state="inferred",
                confidence=0.7,
                source="component_profile.material",
            )

        if any(token in normalized_material for token in ("pa12", "polyamide 12")) or bool(
            process_context.get("has_process") and "additive" in normalized_process
        ):
            declared_context["vdi_3405_additive_candidate"] = _metric(
                label="VDI 3405 additive prototype candidate",
                value=True,
                unit=None,
                state="inferred",
                confidence=0.75,
                source="component_profile",
            )

        if "robot" in normalized_industry or "robot" in normalized_name:
            declared_context["iso9409_1_robot_interface_candidate"] = _metric(
                label="ISO 9409-1 robot interface candidate",
                value=True,
                unit=None,
                state="inferred",
                confidence=0.65,
                source="component_profile.industry",
            )

        threaded_holes = _safe_optional_int(
            manufacturing.get("threaded_holes_count", {}).get("value")
        )
        if threaded_holes is not None and threaded_holes > 0:
            declared_context["iso228_1_thread_standard_candidate"] = _metric(
                label="ISO 228-1 thread declaration candidate",
                value=True,
                unit=None,
                state="inferred",
                confidence=0.7,
                source="manufacturing_signals.threaded_holes_count",
            )

    def _mark_not_applicable(
        self,
        metrics: dict[str, dict[str, Any]],
        key: str,
        reason: str,
    ) -> None:
        metric = metrics.get(key)
        if not isinstance(metric, dict):
            return
        state = metric.get("state")
        if _state_known(state) or state == "failed":
            return
        metric["value"] = None
        metric["state"] = NOT_APPLICABLE_STATE
        metric["confidence"] = 1.0
        metric["source"] = metric.get("source") or "part_facts.applicability_rules"
        metric["reason"] = reason

    def _coverage_snapshot(
        self,
        *,
        sections: dict[str, dict[str, dict[str, Any]]],
        include_sections: list[str],
    ) -> dict[str, Any]:
        known_count = 0
        total_count = 0
        not_applicable_count = 0
        for section_name in include_sections:
            metrics = sections.get(section_name, {})
            if not isinstance(metrics, dict):
                continue
            for item in metrics.values():
                total_count += 1
                state = item.get("state")
                if _state_not_applicable(state):
                    not_applicable_count += 1
                    continue
                if _state_known(state):
                    known_count += 1
        applicable_count = max(0, total_count - not_applicable_count)
        percent = round((known_count / applicable_count) * 100.0, 1) if applicable_count else 0.0
        return {
            "known_metrics": known_count,
            "applicable_metrics": applicable_count,
            "not_applicable_metrics": not_applicable_count,
            "total_metrics": total_count,
            "percent": percent,
        }

    def _overall_confidence(self, *, coverage_percent: float, error_count: int) -> str:
        adjusted = max(0.0, coverage_percent - (error_count * 8.0))
        if adjusted >= 70.0:
            return "high"
        if adjusted >= 40.0:
            return "medium"
        return "low"

    def _missing_inputs(self, sections: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
        missing: list[str] = []

        process_inputs = sections.get("process_inputs", {})
        for key in self.process_input_keys:
            metric = process_inputs.get(key)
            if (
                not isinstance(metric, dict)
                or _state_known(metric.get("state"))
                or _state_not_applicable(metric.get("state"))
            ):
                continue
            missing.append(key)

        rule_inputs = sections.get("rule_inputs", {})
        for key in self.high_priority_rule_inputs:
            metric = rule_inputs.get(key)
            if (
                not isinstance(metric, dict)
                or _state_known(metric.get("state"))
                or _state_not_applicable(metric.get("state"))
            ):
                continue
            if key not in missing:
                missing.append(key)

        return missing[:24]

    def _facts_path(self, *, model_id: str, component_node_name: str) -> Path:
        safe_component = re.sub(r"[^a-zA-Z0-9_.-]+", "_", component_node_name.strip()).strip("._")
        if not safe_component:
            safe_component = "component"
        return self.root / model_id / "part_facts" / f"{safe_component}.json"

    def _collect_rule_input_frequency(self, bundle: Any) -> dict[str, int]:
        frequency: dict[str, int] = {}
        rule_library = getattr(bundle, "rule_library", {}) if bundle is not None else {}
        rules = rule_library.get("rules", []) if isinstance(rule_library, dict) else []
        if not isinstance(rules, list):
            return frequency
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            inputs = rule.get("inputs_required")
            if not isinstance(inputs, list):
                continue
            for key in inputs:
                if not isinstance(key, str):
                    continue
                name = key.strip()
                if not name:
                    continue
                frequency[name] = frequency.get(name, 0) + 1
        return frequency

    def _collect_process_input_keys(self, bundle: Any) -> list[str]:
        process_classifier = getattr(bundle, "process_classifier", {}) if bundle is not None else {}
        if not isinstance(process_classifier, dict):
            return []
        input_facts = process_classifier.get("input_facts")
        if not isinstance(input_facts, list):
            return []
        keys: list[str] = []
        seen: set[str] = set()
        for item in input_facts:
            if not isinstance(item, str):
                continue
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _now_iso(self) -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
