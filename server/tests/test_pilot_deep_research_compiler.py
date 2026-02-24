from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_pilot_deep_research import compile_deep_research_payload  # noqa: E402


def _sample_payload() -> dict:
    return {
        "references_patch": [
            {
                "ref_id": "REF-GPS-6",
                "title": "ISO 5459",
                "url": "https://example.com/5459",
                "type": "standard",
                "notes": "Datum systems. citeturn1",
            }
        ],
        "overlay_patch": {
            "overlay_id": "pilot_prototype",
            "label": "Pilots",
            "adds_refs": ["REF-GPS-6"],
            "rule_prefixes_to_include": ["PSTD-"],
        },
        "rule_candidates": [
            {
                "rule_id": "PILOTSTD-001",
                "pack_id": "F_OVERLAY",
                "title": "Datum system references are explicit",
                "description": "Datum system references are explicit",
                "applies_to": ["compliance_overlay"],
                "analysis_mode": "drawing_spec",
                "inputs_required": [
                    "drawing.gdt.undefined_datum_reference_count",
                    "drawing.text_all",
                ],
                "check_logic": {
                    "type": "deterministic",
                    "predicate": {
                        "left": "drawing.gdt.undefined_datum_reference_count",
                        "op": "==",
                        "right": 0,
                    },
                    "evaluator_hint": "Parse datum frame references from drawing text.",
                },
                "severity": "major",
                "fix_template": "Add explicit datum references.",
                "refs": ["REF-GPS-6"],
                "standard_clause": None,
                "finding_type_default": "evidence_gap",
                "pilot_sets": ["SET_C_GPS_DRAWING"],
                "needs_new_metric": False,
                "new_metric_definition": None,
                "evidence_quality": "official_abstract",
                "needs_manual_confirmation": True,
            }
        ],
    }


def test_compiler_maps_rule_id_and_inputs_to_runtime_contract():
    result = compile_deep_research_payload(_sample_payload())
    assert result.compiled_rules_executable
    compiled_rule = result.compiled_rules_executable[0]
    assert compiled_rule["rule_id"] == "PSTD-001"
    assert "datum_scheme" in compiled_rule["inputs_required"]
    assert "drawing_notes" in compiled_rule["inputs_required"]
    assert compiled_rule["thresholds"]["source_rule_id"] == "PILOTSTD-001"


def test_compiler_sanitizes_citation_tokens_in_notes():
    result = compile_deep_research_payload(_sample_payload())
    notes = result.references_patch[0]["notes"]
    assert "cite" not in notes
    assert "" not in notes
    assert "" not in notes

