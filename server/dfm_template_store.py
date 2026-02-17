from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dfm_bundle import DfmBundle


STANDARDS_SECTION_KEY = "standards_references_auto"


class DfmTemplateStoreError(ValueError):
    pass


class DfmTemplateNotFoundError(DfmTemplateStoreError):
    pass


class DfmTemplateStore:
    def __init__(
        self,
        *,
        root: Path,
        bundle: DfmBundle,
        max_custom_templates: int = 100,
    ) -> None:
        self.root = root
        self.bundle = bundle
        self.max_custom_templates = max_custom_templates
        self.root.mkdir(parents=True, exist_ok=True)

        self._bundle_templates = [
            template
            for template in bundle.report_templates.get("templates", [])
            if isinstance(template, dict)
            and isinstance(template.get("template_id"), str)
            and template.get("template_id")
        ]
        self._bundle_template_map = {
            str(template["template_id"]): template for template in self._bundle_templates
        }
        self._role_ids = {
            role.get("role_id")
            for role in bundle.roles.get("roles", [])
            if isinstance(role, dict) and isinstance(role.get("role_id"), str)
        }
        self._overlay_map = {
            overlay.get("overlay_id"): overlay
            for overlay in bundle.overlays.get("overlays", [])
            if isinstance(overlay, dict) and isinstance(overlay.get("overlay_id"), str)
        }
        self._section_catalog = self._build_section_catalog()

    def list_templates(self, model_id: str) -> dict[str, Any]:
        custom_templates = self._custom_template_records(model_id)
        bundle_records = [self._bundle_template_record(template) for template in self._bundle_templates]
        merged = bundle_records + custom_templates
        return {"templates": merged, "count": len(merged)}

    def get_template(self, model_id: str, template_id: str) -> dict[str, Any]:
        if template_id in self._bundle_template_map:
            return self._bundle_template_record(self._bundle_template_map[template_id])

        for template in self._custom_templates(model_id):
            if template.get("template_id") == template_id:
                return self._normalize_custom_template(template)
        raise DfmTemplateNotFoundError(f"Unknown template_id '{template_id}'.")

    def create_template(
        self,
        *,
        model_id: str,
        template_name: str,
        base_template_id: str,
        overlay_id: str | None,
        default_role_id: str | None,
        enabled_section_keys: list[str],
    ) -> dict[str, Any]:
        name = template_name.strip()
        if not name:
            raise DfmTemplateStoreError("template_name is required.")
        if len(name) > 80:
            raise DfmTemplateStoreError("template_name must be 80 characters or fewer.")

        base_template = self._bundle_template_map.get(base_template_id)
        if not base_template:
            raise DfmTemplateStoreError(f"Unknown base_template_id '{base_template_id}'.")

        normalized_overlay_id = self._normalize_overlay_id(overlay_id)
        normalized_role_id = self._normalize_role_id(default_role_id)

        payload = self._read_store(model_id)
        custom_templates = payload.get("custom_templates", [])
        if len(custom_templates) >= self.max_custom_templates:
            raise DfmTemplateStoreError(
                f"Maximum custom templates reached ({self.max_custom_templates})."
            )

        existing_labels = {
            str(template.get("label", "")).strip().lower()
            for template in custom_templates
            if isinstance(template, dict)
        }
        existing_labels.update(
            {
                str(template.get("label", "")).strip().lower()
                for template in self._bundle_templates
            }
        )
        if name.lower() in existing_labels:
            raise DfmTemplateStoreError("template_name must be unique for this model.")

        enabled_keys = self._normalize_enabled_keys(enabled_section_keys)
        sections = self._resolve_sections_for_save(
            base_template=base_template,
            overlay_id=normalized_overlay_id,
            enabled_section_keys=enabled_keys,
        )

        next_id = int(payload.get("next_custom_template_id", 1))
        template_id = f"custom_tpl_{next_id:04d}"
        timestamp = self._now_iso()

        custom_template = {
            "template_id": template_id,
            "label": name,
            "description": f"Custom template based on {base_template.get('label', base_template_id)}.",
            "source": "custom",
            "base_template_id": base_template_id,
            "overlay_id": normalized_overlay_id,
            "default_role_id": normalized_role_id,
            "template_sections": sections["enabled"],
            "suppressed_template_sections": sections["suppressed"],
            "section_order": sections["order"],
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        payload["next_custom_template_id"] = next_id + 1
        payload.setdefault("custom_templates", []).append(custom_template)
        self._write_store(model_id, payload)

        response = dict(custom_template)
        response["validation_warnings"] = sections["validation_warnings"]
        return response

    def planning_templates(self, model_id: str) -> list[dict[str, Any]]:
        templates = [dict(template) for template in self._bundle_templates]
        for custom in self._custom_templates(model_id):
            template_sections = [
                section
                for section in custom.get("template_sections", [])
                if isinstance(section, str) and section
            ]
            suppressed_sections = [
                section
                for section in custom.get("suppressed_template_sections", [])
                if isinstance(section, str) and section
            ]
            templates.append(
                {
                    "template_id": custom.get("template_id"),
                    "label": custom.get("label"),
                    "description": custom.get("description"),
                    "source": "custom",
                    "base_template_id": custom.get("base_template_id"),
                    "overlay_id": custom.get("overlay_id"),
                    "default_role_id": custom.get("default_role_id"),
                    "template_sections": template_sections,
                    "suppressed_template_sections": suppressed_sections,
                }
            )
        return templates

    def _build_section_catalog(self) -> set[str]:
        section_keys = {STANDARDS_SECTION_KEY}
        for template in self._bundle_templates:
            for section in template.get("sections", []):
                if not isinstance(section, dict):
                    continue
                section_key = section.get("section_key")
                if isinstance(section_key, str) and section_key:
                    section_keys.add(section_key)
        return section_keys

    def _model_dir(self, model_id: str) -> Path:
        return self.root / model_id

    def _store_path(self, model_id: str) -> Path:
        return self._model_dir(model_id) / "dfm_templates.json"

    def _default_payload(self) -> dict[str, Any]:
        return {
            "next_custom_template_id": 1,
            "custom_templates": [],
        }

    def _ensure_store(self, model_id: str) -> Path:
        model_dir = self._model_dir(model_id)
        model_dir.mkdir(parents=True, exist_ok=True)
        store_path = self._store_path(model_id)
        if not store_path.exists():
            self._write_json(store_path, self._default_payload())
        return store_path

    def _read_store(self, model_id: str) -> dict[str, Any]:
        store_path = self._ensure_store(model_id)
        payload = json.loads(store_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise DfmTemplateStoreError(
                f"Invalid template store for model '{model_id}': expected object."
            )
        if not isinstance(payload.get("next_custom_template_id"), int):
            payload["next_custom_template_id"] = 1
        if not isinstance(payload.get("custom_templates"), list):
            payload["custom_templates"] = []
        return payload

    def _write_store(self, model_id: str, payload: dict[str, Any]) -> None:
        store_path = self._ensure_store(model_id)
        tmp_path = store_path.with_name(f"{store_path.name}.tmp")
        self._write_json(tmp_path, payload)
        tmp_path.replace(store_path)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _custom_templates(self, model_id: str) -> list[dict[str, Any]]:
        payload = self._read_store(model_id)
        templates = payload.get("custom_templates", [])
        return [template for template in templates if isinstance(template, dict)]

    def _custom_template_records(self, model_id: str) -> list[dict[str, Any]]:
        return [self._normalize_custom_template(template) for template in self._custom_templates(model_id)]

    def _normalize_custom_template(self, template: dict[str, Any]) -> dict[str, Any]:
        section_order = [
            section
            for section in template.get("section_order", [])
            if isinstance(section, str) and section
        ]
        if not section_order:
            section_order = self._dedupe_preserve_order(
                [
                    *[
                        section
                        for section in template.get("template_sections", [])
                        if isinstance(section, str) and section
                    ],
                    *[
                        section
                        for section in template.get("suppressed_template_sections", [])
                        if isinstance(section, str) and section
                    ],
                ]
            )

        return {
            "template_id": template.get("template_id"),
            "label": template.get("label"),
            "description": template.get("description"),
            "source": "custom",
            "base_template_id": template.get("base_template_id"),
            "overlay_id": template.get("overlay_id"),
            "default_role_id": template.get("default_role_id"),
            "template_sections": [
                section
                for section in template.get("template_sections", [])
                if isinstance(section, str) and section
            ],
            "suppressed_template_sections": [
                section
                for section in template.get("suppressed_template_sections", [])
                if isinstance(section, str) and section
            ],
            "section_order": section_order,
            "created_at": template.get("created_at"),
            "updated_at": template.get("updated_at"),
        }

    def _bundle_template_record(self, template: dict[str, Any]) -> dict[str, Any]:
        section_order = []
        enabled = []
        for section in template.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_key = section.get("section_key")
            if not isinstance(section_key, str) or not section_key:
                continue
            if section_key not in section_order:
                section_order.append(section_key)
            if bool(section.get("enabled_by_default")) and section_key not in enabled:
                enabled.append(section_key)

        if STANDARDS_SECTION_KEY not in section_order:
            section_order.append(STANDARDS_SECTION_KEY)
        if STANDARDS_SECTION_KEY not in enabled:
            enabled.append(STANDARDS_SECTION_KEY)

        suppressed = [section for section in section_order if section not in enabled]
        return {
            "template_id": template.get("template_id"),
            "label": template.get("label"),
            "description": template.get("description"),
            "source": "bundle",
            "base_template_id": template.get("template_id"),
            "overlay_id": None,
            "default_role_id": None,
            "template_sections": enabled,
            "suppressed_template_sections": suppressed,
            "section_order": section_order,
        }

    def _normalize_overlay_id(self, overlay_id: str | None) -> str | None:
        if overlay_id is None:
            return None
        normalized = overlay_id.strip()
        if not normalized:
            return None
        if normalized not in self._overlay_map:
            raise DfmTemplateStoreError(f"Unknown overlay_id '{overlay_id}'.")
        return normalized

    def _normalize_role_id(self, role_id: str | None) -> str | None:
        if role_id is None:
            return None
        normalized = role_id.strip()
        if not normalized:
            return None
        if normalized not in self._role_ids:
            raise DfmTemplateStoreError(f"Unknown default_role_id '{role_id}'.")
        return normalized

    def _normalize_enabled_keys(self, enabled_section_keys: list[str]) -> list[str]:
        if not isinstance(enabled_section_keys, list):
            raise DfmTemplateStoreError("enabled_section_keys must be an array.")
        normalized: list[str] = []
        for section_key in enabled_section_keys:
            if not isinstance(section_key, str):
                raise DfmTemplateStoreError("enabled_section_keys must contain strings only.")
            key = section_key.strip()
            if not key:
                continue
            if key not in self._section_catalog:
                raise DfmTemplateStoreError(
                    f"enabled_section_keys contains unknown section '{section_key}'."
                )
            if key not in normalized:
                normalized.append(key)
        return normalized

    def _resolve_sections_for_save(
        self,
        *,
        base_template: dict[str, Any],
        overlay_id: str | None,
        enabled_section_keys: list[str],
    ) -> dict[str, Any]:
        section_order: list[str] = []
        default_enabled: set[str] = set()
        forced_suppressed: set[str] = set()

        for section in base_template.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_key = section.get("section_key")
            if not isinstance(section_key, str) or not section_key:
                continue
            if section_key not in section_order:
                section_order.append(section_key)
            if bool(section.get("enabled_by_default")):
                default_enabled.add(section_key)

            overlay_required = section.get("overlay_required")
            if (
                isinstance(overlay_required, str)
                and overlay_required
                and overlay_required != overlay_id
            ):
                forced_suppressed.add(section_key)

        overlay_auto_sections: list[str] = []
        validation_warnings: list[str] = []
        if overlay_id:
            overlay = self._overlay_map.get(overlay_id, {})
            for section_key in overlay.get("extra_report_sections", []):
                if not isinstance(section_key, str) or not section_key:
                    continue
                if section_key not in self._section_catalog:
                    validation_warnings.append(
                        f"overlay extra section '{section_key}' is not supported and was ignored."
                    )
                    continue
                if section_key not in overlay_auto_sections:
                    overlay_auto_sections.append(section_key)
                if section_key not in section_order:
                    section_order.append(section_key)

        if STANDARDS_SECTION_KEY not in section_order:
            section_order.append(STANDARDS_SECTION_KEY)

        allowed_for_user = {
            section_key
            for section_key in section_order
            if section_key not in forced_suppressed
        }
        requested_enabled = set(enabled_section_keys) if enabled_section_keys else set(default_enabled)
        invalid_requested = sorted(requested_enabled - allowed_for_user)
        if invalid_requested:
            raise DfmTemplateStoreError(
                "enabled_section_keys contains sections not available for the selected template/overlay: "
                + ", ".join(invalid_requested)
            )

        locked_enabled = {STANDARDS_SECTION_KEY, *overlay_auto_sections}
        enabled: list[str] = []
        for section_key in section_order:
            if section_key in locked_enabled:
                enabled.append(section_key)
                continue
            if section_key in forced_suppressed:
                continue
            if section_key in requested_enabled:
                enabled.append(section_key)

        suppressed = [section_key for section_key in section_order if section_key not in enabled]
        return {
            "order": section_order,
            "enabled": enabled,
            "suppressed": suppressed,
            "validation_warnings": validation_warnings,
        }

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
