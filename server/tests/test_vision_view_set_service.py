from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.vision_views import VisionViewSetService  # noqa: E402


class _FakeOccService:
    def __init__(self) -> None:
        self.last_component_node_name: str | None = None
        self.last_component_solid_index: int | None = None

    def generate_occ_views(
        self,
        step_path: Path,
        output_dir: Path,
        *,
        component_node_name: str | None = None,
        component_solid_index: int | None = None,
    ):
        self.last_component_node_name = component_node_name
        self.last_component_solid_index = component_solid_index
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}
        for name in ("x", "y", "z"):
            path = output_dir / f"{name}.png"
            path.write_bytes(b"png")
            paths[name] = path
        return paths


def test_view_set_service_passes_component_selection_to_occ(tmp_path: Path):
    step_path = tmp_path / "source.step"
    step_path.write_text("dummy", encoding="utf-8")

    occ = _FakeOccService()
    service = VisionViewSetService(root=tmp_path, occ_service=occ)

    payload = service.create_view_set(
        model_id="model_x",
        step_path=step_path,
        component_node_name="node_random_name",
        component_solid_index=3,
    )

    assert occ.last_component_node_name == "node_random_name"
    assert occ.last_component_solid_index == 3
    assert payload["views"]["x"].endswith("/views/x")
    assert payload["views"]["y"].endswith("/views/y")
    assert payload["views"]["z"].endswith("/views/z")
