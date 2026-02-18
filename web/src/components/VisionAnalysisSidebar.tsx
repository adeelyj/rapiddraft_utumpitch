import { useEffect, useMemo, useState } from "react";
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
  const [localBaseUrl, setLocalBaseUrl] = useState("");

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
        setLocalBaseUrl(payload.local_defaults?.base_url ?? "http://127.0.0.1:1234/v1");
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

  const routeCanRun = routeConfigured || Boolean(modelOverride.trim());

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

    setRunningAnalysis(true);
    setError(null);

    try {
      const providerPayload: {
        route: VisionProviderRoute;
        model_override?: string;
        local_base_url?: string;
      } = {
        route,
      };

      if (modelOverride.trim()) providerPayload.model_override = modelOverride.trim();
      if (route === "local" && localBaseUrl.trim()) providerPayload.local_base_url = localBaseUrl.trim();

      const path = `/api/models/${modelId}/vision/reports`;
      const response = await runWithFallback(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          view_set_id: viewSet.view_set_id,
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
            <div className="vision-sidebar__thumb-card">
              <span>X</span>
              <img src={viewUrls.x} alt="Vision X view" />
            </div>
            <div className="vision-sidebar__thumb-card">
              <span>Y</span>
              <img src={viewUrls.y} alt="Vision Y view" />
            </div>
            <div className="vision-sidebar__thumb-card">
              <span>Z</span>
              <img src={viewUrls.z} alt="Vision Z view" />
            </div>
          </div>
        ) : (
          <p className="vision-sidebar__hint">Generate a frozen x/y/z view set first.</p>
        )}

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

        {route === "local" ? (
          <label className="vision-sidebar__field">
            <span>Local base URL (optional override)</span>
            <input
              className="vision-sidebar__criteria-input"
              type="text"
              value={localBaseUrl}
              onChange={(event) => setLocalBaseUrl(event.target.value)}
              placeholder="http://127.0.0.1:1234/v1"
            />
          </label>
        ) : null}

        <button
          type="button"
          className="vision-sidebar__submit"
          onClick={handleConductAnalysis}
          disabled={runningAnalysis || generatingViews || !viewSet || !modelId || !selectedComponent || !routeCanRun}
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
