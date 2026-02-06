from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4


@dataclass
class ModelMetadata:
    model_id: str
    original_name: str
    step_path: Path
    preview_path: Path
    views: Dict[str, Path] = field(default_factory=dict)
    view_metadata: Dict[str, Path] = field(default_factory=dict)
    shape_views: Dict[str, Path] = field(default_factory=dict)
    shape_view_metadata: Dict[str, Path] = field(default_factory=dict)
    occ_views: Dict[str, Path] = field(default_factory=dict)
    mid_views: Dict[str, Path] = field(default_factory=dict)
    isometric_shape2d: Dict[str, Path] = field(default_factory=dict)
    isometric_shape2d_metadata: Dict[str, Path] = field(default_factory=dict)
    isometric_matplotlib: Dict[str, Path] = field(default_factory=dict)
    isometric_matplotlib_metadata: Dict[str, Path] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "modelId": self.model_id,
            "originalName": self.original_name,
            "stepPath": str(self.step_path),
            "previewPath": str(self.preview_path),
            "views": {name: str(path) for name, path in self.views.items()},
            "viewMetadata": {name: str(path) for name, path in self.view_metadata.items()},
            "shapeViews": {name: str(path) for name, path in self.shape_views.items()},
            "shapeViewMetadata": {name: str(path) for name, path in self.shape_view_metadata.items()},
            "occViews": {name: str(path) for name, path in self.occ_views.items()},
            "midViews": {name: str(path) for name, path in self.mid_views.items()},
            "isometricShape2d": {name: str(path) for name, path in self.isometric_shape2d.items()},
            "isometricShape2dMetadata": {name: str(path) for name, path in self.isometric_shape2d_metadata.items()},
            "isometricMatplotlib": {name: str(path) for name, path in self.isometric_matplotlib.items()},
            "isometricMatplotlibMetadata": {name: str(path) for name, path in self.isometric_matplotlib_metadata.items()},
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "ModelMetadata":
        return cls(
            model_id=payload["modelId"],
            original_name=payload["originalName"],
            step_path=Path(payload["stepPath"]),
            preview_path=Path(payload["previewPath"]),
            views={name: Path(path) for name, path in payload.get("views", {}).items()},
            view_metadata={name: Path(path) for name, path in payload.get("viewMetadata", {}).items()},
            shape_views={name: Path(path) for name, path in payload.get("shapeViews", {}).items()},
            shape_view_metadata={name: Path(path) for name, path in payload.get("shapeViewMetadata", {}).items()},
            occ_views={name: Path(path) for name, path in payload.get("occViews", {}).items()},
            mid_views={name: Path(path) for name, path in payload.get("midViews", {}).items()},
            isometric_shape2d={name: Path(path) for name, path in payload.get("isometricShape2d", {}).items()},
            isometric_shape2d_metadata={name: Path(path) for name, path in payload.get("isometricShape2dMetadata", {}).items()},
            isometric_matplotlib={name: Path(path) for name, path in payload.get("isometricMatplotlib", {}).items()},
            isometric_matplotlib_metadata={name: Path(path) for name, path in payload.get("isometricMatplotlibMetadata", {}).items()},
        )


class ModelStore:
    """
    Handles persistence of uploaded models on disk.
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _read_metadata(self, metadata_path: Path) -> Optional[ModelMetadata]:
        if not metadata_path.exists():
            return None
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        return ModelMetadata.from_dict(payload)

    def _write_metadata(self, metadata_path: Path, metadata: ModelMetadata) -> None:
        metadata_path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")

    def create(self, original_name: str) -> ModelMetadata:
        model_id = uuid4().hex
        model_dir = self.root / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        metadata = ModelMetadata(
            model_id=model_id,
            original_name=original_name,
            step_path=model_dir / "source.step",
            preview_path=model_dir / "preview.glb",
        )
        self._write_metadata(model_dir / "metadata.json", metadata)
        return metadata

    def get(self, model_id: str) -> Optional[ModelMetadata]:
        metadata_path = self.root / model_id / "metadata.json"
        return self._read_metadata(metadata_path)

    def update(self, metadata: ModelMetadata) -> ModelMetadata:
        metadata_path = metadata.step_path.parent / "metadata.json"
        self._write_metadata(metadata_path, metadata)
        return metadata
