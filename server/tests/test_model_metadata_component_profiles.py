from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.model_store import ModelMetadata


def test_model_metadata_roundtrip_includes_component_profiles(tmp_path: Path):
    metadata = ModelMetadata(
        model_id="model-2",
        original_name="assembly.step",
        step_path=tmp_path / "source.step",
        preview_path=tmp_path / "preview.glb",
        component_profiles={
            "component_1": {
                "material": "Aluminum",
                "manufacturingProcess": "CNC Machining",
                "industry": "App Advance",
            }
        },
    )

    payload = metadata.to_dict()
    parsed = ModelMetadata.from_dict(payload)

    assert parsed.component_profiles == metadata.component_profiles
