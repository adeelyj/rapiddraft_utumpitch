import { type ClipboardEvent, useEffect, useMemo, useState } from "react";
import type {
  VisionCriteria,
  VisionFinding,
  VisionProviderRoute,
  VisionProvidersResponse,
  VisionReportResponse,
  VisionViewSetResponse,
} from "../types/vision";

type VisionAnalysisSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  onClose: () => void;
};

type CriteriaProfile = "default" | "custom";
type GeneratedViewName = "x" | "y" | "z";

type PastedVisionImage = {
  id: string;
  label: string;
  dataUrl: string;
  selected: boolean;
};

const GENERATED_VIEW_NAMES: GeneratedViewName[] = ["x", "y", "z"];

const DEFAULT_CRITERIA: VisionCriteria = {
  checks: {
    internal_pocket_tight_corners: true,
    tool_access_risk: true,
    annotation_note_scan: true,
  },
  sensitivity: "medium",
  max_flagged_features: 8,
  confidence_threshold: "medium",
};

const cloneDefaultCriteria = (): VisionCriteria => ({
  checks: { ...DEFAULT_CRITERIA.checks },
  sensitivity: DEFAULT_CRITERIA.sensitivity,
  max_flagged_features: DEFAULT_CRITERIA.max_flagged_features,
  confidence_threshold: DEFAULT_CRITERIA.confidence_threshold,
});

const joinApiUrl = (base: string, path: string): string => {
  const normalizedBase = base.replace(/\/$/, "");
  if (!normalizedBase) return path;
  if (path.startsWith("http")) return path;
  return `${normalizedBase}${path}`;
};

const severityClass = (severity: VisionFinding["severity"]): string => {
  if (severity === "critical") return "vision-sidebar__status vision-sidebar__status--critical";
  if (severity === "warning") return "vision-sidebar__status vision-sidebar__status--warning";
  if (severity === "caution") return "vision-sidebar__status vision-sidebar__status--caution";
  return "vision-sidebar__status vision-sidebar__status--info";
};

const VisionAnalysisSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  onClose,
}: VisionAnalysisSidebarProps) => {
  const [criteriaProfile, setCriteriaProfile] = useState<CriteriaProfile>("default");
  const [criteriaExpanded, setCriteriaExpanded] = useState(true);
  const [criteria, setCriteria] = useState<VisionCriteria>(cloneDefaultCriteria());

  const [providers, setProviders] = useState<VisionProvidersResponse | null>(null);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [route, setRoute] = useState<VisionProviderRoute>("openai");
  const [modelOverride, setModelOverride] = useState("");
  const [baseUrlOverride, setBaseUrlOverride] = useState("");
  const [apiKeyOverride, setApiKeyOverride] = useState("");
  const [selectedGeneratedViews, setSelectedGeneratedViews] = useState<Record<GeneratedViewName, boolean>>({
    x: true,
    y: true,
    z: true,
  });
  const [pastedImages, setPastedImages] = useState<PastedVisionImage[]>([]);

  const [viewSet, setViewSet] = useState<VisionViewSetResponse | null>(null);
  const [report, setReport] = useState<VisionReportResponse | null>(null);

  const [generatingViews, setGeneratingViews] = useState(false);
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeApiBase, setActiveApiBase] = useState<string>(apiBase);

  useEffect(() => {
    setActiveApiBase(apiBase);
  }, [apiBase]);

  useEffect(() => {
    setViewSet(null);
    setReport(null);
    setError(null);
    setSelectedGeneratedViews({ x: true, y: true, z: true });
    setPastedImages([]);
  }, [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    if (criteriaProfile === "default") {
      setCriteria(cloneDefaultCriteria());
    }
  }, [criteriaProfile]);

  useEffect(() => {
    if (!open || !modelId) return;

    let cancelled = false;
    const loadProviders = async () => {
      setLoadingProviders(true);
      setError(null);
      try {
        const path = `/api/models/${modelId}/vision/providers`;
        const response = await runWithFallback(path, {
          method: "GET",
        });
        if (!response.ok) {
          const detail = await readErrorText(response, "Failed to load vision providers");
          throw new Error(`${detail} (HTTP ${response.status})`);
        }
        const payload = (await response.json()) as VisionProvidersResponse;
        if (cancelled) return;

        setProviders(payload);
        setRoute(payload.default_provider);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Unexpected error while loading providers");
      } finally {
        if (!cancelled) setLoadingProviders(false);
      }
    };

    loadProviders();
    return () => {
      cancelled = true;
    };
  }, [apiBase, modelId, open]);

  const readErrorText = async (response: Response, fallback: string): Promise<string> => {
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      return payload.detail ?? payload.message ?? fallback;
    } catch {
      return fallback;
    }
  };

  const runWithFallback = async (path: string, init: RequestInit): Promise<Response> => {
    try {
      const response = await fetch(joinApiUrl(apiBase, path), init);
      setActiveApiBase(apiBase);
      return response;
    } catch {
      const response = await fetch(path, init);
      setActiveApiBase("");
      return response;
    }
  };

  const viewUrls = useMemo(() => {
    if (!viewSet) return null;
    return {
      x: joinApiUrl(activeApiBase, viewSet.views.x),
      y: joinApiUrl(activeApiBase, viewSet.views.y),
      z: joinApiUrl(activeApiBase, viewSet.views.z),
    };
  }, [activeApiBase, viewSet]);

  const routeConfigured = useMemo(() => {
    if (!providers) return true;
    const found = providers.providers.find((entry) => entry.id === route);
    return found ? found.configured : true;
  }, [providers, route]);

  const routeCanRun = routeConfigured || Boolean(modelOverride.trim()) || Boolean(apiKeyOverride.trim());
  const routeDefaultBaseUrl = useMemo(() => {
    const configuredDefault = providers?.provider_defaults?.[route]?.base_url;
    if (configuredDefault && configuredDefault.trim()) return configuredDefault;

    if (route === "openai") return "https://api.openai.com/v1";
    if (route === "claude") return "https://api.anthropic.com";
    if (route === "local") return providers?.local_defaults?.base_url ?? "http://127.0.0.1:1234/v1";
    return "";
  }, [providers, route]);
  const selectedGeneratedViewNames = useMemo(
    () => GENERATED_VIEW_NAMES.filter((viewName) => selectedGeneratedViews[viewName]),
    [selectedGeneratedViews],
  );
  const selectedPastedImages = useMemo(
    () => pastedImages.filter((image) => image.selected),
    [pastedImages],
  );
  const hasAnySelectedImages = selectedGeneratedViewNames.length > 0 || selectedPastedImages.length > 0;

  const toggleGeneratedView = (viewName: GeneratedViewName, checked: boolean) => {
    setSelectedGeneratedViews((prev) => ({ ...prev, [viewName]: checked }));
  };

  const togglePastedImage = (id: string, checked: boolean) => {
    setPastedImages((prev) =>
      prev.map((image) =>
        image.id === id
          ? {
              ...image,
              selected: checked,
            }
          : image,
      ),
    );
  };

  const removePastedImage = (id: string) => {
    setPastedImages((prev) => prev.filter((image) => image.id !== id));
  };

  const appendPastedImage = (dataUrl: string, fileNameHint?: string) => {
    if (!dataUrl.startsWith("data:image/")) {
      setError("Clipboard data is not a supported image.");
      return;
    }
    setPastedImages((prev) => {
      const nextIndex = prev.length + 1;
      const fallbackLabel = `Screenshot ${nextIndex}`;
      const trimmedName = (fileNameHint ?? "").trim();
      const label = trimmedName ? trimmedName : fallbackLabel;
      const id =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `shot_${Date.now()}_${nextIndex}`;
      return [
        ...prev,
        {
          id,
          label,
          dataUrl,
          selected: true,
        },
      ];
    });
  };

  const handlePasteScreenshot = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(event.clipboardData?.items ?? []);
    const imageItem = items.find((item) => item.type.startsWith("image/"));
    if (!imageItem) return;

    const file = imageItem.getAsFile();
    if (!file) return;
    event.preventDefault();
    setError(null);

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        setError("Failed to read pasted image.");
        return;
      }
      appendPastedImage(result, file.name);
    };
    reader.onerror = () => {
      setError("Failed to read pasted image.");
    };
    reader.readAsDataURL(file);
  };

  const setCheck = (key: keyof VisionCriteria["checks"], checked: boolean) => {
    setCriteria((prev) => ({
      ...prev,
      checks: {
        ...prev.checks,
        [key]: checked,
      },
    }));
  };

  const setCriteriaNumber = (key: keyof VisionCriteria, raw: string) => {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    if (key !== "max_flagged_features") return;
    setCriteria((prev) => ({
      ...prev,
      max_flagged_features: Math.max(1, Math.min(50, Math.round(value))),
    }));
  };

  const criteriaEditable = criteriaProfile === "custom";

  const handleGenerateViews = async () => {
    if (!modelId) {
      setError("Load a model before generating vision views.");
      return;
    }
    if (!selectedComponent) {
      setError("Select a part from the assembly tree before generating vision views.");
      return;
    }

    setGeneratingViews(true);
    setError(null);
    setReport(null);

    try {
      const path = `/api/models/${modelId}/vision/view-sets`;
      const response = await runWithFallback(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ component_node_name: selectedComponent.nodeName }),
      });

      if (!response.ok) {
        const detail = await readErrorText(response, "Failed to generate vision view set");
        throw new Error(`${detail} (HTTP ${response.status})`);
      }

      const payload = (await response.json()) as VisionViewSetResponse;
      setViewSet(payload);
      setSelectedGeneratedViews({ x: true, y: true, z: true });
    } catch (err) {
      if (err instanceof TypeError) {
        setError(
          `Network error contacting API. Verify backend reachability and VITE_API_BASE_URL (current: ${apiBase || "same-origin"}).`,
        );
      } else {
        setError(err instanceof Error ? err.message : "Unexpected error while generating view set");
      }
    } finally {
      setGeneratingViews(false);
    }
  };

  const handleConductAnalysis = async () => {
    if (!modelId) {
      setError("Load a model before running vision analysis.");
      return;
    }
    if (!selectedComponent) {
      setError("Select a part from the assembly tree before running vision analysis.");
      return;
    }
    if (!viewSet) {
      setError("Generate views first before conducting analysis.");
      return;
    }
    if (!hasAnySelectedImages) {
      setError("Select at least one generated or pasted image before conducting analysis.");
      return;
    }

    setRunningAnalysis(true);
    setError(null);

    try {
      const providerPayload: {
        route: VisionProviderRoute;
        model_override?: string;
        base_url_override?: string;
        api_key_override?: string;
        local_base_url?: string;
      } = {
        route,
      };

      if (modelOverride.trim()) providerPayload.model_override = modelOverride.trim();
      if (baseUrlOverride.trim()) providerPayload.base_url_override = baseUrlOverride.trim();
      if (apiKeyOverride.trim()) providerPayload.api_key_override = apiKeyOverride.trim();
      if (route === "local" && baseUrlOverride.trim()) providerPayload.local_base_url = baseUrlOverride.trim();

      const path = `/api/models/${modelId}/vision/reports`;
      const response = await runWithFallback(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          view_set_id: viewSet.view_set_id,
          selected_view_names: selectedGeneratedViewNames,
          pasted_images: selectedPastedImages.map((image) => ({
            name: image.label,
            data_url: image.dataUrl,
          })),
          criteria,
          provider: providerPayload,
        }),
      });

      if (!response.ok) {
        const detail = await readErrorText(response, "Failed to conduct vision analysis");
        throw new Error(`${detail} (HTTP ${response.status})`);
      }

      const payload = (await response.json()) as VisionReportResponse;
      setReport(payload);
    } catch (err) {
      if (err instanceof TypeError) {
        setError(
          `Network error contacting API. Verify backend reachability and VITE_API_BASE_URL (current: ${apiBase || "same-origin"}).`,
        );
      } else {
        setError(err instanceof Error ? err.message : "Unexpected error during vision analysis");
      }
    } finally {
      setRunningAnalysis(false);
    }
  };

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="vision-sidebar">
        <div className="vision-sidebar__header">
          <h2>Vision Analysis</h2>
          <button type="button" onClick={onClose} className="vision-sidebar__close" aria-label="Close Vision panel">
            x
          </button>
        </div>

        <div className="vision-sidebar__field">
          <span>Selected part</span>
          <div className="vision-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>

        <button
          type="button"
          className="vision-sidebar__submit"
          onClick={handleGenerateViews}
          disabled={generatingViews || runningAnalysis || !modelId || !selectedComponent}
        >
          {generatingViews ? "Generating views..." : "Generate Views"}
        </button>

        {viewUrls ? (
          <div className="vision-sidebar__thumb-grid">
            {GENERATED_VIEW_NAMES.map((viewName) => (
              <div className="vision-sidebar__thumb-card" key={viewName}>
                <label className="vision-sidebar__thumb-select">
                  <input
                    type="checkbox"
                    checked={selectedGeneratedViews[viewName]}
                    onChange={(event) => toggleGeneratedView(viewName, event.target.checked)}
                  />
                  <span>{viewName.toUpperCase()}</span>
                </label>
                <img src={viewUrls[viewName]} alt={`Vision ${viewName.toUpperCase()} view`} />
              </div>
            ))}
          </div>
        ) : (
          <p className="vision-sidebar__hint">Generate a frozen x/y/z view set first.</p>
        )}

        <label className="vision-sidebar__field">
          <span>Paste screenshot (optional)</span>
          <textarea
            className="vision-sidebar__criteria-input vision-sidebar__paste-target"
            rows={3}
            onPaste={handlePasteScreenshot}
            placeholder="Click here and paste image from clipboard (Ctrl+V)."
          />
          <p className="vision-sidebar__hint">
            Paste one or more screenshots, then check which generated/pasted images to send to the model.
          </p>
        </label>

        {pastedImages.length ? (
          <div className="vision-sidebar__thumb-grid vision-sidebar__thumb-grid--pasted">
            {pastedImages.map((image) => (
              <div className="vision-sidebar__thumb-card" key={image.id}>
                <label className="vision-sidebar__thumb-select">
                  <input
                    type="checkbox"
                    checked={image.selected}
                    onChange={(event) => togglePastedImage(image.id, event.target.checked)}
                  />
                  <span>{image.label}</span>
                </label>
                <button
                  type="button"
                  className="vision-sidebar__thumb-remove"
                  onClick={() => removePastedImage(image.id)}
                >
                  Remove
                </button>
                <img src={image.dataUrl} alt={`Pasted screenshot ${image.label}`} />
              </div>
            ))}
          </div>
        ) : null}

        <label className="vision-sidebar__field">
          <span>Criteria profile</span>
          <select
            value={criteriaProfile}
            onChange={(event) => setCriteriaProfile(event.target.value as CriteriaProfile)}
          >
            <option value="default">Default Vision Criteria</option>
            <option value="custom">Custom Vision Criteria</option>
          </select>
        </label>

        <button
          type="button"
          className="vision-sidebar__criteria-toggle"
          onClick={() => setCriteriaExpanded((prev) => !prev)}
        >
          <span>Vision Criteria</span>
          <span>{criteriaExpanded ? "v" : ">"}</span>
        </button>

        {criteriaExpanded ? (
          <div className="vision-sidebar__criteria-card">
            <h3>Checks</h3>
            <label className="vision-sidebar__toggle">
              <input
                type="checkbox"
                checked={criteria.checks.internal_pocket_tight_corners}
                disabled={!criteriaEditable}
                onChange={(event) => setCheck("internal_pocket_tight_corners", event.target.checked)}
              />
              <span>Internal pocket tight corners</span>
            </label>
            <label className="vision-sidebar__toggle">
              <input
                type="checkbox"
                checked={criteria.checks.tool_access_risk}
                disabled={!criteriaEditable}
                onChange={(event) => setCheck("tool_access_risk", event.target.checked)}
              />
              <span>Tool access risk</span>
            </label>
            <label className="vision-sidebar__toggle">
              <input
                type="checkbox"
                checked={criteria.checks.annotation_note_scan}
                disabled={!criteriaEditable}
                onChange={(event) => setCheck("annotation_note_scan", event.target.checked)}
              />
              <span>Annotation/note scan</span>
            </label>

            <h3>Output Controls</h3>
            <label className="vision-sidebar__field">
              <span>Sensitivity</span>
              <select
                value={criteria.sensitivity}
                disabled={!criteriaEditable}
                onChange={(event) =>
                  setCriteria((prev) => ({ ...prev, sensitivity: event.target.value as VisionCriteria["sensitivity"] }))
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label className="vision-sidebar__field">
              <span>Confidence threshold</span>
              <select
                value={criteria.confidence_threshold}
                disabled={!criteriaEditable}
                onChange={(event) =>
                  setCriteria((prev) => ({
                    ...prev,
                    confidence_threshold: event.target.value as VisionCriteria["confidence_threshold"],
                  }))
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label className="vision-sidebar__field">
              <span>Max flagged features</span>
              <input
                className="vision-sidebar__criteria-input"
                type="number"
                min={1}
                max={50}
                value={criteria.max_flagged_features}
                disabled={!criteriaEditable}
                onChange={(event) => setCriteriaNumber("max_flagged_features", event.target.value)}
              />
            </label>
          </div>
        ) : null}

        <label className="vision-sidebar__field">
          <span>Analysis route</span>
          <select
            value={route}
            onChange={(event) => setRoute(event.target.value as VisionProviderRoute)}
            disabled={loadingProviders}
          >
            {(providers?.providers ?? [
              { id: "openai", label: "OpenAI", configured: true, default_model: "" },
              { id: "claude", label: "Claude", configured: true, default_model: "" },
              { id: "local", label: "Local LM Studio", configured: true, default_model: "" },
            ]).map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.label} {provider.configured ? "" : "(Not configured)"}
              </option>
            ))}
          </select>
        </label>

        <label className="vision-sidebar__field">
          <span>Model override (optional)</span>
          <input
            className="vision-sidebar__criteria-input"
            type="text"
            value={modelOverride}
            onChange={(event) => setModelOverride(event.target.value)}
            placeholder="Use provider default if blank"
          />
        </label>

        <label className="vision-sidebar__field">
          <span>Endpoint base URL (optional override)</span>
          <input
            className="vision-sidebar__criteria-input"
            type="text"
            value={baseUrlOverride}
            onChange={(event) => setBaseUrlOverride(event.target.value)}
            placeholder={routeDefaultBaseUrl}
          />
          <p className="vision-sidebar__hint">By default API key is read from backend env.</p>
        </label>

        <label className="vision-sidebar__field">
          <span>API key override (optional)</span>
          <input
            className="vision-sidebar__criteria-input"
            type="password"
            value={apiKeyOverride}
            onChange={(event) => setApiKeyOverride(event.target.value)}
            placeholder="Paste provider API key for this run"
            autoComplete="off"
          />
          <p className="vision-sidebar__hint">Hidden input. Used only for this request.</p>
        </label>

        <button
          type="button"
          className="vision-sidebar__submit"
          onClick={handleConductAnalysis}
          disabled={
            runningAnalysis ||
            generatingViews ||
            !viewSet ||
            !modelId ||
            !selectedComponent ||
            !routeCanRun ||
            !hasAnySelectedImages
          }
        >
          {runningAnalysis ? "Conducting analysis..." : "Conduct Analysis"}
        </button>

        {report ? (
          <>
            <div className="vision-sidebar__summary">
              <div className="vision-sidebar__chip">Flagged: {report.summary.flagged_count}</div>
              <div className="vision-sidebar__chip">Confidence: {report.summary.confidence}</div>
              <div className="vision-sidebar__chip">Route: {report.provider_applied.route_used}</div>
              <div className="vision-sidebar__chip">Model: {report.provider_applied.model_used}</div>
            </div>

            <div className="vision-sidebar__table-wrap">
              <table className="vision-sidebar__table">
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Severity</th>
                    <th>Confidence</th>
                    <th>Views</th>
                  </tr>
                </thead>
                <tbody>
                  {report.findings.length ? (
                    report.findings.map((finding) => (
                      <tr key={finding.feature_id}>
                        <td title={finding.description}>{finding.description}</td>
                        <td>
                          <span className={severityClass(finding.severity)}>{finding.severity}</span>
                        </td>
                        <td>{finding.confidence}</td>
                        <td>{finding.source_views.join(", ") || "-"}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4}>No findings passed current criteria filters.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {report.general_observations ? (
              <div className="vision-sidebar__assumptions">
                <h3>General Observations</h3>
                <p>{report.general_observations}</p>
              </div>
            ) : null}

            <div className="vision-sidebar__assumptions">
              <h3>Applied Criteria (Engine Echo)</h3>
              <ul>
                <li>Internal pocket tight corners: {report.criteria_applied.checks.internal_pocket_tight_corners ? "on" : "off"}</li>
                <li>Tool access risk: {report.criteria_applied.checks.tool_access_risk ? "on" : "off"}</li>
                <li>Annotation scan: {report.criteria_applied.checks.annotation_note_scan ? "on" : "off"}</li>
                <li>Sensitivity: {report.criteria_applied.sensitivity}</li>
                <li>Confidence threshold: {report.criteria_applied.confidence_threshold}</li>
                <li>Max findings: {report.criteria_applied.max_flagged_features}</li>
              </ul>
            </div>

            <div className="vision-sidebar__assumptions">
              <h3>Provider Echo</h3>
              <ul>
                <li>Requested route: {report.provider_applied.route_requested}</li>
                <li>Used route: {report.provider_applied.route_used}</li>
                <li>Model: {report.provider_applied.model_used}</li>
                <li>Base URL: {report.provider_applied.base_url_used}</li>
              </ul>
            </div>

            <div className="vision-sidebar__assumptions">
              <h3>Raw Model Output</h3>
              <pre className="vision-sidebar__raw-output">
                {report.raw_output_text?.trim() || "No raw provider output captured for this run."}
              </pre>
            </div>
          </>
        ) : (
          <p className="vision-sidebar__hint">Generate a view set, then conduct vision analysis.</p>
        )}

        {error ? <p className="vision-sidebar__error">{error}</p> : null}
      </div>
    </aside>
  );
};

export default VisionAnalysisSidebar;


