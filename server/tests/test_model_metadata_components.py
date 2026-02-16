from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.model_store import ModelMetadata


def test_model_metadata_roundtrip_includes_components(tmp_path: Path):
    metadata = ModelMetadata(
        model_id="model-1",
        original_name="assembly.step",
        step_path=tmp_path / "source.step",
        preview_path=tmp_path / "preview.glb",
        components=[
            {
                "id": "component_1",
                "nodeName": "component_1",
                "displayName": "Part 1",
                "triangleCount": 128,
            }
        ],
    )

    payload = metadata.to_dict()
    parsed = ModelMetadata.from_dict(payload)

    assert parsed.components == metadata.components
