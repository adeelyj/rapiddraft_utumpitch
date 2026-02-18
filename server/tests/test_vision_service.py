from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.vision_analysis import VisionAnalysisError, VisionAnalysisService  # noqa: E402
from server.vision_providers import VisionProviderResult  # noqa: E402


class _FakeViewSetService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.model_id = "model_x"
        self.view_set_id = "vset_20260218_001"
        self.views_dir = root / self.model_id / "vision_view_sets" / self.view_set_id / "views"
        self.views_dir.mkdir(parents=True, exist_ok=True)
        for name in ("x", "y", "z"):
            (self.views_dir / f"{name}.png").write_bytes(b"fake-png")

    def create_view_set(self, *, model_id: str, step_path: Path, component_node_name: str | None = None):
        return {
            "view_set_id": self.view_set_id,
            "model_id": model_id,
            "component_node_name": component_node_name,
            "views": {
                name: f"/api/models/{model_id}/vision/view-sets/{self.view_set_id}/views/{name}"
                for name in ("x", "y", "z")
            },
            "generated_at": "2026-02-18T12:00:00Z",
        }

    def get_view_set_paths(self, *, model_id: str, view_set_id: str):
        if model_id != self.model_id or view_set_id != self.view_set_id:
            raise RuntimeError("missing")
        return {
            "x": self.views_dir / "x.png",
            "y": self.views_dir / "y.png",
            "z": self.views_dir / "z.png",
        }

    def get_view_image_path(self, *, model_id: str, view_set_id: str, view_name: str) -> Path:
        return self.get_view_set_paths(model_id=model_id, view_set_id=view_set_id)[view_name]


class _FakeProvider:
    def __init__(
        self,
        *,
        route_id: str,
        label: str,
        configured: bool,
        default_model: str,
        base_url: str,
        per_view_responses: dict[str, str] | None = None,
        multi_response: str | None = None,
    ) -> None:
        self.route_id = route_id
        self.label = label
        self.configured = configured
        self.default_model = default_model
        self.base_url = base_url
        self.per_view_responses = per_view_responses or {}
        self.multi_response = multi_response
        self.calls: list[dict[str, object]] = []

    def availability(self):
        return {
            "id": self.route_id,
            "label": self.label,
            "configured": self.configured,
            "default_model": self.default_model,
        }

    def analyze(
        self,
        *,
        prompt: str,
        image_paths: list[Path],
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> VisionProviderResult:
        self.calls.append(
            {
                "prompt": prompt,
                "image_count": len(image_paths),
                "model_override": model_override,
                "base_url_override": base_url_override,
            }
        )

        if self.route_id == "local":
            view_name = image_paths[0].stem.lower()
            text = self.per_view_responses.get(view_name, "{}")
        else:
            text = self.multi_response or "{}"

        return VisionProviderResult(
            text=text,
            raw_response={"ok": True},
            model_used=model_override or self.default_model,
            base_url_used=base_url_override or self.base_url,
            request_metadata={"provider": self.route_id, "image_count": len(image_paths)},
        )


def test_create_report_local_runs_sequential_and_persists_artifacts(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    local_provider = _FakeProvider(
        route_id="local",
        label="Local",
        configured=True,
        default_model="mistral-small",
        base_url="http://127.0.0.1:1234/v1",
        per_view_responses={
            "x": json.dumps(
                {
                    "flagged_features": [
                        {
                            "description": "Tight corner near pocket",
                            "severity": "warning",
                            "confidence": "high",
                        }
                    ],
                    "general_observations": "X view finding",
                    "confidence": "high",
                }
            ),
            "y": json.dumps(
                {
                    "flagged_features": [
                        {
                            "description": "Tight corner near pocket",
                            "severity": "critical",
                            "confidence": "medium",
                        }
                    ],
                    "general_observations": "Y view finding",
                    "confidence": "medium",
                }
            ),
            "z": json.dumps(
                {
                    "flagged_features": [
                        {
                            "description": "Secondary narrow slot",
                            "severity": "caution",
                            "confidence": "medium",
                        }
                    ],
                    "general_observations": "Z view finding",
                    "confidence": "medium",
                }
            ),
        },
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={
            "local": local_provider,
            "openai": _FakeProvider(
                route_id="openai",
                label="OpenAI",
                configured=True,
                default_model="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
            ),
            "claude": _FakeProvider(
                route_id="claude",
                label="Claude",
                configured=True,
                default_model="claude-3-5-sonnet-latest",
                base_url="https://api.anthropic.com",
            ),
        },
    )

    payload = service.create_report(
        model_id="model_x",
        component_node_name="component_1",
        view_set_id="vset_20260218_001",
        criteria_payload={"confidence_threshold": "low", "max_flagged_features": 10},
        provider_payload={"route": "local"},
    )

    assert len(local_provider.calls) == 3
    assert payload["provider_applied"]["route_used"] == "local"
    assert payload["summary"]["flagged_count"] == 2
    assert payload["report_id"].startswith("vision_rpt_")

    report_dir = tmp_path / "model_x" / "vision_reports" / payload["report_id"]
    assert (report_dir / "result.json").exists()
    assert (report_dir / "request.json").exists()
    assert (report_dir / "raw_response.json").exists()
    assert (report_dir / "views" / "x.png").exists()


def test_create_report_requires_configured_provider(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    openai_provider = _FakeProvider(
        route_id="openai",
        label="OpenAI",
        configured=False,
        default_model="",
        base_url="https://api.openai.com/v1",
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={"openai": openai_provider},
    )

    with pytest.raises(VisionAnalysisError):
        service.create_report(
            model_id="model_x",
            component_node_name="component_1",
            view_set_id="vset_20260218_001",
            criteria_payload=None,
            provider_payload={"route": "openai"},
        )
