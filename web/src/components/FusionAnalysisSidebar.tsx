import { useEffect, useMemo, useState } from "react";
import type { AnalysisFocusPayload } from "../types/analysis";
import type { FusionReportResponse, FusionTuning } from "../types/fusion";

type FusionAnalysisSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  onFocusInModel?: (payload: AnalysisFocusPayload) => void;
  onClose: () => void;
};

type AnalysisMode = "geometry_dfm" | "drawing_spec" | "full";
type StandardsProfileMode = "pilot" | "profile";
type CachedFusionReportEnvelope = {
  saved_at?: string;
  report_id?: string;
  payload?: FusionReportResponse;
};

const formatSignal = (value: number): string => value.toFixed(3);
const FUSION_TUNING_STORAGE_KEY = "fusion_tuning_v1";
const FUSION_REPORT_CACHE_PREFIX = "fusion_report_last_v1";
const DEFAULT_FUSION_TUNING: FusionTuning = {
  threshold: 0.28,
  weight_semantic: 0.6,
  weight_refs: 0.25,
  weight_geometry: 0.15,
};

const buildFusionReportCacheKey = (modelId: string | null, componentNodeName: string | null | undefined): string | null => {
  if (!modelId || !componentNodeName) return null;
  return `${FUSION_REPORT_CACHE_PREFIX}:${modelId}:${componentNodeName}`;
};

const readCachedFusionReport = (cacheKey: string | null): CachedFusionReportEnvelope | null => {
  if (!cacheKey) return null;
  try {
    const raw = window.localStorage.getItem(cacheKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as FusionReportResponse | CachedFusionReportEnvelope;
    if (!parsed || typeof parsed !== "object") return null;
    if ("payload" in parsed || "report_id" in parsed || "saved_at" in parsed) {
      const envelope = parsed as CachedFusionReportEnvelope;
      if (envelope.payload && typeof envelope.payload === "object") {
        return envelope;
      }
      return {
        report_id: envelope.report_id,
      };
    }
    const payload = parsed as FusionReportResponse;
    if (!payload.report_id) return null;
    return {
      report_id: payload.report_id,
      payload,
    };
  } catch {
    return null;
  }
};

const writeCachedFusionReport = (cacheKey: string | null, payload: FusionReportResponse): void => {
  if (!cacheKey) return;
  try {
    window.localStorage.setItem(
      cacheKey,
      JSON.stringify({
        saved_at: new Date().toISOString(),
        report_id: payload.report_id,
        payload,
      } satisfies CachedFusionReportEnvelope),
    );
  } catch {
    // Best effort cache only.
  }
};

const FusionAnalysisSidebar = ({ open, apiBase, modelId, selectedComponent, onFocusInModel, onClose }: FusionAnalysisSidebarProps) => {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<FusionReportResponse | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("geometry_dfm");
  const [standardsProfileMode, setStandardsProfileMode] = useState<StandardsProfileMode>("pilot");
  const [useLatestVisionReport, setUseLatestVisionReport] = useState(true);
  const [visionReportId, setVisionReportId] = useState("");
  const [tuningExpanded, setTuningExpanded] = useState(false);
  const [fusionTuning, setFusionTuning] = useState<FusionTuning>(DEFAULT_FUSION_TUNING);
  const cacheKey = useMemo(() => buildFusionReportCacheKey(modelId, selectedComponent?.nodeName), [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    setReport(null);
    setError(null);
    const cached = readCachedFusionReport(cacheKey);
    if (cached?.payload) {
      setReport(cached.payload);
    }
  }, [cacheKey]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(FUSION_TUNING_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<FusionTuning>;
      setFusionTuning({
        threshold: typeof parsed.threshold === "number" ? parsed.threshold : DEFAULT_FUSION_TUNING.threshold,
        weight_semantic:
          typeof parsed.weight_semantic === "number" ? parsed.weight_semantic : DEFAULT_FUSION_TUNING.weight_semantic,
        weight_refs: typeof parsed.weight_refs === "number" ? parsed.weight_refs : DEFAULT_FUSION_TUNING.weight_refs,
        weight_geometry:
          typeof parsed.weight_geometry === "number" ? parsed.weight_geometry : DEFAULT_FUSION_TUNING.weight_geometry,
      });
    } catch {
      // Ignore malformed local storage; defaults remain active.
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(FUSION_TUNING_STORAGE_KEY, JSON.stringify(fusionTuning));
    } catch {
      // Best effort only.
    }
  }, [fusionTuning]);

  useEffect(() => {
    if (!cacheKey || !modelId) return;
    const cached = readCachedFusionReport(cacheKey);
    const cachedReportId = cached?.report_id ?? cached?.payload?.report_id;
    if (!cachedReportId) return;

    let cancelled = false;
    const refreshFromServer = async () => {
      try {
        const response = await fetch(`${apiBase}/api/models/${modelId}/fusion/reports/${cachedReportId}`, {
          method: "GET",
        });
        if (!response.ok) return;
        const payload = (await response.json()) as FusionReportResponse;
        if (cancelled) return;
        setReport(payload);
        writeCachedFusionReport(cacheKey, payload);
      } catch {
        // Keep cached payload if network retrieval fails.
      }
    };

    refreshFromServer();
    return () => {
      cancelled = true;
    };
  }, [apiBase, cacheKey, modelId]);

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

  const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));
  const setTuningField = (field: keyof FusionTuning, rawValue: string) => {
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) return;
    setFusionTuning((prev) => ({ ...prev, [field]: clamp01(parsed) }));
  };
  const resetFusionTuning = () => setFusionTuning(DEFAULT_FUSION_TUNING);

  const focusFindingInModel = (payload: {
    id: string;
    title: string;
    details?: string;
    severity?: string;
  }) => {
    if (!onFocusInModel) return;
    onFocusInModel({
      id: payload.id,
      source: "fusion",
      title: payload.title,
      details: payload.details,
      severity: payload.severity,
      component_node_name: selectedComponent?.nodeName ?? report?.component_node_name ?? null,
    });
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
          fusion_tuning: fusionTuning,
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
      writeCachedFusionReport(cacheKey, payload);
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

        <button
          type="button"
          className="fusion-sidebar__details-toggle"
          onClick={() => setTuningExpanded((prev) => !prev)}
        >
          <span>Advanced matching controls</span>
          <span>{tuningExpanded ? "v" : ">"}</span>
        </button>

        {tuningExpanded ? (
          <div className="fusion-sidebar__tuning-card">
            <label className="fusion-sidebar__field">
              <span>Match threshold</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={fusionTuning.threshold}
                onChange={(event) => setTuningField("threshold", event.target.value)}
              />
            </label>
            <label className="fusion-sidebar__field">
              <span>Semantic weight</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={fusionTuning.weight_semantic}
                onChange={(event) => setTuningField("weight_semantic", event.target.value)}
              />
            </label>
            <label className="fusion-sidebar__field">
              <span>Refs weight</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={fusionTuning.weight_refs}
                onChange={(event) => setTuningField("weight_refs", event.target.value)}
              />
            </label>
            <label className="fusion-sidebar__field">
              <span>Geometry weight</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={fusionTuning.weight_geometry}
                onChange={(event) => setTuningField("weight_geometry", event.target.value)}
              />
            </label>
            <button type="button" className="fusion-sidebar__reset" onClick={resetFusionTuning}>
              Reset defaults
            </button>
          </div>
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

            {report.tuning_applied ? (
              <div className="fusion-sidebar__meta">
                Tuning: threshold={formatSignal(report.tuning_applied.threshold)} | weights S/R/G=
                {formatSignal(report.tuning_applied.weight_semantic)}/
                {formatSignal(report.tuning_applied.weight_refs)}/
                {formatSignal(report.tuning_applied.weight_geometry)}
              </div>
            ) : null}
            {report.analysis_run_id ? (
              <div className="fusion-sidebar__meta">Analysis run: {report.analysis_run_id}</div>
            ) : null}

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
                      <div className="fusion-sidebar__meta fusion-sidebar__meta--rationale">{finding.match_rationale}</div>
                      <div className="fusion-sidebar__signals">
                        <span>S: {formatSignal(finding.match_signals.semantic_score)}</span>
                        <span>R: {formatSignal(finding.match_signals.refs_overlap_score)}</span>
                        <span>G: {formatSignal(finding.match_signals.geometry_anchor_score)}</span>
                        <span>O: {formatSignal(finding.match_signals.overall_match_score)}</span>
                      </div>
                      <button
                        type="button"
                        className="analysis-focus-action"
                        onClick={() =>
                          focusFindingInModel({
                            id: finding.id,
                            title: finding.vision.description || finding.dfm.title,
                            details: finding.match_rationale,
                            severity: finding.vision.severity || finding.dfm.severity,
                          })
                        }
                      >
                        Show in model
                      </button>
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
                      <div className="fusion-sidebar__meta fusion-sidebar__meta--rationale">{finding.match_rationale}</div>
                      <div className="fusion-sidebar__signals">
                        <span>S: {formatSignal(finding.match_signals.semantic_score)}</span>
                        <span>R: {formatSignal(finding.match_signals.refs_overlap_score)}</span>
                        <span>G: {formatSignal(finding.match_signals.geometry_anchor_score)}</span>
                        <span>O: {formatSignal(finding.match_signals.overall_match_score)}</span>
                        <span>T: {formatSignal(finding.match_signals.threshold)}</span>
                      </div>
                      <button
                        type="button"
                        className="analysis-focus-action"
                        onClick={() =>
                          focusFindingInModel({
                            id: finding.id,
                            title: finding.dfm.title,
                            details: finding.dfm.description || finding.match_rationale,
                            severity: finding.dfm.severity,
                          })
                        }
                      >
                        Show in model
                      </button>
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
                      <div className="fusion-sidebar__meta fusion-sidebar__meta--rationale">{finding.match_rationale}</div>
                      <div className="fusion-sidebar__signals">
                        <span>S: {formatSignal(finding.match_signals.semantic_score)}</span>
                        <span>R: {formatSignal(finding.match_signals.refs_overlap_score)}</span>
                        <span>G: {formatSignal(finding.match_signals.geometry_anchor_score)}</span>
                        <span>O: {formatSignal(finding.match_signals.overall_match_score)}</span>
                        <span>T: {formatSignal(finding.match_signals.threshold)}</span>
                      </div>
                      <button
                        type="button"
                        className="analysis-focus-action"
                        onClick={() =>
                          focusFindingInModel({
                            id: finding.id,
                            title: finding.vision.description,
                            details: finding.match_rationale,
                            severity: finding.vision.severity,
                          })
                        }
                      >
                        Show in model
                      </button>
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
