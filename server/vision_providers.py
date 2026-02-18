from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import httpx as _httpx
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    _httpx = None


class VisionProviderError(RuntimeError):
    pass


@dataclass
class VisionProviderResult:
    text: str
    raw_response: Any
    model_used: str
    base_url_used: str
    request_metadata: dict[str, Any]


@dataclass
class _SimpleHttpResponse:
    status_code: int
    text: str

    def json(self) -> Any:
        return json.loads(self.text)


class _BaseVisionProvider:
    route_id: str = ""
    label: str = ""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.default_model = default_model.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.default_model)

    def availability(self) -> dict[str, Any]:
        return {
            "id": self.route_id,
            "label": self.label,
            "configured": bool(self.configured),
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
        raise NotImplementedError


class OpenAIVisionProvider(_BaseVisionProvider):
    route_id = "openai"
    label = "OpenAI"

    @classmethod
    def from_env(cls) -> "OpenAIVisionProvider":
        timeout_seconds = _parse_timeout_seconds(
            os.getenv("VISION_REQUEST_TIMEOUT_SECONDS"),
            fallback=90.0,
        )
        return cls(
            api_key=os.getenv("VISION_OPENAI_API_KEY", ""),
            base_url=os.getenv("VISION_OPENAI_BASE_URL", "https://api.openai.com/v1"),
            default_model=os.getenv("VISION_OPENAI_MODEL", ""),
            timeout_seconds=timeout_seconds,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.default_model)

    def analyze(
        self,
        *,
        prompt: str,
        image_paths: list[Path],
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> VisionProviderResult:
        if not image_paths:
            raise VisionProviderError("At least one image is required for OpenAI vision analysis.")

        api_key = self.api_key
        if not api_key:
            raise VisionProviderError("OpenAI provider is not configured (missing VISION_OPENAI_API_KEY).")

        model_used = (model_override or self.default_model).strip()
        if not model_used:
            raise VisionProviderError("OpenAI provider is not configured (missing model).")

        base_url = (base_url_override or self.base_url).strip().rstrip("/")
        if not base_url.startswith("http"):
            raise VisionProviderError("Invalid OpenAI base URL.")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_path in image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": _to_data_url(image_path),
                    },
                }
            )

        request_payload = {
            "model": model_used,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        }

        url = f"{base_url}/chat/completions"
        response = _post_json(
            url=url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            request_payload=request_payload,
            timeout_seconds=self.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise VisionProviderError(
                f"OpenAI request failed ({response.status_code}): {detail}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise VisionProviderError(f"OpenAI response was not valid JSON: {exc}") from exc

        text = _extract_openai_text(payload)
        return VisionProviderResult(
            text=text,
            raw_response=payload,
            model_used=model_used,
            base_url_used=base_url,
            request_metadata={
                "provider": self.route_id,
                "endpoint": url,
                "model": model_used,
                "image_count": len(image_paths),
            },
        )


class ClaudeVisionProvider(_BaseVisionProvider):
    route_id = "claude"
    label = "Claude"

    @classmethod
    def from_env(cls) -> "ClaudeVisionProvider":
        timeout_seconds = _parse_timeout_seconds(
            os.getenv("VISION_REQUEST_TIMEOUT_SECONDS"),
            fallback=90.0,
        )
        return cls(
            api_key=os.getenv("VISION_CLAUDE_API_KEY", ""),
            base_url=os.getenv("VISION_CLAUDE_BASE_URL", "https://api.anthropic.com"),
            default_model=os.getenv("VISION_CLAUDE_MODEL", ""),
            timeout_seconds=timeout_seconds,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.default_model)

    def analyze(
        self,
        *,
        prompt: str,
        image_paths: list[Path],
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> VisionProviderResult:
        if not image_paths:
            raise VisionProviderError("At least one image is required for Claude vision analysis.")

        api_key = self.api_key
        if not api_key:
            raise VisionProviderError("Claude provider is not configured (missing VISION_CLAUDE_API_KEY).")

        model_used = (model_override or self.default_model).strip()
        if not model_used:
            raise VisionProviderError("Claude provider is not configured (missing model).")

        base_url = (base_url_override or self.base_url).strip().rstrip("/")
        if not base_url.startswith("http"):
            raise VisionProviderError("Invalid Claude base URL.")

        endpoint = f"{base_url}/messages" if base_url.endswith("/v1") else f"{base_url}/v1/messages"

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_path in image_paths:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": _to_base64(image_path),
                    },
                }
            )

        request_payload = {
            "model": model_used,
            "max_tokens": 1200,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        }

        response = _post_json(
            url=endpoint,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            request_payload=request_payload,
            timeout_seconds=self.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise VisionProviderError(
                f"Claude request failed ({response.status_code}): {detail}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise VisionProviderError(f"Claude response was not valid JSON: {exc}") from exc

        text = _extract_claude_text(payload)
        return VisionProviderResult(
            text=text,
            raw_response=payload,
            model_used=model_used,
            base_url_used=base_url,
            request_metadata={
                "provider": self.route_id,
                "endpoint": endpoint,
                "model": model_used,
                "image_count": len(image_paths),
            },
        )


class LocalOpenAICompatVisionProvider(_BaseVisionProvider):
    route_id = "local"
    label = "Local LM Studio"

    @classmethod
    def from_env(cls) -> "LocalOpenAICompatVisionProvider":
        timeout_seconds = _parse_timeout_seconds(
            os.getenv("VISION_REQUEST_TIMEOUT_SECONDS"),
            fallback=90.0,
        )
        return cls(
            api_key=os.getenv("VISION_LOCAL_API_KEY", ""),
            base_url=os.getenv("VISION_LOCAL_BASE_URL", "http://127.0.0.1:1234/v1"),
            default_model=os.getenv("VISION_LOCAL_MODEL", ""),
            timeout_seconds=timeout_seconds,
        )

    def analyze(
        self,
        *,
        prompt: str,
        image_paths: list[Path],
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> VisionProviderResult:
        if not image_paths:
            raise VisionProviderError("At least one image is required for local vision analysis.")

        model_used = (model_override or self.default_model).strip()
        if not model_used:
            raise VisionProviderError("Local provider is not configured (missing VISION_LOCAL_MODEL).")

        base_url = (base_url_override or self.base_url).strip().rstrip("/")
        if not base_url.startswith("http"):
            raise VisionProviderError("Invalid local base URL.")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_path in image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": _to_data_url(image_path),
                    },
                }
            )

        request_payload = {
            "model": model_used,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{base_url}/chat/completions"
        response = _post_json(
            url=url,
            headers=headers,
            request_payload=request_payload,
            timeout_seconds=self.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise VisionProviderError(
                f"Local provider request failed ({response.status_code}): {detail}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise VisionProviderError(f"Local provider response was not valid JSON: {exc}") from exc

        text = _extract_openai_text(payload)
        return VisionProviderResult(
            text=text,
            raw_response=payload,
            model_used=model_used,
            base_url_used=base_url,
            request_metadata={
                "provider": self.route_id,
                "endpoint": url,
                "model": model_used,
                "image_count": len(image_paths),
            },
        )


def build_default_providers() -> dict[str, _BaseVisionProvider]:
    providers: dict[str, _BaseVisionProvider] = {
        "openai": OpenAIVisionProvider.from_env(),
        "claude": ClaudeVisionProvider.from_env(),
        "local": LocalOpenAICompatVisionProvider.from_env(),
    }
    return providers


def _parse_timeout_seconds(raw_value: str | None, *, fallback: float) -> float:
    if raw_value is None:
        return fallback
    try:
        parsed = float(raw_value)
    except Exception:
        return fallback
    if parsed <= 0:
        return fallback
    return parsed


def _to_base64(path: Path) -> str:
    try:
        data = path.read_bytes()
    except Exception as exc:
        raise VisionProviderError(f"Failed to read image '{path.name}': {exc}") from exc
    return base64.b64encode(data).decode("ascii")


def _to_data_url(path: Path) -> str:
    return f"data:image/png;base64,{_to_base64(path)}"


def _post_json(
    *,
    url: str,
    headers: dict[str, str],
    request_payload: dict[str, Any],
    timeout_seconds: float,
) -> _SimpleHttpResponse:
    if _httpx is not None:
        try:
            response = _httpx.post(
                url,
                headers=headers,
                json=request_payload,
                timeout=timeout_seconds,
            )
            return _SimpleHttpResponse(
                status_code=int(response.status_code),
                text=response.text,
            )
        except Exception as exc:
            raise VisionProviderError(f"HTTP request failed: {exc}") from exc

    body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status_code = int(getattr(response, "status", 200))
            return _SimpleHttpResponse(status_code=status_code, text=raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return _SimpleHttpResponse(status_code=int(exc.code), text=raw)
    except Exception as exc:
        raise VisionProviderError(f"HTTP request failed: {exc}") from exc


def _extract_openai_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise VisionProviderError("Invalid OpenAI response payload.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise VisionProviderError("OpenAI response does not contain choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise VisionProviderError("OpenAI response missing message payload.")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        if chunks:
            return "\n".join(chunks)
    raise VisionProviderError("OpenAI response did not include text content.")


def _extract_claude_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise VisionProviderError("Invalid Claude response payload.")
    content = payload.get("content")
    if not isinstance(content, list):
        raise VisionProviderError("Claude response missing content array.")
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            chunks.append(item["text"])
    if not chunks:
        raise VisionProviderError("Claude response did not include text content.")
    return "\n".join(chunks)


def _extract_error_detail(response: Any) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            if isinstance(payload.get("error"), dict):
                message = payload["error"].get("message")
                if isinstance(message, str) and message:
                    return message
            detail = payload.get("detail")
            if isinstance(detail, str) and detail:
                return detail
    except Exception:
        pass
    body = response.text.strip()
    return body[:300] if body else "Unknown provider error"
