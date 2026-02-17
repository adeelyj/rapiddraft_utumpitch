from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_review_v2 import generate_dfm_review_v2


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def test_review_v2_accepts_custom_template_in_execution_plan():
    bundle = _bundle()
    response = generate_dfm_review_v2(
        bundle,
        model_id="model-custom-template-review",
        component_context={
            "component_node_name": "component_1",
            "component_display_name": "Part 1",
            "profile": {
                "material": "Aluminum",
                "manufacturingProcess": "Sheet Metal",
                "industry": "Medical",
            },
        },
        execution_plans=[
            {
                "plan_id": "plan_1",
                "route_source": "selected",
                "process_id": "sheet_metal",
                "pack_ids": ["A_DRAWING", "C_SHEET", "E_ASSEMBLY", "F_OVERLAY"],
                "overlay_id": "medical",
                "role_id": "quality_engineer",
                "template_id": "custom_tpl_0001",
                "template_label": "Custom Med Pack",
                "template_sections": [
                    "header_metadata",
                    "issues_table",
                    "evidence_appendix",
                    "standards_references_auto",
                ],
                "suppressed_template_sections": [
                    "dfm_summary",
                    "compliance_matrix",
                ],
            }
        ],
        context_payload={},
    )

    route = response["routes"][0]
    assert route["template_id"] == "custom_tpl_0001"
    assert route["template_label"] == "Custom Med Pack"
    assert route["report_skeleton"]["template_sections"] == [
        "header_metadata",
        "issues_table",
        "evidence_appendix",
        "standards_references_auto",
    ]
