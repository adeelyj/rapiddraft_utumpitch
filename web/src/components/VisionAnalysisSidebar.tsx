import { useEffect, useMemo, useState } from "react";
import type { AnalysisFocusPayload } from "../types/analysis";
import type {
  VisionCriteria,
  VisionFinding,
  VisionProviderRoute,
  VisionProvidersResponse,
  VisionReportResponse,
  VisionViewSetResponse,
} from "../types/vision";

type VisionInputSource = {
  id: string;
  label: string;
  src: string;
};

type VisionAnalysisSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  selectedInputSources: VisionInputSource[];
  onFocusInModel?: (payload: AnalysisFocusPayload) => void;
  onClose: () => void;
};

type CriteriaProfile = "default" | "custom";

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

const customerStatusClass = (status: string | undefined): string => {
  if (status === "critical") return "vision-sidebar__status vision-sidebar__status--critical";
  if (status === "attention") return "vision-sidebar__status vision-sidebar__status--warning";
  if (status === "watch") return "vision-sidebar__status vision-sidebar__status--caution";
  return "vision-sidebar__status vision-sidebar__status--info";
};

const blobToDataUrl = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Failed to convert image blob to data URL."));
      }
    };
    reader.onerror = () => reject(new Error("Failed to read image blob."));
    reader.readAsDataURL(blob);
  });

const VisionAnalysisSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  selectedInputSources,
  onFocusInModel,
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
  const [promptOverride, setPromptOverride] = useState("");
  const [promptEditorOpen, setPromptEditorOpen] = useState(false);
  const [promptEditorDraft, setPromptEditorDraft] = useState("");

  const [report, setReport] = useState<VisionReportResponse | null>(null);
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeApiBase, setActiveApiBase] = useState<string>(apiBase);

  useEffect(() => {
    setActiveApiBase(apiBase);
  }, [apiBase]);

  useEffect(() => {
    setReport(null);
    setError(null);
  }, [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    if (criteriaProfile === "default") {
      setCriteria(cloneDefaultCriteria());
    }
  }, [criteriaProfile]);

  useEffect(() => {
    if (!promptEditorOpen) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPromptEditorOpen(false);
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("keydown", handleEscape);
    };
  }, [promptEditorOpen]);

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
  const hasAnySelectedImages = selectedInputSources.length > 0;
  const hasPromptOverride = promptOverride.trim().length > 0;

  const focusFindingInModel = (payload: {
    id: string;
    title: string;
    details?: string;
    severity?: string;
  }) => {
    if (!onFocusInModel) return;
    onFocusInModel({
      id: payload.id,
      source: "vision",
      title: payload.title,
      details: payload.details,
      severity: payload.severity,
      component_node_name: selectedComponent?.nodeName ?? report?.component_node_name ?? null,
    });
  };

  const resolveInputDataUrl = async (source: VisionInputSource): Promise<string> => {
    if (source.src.startsWith("data:image/")) {
      return source.src;
    }
    const response = await fetch(source.src);
    if (!response.ok) {
      throw new Error(`Failed to read selected input '${source.label}' (HTTP ${response.status}).`);
    }
    const blob = await response.blob();
    return blobToDataUrl(blob);
  };

  const handleOpenPromptEditor = () => {
    setPromptEditorDraft(promptOverride || report?.prompt_used || "");
    setPromptEditorOpen(true);
  };

  const handleSavePromptEditor = () => {
    setPromptOverride(promptEditorDraft);
    setPromptEditorOpen(false);
  };

  const handleResetPromptEditor = () => {
    setPromptOverride("");
    setPromptEditorDraft("");
    setPromptEditorOpen(false);
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
    if (!hasAnySelectedImages) {
      setError("Select at least one view/screenshot from the left Views panel.");
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

      const createViewSetPath = `/api/models/${modelId}/vision/view-sets`;
      const viewSetResponse = await runWithFallback(createViewSetPath, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ component_node_name: selectedComponent.nodeName }),
      });
      if (!viewSetResponse.ok) {
        const detail = await readErrorText(viewSetResponse, "Failed to prepare vision view set");
        throw new Error(`${detail} (HTTP ${viewSetResponse.status})`);
      }
      const viewSetPayload = (await viewSetResponse.json()) as VisionViewSetResponse;

      const pastedImages = await Promise.all(
        selectedInputSources.map(async (source, index) => ({
          name: source.label || `Selected image ${index + 1}`,
          data_url: await resolveInputDataUrl(source),
        })),
      );

      const path = `/api/models/${modelId}/vision/reports`;
      const promptOverrideForRequest = promptOverride.trim() ? promptOverride : undefined;
      const response = await runWithFallback(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          view_set_id: viewSetPayload.view_set_id,
          selected_view_names: [],
          pasted_images: pastedImages,
          criteria,
          provider: providerPayload,
          prompt_override: promptOverrideForRequest,
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

        <div className="vision-sidebar__assumptions">
          <h3>Selected Inputs (Views panel)</h3>
          <p>{selectedInputSources.length} image(s) selected for analysis.</p>
          {selectedInputSources.length ? (
            <ul>
              {selectedInputSources.map((source) => (
                <li key={source.id}>{source.label}</li>
              ))}
            </ul>
          ) : (
            <p className="vision-sidebar__hint">Open left Views tab and tick V on the views/screenshots to use.</p>
          )}
        </div>

        <div className="vision-sidebar__field">
          <span>Prompt</span>
          <div className="vision-sidebar__prompt-row">
            <button type="button" className="vision-sidebar__prompt-button" onClick={handleOpenPromptEditor}>
              Edit prompt
            </button>
            <span className="vision-sidebar__prompt-state">{hasPromptOverride ? "Custom" : "Default"}</span>
          </div>
        </div>

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
          disabled={runningAnalysis || !modelId || !selectedComponent || !routeCanRun || !hasAnySelectedImages}
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

            {report.customer_summary ? (
              <div className="vision-sidebar__customer-summary">
                <h3>Customer Summary</h3>
                <div className="vision-sidebar__customer-topline">
                  <span className={customerStatusClass(report.customer_summary.status)}>
                    {report.customer_summary.status}
                  </span>
                  <span className="vision-sidebar__chip">Confidence: {report.customer_summary.confidence}</span>
                </div>
                <p className="vision-sidebar__customer-headline">{report.customer_summary.headline}</p>
                {report.customer_summary.top_risks.length ? (
                  <div className="vision-sidebar__customer-risks">
                    <h4>Top risks</h4>
                    <ul>
                      {report.customer_summary.top_risks.map((risk, index) => (
                        <li key={`${index}_${risk}`}>{risk}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <p className="vision-sidebar__customer-next">
                  <strong>Recommended next step:</strong> {report.customer_summary.recommended_next_step}
                </p>
              </div>
            ) : null}

            {(report.customer_findings ?? []).length ? (
              <div className="vision-sidebar__customer-actions">
                <h3>Recommended Actions</h3>
                <div className="vision-sidebar__customer-cards">
                  {(report.customer_findings ?? []).map((item) => (
                    <article key={item.finding_id} className="vision-sidebar__customer-card">
                      <div className="vision-sidebar__customer-card-header">
                        <strong>{item.title}</strong>
                        <span className={severityClass(item.severity)}>{item.severity}</span>
                      </div>
                      <p>
                        <strong>Why it matters:</strong> {item.why_it_matters}
                      </p>
                      <p>
                        <strong>Action:</strong> {item.recommended_action}
                      </p>
                      <p>
                        <strong>Views:</strong> {item.source_views.join(", ") || "-"}
                      </p>
                      {item.refs?.length ? (
                        <p>
                          <strong>Standards:</strong> {item.refs.join(", ")}
                        </p>
                      ) : null}
                      <button
                        type="button"
                        className="analysis-focus-action"
                        onClick={() =>
                          focusFindingInModel({
                            id: item.finding_id,
                            title: item.title,
                            details: item.recommended_action,
                            severity: item.severity,
                          })
                        }
                      >
                        Show in model
                      </button>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}

            <details className="vision-sidebar__assumptions">
              <summary>Technical details</summary>

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
                          <td title={finding.description}>
                            <div className="vision-sidebar__finding-cell">
                              <span>{finding.description}</span>
                              <button
                                type="button"
                                className="analysis-focus-action"
                                onClick={() =>
                                  focusFindingInModel({
                                    id: finding.feature_id,
                                    title: finding.description,
                                    details: report.general_observations,
                                    severity: finding.severity,
                                  })
                                }
                              >
                                Show
                              </button>
                            </div>
                          </td>
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
            </details>
          </>
        ) : (
          <p className="vision-sidebar__hint">Select inputs in left Views panel, then run analysis here.</p>
        )}

        {promptEditorOpen ? (
          <div className="vision-sidebar__prompt-backdrop" role="dialog" aria-modal="true" aria-label="Vision prompt editor">
            <div className="vision-sidebar__prompt-modal">
              <div className="vision-sidebar__prompt-header">
                <h3>Vision Prompt Editor</h3>
                <button
                  type="button"
                  className="vision-sidebar__close"
                  onClick={() => setPromptEditorOpen(false)}
                  aria-label="Close prompt editor"
                >
                  x
                </button>
              </div>
              <p className="vision-sidebar__hint">
                Save a custom prompt override for this session. Leave empty to use the backend default prompt.
              </p>
              <textarea
                className="vision-sidebar__prompt-textarea"
                value={promptEditorDraft}
                onChange={(event) => setPromptEditorDraft(event.target.value)}
                placeholder="Using backend default prompt. Paste or edit custom prompt here."
              />
              <div className="vision-sidebar__prompt-actions">
                <button type="button" className="vision-sidebar__prompt-action" onClick={handleResetPromptEditor}>
                  Reset default
                </button>
                <button
                  type="button"
                  className="vision-sidebar__prompt-action"
                  onClick={() => setPromptEditorOpen(false)}
                >
                  Cancel
                </button>
                <button type="button" className="vision-sidebar__prompt-action vision-sidebar__prompt-action--primary" onClick={handleSavePromptEditor}>
                  Save
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {error ? <p className="vision-sidebar__error">{error}</p> : null}
      </div>
    </aside>
  );
};

export default VisionAnalysisSidebar;
