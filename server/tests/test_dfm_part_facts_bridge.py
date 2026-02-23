from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_part_facts_bridge import (  # noqa: E402
    NOT_APPLICABLE_INPUTS_KEY,
    build_extracted_facts_from_part_facts,
)


def test_bridge_maps_known_metrics_derives_fields_and_tracks_not_applicable():
    payload = {
        "sections": {
            "geometry": {
                "bbox_x_mm": {
                    "state": "measured",
                    "value": 42.5,
                },
            },
            "manufacturing_signals": {
                "hole_count": {
                    "state": "measured",
                    "value": 3,
                },
                "min_wall_thickness_mm": {
                    "state": "measured",
                    "value": 1.2,
                },
                "threaded_holes_count": {
                    "state": "unknown",
                    "value": None,
                },
            },
            "declared_context": {
                "material_spec": {
                    "state": "declared",
                    "value": "Steel",
                },
            },
            "process_inputs": {
                "bends_present": {
                    "state": "not_applicable",
                    "value": None,
                },
                "threaded_holes_count": {
                    "state": "inferred",
                    "value": 2,
                },
            },
            "rule_inputs": {
                "hole_depth": {
                    "state": "measured",
                    "value": True,
                },
                "drawing_notes": {
                    "state": "unknown",
                    "value": None,
                },
            },
        }
    }

    facts = build_extracted_facts_from_part_facts(
        part_facts_payload=payload,
        component_profile={
            "material": "Aluminum",
            "manufacturingProcess": "CNC Milling",
            "industry": "Medical Devices",
        },
        context_payload={"advanced_llm_model": "gpt-5", "manual_context": True},
    )

    assert facts["bbox_x_mm"] == 42.5
    assert facts["hole_count"] == 3
    assert facts["hole_features"] is True
    assert facts["min_wall_thickness"] == 1.2
    assert facts["wall_thickness_map"] is True

    # Profile values override lower-fidelity bridge hints.
    assert facts["material_spec"] == "Aluminum"
    assert facts["manufacturing_process"] == "CNC Milling"
    assert facts["industry"] == "Medical Devices"

    assert facts["manual_context"] is True
    assert "drawing_notes" not in facts
    assert facts[NOT_APPLICABLE_INPUTS_KEY] == ["bends_present"]


def test_bridge_ignores_unknown_and_failed_states_and_handles_empty_payload():
    payload = {
        "sections": {
            "process_inputs": {
                "pockets_present": {
                    "state": "failed",
                    "value": True,
                },
            },
            "rule_inputs": {
                "geometry_features": {
                    "state": "unknown",
                    "value": True,
                },
            },
        }
    }

    facts = build_extracted_facts_from_part_facts(
        part_facts_payload=payload,
        component_profile={},
        context_payload={},
    )

    assert "pockets_present" not in facts
    assert "geometry_features" not in facts
    assert facts[NOT_APPLICABLE_INPUTS_KEY] == []
