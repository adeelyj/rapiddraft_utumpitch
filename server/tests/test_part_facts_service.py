from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.cnc_geometry_occ import CncGeometryError  # noqa: E402
from server.part_facts import PartFactsService  # noqa: E402


class _FailingGeometryAnalyzer:
    def _import_occ(self):
        raise CncGeometryError("pythonOCC unavailable in test")


def test_part_facts_service_persists_payload_when_geometry_extraction_fails(tmp_path: Path):
    bundle = SimpleNamespace(
        rule_library={
            "rules": [
                {"inputs_required": ["geometry_features", "material_spec"]},
                {"inputs_required": ["manual_context", "geometry_features"]},
            ]
        },
        process_classifier={
            "input_facts": ["pockets_present", "bbox_dimensions", "feature_complexity_score"]
        },
    )
    service = PartFactsService(
        root=tmp_path,
        bundle=bundle,
        geometry_analyzer=_FailingGeometryAnalyzer(),
    )

    step_path = tmp_path / "source.step"
    step_path.write_text("dummy", encoding="utf-8")

    payload = service.get_or_create(
        model_id="model_x",
        step_path=step_path,
        component_node_name="component_1",
        component_display_name="Part 1",
        component_profile={"material": "Aluminum", "manufacturingProcess": "", "industry": ""},
        triangle_count=42,
        assembly_component_count=2,
        force_refresh=True,
    )

    assert payload["schema_version"] == "1.2.0"
    core = payload["coverage"]["core_extraction_coverage"]
    readiness = payload["coverage"]["full_rule_readiness_coverage"]
    assert core["total_metrics"] == core["applicable_metrics"] + core["not_applicable_metrics"]
    assert readiness["total_metrics"] == readiness["applicable_metrics"] + readiness["not_applicable_metrics"]
    assert core["applicable_metrics"] >= core["known_metrics"]
    assert readiness["applicable_metrics"] >= readiness["known_metrics"]
    assert payload["errors"], "Expected geometry extraction error to be surfaced."
    assert payload["sections"]["declared_context"]["material_spec"]["state"] == "declared"
    assert payload["sections"]["rule_inputs"]["material_spec"]["state"] == "declared"
    assert payload["sections"]["rule_inputs"]["assembly_model"]["state"] == "inferred"

    facts_path = tmp_path / "model_x" / "part_facts" / "component_1.json"
    assert facts_path.exists()


def test_part_facts_marks_not_applicable_for_irrelevant_process_inputs(tmp_path: Path):
    bundle = SimpleNamespace(
        rule_library={
            "rules": [
                {
                    "inputs_required": [
                        "bend_features",
                        "flange_length",
                        "weld_data",
                        "bom_items",
                    ]
                }
            ]
        },
        process_classifier={
            "input_facts": [
                "bends_present",
                "constant_thickness",
                "sheet_thickness",
                "turned_faces_present",
                "rotational_symmetry",
                "weld_symbols_detected",
                "multi_part_joined",
            ]
        },
    )
    service = PartFactsService(
        root=tmp_path,
        bundle=bundle,
        geometry_analyzer=_FailingGeometryAnalyzer(),
    )

    step_path = tmp_path / "source.step"
    step_path.write_text("dummy", encoding="utf-8")

    payload = service.get_or_create(
        model_id="model_x",
        step_path=step_path,
        component_node_name="component_1",
        component_display_name="Part 1",
        component_profile={"material": "Aluminum", "manufacturingProcess": "CNC Milling", "industry": ""},
        triangle_count=42,
        assembly_component_count=1,
        force_refresh=True,
    )

    process_inputs = payload["sections"]["process_inputs"]
    assert process_inputs["bends_present"]["state"] == "not_applicable"
    assert process_inputs["constant_thickness"]["state"] == "not_applicable"
    assert process_inputs["sheet_thickness"]["state"] == "not_applicable"
    assert process_inputs["turned_faces_present"]["state"] == "not_applicable"
    assert process_inputs["rotational_symmetry"]["state"] == "not_applicable"
    assert process_inputs["weld_symbols_detected"]["state"] == "not_applicable"
    assert process_inputs["multi_part_joined"]["state"] == "not_applicable"

    rule_inputs = payload["sections"]["rule_inputs"]
    assert rule_inputs["bend_features"]["state"] == "not_applicable"
    assert rule_inputs["flange_length"]["state"] == "not_applicable"
    assert rule_inputs["weld_data"]["state"] == "not_applicable"
    assert rule_inputs["bom_items"]["state"] == "not_applicable"

    assert "bends_present" not in payload["missing_inputs"]
    assert "bend_features" not in payload["missing_inputs"]
