import { useEffect, useMemo, useState } from "react";

type DfmConfigTemplate = {
  template_id: string;
  label: string;
};

type DfmConfigOverlay = {
  overlay_id: string;
  label: string;
  extra_report_sections?: string[];
};

type DfmConfigRole = {
  role_id: string;
  label: string;
};

type DfmConfigControl = {
  control_id: string;
  label?: string;
};

type DfmBuilderPanelBindings = {
  controls?: DfmConfigControl[];
};

type DfmConfigResponse = {
  templates: DfmConfigTemplate[];
  overlays: DfmConfigOverlay[];
  roles: DfmConfigRole[];
  ui_bindings?: {
    screens?: {
      report_template_builder_panel?: DfmBuilderPanelBindings;
    };
  };
};

type DfmModelTemplateRecord = {
  template_id: string;
  label: string;
  description: string;
  source: "bundle" | "custom";
  base_template_id: string;
  overlay_id: string | null;
  default_role_id: string | null;
  template_sections: string[];
  suppressed_template_sections: string[];
  section_order?: string[];
  created_at?: string;
  updated_at?: string;
};

type DfmModelTemplateListResponse = {
  templates: DfmModelTemplateRecord[];
  count: number;
};

type SaveTemplateResponse = DfmModelTemplateRecord & {
  validation_warnings?: string[];
};

type ReportTemplateBuilderSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  onClose: () => void;
};

const STANDARDS_SECTION_KEY = "standards_references_auto";

const formatSectionLabel = (sectionKey: string): string => {
  if (sectionKey === STANDARDS_SECTION_KEY) return "Standards / References";
  return sectionKey
    .split("_")
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
};

const ReportTemplateBuilderSidebar = ({
  open,
  apiBase,
  modelId,
  onClose,
}: ReportTemplateBuilderSidebarProps) => {
  const [dfmConfig, setDfmConfig] = useState<DfmConfigResponse | null>(null);
  const [templates, setTemplates] = useState<DfmModelTemplateRecord[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedOverlayId, setSelectedOverlayId] = useState("");
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [sectionOrder, setSectionOrder] = useState<string[]>([]);
  const [userEnabledSections, setUserEnabledSections] = useState<string[]>([]);

  const [loading, setLoading] = useState(false);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);

  const controlsById = useMemo(() => {
    const map = new Map<string, DfmConfigControl>();
    const controls = dfmConfig?.ui_bindings?.screens?.report_template_builder_panel?.controls ?? [];
    controls.forEach((control) => {
      if (control?.control_id) map.set(control.control_id, control);
    });
    return map;
  }, [dfmConfig]);

  const templateTypeLabel = controlsById.get("template_type")?.label ?? "Template type";
  const overlayLabel = controlsById.get("overlay_pack")?.label ?? "Overlay pack";
  const roleLabel = controlsById.get("default_role_lens")?.label ?? "Default role lens";
  const sectionTreeLabel = controlsById.get("section_tree")?.label ?? "Section tree";

  const selectedOverlayAutoSections = useMemo(() => {
    if (!selectedOverlayId || !dfmConfig) return [];
    const overlay = dfmConfig.overlays.find((item) => item.overlay_id === selectedOverlayId);
    if (!overlay || !Array.isArray(overlay.extra_report_sections)) return [];
    return overlay.extra_report_sections.filter(
      (sectionKey) => sectionOrder.includes(sectionKey),
    );
  }, [dfmConfig, sectionOrder, selectedOverlayId]);

  const lockedSections = useMemo(() => {
    return new Set<string>([STANDARDS_SECTION_KEY, ...selectedOverlayAutoSections]);
  }, [selectedOverlayAutoSections]);

  const enabledSections = useMemo(() => {
    return sectionOrder.filter((sectionKey) => {
      return lockedSections.has(sectionKey) || userEnabledSections.includes(sectionKey);
    });
  }, [lockedSections, sectionOrder, userEnabledSections]);

  const selectedTemplate = useMemo(() => {
    return templates.find((template) => template.template_id === selectedTemplateId) ?? null;
  }, [selectedTemplateId, templates]);

  const readErrorText = async (response: Response, fallback: string) => {
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      return payload.detail ?? payload.message ?? fallback;
    } catch {
      return fallback;
    }
  };

  const loadTemplateList = async (targetModelId: string) => {
    const response = await fetch(`${apiBase}/api/models/${targetModelId}/dfm/templates`);
    if (!response.ok) {
      throw new Error(await readErrorText(response, "Failed to load template list"));
    }
    const payload = (await response.json()) as DfmModelTemplateListResponse;
    setTemplates(payload.templates ?? []);
    return payload.templates ?? [];
  };

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    const load = async () => {
      if (!modelId) {
        setError("Load a model before opening the template builder.");
        setTemplates([]);
        return;
      }

      setLoading(true);
      setError(null);
      setInfo(null);
      setValidationWarnings([]);
      try {
        const [configResponse, modelTemplates] = await Promise.all([
          fetch(`${apiBase}/api/dfm/config`),
          loadTemplateList(modelId),
        ]);

        if (!configResponse.ok) {
          throw new Error(await readErrorText(configResponse, "Failed to load DFM config"));
        }
        const configPayload = (await configResponse.json()) as DfmConfigResponse;
        if (cancelled) return;
        setDfmConfig(configPayload);

        const firstTemplateId = modelTemplates[0]?.template_id ?? "";
        setSelectedTemplateId((current) => current || firstTemplateId);
        setSelectedRoleId((current) => current || configPayload.roles[0]?.role_id || "");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unexpected error while loading builder data");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [apiBase, modelId, open]);

  useEffect(() => {
    if (!open || !modelId || !selectedTemplateId) return;
    let cancelled = false;

    const loadTemplate = async () => {
      setLoadingTemplate(true);
      setError(null);
      setInfo(null);
      setValidationWarnings([]);
      try {
        const response = await fetch(
          `${apiBase}/api/models/${modelId}/dfm/templates/${selectedTemplateId}`,
        );
        if (!response.ok) {
          throw new Error(await readErrorText(response, "Failed to load template details"));
        }
        const payload = (await response.json()) as DfmModelTemplateRecord;
        if (cancelled) return;

        const resolvedSectionOrder = payload.section_order?.length
          ? payload.section_order
          : [...payload.template_sections, ...payload.suppressed_template_sections];
        const dedupedSectionOrder = resolvedSectionOrder.filter(
          (sectionKey, index) =>
            typeof sectionKey === "string" &&
            sectionKey.length > 0 &&
            resolvedSectionOrder.indexOf(sectionKey) === index,
        );
        if (!dedupedSectionOrder.includes(STANDARDS_SECTION_KEY)) {
          dedupedSectionOrder.push(STANDARDS_SECTION_KEY);
        }
        setSectionOrder(dedupedSectionOrder);

        setUserEnabledSections(
          payload.template_sections.filter(
            (sectionKey) => sectionKey !== STANDARDS_SECTION_KEY,
          ),
        );
        setSelectedOverlayId(payload.overlay_id ?? "");
        setSelectedRoleId(
          payload.default_role_id ?? dfmConfig?.roles[0]?.role_id ?? "",
        );
        setTemplateName(payload.source === "custom" ? payload.label : "");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unexpected error while loading template details");
        }
      } finally {
        if (!cancelled) setLoadingTemplate(false);
      }
    };

    loadTemplate();
    return () => {
      cancelled = true;
    };
  }, [apiBase, dfmConfig?.roles, modelId, open, selectedTemplateId]);

  const toggleSection = (sectionKey: string) => {
    if (lockedSections.has(sectionKey)) return;
    setUserEnabledSections((current) => {
      if (current.includes(sectionKey)) {
        return current.filter((key) => key !== sectionKey);
      }
      return [...current, sectionKey];
    });
  };

  const handleSave = async () => {
    if (!modelId) {
      setError("Load a model before saving templates.");
      return;
    }
    if (!selectedTemplate) {
      setError("Select a template before saving.");
      return;
    }
    const trimmedName = templateName.trim();
    if (!trimmedName) {
      setError("Template name is required.");
      return;
    }

    const baseTemplateId =
      selectedTemplate.source === "bundle"
        ? selectedTemplate.template_id
        : selectedTemplate.base_template_id;

    setSaving(true);
    setError(null);
    setInfo(null);
    setValidationWarnings([]);
    try {
      const response = await fetch(`${apiBase}/api/models/${modelId}/dfm/templates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_name: trimmedName,
          base_template_id: baseTemplateId,
          overlay_id: selectedOverlayId || null,
          default_role_id: selectedRoleId || null,
          enabled_section_keys: enabledSections,
        }),
      });
      if (!response.ok) {
        throw new Error(await readErrorText(response, "Failed to save custom template"));
      }
      const payload = (await response.json()) as SaveTemplateResponse;
      setValidationWarnings(payload.validation_warnings ?? []);
      setInfo(`Saved template '${payload.label}'.`);
      const nextTemplates = await loadTemplateList(modelId);
      setSelectedTemplateId(payload.template_id);
      if (!nextTemplates.length) {
        setTemplates([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error while saving template");
    } finally {
      setSaving(false);
    }
  };

  const canSave =
    Boolean(modelId) &&
    Boolean(selectedTemplate) &&
    Boolean(templateName.trim()) &&
    Boolean(sectionOrder.length) &&
    !saving &&
    !loadingTemplate;

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="rep-sidebar">
        <div className="rep-sidebar__header">
          <h2>Report Template Builder</h2>
          <button type="button" onClick={onClose} className="rep-sidebar__close" aria-label="Close report template builder">
            x
          </button>
        </div>

        <label className="rep-sidebar__field">
          <span>{templateTypeLabel}</span>
          <select
            value={selectedTemplateId}
            onChange={(event) => setSelectedTemplateId(event.target.value)}
            disabled={loading || loadingTemplate || !templates.length}
          >
            {templates.map((template) => (
              <option key={template.template_id} value={template.template_id}>
                {template.label} {template.source === "custom" ? "(custom)" : ""}
              </option>
            ))}
          </select>
        </label>

        <label className="rep-sidebar__field">
          <span>{overlayLabel}</span>
          <select
            value={selectedOverlayId}
            onChange={(event) => setSelectedOverlayId(event.target.value)}
            disabled={loading || loadingTemplate}
          >
            <option value="">None</option>
            {(dfmConfig?.overlays ?? []).map((overlay) => (
              <option key={overlay.overlay_id} value={overlay.overlay_id}>
                {overlay.label}
              </option>
            ))}
          </select>
        </label>

        <label className="rep-sidebar__field">
          <span>{roleLabel}</span>
          <select
            value={selectedRoleId}
            onChange={(event) => setSelectedRoleId(event.target.value)}
            disabled={loading || loadingTemplate}
          >
            {(dfmConfig?.roles ?? []).map((role) => (
              <option key={role.role_id} value={role.role_id}>
                {role.label}
              </option>
            ))}
          </select>
        </label>

        <div className="rep-sidebar__save-row">
          <input
            type="text"
            value={templateName}
            onChange={(event) => setTemplateName(event.target.value)}
            placeholder="Template name"
            maxLength={80}
            disabled={loading || loadingTemplate || saving}
          />
          <button type="button" className="rep-sidebar__save-btn" onClick={handleSave} disabled={!canSave}>
            {saving ? "Saving..." : "Save"}
          </button>
        </div>

        <div className="rep-sidebar__section-tree">
          <h3>{sectionTreeLabel}</h3>
          <ul className="rep-sidebar__section-list">
            {sectionOrder.map((sectionKey) => {
              const isLocked = lockedSections.has(sectionKey);
              const isEnabled = enabledSections.includes(sectionKey);
              return (
                <li key={sectionKey} className={`rep-sidebar__section-item ${isLocked ? "rep-sidebar__section-item--locked" : ""}`}>
                  <label>
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      disabled={isLocked || loadingTemplate}
                      onChange={() => toggleSection(sectionKey)}
                    />
                    <span>{formatSectionLabel(sectionKey)}</span>
                  </label>
                </li>
              );
            })}
          </ul>
          <p className="rep-sidebar__hint">Standards list is auto-generated from findings, not selected.</p>
        </div>

        {validationWarnings.length ? (
          <div className="rep-sidebar__warnings">
            {validationWarnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        ) : null}

        {info ? <p className="rep-sidebar__info">{info}</p> : null}
        {error ? <p className="rep-sidebar__error">{error}</p> : null}
      </div>
    </aside>
  );
};

export default ReportTemplateBuilderSidebar;
