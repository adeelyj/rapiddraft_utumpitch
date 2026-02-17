from __future__ import annotations

import io
import os
import shutil
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .cad_service import CADProcessingError, CADService
from .cad_service_occ import CADServiceOCC
from .dfm_bundle import DfmBundleValidationError, load_dfm_bundle
from .dfm_planning import (
    DfmPlanningError,
    build_component_profile_options,
    build_dfm_config,
    plan_dfm_execution,
    plan_dfm_execution_with_template_catalog,
)
from .dfm_review_v2 import DfmReviewV2Body, DfmReviewV2Error, generate_dfm_review_v2
from .dfm_template_store import (
    DfmTemplateNotFoundError,
    DfmTemplateStore,
    DfmTemplateStoreError,
)
from .model_store import ModelStore
from .review_store import ReviewStore

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
PROCESS_DIR = DATA_DIR / "processing"
WEB_DIST_DIR = BASE_DIR.parent / "web" / "dist"
DFM_COST_ENABLED = os.getenv("DFM_COST_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "off",
    "no",
}

# Drawing template lives at the repo root under /template.
TEMPLATE_PNG = BASE_DIR.parent / "template" / "a4_iso_minimal.png"

cad_service = CADService(workspace=PROCESS_DIR)
cad_service_occ = CADServiceOCC(workspace=PROCESS_DIR / "occ")
model_store = ModelStore(root=MODELS_DIR)
review_store = ReviewStore(root=MODELS_DIR, templates_path=DATA_DIR / "review_templates.json")

app = FastAPI(title="TextCAD Drafting Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fail fast on startup if the canonical DFM bundle is missing or invalid.
try:
    DFM_BUNDLE = load_dfm_bundle(bundle_dir=BASE_DIR / "dfm", repo_root=BASE_DIR.parent)
except DfmBundleValidationError as exc:
    raise RuntimeError(f"DFM bundle validation failed during startup: {exc}") from exc

dfm_template_store = DfmTemplateStore(root=MODELS_DIR, bundle=DFM_BUNDLE)


class PinPositionBody(BaseModel):
    position: list[float]
    normal: list[float]
    cameraState: dict


class CreateTicketBody(BaseModel):
    title: str
    description: str = ""
    type: str = "comment"
    priority: str = "medium"
    author: str
    tag: str = ""
    pin: PinPositionBody


class UpdateTicketBody(BaseModel):
    title: str | None = None
    description: str | None = None
    type: str | None = None
    priority: str | None = None
    status: str | None = None
    tag: str | None = None


class CreateReplyBody(BaseModel):
    author: str
    text: str


class CreateReviewBody(BaseModel):
    template_id: str
    title: str = ""
    author: str
    pin: PinPositionBody


class UpdateReviewBody(BaseModel):
    title: str | None = None
    status: str | None = None


class UpdateChecklistItemBody(BaseModel):
    status: str | None = None
    note: str | None = None


class ComponentProfileBody(BaseModel):
    material: str
    manufacturing_process: str
    industry: str


class DfmPlanBody(BaseModel):
    extracted_part_facts: dict[str, object] = Field(default_factory=dict)
    selected_process_override: str | None = None
    selected_overlay: str | None = None
    selected_role: str
    selected_template: str
    run_both_if_mismatch: bool = True


class DfmTemplateCreateBody(BaseModel):
    template_name: str
    base_template_id: str
    overlay_id: str | None = None
    default_role_id: str | None = None
    enabled_section_keys: list[str] = Field(default_factory=list)


def _collect_option_labels(options: dict, key: str) -> set[str]:
    records = options.get(key, [])
    labels = set()
    for entry in records:
        if isinstance(entry, dict):
            label = entry.get("label")
            if isinstance(label, str) and label.strip():
                labels.add(label.strip())
    return labels


def _get_component_entry(metadata, node_name: str) -> dict | None:
    for component in metadata.components:
        if component.get("nodeName") == node_name:
            return component
    return None


def _require_model(model_id: str) -> None:
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/review-templates")
async def list_review_templates():
    return review_store.list_templates()


@app.get("/api/dfm/config")
async def get_dfm_config():
    return build_dfm_config(DFM_BUNDLE)


@app.post("/api/dfm/plan")
async def create_dfm_plan(body: DfmPlanBody):
    try:
        return plan_dfm_execution(
            DFM_BUNDLE,
            extracted_part_facts=body.extracted_part_facts,
            selected_process_override=body.selected_process_override,
            selected_overlay=body.selected_overlay,
            selected_role=body.selected_role,
            selected_template=body.selected_template,
            run_both_if_mismatch=body.run_both_if_mismatch,
        )
    except DfmPlanningError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/models/{model_id}/dfm/templates")
async def list_model_dfm_templates(model_id: str):
    _require_model(model_id)
    return dfm_template_store.list_templates(model_id)


@app.get("/api/models/{model_id}/dfm/templates/{template_id}")
async def get_model_dfm_template(model_id: str, template_id: str):
    _require_model(model_id)
    try:
        return dfm_template_store.get_template(model_id, template_id)
    except DfmTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/models/{model_id}/dfm/templates")
async def create_model_dfm_template(model_id: str, body: DfmTemplateCreateBody):
    _require_model(model_id)
    try:
        return dfm_template_store.create_template(
            model_id=model_id,
            template_name=body.template_name,
            base_template_id=body.base_template_id,
            overlay_id=body.overlay_id,
            default_role_id=body.default_role_id,
            enabled_section_keys=body.enabled_section_keys,
        )
    except DfmTemplateStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/models/{model_id}/dfm/plan")
async def create_model_dfm_plan(model_id: str, body: DfmPlanBody):
    _require_model(model_id)
    try:
        return plan_dfm_execution_with_template_catalog(
            DFM_BUNDLE,
            extracted_part_facts=body.extracted_part_facts,
            selected_process_override=body.selected_process_override,
            selected_overlay=body.selected_overlay,
            selected_role=body.selected_role,
            selected_template=body.selected_template,
            run_both_if_mismatch=body.run_both_if_mismatch,
            template_catalog=dfm_template_store.planning_templates(model_id),
        )
    except (DfmPlanningError, DfmTemplateStoreError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/models/{model_id}/component-profiles")
async def list_component_profiles(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"componentProfiles": metadata.component_profiles}


@app.put("/api/models/{model_id}/component-profiles/{node_name}")
async def upsert_component_profile(model_id: str, node_name: str, body: ComponentProfileBody):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")

    component = _get_component_entry(metadata, node_name)
    if not component:
        raise HTTPException(status_code=400, detail="Unknown component node_name")

    options = build_component_profile_options(DFM_BUNDLE)
    material_labels = _collect_option_labels(options, "materials")
    process_labels = _collect_option_labels(options, "manufacturingProcesses")
    industry_labels = _collect_option_labels(options, "industries")

    if body.material and body.material not in material_labels:
        raise HTTPException(status_code=400, detail="Invalid material")
    if body.manufacturing_process and body.manufacturing_process not in process_labels:
        raise HTTPException(status_code=400, detail="Invalid manufacturing_process")
    if body.industry and body.industry not in industry_labels:
        raise HTTPException(status_code=400, detail="Invalid industry")

    metadata.component_profiles[node_name] = {
        "material": body.material,
        "manufacturingProcess": body.manufacturing_process,
        "industry": body.industry,
    }
    model_store.update(metadata)
    return {"nodeName": node_name, "profile": metadata.component_profiles[node_name]}


@app.post("/api/models/{model_id}/dfm/review-v2")
async def create_component_dfm_review_v2(model_id: str, body: DfmReviewV2Body):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")

    component = None
    if body.component_node_name:
        component = _get_component_entry(metadata, body.component_node_name)
        if not component:
            raise HTTPException(status_code=400, detail="Unknown component_node_name")

    component_node_name = body.component_node_name
    component_display_name = (
        (component or {}).get("displayName")
        if component
        else "Global Context"
    )
    component_profile = (
        metadata.component_profiles.get(component_node_name, {})
        if component_node_name
        else {}
    )
    component_context = {
        "component_node_name": component_node_name,
        "component_display_name": component_display_name,
        "profile": component_profile,
        "triangle_count": (component or {}).get("triangleCount") if component else None,
    }

    planning_inputs = body.planning_inputs.dict() if body.planning_inputs else None
    execution_plans = (
        [plan.dict() for plan in body.execution_plans]
        if body.execution_plans
        else None
    )
    try:
        return generate_dfm_review_v2(
            DFM_BUNDLE,
            model_id=model_id,
            component_context=component_context,
            planning_inputs=planning_inputs,
            execution_plans=execution_plans,
            selected_execution_plan_id=body.selected_execution_plan_id,
            screenshot_data_url=body.screenshot_data_url,
            context_payload=body.context_payload,
            cost_enabled=DFM_COST_ENABLED,
        )
    except (DfmReviewV2Error, DfmPlanningError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/models/{model_id}/tickets")
async def list_tickets(model_id: str):
    _require_model(model_id)
    return review_store.list_tickets(model_id)


@app.post("/api/models/{model_id}/tickets")
async def create_ticket(model_id: str, body: CreateTicketBody):
    _require_model(model_id)
    return review_store.create_ticket(model_id, body.dict())


@app.get("/api/models/{model_id}/tickets/{ticket_id}")
async def get_ticket(model_id: str, ticket_id: str):
    _require_model(model_id)
    ticket = review_store.get_ticket(model_id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.patch("/api/models/{model_id}/tickets/{ticket_id}")
async def update_ticket(model_id: str, ticket_id: str, body: UpdateTicketBody):
    _require_model(model_id)
    fields = body.dict(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ticket = review_store.update_ticket(model_id, ticket_id, fields)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.delete("/api/models/{model_id}/tickets/{ticket_id}")
async def delete_ticket(model_id: str, ticket_id: str):
    _require_model(model_id)
    deleted = review_store.delete_ticket(model_id, ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"status": "deleted"}


@app.post("/api/models/{model_id}/tickets/{ticket_id}/replies")
async def add_ticket_reply(model_id: str, ticket_id: str, body: CreateReplyBody):
    _require_model(model_id)
    reply = review_store.add_ticket_reply(model_id, ticket_id, body.dict())
    if not reply:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return reply


@app.delete("/api/models/{model_id}/tickets/{ticket_id}/replies/{reply_id}")
async def delete_ticket_reply(model_id: str, ticket_id: str, reply_id: str):
    _require_model(model_id)
    deleted = review_store.delete_ticket_reply(model_id, ticket_id, reply_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reply not found")
    return {"status": "deleted"}


@app.get("/api/models/{model_id}/design-reviews")
async def list_design_reviews(model_id: str):
    _require_model(model_id)
    return review_store.list_reviews(model_id)


@app.post("/api/models/{model_id}/design-reviews")
async def create_design_review(model_id: str, body: CreateReviewBody):
    _require_model(model_id)
    review = review_store.create_review(model_id, body.dict())
    if not review:
        raise HTTPException(status_code=400, detail="Invalid template_id")
    return review


@app.get("/api/models/{model_id}/design-reviews/{review_id}")
async def get_design_review(model_id: str, review_id: str):
    _require_model(model_id)
    review = review_store.get_review(model_id, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.patch("/api/models/{model_id}/design-reviews/{review_id}")
async def update_design_review(model_id: str, review_id: str, body: UpdateReviewBody):
    _require_model(model_id)
    fields = body.dict(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    review = review_store.update_review(model_id, review_id, fields)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.patch("/api/models/{model_id}/design-reviews/{review_id}/checklist/{item_id}")
async def update_review_checklist_item(model_id: str, review_id: str, item_id: str, body: UpdateChecklistItemBody):
    _require_model(model_id)
    fields = body.dict(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    item = review_store.update_checklist_item(model_id, review_id, item_id, fields)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return item


@app.delete("/api/models/{model_id}/design-reviews/{review_id}")
async def delete_design_review(model_id: str, review_id: str):
    _require_model(model_id)
    deleted = review_store.delete_review(model_id, review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"status": "deleted"}


@app.post("/api/models/{model_id}/design-reviews/{review_id}/replies")
async def add_design_review_reply(model_id: str, review_id: str, body: CreateReplyBody):
    _require_model(model_id)
    reply = review_store.add_review_reply(model_id, review_id, body.dict())
    if not reply:
        raise HTTPException(status_code=404, detail="Review not found")
    return reply


@app.get("/api/template/drawing")
async def get_drawing_template():
    if not TEMPLATE_PNG.exists():
        raise HTTPException(status_code=404, detail="Drawing template not found on server")
    return FileResponse(TEMPLATE_PNG, media_type="image/png")


@app.post("/api/models")
async def upload_model(file: UploadFile = File(...)):
    metadata = model_store.create(file.filename)
    with metadata.step_path.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)
    try:
        import_result = cad_service.import_model(metadata.step_path, metadata.preview_path)
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.components = [
        {
            "id": component.id,
            "nodeName": component.node_name,
            "displayName": component.display_name,
            "triangleCount": component.triangle_count,
        }
        for component in import_result.components
    ]
    model_store.update(metadata)

    response = {
        "modelId": metadata.model_id,
        "originalName": metadata.original_name,
        "previewUrl": f"/api/models/{metadata.model_id}/preview",
        "views": {},
        "components": metadata.components,
        "componentProfiles": metadata.component_profiles,
    }
    return response


@app.post("/api/models/{model_id}/views")
async def generate_views(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        view_files, meta_files = cad_service.generate_views(metadata.step_path, metadata.step_path.parent / "views")
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.views = view_files
    metadata.view_metadata = meta_files
    model_store.update(metadata)

    views_response = {name: f"/api/models/{model_id}/views/{name}" for name in view_files.keys()}
    meta_response = {name: f"/api/models/{model_id}/views/{name}/metadata" for name in meta_files.keys()}
    return {"modelId": model_id, "views": views_response, "metadata": meta_response}


@app.post("/api/models/{model_id}/shape2d")
async def generate_shape2d_views(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        view_files, meta_files = cad_service.generate_shape2d_views(metadata.step_path, metadata.step_path.parent / "shape2d")
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.shape_views = view_files
    metadata.shape_view_metadata = meta_files
    model_store.update(metadata)

    views_response = {name: f"/api/models/{model_id}/shape2d/{name}" for name in view_files.keys()}
    meta_response = {name: f"/api/models/{model_id}/shape2d/{name}/metadata" for name in meta_files.keys()}
    return {"modelId": model_id, "views": views_response, "metadata": meta_response}


@app.get("/api/models/{model_id}/preview")
async def preview_model(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata or not metadata.preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(
        metadata.preview_path,
        media_type="model/gltf-binary",
        filename=f"{metadata.model_id}-preview.glb",
    )


@app.get("/api/models/{model_id}/views/{view_name}")
async def fetch_view(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.views:
        raise HTTPException(status_code=404, detail="View not found")

    file_path = metadata.views[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="View image missing on disk")
    return FileResponse(file_path, media_type="image/png")

@app.get("/api/models/{model_id}/views/{view_name}/metadata")
async def fetch_view_metadata(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.view_metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    file_path = metadata.view_metadata[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Metadata file missing on disk")
    return FileResponse(file_path, media_type="application/json")


@app.get("/api/models/{model_id}/shape2d/{view_name}")
async def fetch_shape2d_view(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.shape_views:
        raise HTTPException(status_code=404, detail="View not found")

    file_path = metadata.shape_views[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Shape2D view missing on disk")
    return FileResponse(file_path, media_type="image/png")

@app.get("/api/models/{model_id}/shape2d/{view_name}/metadata")
async def fetch_shape2d_view_metadata(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.shape_view_metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    file_path = metadata.shape_view_metadata[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Shape2D metadata missing on disk")
    return FileResponse(file_path, media_type="application/json")


@app.post("/api/models/{model_id}/occ_views")
async def generate_occ_views(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        view_files = cad_service_occ.generate_occ_views(metadata.step_path, metadata.step_path.parent / "occ_views")
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.occ_views = view_files
    model_store.update(metadata)

    views_response = {name: f"/api/models/{model_id}/occ_views/{name}" for name in view_files.keys()}
    return {"modelId": model_id, "views": views_response}


@app.get("/api/models/{model_id}/occ_views/{view_name}")
async def fetch_occ_view(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.occ_views:
        raise HTTPException(status_code=404, detail="View not found")

    file_path = metadata.occ_views[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="OCC view missing on disk")
    return FileResponse(file_path, media_type="image/png")


@app.post("/api/models/{model_id}/mid_views")
async def generate_mid_views(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        view_files = cad_service_occ.generate_mid_views(metadata.step_path, metadata.step_path.parent / "mid_views")
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.mid_views = view_files
    model_store.update(metadata)

    views_response = {name: f"/api/models/{model_id}/mid_views/{name}" for name in view_files.keys()}
    return {"modelId": model_id, "views": views_response}


@app.get("/api/models/{model_id}/mid_views/{view_name}")
async def fetch_mid_view(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.mid_views:
        raise HTTPException(status_code=404, detail="View not found")

    file_path = metadata.mid_views[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Mid view missing on disk")
    return FileResponse(file_path, media_type="image/png")


@app.post("/api/models/{model_id}/isometric_shape2d")
async def generate_isometric_shape2d(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        view_files, meta_files = cad_service.generate_isometric_shape2d_view(metadata.step_path, metadata.step_path.parent / "isometric_shape2d")
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.isometric_shape2d = view_files
    metadata.isometric_shape2d_metadata = meta_files
    model_store.update(metadata)

    views_response = {name: f"/api/models/{model_id}/isometric_shape2d/{name}" for name in view_files.keys()}
    meta_response = {name: f"/api/models/{model_id}/isometric_shape2d/{name}/metadata" for name in meta_files.keys()}
    return {"modelId": model_id, "views": views_response, "metadata": meta_response}


@app.get("/api/models/{model_id}/isometric_shape2d/{view_name}")
async def fetch_isometric_shape2d(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.isometric_shape2d:
        raise HTTPException(status_code=404, detail="View not found")

    file_path = metadata.isometric_shape2d[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Isometric Shape2D view missing on disk")
    return FileResponse(file_path, media_type="image/png")

@app.get("/api/models/{model_id}/isometric_shape2d/{view_name}/metadata")
async def fetch_isometric_shape2d_metadata(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.isometric_shape2d_metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    file_path = metadata.isometric_shape2d_metadata[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Isometric Shape2D metadata missing on disk")
    return FileResponse(file_path, media_type="application/json")


@app.post("/api/models/{model_id}/isometric_matplotlib")
async def generate_isometric_matplotlib(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        view_files, meta_files = cad_service.generate_isometric_matplotlib_view(metadata.step_path, metadata.step_path.parent / "isometric_matplotlib")
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    metadata.isometric_matplotlib = view_files
    metadata.isometric_matplotlib_metadata = meta_files
    model_store.update(metadata)

    views_response = {name: f"/api/models/{model_id}/isometric_matplotlib/{name}" for name in view_files.keys()}
    meta_response = {name: f"/api/models/{model_id}/isometric_matplotlib/{name}/metadata" for name in meta_files.keys()}
    return {"modelId": model_id, "views": views_response, "metadata": meta_response}


@app.get("/api/models/{model_id}/isometric_matplotlib/{view_name}")
async def fetch_isometric_matplotlib(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.isometric_matplotlib:
        raise HTTPException(status_code=404, detail="View not found")

    file_path = metadata.isometric_matplotlib[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Isometric matplotlib view missing on disk")
    return FileResponse(file_path, media_type="image/png")

@app.get("/api/models/{model_id}/isometric_matplotlib/{view_name}/metadata")
async def fetch_isometric_matplotlib_metadata(model_id: str, view_name: str):
    metadata = model_store.get(model_id)
    if not metadata or view_name not in metadata.isometric_matplotlib_metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    file_path = metadata.isometric_matplotlib_metadata[view_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Isometric matplotlib metadata missing on disk")
    return FileResponse(file_path, media_type="application/json")


@app.post("/api/models/{model_id}/export")
async def export_views(model_id: str):
    metadata = model_store.get(model_id)
    if not metadata or not metadata.views:
        raise HTTPException(status_code=404, detail="Views not generated yet")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in metadata.views.items():
            if not path.exists():
                continue
            zf.write(path, arcname=f"{name}.png")
    memory_file.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="views-{model_id}.zip"'}

    return StreamingResponse(memory_file, media_type="application/zip", headers=headers)


if WEB_DIST_DIR.exists():
    assets_dir = WEB_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(WEB_DIST_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str):
        file_path = WEB_DIST_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(WEB_DIST_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
