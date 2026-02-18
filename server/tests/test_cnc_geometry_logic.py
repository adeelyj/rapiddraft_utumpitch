from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.cnc_geometry_occ import (  # noqa: E402
    CncGeometryAnalyzer,
    classify_radius_status,
    classify_radius_status_with_criteria,
    compute_cost_impact,
    compute_machinability_score,
    parse_criteria,
)


def test_radius_status_threshold_boundaries():
    assert classify_radius_status(0.0) == "CRITICAL"
    assert classify_radius_status(0.0001) == "CRITICAL"
    assert classify_radius_status(0.0001001) == "WARNING"
    assert classify_radius_status(1.5) == "CAUTION"
    assert classify_radius_status(2.2) == "CAUTION"
    assert classify_radius_status(3.0) == "OK"


def test_custom_thresholds_and_enabled_statuses_are_applied():
    criteria = parse_criteria(
        {
            "thresholds": {
                "critical_enabled": False,
                "critical_max_mm": 0.2,
                "warning_enabled": True,
                "warning_max_mm": 2.0,
                "caution_enabled": False,
                "caution_max_mm": 4.0,
                "ok_enabled": True,
                "ok_min_mm": 4.0,
            },
            "aggravating_factor_ratio_threshold": 7.5,
        }
    )

    # critical interval disabled
    assert classify_radius_status_with_criteria(0.1, criteria=criteria) is None
    # warning still enabled with custom max
    assert classify_radius_status_with_criteria(1.4, criteria=criteria) == "WARNING"
    # caution interval disabled
    assert classify_radius_status_with_criteria(2.5, criteria=criteria) is None
    # ok uses custom min
    assert classify_radius_status_with_criteria(4.0, criteria=criteria) == "OK"
    assert criteria.aggravating_factor_ratio_threshold == pytest.approx(7.5)


def test_score_and_cost_impact_mapping():
    assert compute_machinability_score(critical_count=0, warning_count=0, caution_count=0) == 100
    assert compute_machinability_score(critical_count=1, warning_count=0, caution_count=0) == 75
    assert compute_machinability_score(critical_count=2, warning_count=3, caution_count=4) == 0

    assert compute_cost_impact(critical_count=0, warning_count=2, caution_count=0) == "LOW"
    assert compute_cost_impact(critical_count=0, warning_count=2, caution_count=1) == "MODERATE"
    assert compute_cost_impact(critical_count=1, warning_count=3, caution_count=0) == "HIGH"


def test_measure_radius_for_line_circle_and_non_circular_curve():
    class FakeEdge:
        def __init__(self, curve_type: str, radius: float = 0.0, curvature: float = 0.5):
            self.curve_type = curve_type
            self.radius = radius
            self.curvature = curvature

    class FakeCircle:
        def __init__(self, radius: float):
            self._radius = radius

        def Radius(self) -> float:
            return self._radius

    class FakeAdaptor:
        def __init__(self, edge: FakeEdge):
            self.edge = edge

        def GetType(self):
            return self.edge.curve_type

        def Circle(self):
            return FakeCircle(self.edge.radius)

    class FakeBRepTool:
        @staticmethod
        def Curve(edge: FakeEdge):
            return edge, 0.0, 1.0

    class FakeCLProps:
        def __init__(self, curve_handle: FakeEdge, _mid: float, _order: int, _tol: float):
            self.curve_handle = curve_handle

        def Curvature(self):
            return self.curve_handle.curvature

    occ = {
        "BRepAdaptor_Curve": FakeAdaptor,
        "GeomAbs_Line": "line",
        "GeomAbs_Circle": "circle",
        "BRep_Tool": FakeBRepTool,
        "GeomLProp_CLProps": FakeCLProps,
    }

    analyzer = CncGeometryAnalyzer()
    assert analyzer._measure_radius_mm(occ, FakeEdge("line")) == 0.0
    assert analyzer._measure_radius_mm(occ, FakeEdge("circle", radius=1.75)) == pytest.approx(1.75)
    assert analyzer._measure_radius_mm(occ, FakeEdge("spline", curvature=0.25)) == pytest.approx(4.0)


def test_component_mapping_falls_back_to_full_shape_when_index_missing():
    class FakeShape:
        def __init__(self, solids: list[str]):
            self.solids = solids

    class FakeTopods:
        @staticmethod
        def Solid(item: str):
            return item

    class FakeExplorer:
        def __init__(self, shape: FakeShape, _target):
            self._items = shape.solids
            self._index = 0

        def More(self):
            return self._index < len(self._items)

        def Current(self):
            return self._items[self._index]

        def Next(self):
            self._index += 1

    occ = {
        "TopExp_Explorer": FakeExplorer,
        "TopAbs_SOLID": "solid",
        "topods": FakeTopods,
    }

    analyzer = CncGeometryAnalyzer()
    shape = FakeShape(["solid_1", "solid_2"])

    resolved_shape, fallback = analyzer._resolve_analysis_shape(occ, shape, "component_2")
    assert resolved_shape == "solid_2"
    assert fallback is False

    resolved_shape, fallback = analyzer._resolve_analysis_shape(occ, shape, "component_7")
    assert resolved_shape is shape
    assert fallback is True
