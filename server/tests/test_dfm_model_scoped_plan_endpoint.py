from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_planning import plan_dfm_execution_with_template_catalog
from server.dfm_template_store import DfmTemplateStore


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def test_model_scoped_plan_accepts_custom_template_catalog(tmp_path: Path):
    bundle = _bundle()
    store = DfmTemplateStore(root=tmp_path / "models", bundle=bundle)
    store.create_template(
        model_id="model-plan-custom-template",
        template_name="Custom Med Pack",
        base_template_id="medical_design_review",
        overlay_id="medical",
        default_role_id="quality_engineer",
        enabled_section_keys=[
            "header_metadata",
            "issues_table",
            "evidence_appendix",
            "compliance_matrix",
        ],
    )

    payload = plan_dfm_execution_with_template_catalog(
        bundle,
        extracted_part_facts={
            "bends_present": True,
            "constant_thickness": True,
            "sheet_thickness": 2.0,
        },
        selected_process_override=None,
        selected_overlay="medical",
        selected_role="quality_engineer",
        selected_template="custom_tpl_0001",
        run_both_if_mismatch=False,
        template_catalog=store.planning_templates("model-plan-custom-template"),
    )

    assert payload["execution_plans"]
    plan = payload["execution_plans"][0]
    assert plan["template_id"] == "custom_tpl_0001"
    assert plan["template_label"] == "Custom Med Pack"
    assert plan["template_sections"] == [
        "header_metadata",
        "issues_table",
        "compliance_matrix",
        "evidence_appendix",
        "standards_references_auto",
    ]
