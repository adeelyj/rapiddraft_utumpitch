import { useMemo, useState } from "react";
import type { FusionReportResponse } from "../types/fusion";

type FusionAnalysisSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  onClose: () => void;
};

type AnalysisMode = "geometry_dfm" | "drawing_spec" | "full";
type StandardsProfileMode = "pilot" | "profile";

const FusionAnalysisSidebar = ({ open, apiBase, modelId, selectedComponent, onClose }: FusionAnalysisSidebarProps) => {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<FusionReportResponse | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("geometry_dfm");
  const [standardsProfileMode, setStandardsProfileMode] = useState<StandardsProfileMode>("pilot");
  const [useLatestVisionReport, setUseLatestVisionReport] = useState(true);
  const [visionReportId, setVisionReportId] = useState("");

  const canRun = Boolean(modelId && selectedComponent && !running);
  const selectedVisionReportId = useMemo(() => {
    if (useLatestVisionReport) return null;
    const trimmed = visionReportId.trim();
    return trimmed ? trimmed : null;
  }, [useLatestVisionReport, visionReportId]);

  const readErrorText = async (response: Response, fallback: string): Promise<string> => {
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      return payload.detail ?? payload.message ?? fallback;
    } catch {
      return fallback;
    }
  };

  const handleRunFusion = async () => {
    if (!modelId) {
      setError("Load a model before running fusion analysis.");
      return;
    }
    if (!selectedComponent) {
      setError("Select a part before running fusion analysis.");
      return;
    }

    setRunning(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/api/models/${modelId}/fusion/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          vision_report_id: selectedVisionReportId,
          dfm_review_request: {
            component_node_name: selectedComponent.nodeName,
            planning_inputs: {
              extracted_part_facts: {},
              analysis_mode: analysisMode,
              selected_process_override: null,
              selected_overlay: standardsProfileMode === "pilot" ? "pilot_prototype" : null,
              process_selection_mode: "auto",
              overlay_selection_mode: standardsProfileMode === "pilot" ? "override" : "profile",
              selected_role: "general_dfm",
              selected_template: "executive_1page",
              run_both_if_mismatch: true,
            },
            context_payload: {},
          },
        }),
      });
      if (!response.ok) {
        throw new Error(await readErrorText(response, "Failed to run fusion analysis"));
      }
      const payload = (await response.json()) as FusionReportResponse;
      setReport(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error while running fusion analysis");
    } finally {
      setRunning(false);
    }
  };

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="fusion-sidebar">
        <div className="fusion-sidebar__header">
          <h2>Fusion Analysis</h2>
          <button type="button" onClick={onClose} className="fusion-sidebar__close" aria-label="Close Fusion panel">
            x
          </button>
        </div>

        <div className="fusion-sidebar__field">
          <span>Selected part</span>
          <div className="fusion-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>

        <label className="fusion-sidebar__field">
          <span>DFM mode</span>
          <select value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value as AnalysisMode)}>
            <option value="geometry_dfm">Geometry DFM (recommended)</option>
            <option value="drawing_spec">Drawing/spec completeness</option>
            <option value="full">Full</option>
          </select>
        </label>

        <label className="fusion-sidebar__field">
          <span>Standards profile</span>
          <select
            value={standardsProfileMode}
            onChange={(event) => setStandardsProfileMode(event.target.value as StandardsProfileMode)}
          >
            <option value="pilot">Pilots (all pilot standards)</option>
            <option value="profile">Use component profile mapping</option>
          </select>
        </label>

        <label className="fusion-sidebar__field fusion-sidebar__toggle">
          <input
            type="checkbox"
            checked={useLatestVisionReport}
            onChange={(event) => setUseLatestVisionReport(event.target.checked)}
          />
          <span>Use latest Vision report automatically</span>
        </label>

        {!useLatestVisionReport ? (
          <label className="fusion-sidebar__field">
            <span>Vision report ID</span>
            <input
              className="fusion-sidebar__input"
              value={visionReportId}
              onChange={(event) => setVisionReportId(event.target.value)}
              placeholder="vision_rpt_YYYYMMDD_001"
            />
          </label>
        ) : null}

        <button type="button" className="fusion-sidebar__submit" onClick={handleRunFusion} disabled={!canRun}>
          {running ? "Running fusion..." : "Generate fusion review"}
        </button>

        {report ? (
          <>
            <div className="fusion-sidebar__summary">
              <div className="fusion-sidebar__chip">Confirmed: {report.priority_summary.confirmed_count}</div>
              <div className="fusion-sidebar__chip">DFM only: {report.priority_summary.dfm_only_count}</div>
              <div className="fusion-sidebar__chip">Vision only: {report.priority_summary.vision_only_count}</div>
              <div className="fusion-sidebar__chip">Max score: {report.priority_summary.max_priority_score}</div>
            </div>

            <div className="fusion-sidebar__card">
              <h3>Top actions</h3>
              <ol className="fusion-sidebar__actions">
                {report.priority_summary.top_actions.map((action, index) => (
                  <li key={`action-${index + 1}`}>{action}</li>
                ))}
              </ol>
            </div>

            <details className="fusion-sidebar__details" open>
              <summary>Confirmed by both ({report.confirmed_by_both.length})</summary>
              {report.confirmed_by_both.length ? (
                <ul className="fusion-sidebar__list">
                  {report.confirmed_by_both.map((finding) => (
                    <li key={finding.id}>
                      <strong>{finding.dfm.rule_id}</strong> {finding.dfm.title}
                      <div className="fusion-sidebar__meta">
                        Priority: {finding.priority_score} | Match: {finding.match_score}
                      </div>
                      <div className="fusion-sidebar__meta">Vision: {finding.vision.description}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="fusion-sidebar__hint">No cross-confirmed findings in this run.</p>
              )}
            </details>

            <details className="fusion-sidebar__details">
              <summary>DFM only ({report.dfm_only.length})</summary>
              {report.dfm_only.length ? (
                <ul className="fusion-sidebar__list">
                  {report.dfm_only.map((finding) => (
                    <li key={finding.id}>
                      <strong>{finding.dfm.rule_id}</strong> {finding.dfm.title}
                      <div className="fusion-sidebar__meta">Priority: {finding.priority_score}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="fusion-sidebar__hint">No DFM-only findings in this run.</p>
              )}
            </details>

            <details className="fusion-sidebar__details">
              <summary>Vision only ({report.vision_only.length})</summary>
              {report.vision_only.length ? (
                <ul className="fusion-sidebar__list">
                  {report.vision_only.map((finding) => (
                    <li key={finding.id}>
                      <strong>{finding.vision.feature_id}</strong> {finding.vision.description}
                      <div className="fusion-sidebar__meta">
                        Priority: {finding.priority_score} | Confidence: {finding.vision.confidence}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="fusion-sidebar__hint">No Vision-only findings in this run.</p>
              )}
            </details>

            <details className="fusion-sidebar__details">
              <summary>Standards trace ({report.standards_trace_union.length})</summary>
              {report.standards_trace_union.length ? (
                <ul className="fusion-sidebar__list">
                  {report.standards_trace_union.map((entry) => (
                    <li key={`std-${entry.ref_id}`}>
                      <strong>{entry.ref_id}</strong> {entry.title ?? entry.ref_id}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="fusion-sidebar__hint">No standards trace available for this fusion run.</p>
              )}
            </details>
          </>
        ) : (
          <p className="fusion-sidebar__hint">Run fusion to combine DFM + Vision into one ranked output.</p>
        )}

        {error ? <p className="fusion-sidebar__error">{error}</p> : null}
      </div>
    </aside>
  );
};

export default FusionAnalysisSidebar;

