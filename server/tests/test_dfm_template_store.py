from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.dfm_bundle import load_dfm_bundle
from server.dfm_template_store import DfmTemplateStore, DfmTemplateStoreError


def _bundle():
    return load_dfm_bundle(bundle_dir=REPO_ROOT / "server" / "dfm", repo_root=REPO_ROOT)


def _store(tmp_path: Path) -> DfmTemplateStore:
    root = tmp_path / "models"
    root.mkdir(parents=True, exist_ok=True)
    return DfmTemplateStore(root=root, bundle=_bundle())


def test_template_store_create_list_and_get_custom_template(tmp_path: Path):
    store = _store(tmp_path)
    created = store.create_template(
        model_id="model-template-store",
        template_name="Fixture Focus",
        base_template_id="dfm_issue_list",
        overlay_id="medical",
        default_role_id="quality_engineer",
        enabled_section_keys=[
            "header_metadata",
            "issues_table",
            "evidence_appendix",
        ],
    )

    assert created["template_id"].startswith("custom_tpl_")
    assert created["source"] == "custom"
    assert created["base_template_id"] == "dfm_issue_list"
    assert created["overlay_id"] == "medical"
    assert created["default_role_id"] == "quality_engineer"
    assert "standards_references_auto" in created["template_sections"]

    listing = store.list_templates("model-template-store")
    assert listing["count"] >= 1
    assert any(
        template.get("template_id") == created["template_id"]
        for template in listing["templates"]
    )

    loaded = store.get_template("model-template-store", created["template_id"])
    assert loaded["template_id"] == created["template_id"]
    assert loaded["section_order"]
    assert "standards_references_auto" in loaded["template_sections"]


def test_template_store_rejects_duplicate_name_case_insensitive(tmp_path: Path):
    store = _store(tmp_path)
    store.create_template(
        model_id="model-dup",
        template_name="Process Review",
        base_template_id="executive_1page",
        overlay_id=None,
        default_role_id=None,
        enabled_section_keys=["header_metadata", "dfm_summary"],
    )

    with pytest.raises(DfmTemplateStoreError, match="unique"):
        store.create_template(
            model_id="model-dup",
            template_name="process review",
            base_template_id="executive_1page",
            overlay_id=None,
            default_role_id=None,
            enabled_section_keys=["header_metadata"],
        )


def test_template_store_rejects_unknown_identifiers(tmp_path: Path):
    store = _store(tmp_path)

    with pytest.raises(DfmTemplateStoreError, match="base_template_id"):
        store.create_template(
            model_id="model-invalid-base",
            template_name="Bad Base",
            base_template_id="missing_base",
            overlay_id=None,
            default_role_id=None,
            enabled_section_keys=["header_metadata"],
        )

    with pytest.raises(DfmTemplateStoreError, match="overlay_id"):
        store.create_template(
            model_id="model-invalid-overlay",
            template_name="Bad Overlay",
            base_template_id="executive_1page",
            overlay_id="unknown_overlay",
            default_role_id=None,
            enabled_section_keys=["header_metadata"],
        )

    with pytest.raises(DfmTemplateStoreError, match="default_role_id"):
        store.create_template(
            model_id="model-invalid-role",
            template_name="Bad Role",
            base_template_id="executive_1page",
            overlay_id=None,
            default_role_id="missing_role",
            enabled_section_keys=["header_metadata"],
        )


def test_template_store_enforces_standards_section_lock(tmp_path: Path):
    store = _store(tmp_path)
    created = store.create_template(
        model_id="model-standards-lock",
        template_name="No Standards Attempt",
        base_template_id="executive_1page",
        overlay_id=None,
        default_role_id=None,
        enabled_section_keys=["header_metadata", "dfm_summary"],
    )

    assert "standards_references_auto" in created["template_sections"]
