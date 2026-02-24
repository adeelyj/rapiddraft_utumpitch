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
        api_key_override: str | None = None,
    ) -> VisionProviderResult:
        self.calls.append(
            {
                "prompt": prompt,
                "image_count": len(image_paths),
                "model_override": model_override,
                "base_url_override": base_url_override,
                "api_key_override": api_key_override,
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
    assert "--- x ---" in payload["raw_output_text"]
    assert "X view finding" in payload["raw_output_text"]
    assert payload["report_id"].startswith("vision_rpt_")

    report_dir = tmp_path / "model_x" / "vision_reports" / payload["report_id"]
    assert (report_dir / "result.json").exists()
    assert (report_dir / "request.json").exists()
    assert (report_dir / "raw_response.json").exists()
    assert any(path.name.endswith("_x.png") for path in (report_dir / "views").iterdir())


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


def test_create_report_openai_passes_base_url_override(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    openai_provider = _FakeProvider(
        route_id="openai",
        label="OpenAI",
        configured=True,
        default_model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        multi_response=json.dumps(
            {
                "flagged_features": [
                    {
                        "description": "Possible tool access issue near deep cavity",
                        "severity": "warning",
                        "confidence": "high",
                        "source_views": ["x", "y"],
                    }
                ],
                "general_observations": "Review complete.",
                "confidence": "high",
            }
        ),
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={"openai": openai_provider},
    )

    fireworks_base_url = "https://api.fireworks.ai/inference/v1"
    payload = service.create_report(
        model_id="model_x",
        component_node_name="component_1",
        view_set_id="vset_20260218_001",
        criteria_payload=None,
        provider_payload={
            "route": "openai",
            "base_url_override": fireworks_base_url,
        },
    )

    assert len(openai_provider.calls) == 1
    assert openai_provider.calls[0]["base_url_override"] == fireworks_base_url
    assert payload["provider_applied"]["base_url_used"] == fireworks_base_url


def test_create_report_openai_passes_api_key_override_without_persisting_secret(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    openai_provider = _FakeProvider(
        route_id="openai",
        label="OpenAI",
        configured=False,
        default_model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        multi_response=json.dumps(
            {
                "flagged_features": [
                    {
                        "description": "Tool access issue",
                        "severity": "warning",
                        "confidence": "high",
                        "source_views": ["x", "y"],
                    }
                ],
                "general_observations": "Review complete.",
                "confidence": "high",
            }
        ),
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={"openai": openai_provider},
    )

    secret = "fw_test_secret_123"
    payload = service.create_report(
        model_id="model_x",
        component_node_name="component_1",
        view_set_id="vset_20260218_001",
        criteria_payload=None,
        provider_payload={
            "route": "openai",
            "api_key_override": secret,
        },
    )

    assert payload["summary"]["flagged_count"] == 1
    assert len(openai_provider.calls) == 1
    assert openai_provider.calls[0]["api_key_override"] == secret

    report_dir = tmp_path / "model_x" / "vision_reports" / payload["report_id"]
    request_payload = json.loads((report_dir / "request.json").read_text(encoding="utf-8"))
    provider_request = request_payload["provider_request"]
    assert provider_request.get("api_key_override_provided") is True
    assert "api_key_override" not in provider_request


def test_create_report_local_supports_legacy_local_base_url_field(tmp_path: Path):
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
                    "flagged_features": [],
                    "general_observations": "Y view clear",
                    "confidence": "high",
                }
            ),
            "z": json.dumps(
                {
                    "flagged_features": [],
                    "general_observations": "Z view clear",
                    "confidence": "high",
                }
            ),
        },
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={"local": local_provider},
    )

    legacy_base_url = "http://legacy-lm-studio:1234/v1"
    payload = service.create_report(
        model_id="model_x",
        component_node_name="component_1",
        view_set_id="vset_20260218_001",
        criteria_payload={"confidence_threshold": "low"},
        provider_payload={
            "route": "local",
            "local_base_url": legacy_base_url,
        },
    )

    assert len(local_provider.calls) == 3
    assert all(call["base_url_override"] == legacy_base_url for call in local_provider.calls)
    assert payload["provider_applied"]["base_url_used"] == legacy_base_url


def test_list_providers_includes_provider_defaults(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={
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
            "local": _FakeProvider(
                route_id="local",
                label="Local",
                configured=True,
                default_model="mistral-small",
                base_url="http://127.0.0.1:1234/v1",
            ),
        },
    )

    payload = service.list_providers()

    assert payload["provider_defaults"]["openai"]["base_url"] == "https://api.openai.com/v1"
    assert payload["provider_defaults"]["claude"]["base_url"] == "https://api.anthropic.com"
    assert payload["provider_defaults"]["local"]["base_url"] == "http://127.0.0.1:1234/v1"
    assert payload["local_defaults"]["base_url"] == "http://127.0.0.1:1234/v1"


def test_create_report_respects_selected_generated_views(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    openai_provider = _FakeProvider(
        route_id="openai",
        label="OpenAI",
        configured=True,
        default_model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        multi_response=json.dumps(
            {
                "flagged_features": [
                    {
                        "description": "Single-view issue",
                        "severity": "warning",
                        "confidence": "high",
                    }
                ],
                "general_observations": "Single image run.",
                "confidence": "high",
            }
        ),
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={"openai": openai_provider},
    )

    payload = service.create_report(
        model_id="model_x",
        component_node_name="component_1",
        view_set_id="vset_20260218_001",
        selected_view_names=["z"],
        criteria_payload=None,
        provider_payload={"route": "openai"},
    )

    assert len(openai_provider.calls) == 1
    assert openai_provider.calls[0]["image_count"] == 1
    assert payload["findings"][0]["source_views"] == ["z"]


def test_create_report_accepts_pasted_images_without_generated_selection(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    openai_provider = _FakeProvider(
        route_id="openai",
        label="OpenAI",
        configured=True,
        default_model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        multi_response=json.dumps(
            {
                "flagged_features": [
                    {
                        "description": "Screenshot-only issue",
                        "severity": "warning",
                        "confidence": "high",
                    }
                ],
                "general_observations": "Screenshot analyzed.",
                "confidence": "high",
            }
        ),
    )

    service = VisionAnalysisService(
        root=tmp_path,
        occ_service=None,
        view_set_service=view_service,
        providers={"openai": openai_provider},
    )

    fake_png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8G0eoAAAAASUVORK5CYII="
    payload = service.create_report(
        model_id="model_x",
        component_node_name="component_1",
        view_set_id="vset_20260218_001",
        selected_view_names=[],
        pasted_images_payload=[
            {
                "name": "ClipboardShot",
                "data_url": f"data:image/png;base64,{fake_png_data}",
            }
        ],
        criteria_payload=None,
        provider_payload={"route": "openai"},
    )

    assert len(openai_provider.calls) == 1
    assert openai_provider.calls[0]["image_count"] == 1
    assert payload["findings"][0]["source_views"] == ["clipboardshot"]
    assert "Screenshot analyzed." in payload["raw_output_text"]


def test_create_report_requires_at_least_one_selected_or_pasted_image(tmp_path: Path):
    view_service = _FakeViewSetService(tmp_path)
    openai_provider = _FakeProvider(
        route_id="openai",
        label="OpenAI",
        configured=True,
        default_model="gpt-4o-mini",
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
            selected_view_names=[],
            pasted_images_payload=[],
            criteria_payload=None,
            provider_payload={"route": "openai"},
        )
