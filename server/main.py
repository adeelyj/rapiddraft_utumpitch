from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .cad_service import CADProcessingError, CADService
from .cad_service_occ import CADServiceOCC
from .model_store import ModelStore
from .review_store import ReviewStore

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
PROCESS_DIR = DATA_DIR / "processing"
WEB_DIST_DIR = BASE_DIR.parent / "web" / "dist"

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
        cad_service.import_model(metadata.step_path, metadata.preview_path)
    except CADProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    response = {
        "modelId": metadata.model_id,
        "originalName": metadata.original_name,
        "previewUrl": f"/api/models/{metadata.model_id}/preview",
        "views": {},
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
