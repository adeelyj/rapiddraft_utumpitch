from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import server.vision_providers as vp  # noqa: E402


def _write_test_png(path: Path) -> None:
    # Tiny valid 1x1 PNG.
    path.write_bytes(
        bytes.fromhex(
            "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE"
            "0000000C49444154789C6360000000020001E221BC330000000049454E44AE426082"
        )
    )


def test_build_openai_request_defaults_fireworks_uses_non_stream_safe_max_tokens(monkeypatch):
    monkeypatch.delenv("VISION_OPENAI_MAX_TOKENS", raising=False)
    defaults = vp._build_openai_request_defaults(
        base_url="https://api.fireworks.ai/inference/v1",
        use_fireworks_preset=True,
    )
    assert defaults.get("max_tokens") == 4096


def test_openai_provider_clamps_fireworks_max_tokens_for_non_stream(monkeypatch, tmp_path: Path):
    sent_payloads: list[dict[str, object]] = []

    def _fake_post_json(*, url, headers, request_payload, timeout_seconds):  # type: ignore[no-untyped-def]
        sent_payloads.append(dict(request_payload))
        return vp._SimpleHttpResponse(
            status_code=200,
            text='{"choices":[{"message":{"content":"ok"}}]}',
        )

    monkeypatch.setattr(vp, "_post_json", _fake_post_json)

    image_path = tmp_path / "x.png"
    _write_test_png(image_path)

    provider = vp.OpenAIVisionProvider(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        default_model="accounts/fireworks/models/qwen3-vl-30b-a3b-thinking",
        timeout_seconds=30.0,
        request_defaults={"max_tokens": 32768, "temperature": 0},
    )

    provider.analyze(
        prompt="Analyze.",
        image_paths=[image_path],
        base_url_override="https://api.fireworks.ai/inference/v1",
    )

    assert sent_payloads
    assert sent_payloads[0].get("max_tokens") == 4096


def test_openai_provider_keeps_large_max_tokens_for_non_fireworks(monkeypatch, tmp_path: Path):
    sent_payloads: list[dict[str, object]] = []

    def _fake_post_json(*, url, headers, request_payload, timeout_seconds):  # type: ignore[no-untyped-def]
        sent_payloads.append(dict(request_payload))
        return vp._SimpleHttpResponse(
            status_code=200,
            text='{"choices":[{"message":{"content":"ok"}}]}',
        )

    monkeypatch.setattr(vp, "_post_json", _fake_post_json)

    image_path = tmp_path / "x.png"
    _write_test_png(image_path)

    provider = vp.OpenAIVisionProvider(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        timeout_seconds=30.0,
        request_defaults={"max_tokens": 32768, "temperature": 0},
    )

    provider.analyze(
        prompt="Analyze.",
        image_paths=[image_path],
        base_url_override="https://api.openai.com/v1",
    )

    assert sent_payloads
    assert sent_payloads[0].get("max_tokens") == 32768
