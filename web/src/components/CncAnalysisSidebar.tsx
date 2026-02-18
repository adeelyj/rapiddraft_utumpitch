import { useEffect, useMemo, useState } from "react";
import type {
  CncGeometryCorner,
  CncGeometryCriteria,
  CncGeometryReportResponse,
} from "../types/cnc";

type CncAnalysisSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  onClose: () => void;
};

const formatRadius = (radius: number | null): string => {
  if (radius === null || !Number.isFinite(radius)) return "-";
  return `R${radius.toFixed(3)} mm`;
};

const formatRatio = (ratio: number | null): string => {
  if (ratio === null || !Number.isFinite(ratio)) return "-";
  return ratio.toFixed(2);
};

const cornerStatusClass = (status: CncGeometryCorner["status"]): string => {
  if (status === "CRITICAL") return "cnc-sidebar__status cnc-sidebar__status--critical";
  if (status === "WARNING") return "cnc-sidebar__status cnc-sidebar__status--warning";
  if (status === "CAUTION") return "cnc-sidebar__status cnc-sidebar__status--caution";
  return "cnc-sidebar__status cnc-sidebar__status--ok";
};

const joinApiUrl = (base: string, path: string): string => {
  const normalizedBase = base.replace(/\/$/, "");
  if (!normalizedBase) return path;
  if (path.startsWith("http")) return path;
  return `${normalizedBase}${path}`;
};

const DEFAULT_CRITERIA: CncGeometryCriteria = {
  thresholds: {
    critical_enabled: true,
    critical_max_mm: 0.0001,
    warning_enabled: true,
    warning_max_mm: 1.5,
    caution_enabled: true,
    caution_max_mm: 3.0,
    ok_enabled: true,
    ok_min_mm: 3.0,
  },
  filters: {
    concave_internal_edges_only: true,
    pocket_internal_cavity_heuristic: true,
    exclude_bbox_exterior_edges: true,
    include_ok_rows_in_output: false,
  },
  aggravating_factor_ratio_threshold: 5.0,
};

const cloneDefaultCriteria = (): CncGeometryCriteria => ({
  thresholds: { ...DEFAULT_CRITERIA.thresholds },
  filters: { ...DEFAULT_CRITERIA.filters },
  aggravating_factor_ratio_threshold: DEFAULT_CRITERIA.aggravating_factor_ratio_threshold,
});

type CriteriaProfile = "default" | "custom";

const CncAnalysisSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  onClose,
}: CncAnalysisSidebarProps) => {
  const [criteriaProfile, setCriteriaProfile] = useState<CriteriaProfile>("default");
  const [criteriaExpanded, setCriteriaExpanded] = useState(true);
  const [criteria, setCriteria] = useState<CncGeometryCriteria>(cloneDefaultCriteria());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<CncGeometryReportResponse | null>(null);
  const [activeApiBase, setActiveApiBase] = useState<string>(apiBase);

  useEffect(() => {
    setReport(null);
    setError(null);
  }, [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    setActiveApiBase(apiBase);
  }, [apiBase]);

  useEffect(() => {
    if (criteriaProfile === "default") {
      setCriteria(cloneDefaultCriteria());
    }
  }, [criteriaProfile]);

  const pdfDownloadUrl = useMemo(() => {
    if (!report?.pdf_url) return null;
    return report.pdf_url.startsWith("http")
      ? report.pdf_url
      : joinApiUrl(activeApiBase, report.pdf_url);
  }, [activeApiBase, report?.pdf_url]);

  const readErrorText = async (response: Response, fallback: string) => {
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      return payload.detail ?? payload.message ?? fallback;
    } catch {
      return fallback;
    }
  };

  const setThresholdEnabled = (
    key: keyof CncGeometryCriteria["thresholds"],
    checked: boolean,
  ) => {
    setCriteria((prev) => ({
      ...prev,
      thresholds: {
        ...prev.thresholds,
        [key]: checked,
      },
    }));
  };

  const setThresholdValue = (
    key: keyof CncGeometryCriteria["thresholds"],
    rawValue: string,
  ) => {
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) return;
    setCriteria((prev) => ({
      ...prev,
      thresholds: {
        ...prev.thresholds,
        [key]: parsed,
      },
    }));
  };

  const setFilterValue = (
    key: keyof CncGeometryCriteria["filters"],
    checked: boolean,
  ) => {
    setCriteria((prev) => ({
      ...prev,
      filters: {
        ...prev.filters,
        [key]: checked,
      },
    }));
  };

  const setAggravatingFactorValue = (rawValue: string) => {
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) return;
    setCriteria((prev) => ({
      ...prev,
      aggravating_factor_ratio_threshold: parsed,
    }));
  };

  const criteriaEditable = criteriaProfile === "custom";

  const runAnalysis = async () => {
    if (!modelId) {
      setError("Load a model before running CNC analysis.");
      return;
    }
    if (!selectedComponent) {
      setError("Select a part from the assembly tree before running CNC analysis.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const path = `/api/models/${modelId}/cnc/geometry-report`;
      const requestBody = JSON.stringify({
        component_node_name: selectedComponent.nodeName,
        include_ok_rows: Boolean(criteria.filters.include_ok_rows_in_output),
        criteria,
      });
      const runRequest = async (url: string) =>
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: requestBody,
        });

      let response: Response;
      try {
        response = await runRequest(joinApiUrl(apiBase, path));
        setActiveApiBase(apiBase);
      } catch {
        // Retry on same-origin path when configured apiBase is unreachable.
        response = await runRequest(path);
        setActiveApiBase("");
      }

      if (!response.ok) {
        const detail = await readErrorText(response, "Failed to generate CNC geometry report");
        throw new Error(`${detail} (HTTP ${response.status})`);
      }
      const payload = (await response.json()) as CncGeometryReportResponse;
      setReport(payload);
    } catch (err) {
      if (err instanceof TypeError) {
        setError(
          `Network error contacting API. Verify backend reachability and VITE_API_BASE_URL (current: ${apiBase || "same-origin"}).`,
        );
      } else {
        setError(err instanceof Error ? err.message : "Unexpected error while generating CNC report");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="cnc-sidebar">
        <div className="cnc-sidebar__header">
          <h2>CNC Geometry Analysis</h2>
          <button type="button" onClick={onClose} className="cnc-sidebar__close" aria-label="Close CNC panel">
            x
          </button>
        </div>

        <div className="cnc-sidebar__field">
          <span>Selected part</span>
          <div className="cnc-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>

        <label className="cnc-sidebar__field">
          <span>Criteria profile</span>
          <select
            value={criteriaProfile}
            onChange={(event) => setCriteriaProfile(event.target.value as CriteriaProfile)}
          >
            <option value="default">Default CNC Rule Set</option>
            <option value="custom">Custom CNC Rule Set</option>
          </select>
        </label>

        <button
          type="button"
          className="cnc-sidebar__criteria-toggle"
          onClick={() => setCriteriaExpanded((prev) => !prev)}
        >
          <span>Geometry Criteria</span>
          <span>{criteriaExpanded ? "v" : ">"}</span>
        </button>

        {criteriaExpanded ? (
          <div className="cnc-sidebar__criteria-card">
            <h3>Status thresholds (mm)</h3>
            <div className="cnc-sidebar__criteria-grid">
              <label className="cnc-sidebar__criteria-row">
                <input
                  type="checkbox"
                  checked={criteria.thresholds.critical_enabled}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdEnabled("critical_enabled", event.target.checked)}
                />
                <span>CRITICAL {"<="}</span>
                <input
                  className="cnc-sidebar__criteria-input"
                  type="number"
                  step="0.0001"
                  min="0"
                  value={criteria.thresholds.critical_max_mm}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdValue("critical_max_mm", event.target.value)}
                />
              </label>
              <label className="cnc-sidebar__criteria-row">
                <input
                  type="checkbox"
                  checked={criteria.thresholds.warning_enabled}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdEnabled("warning_enabled", event.target.checked)}
                />
                <span>WARNING {"<"}</span>
                <input
                  className="cnc-sidebar__criteria-input"
                  type="number"
                  step="0.1"
                  min="0"
                  value={criteria.thresholds.warning_max_mm}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdValue("warning_max_mm", event.target.value)}
                />
              </label>
              <label className="cnc-sidebar__criteria-row">
                <input
                  type="checkbox"
                  checked={criteria.thresholds.caution_enabled}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdEnabled("caution_enabled", event.target.checked)}
                />
                <span>CAUTION {"<"}</span>
                <input
                  className="cnc-sidebar__criteria-input"
                  type="number"
                  step="0.1"
                  min="0"
                  value={criteria.thresholds.caution_max_mm}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdValue("caution_max_mm", event.target.value)}
                />
              </label>
              <label className="cnc-sidebar__criteria-row">
                <input
                  type="checkbox"
                  checked={criteria.thresholds.ok_enabled}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdEnabled("ok_enabled", event.target.checked)}
                />
                <span>OK {">="}</span>
                <input
                  className="cnc-sidebar__criteria-input"
                  type="number"
                  step="0.1"
                  min="0"
                  value={criteria.thresholds.ok_min_mm}
                  disabled={!criteriaEditable}
                  onChange={(event) => setThresholdValue("ok_min_mm", event.target.value)}
                />
              </label>
            </div>

            <h3>Feature filters</h3>
            <label className="cnc-sidebar__toggle">
              <input
                type="checkbox"
                checked={criteria.filters.concave_internal_edges_only}
                disabled={!criteriaEditable}
                onChange={(event) => setFilterValue("concave_internal_edges_only", event.target.checked)}
              />
              <span>Concave internal edges only</span>
            </label>
            <label className="cnc-sidebar__toggle">
              <input
                type="checkbox"
                checked={criteria.filters.pocket_internal_cavity_heuristic}
                disabled={!criteriaEditable}
                onChange={(event) => setFilterValue("pocket_internal_cavity_heuristic", event.target.checked)}
              />
              <span>Pocket/internal cavity heuristic</span>
            </label>
            <label className="cnc-sidebar__toggle">
              <input
                type="checkbox"
                checked={criteria.filters.exclude_bbox_exterior_edges}
                disabled={!criteriaEditable}
                onChange={(event) => setFilterValue("exclude_bbox_exterior_edges", event.target.checked)}
              />
              <span>Exclude bbox exterior edges</span>
            </label>
            <label className="cnc-sidebar__toggle">
              <input
                type="checkbox"
                checked={Boolean(criteria.filters.include_ok_rows_in_output)}
                disabled={!criteriaEditable}
                onChange={(event) => setFilterValue("include_ok_rows_in_output", event.target.checked)}
              />
              <span>Include OK rows in output</span>
            </label>

            <label className="cnc-sidebar__criteria-aggr">
              <span>Aggravating factor ratio {">"}</span>
              <input
                className="cnc-sidebar__criteria-input"
                type="number"
                step="0.1"
                min="0"
                value={criteria.aggravating_factor_ratio_threshold}
                disabled={!criteriaEditable}
                onChange={(event) => setAggravatingFactorValue(event.target.value)}
              />
            </label>
          </div>
        ) : null}

        <button
          type="button"
          className="cnc-sidebar__submit"
          onClick={runAnalysis}
          disabled={submitting || !modelId || !selectedComponent}
        >
          {submitting ? "Running..." : "Run Analysis"}
        </button>

        {report ? (
          <>
            <div className="cnc-sidebar__summary">
              <div className="cnc-sidebar__chip">Critical: {report.summary.critical_count}</div>
              <div className="cnc-sidebar__chip">Warning: {report.summary.warning_count}</div>
              <div className="cnc-sidebar__chip">Caution: {report.summary.caution_count}</div>
              <div className="cnc-sidebar__chip">OK: {report.summary.ok_count}</div>
              <div className="cnc-sidebar__chip">Score: {report.summary.machinability_score}</div>
              <div className="cnc-sidebar__chip">Cost: {report.summary.cost_impact}</div>
            </div>

            <div className="cnc-sidebar__table-wrap">
              <table className="cnc-sidebar__table">
                <thead>
                  <tr>
                    <th>Corner</th>
                    <th>Radius</th>
                    <th>Status</th>
                    <th>Depth</th>
                    <th>D/R</th>
                  </tr>
                </thead>
                <tbody>
                  {report.corners.length ? (
                    report.corners.map((corner) => (
                      <tr key={corner.corner_id}>
                        <td title={corner.location_description}>{corner.corner_id}</td>
                        <td>{formatRadius(corner.radius_mm)}</td>
                        <td>
                          <span className={cornerStatusClass(corner.status)}>{corner.status}</span>
                        </td>
                        <td>{corner.pocket_depth_mm === null ? "-" : `${corner.pocket_depth_mm.toFixed(2)} mm`}</td>
                        <td>{formatRatio(corner.depth_to_radius_ratio)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5}>No corners in current filter.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {pdfDownloadUrl ? (
              <a className="cnc-sidebar__download" href={pdfDownloadUrl} target="_blank" rel="noreferrer">
                Download PDF
              </a>
            ) : null}

            {report.criteria_applied ? (
              <div className="cnc-sidebar__assumptions">
                <h3>Applied Criteria (Engine Echo)</h3>
                <ul>
                  <li>
                    CRITICAL {"<="} {report.criteria_applied.thresholds.critical_max_mm} (
                    {report.criteria_applied.thresholds.critical_enabled ? "on" : "off"})
                  </li>
                  <li>
                    WARNING {"<"} {report.criteria_applied.thresholds.warning_max_mm} (
                    {report.criteria_applied.thresholds.warning_enabled ? "on" : "off"})
                  </li>
                  <li>
                    CAUTION {"<"} {report.criteria_applied.thresholds.caution_max_mm} (
                    {report.criteria_applied.thresholds.caution_enabled ? "on" : "off"})
                  </li>
                  <li>
                    OK {">="} {report.criteria_applied.thresholds.ok_min_mm} (
                    {report.criteria_applied.thresholds.ok_enabled ? "on" : "off"})
                  </li>
                  <li>Aggravating ratio {">"} {report.criteria_applied.aggravating_factor_ratio_threshold}</li>
                </ul>
              </div>
            ) : null}

            {report.assumptions.length ? (
              <div className="cnc-sidebar__assumptions">
                <h3>Assumptions</h3>
                <ul>
                  {report.assumptions.map((assumption) => (
                    <li key={assumption}>{assumption}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : (
          <p className="cnc-sidebar__hint">
            Run analysis to generate deterministic corner classification and a downloadable PDF report.
          </p>
        )}

        {error ? <p className="cnc-sidebar__error">{error}</p> : null}
      </div>
    </aside>
  );
};

export default CncAnalysisSidebar;
