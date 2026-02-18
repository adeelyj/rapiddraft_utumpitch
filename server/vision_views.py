from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cad_service_occ import CADServiceOCC


class VisionViewSetError(RuntimeError):
    pass


class VisionViewSetNotFoundError(VisionViewSetError):
    pass


class VisionViewSetService:
    REQUIRED_VIEWS = ("x", "y", "z")

    def __init__(self, *, root: Path, occ_service: "CADServiceOCC") -> None:
        self.root = root
        self.occ_service = occ_service

    def create_view_set(
        self,
        *,
        model_id: str,
        step_path: Path,
        component_node_name: str | None = None,
        component_solid_index: int | None = None,
    ) -> dict[str, Any]:
        if not step_path.exists():
            raise VisionViewSetError("STEP file not found for model.")

        view_set_id = self._next_view_set_id(model_id)
        view_set_dir = self._view_set_dir(model_id, view_set_id)
        views_dir = view_set_dir / "views"
        views_dir.mkdir(parents=True, exist_ok=True)

        try:
            generated_views = self.occ_service.generate_occ_views(
                step_path,
                views_dir,
                component_node_name=component_node_name,
                component_solid_index=component_solid_index,
            )
        except Exception as exc:
            raise VisionViewSetError(
                f"Failed to generate OCC views for vision: {exc.__class__.__name__}: {exc}"
            ) from exc

        missing = [name for name in self.REQUIRED_VIEWS if name not in generated_views]
        if missing:
            raise VisionViewSetError(
                f"Vision view generation did not produce required views: {', '.join(missing)}"
            )

        file_paths = {
            name: generated_views[name]
            for name in self.REQUIRED_VIEWS
        }
        for name, path in file_paths.items():
            if not path.exists():
                raise VisionViewSetError(f"Generated vision view '{name}' missing on disk.")

        generated_at = self._now_iso()
        response_payload = {
            "view_set_id": view_set_id,
            "model_id": model_id,
            "component_node_name": component_node_name,
            "views": {
                name: f"/api/models/{model_id}/vision/view-sets/{view_set_id}/views/{name}"
                for name in self.REQUIRED_VIEWS
            },
            "generated_at": generated_at,
        }

        metadata_payload = {
            "view_set_id": view_set_id,
            "model_id": model_id,
            "component_node_name": component_node_name,
            "component_solid_index": component_solid_index,
            "generated_at": generated_at,
            "file_paths": {name: str(path) for name, path in file_paths.items()},
        }

        try:
            (view_set_dir / "view_set.json").write_text(
                json.dumps(metadata_payload, indent=2),
                encoding="utf-8",
            )
            (view_set_dir / "response.json").write_text(
                json.dumps(response_payload, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            raise VisionViewSetError(f"Failed to persist vision view set metadata: {exc}") from exc

        return response_payload

    def get_view_set_metadata(self, *, model_id: str, view_set_id: str) -> dict[str, Any]:
        metadata_path = self._view_set_dir(model_id, view_set_id) / "view_set.json"
        if not metadata_path.exists():
            raise VisionViewSetNotFoundError("Vision view set not found.")
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise VisionViewSetError(f"Failed to read vision view set metadata: {exc}") from exc
        if not isinstance(payload, dict):
            raise VisionViewSetError("Invalid vision view set metadata format.")
        return payload

    def get_view_set_paths(self, *, model_id: str, view_set_id: str) -> dict[str, Path]:
        metadata = self.get_view_set_metadata(model_id=model_id, view_set_id=view_set_id)
        raw_paths = metadata.get("file_paths")
        if not isinstance(raw_paths, dict):
            raise VisionViewSetError("Vision view set metadata missing file paths.")

        resolved: dict[str, Path] = {}
        for name in self.REQUIRED_VIEWS:
            raw_path = raw_paths.get(name)
            if not isinstance(raw_path, str) or not raw_path:
                raise VisionViewSetError(f"Vision view set missing path for '{name}'.")
            resolved_path = Path(raw_path)
            if not resolved_path.exists():
                raise VisionViewSetError(
                    f"Vision view '{name}' is missing on disk for view set '{view_set_id}'."
                )
            resolved[name] = resolved_path
        return resolved

    def get_view_image_path(self, *, model_id: str, view_set_id: str, view_name: str) -> Path:
        if view_name not in self.REQUIRED_VIEWS:
            raise VisionViewSetError("view_name must be one of x, y, z.")
        paths = self.get_view_set_paths(model_id=model_id, view_set_id=view_set_id)
        return paths[view_name]

    def _view_sets_root(self, model_id: str) -> Path:
        return self.root / model_id / "vision_view_sets"

    def _view_set_dir(self, model_id: str, view_set_id: str) -> Path:
        return self._view_sets_root(model_id) / view_set_id

    def _next_view_set_id(self, model_id: str) -> str:
        utc_now = datetime.now(timezone.utc)
        date_token = utc_now.strftime("%Y%m%d")
        prefix = f"vset_{date_token}_"

        root = self._view_sets_root(model_id)
        root.mkdir(parents=True, exist_ok=True)

        pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})$")
        latest = 0
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            match = pattern.match(entry.name)
            if not match:
                continue
            latest = max(latest, int(match.group(1)))
        return f"{prefix}{latest + 1:03d}"

    def _now_iso(self) -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
