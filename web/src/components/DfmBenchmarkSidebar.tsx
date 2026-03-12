import { useEffect, useMemo, useState } from "react";

type DfmBenchmarkSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  selectedProfile: {
    material: string;
    manufacturingProcess: string;
    industry: string;
  } | null;
  profileComplete: boolean;
  onClose: () => void;
};

type ProcessOverrideMode = "profile" | "auto" | "force";
type AnalysisMode = "geometry_dfm" | "drawing_spec" | "full";
type StandardsProfileSelection = "profile_auto" | "none" | "pilot" | `overlay:${string}`;
type GeometryMetric = {
  key: string;
  label: string;
  value: string | number | boolean;
  unit?: string | null;
};

const DFM_BENCHMARK_CACHE_PREFIX = "dfm_benchmark_sidebar_review_last_v1";
const DEFAULT_FLOW_ORDER = [
  "analysis_mode",
  "manufacturing_process",
  "industry_overlay",
  "role_lens",
  "report_template",
  "advanced_llm_model",
  "run_both_if_mismatch",
  "generate_review",
];
const PILOT_OVERLAY_ID = "pilot_prototype";
const ALL_STANDARDS_OVERLAY_WITH_PILOT_ID = "all_standards_with_pilot";
const ALL_STANDARDS_OVERLAY_NON_PILOT_ID = "all_standards_non_pilot";

const buildCacheKey = (modelId: string | null, componentNodeName: string | null | undefined): string | null => {
  if (!modelId || !componentNodeName) return null;
  return `${DFM_BENCHMARK_CACHE_PREFIX}:${modelId}:${componentNodeName}`;
};

const readCachedReview = (cacheKey: string | null) => {
  if (!cacheKey) return null;
  try {
    const raw = window.localStorage.getItem(cacheKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { payload?: Record<string, unknown> } | Record<string, unknown>;
    const payload = "payload" in parsed ? parsed.payload : parsed;
    return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : null;
  } catch {
    return null;
  }
};

const writeCachedReview = (cacheKey: string | null, payload: Record<string, unknown>) => {
  if (!cacheKey) return;
  try {
    window.localStorage.setItem(
      cacheKey,
      JSON.stringify({
        saved_at: new Date().toISOString(),
        payload,
      }),
    );
  } catch {
    // Best effort cache only.
  }
};

const metricValue = (metric: GeometryMetric): string => {
  if (typeof metric.value === "boolean") return metric.value ? "Yes" : "No";
  if (typeof metric.value === "number") {
    const rendered = Number.isInteger(metric.value) ? metric.value.toString() : metric.value.toFixed(2);
    return metric.unit ? `${rendered} ${metric.unit}` : rendered;
  }
  return metric.unit ? `${metric.value} ${metric.unit}` : metric.value;
};

const processLabelById = (processes: Array<{ process_id: string; label: string }>, processId: string | null) => {
  if (!processId) return "";
  return processes.find((process) => process.process_id === processId)?.label ?? processId;
};

const overlayLabelById = (overlays: Array<{ overlay_id: string; label: string }>, overlayId: string | null) => {
  if (!overlayId) return "None";
  return overlays.find((overlay) => overlay.overlay_id === overlayId)?.label ?? overlayId;
};

const DfmBenchmarkSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  selectedProfile,
  profileComplete,
  onClose,
}: DfmBenchmarkSidebarProps) => {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dfmConfig, setDfmConfig] = useState<Record<string, any> | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("geometry_dfm");
  const [processOverrideMode, setProcessOverrideMode] = useState<ProcessOverrideMode>("auto");
  const [forcedProcessId, setForcedProcessId] = useState("");
  const [standardsProfileSelection, setStandardsProfileSelection] =
    useState<StandardsProfileSelection>("profile_auto");
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedAdvancedModel, setSelectedAdvancedModel] = useState("");
  const [modelTemplates, setModelTemplates] = useState<Array<{ template_id: string; label: string; source: string }>>([]);
  const [runBothIfMismatch, setRunBothIfMismatch] = useState(true);
  const [reviewResult, setReviewResult] = useState<Record<string, any> | null>(null);
  const [detailsVersion, setDetailsVersion] = useState(0);

  const panelBindings = useMemo(() => dfmConfig?.ui_bindings?.screens?.dfm_review_panel ?? null, [dfmConfig]);

  const controlsById = useMemo(() => {
    const map = new Map<string, Record<string, any>>();
    (panelBindings?.controls ?? []).forEach((control: Record<string, any>) => {
      if (typeof control?.control_id === "string") map.set(control.control_id, control);
    });
    return map;
  }, [panelBindings]);

  const flowOrder = useMemo(() => {
    const configured = panelBindings?.flow_order;
    return Array.isArray(configured) && configured.length ? configured : DEFAULT_FLOW_ORDER;
  }, [panelBindings]);

  const primaryControlIds = useMemo(
    () => flowOrder.filter((controlId) => ["analysis_mode", "industry_overlay", "generate_review"].includes(controlId)),
    [flowOrder],
  );

  const secondaryControlIds = useMemo(
    () =>
      flowOrder.filter((controlId) =>
        ["manufacturing_process", "run_both_if_mismatch", "role_lens", "report_template", "advanced_llm_model"].includes(
          controlId,
        ),
      ),
    [flowOrder],
  );

  const processes = (dfmConfig?.processes ?? []) as Array<{ process_id: string; label: string }>;
  const overlays = (dfmConfig?.overlays ?? []) as Array<{ overlay_id: string; label: string }>;
  const roles = (dfmConfig?.roles ?? []) as Array<{ role_id: string; label: string }>;
  const pilotOverlay = overlays.find((overlay) => overlay.overlay_id === PILOT_OVERLAY_ID) ?? null;
  const allStandardsOverlayId = overlays.some((overlay) => overlay.overlay_id === ALL_STANDARDS_OVERLAY_WITH_PILOT_ID)
    ? ALL_STANDARDS_OVERLAY_WITH_PILOT_ID
    : overlays.some((overlay) => overlay.overlay_id === ALL_STANDARDS_OVERLAY_NON_PILOT_ID)
    ? ALL_STANDARDS_OVERLAY_NON_PILOT_ID
    : null;
  const standardsOverlayOptions = overlays.filter(
    (overlay) =>
      overlay.overlay_id !== PILOT_OVERLAY_ID &&
      overlay.overlay_id !== ALL_STANDARDS_OVERLAY_WITH_PILOT_ID &&
      overlay.overlay_id !== ALL_STANDARDS_OVERLAY_NON_PILOT_ID,
  );
  const advancedModelOptions = ((controlsById.get("advanced_llm_model")?.options as string[] | undefined) ?? []).filter(Boolean);

  useEffect(() => {
    setError(null);
    setReviewResult(readCachedReview(buildCacheKey(modelId, selectedComponent?.nodeName)));
    setDetailsVersion((current) => current + 1);
  }, [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    setSelectedTemplateId("");
  }, [modelId]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const load = async () => {
      try {
        const configResponse = await fetch(`${apiBase}/api/dfm/config`);
        if (!configResponse.ok) throw new Error("Failed to load DFM config");
        const configPayload = (await configResponse.json()) as Record<string, any>;
        if (!cancelled) setDfmConfig(configPayload);

        if (modelId) {
          const templateResponse = await fetch(`${apiBase}/api/models/${modelId}/dfm/templates`);
          if (!templateResponse.ok) throw new Error(await readErrorText(templateResponse, "Failed to load model templates"));
          const templatePayload = (await templateResponse.json()) as { templates?: Array<{ template_id: string; label: string; source: string }> };
          if (!cancelled) setModelTemplates(templatePayload.templates ?? []);
        } else if (!cancelled) {
          setModelTemplates([]);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unexpected DFM sidebar error");
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [apiBase, modelId, open]);

  useEffect(() => {
    if (!dfmConfig) return;
    const defaultRole = controlsById.get("role_lens")?.default;
    const defaultTemplate = modelTemplates[0]?.template_id ?? "";
    const defaultProcess = processes[0]?.process_id ?? "";
    const defaultAnalysisMode = controlsById.get("analysis_mode")?.default;
    const defaultProcessMode = controlsById.get("manufacturing_process")?.default_mode;
    const defaultRunBoth = controlsById.get("run_both_if_mismatch")?.default;

    setSelectedRoleId((current) => current || (typeof defaultRole === "string" ? defaultRole : roles[0]?.role_id ?? ""));
    setSelectedTemplateId((current) => current || defaultTemplate);
    setForcedProcessId((current) => current || defaultProcess);
    if (typeof defaultAnalysisMode === "string" && ["geometry_dfm", "drawing_spec", "full"].includes(defaultAnalysisMode)) {
      setAnalysisMode(defaultAnalysisMode as AnalysisMode);
    }
    if (typeof defaultProcessMode === "string" && ["profile", "auto", "force"].includes(defaultProcessMode)) {
      setProcessOverrideMode(defaultProcessMode as ProcessOverrideMode);
    }
    if (typeof defaultRunBoth === "boolean") setRunBothIfMismatch(defaultRunBoth);
    if (!selectedAdvancedModel && advancedModelOptions.length) setSelectedAdvancedModel(advancedModelOptions[0]);
  }, [advancedModelOptions, controlsById, dfmConfig, modelTemplates, processes, roles, selectedAdvancedModel]);

  const mismatchBanner = useMemo(() => {
    if (!reviewResult?.mismatch?.has_mismatch) return null;
    if (reviewResult.mismatch.banner) return reviewResult.mismatch.banner as string;
    const user = reviewResult.mismatch.user_selected_process?.process_label as string | undefined;
    const ai = reviewResult.mismatch.ai_process?.process_label as string | undefined;
    return user && ai ? `User selected ${user}, AI recommended ${ai}.` : null;
  }, [reviewResult]);

  const readErrorText = async (response: Response, fallback: string) => {
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      return payload.detail ?? payload.message ?? fallback;
    } catch {
      return fallback;
    }
  };

  const handleSubmit = async () => {
    if (!modelId || !selectedComponent) {
      setError("Select a part from the assembly tree before generating a review.");
      return;
    }
    if (!selectedRoleId || !selectedTemplateId) {
      setError("Role lens and report template are required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      let selectedOverlayId: string | null = null;
      let overlaySelectionMode: "none" | "profile" | "override" = "profile";
      if (standardsProfileSelection === "none") overlaySelectionMode = "none";
      if (standardsProfileSelection === "pilot") {
        overlaySelectionMode = "override";
        selectedOverlayId = pilotOverlay?.overlay_id ?? null;
      }
      if (standardsProfileSelection.startsWith("overlay:")) {
        overlaySelectionMode = "override";
        selectedOverlayId = standardsProfileSelection.slice("overlay:".length) || null;
      }

      const response = await fetch(`${apiBase}/api/models/${modelId}/dfm/review-v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          planning_inputs: {
            extracted_part_facts: {},
            analysis_mode: analysisMode,
            selected_process_override: processOverrideMode === "force" ? forcedProcessId || null : null,
            selected_overlay: selectedOverlayId,
            process_selection_mode: processOverrideMode === "force" ? "override" : processOverrideMode,
            overlay_selection_mode: overlaySelectionMode,
            selected_role: selectedRoleId,
            selected_template: selectedTemplateId,
            run_both_if_mismatch: runBothIfMismatch,
          },
          context_payload: selectedAdvancedModel ? { advanced_llm_model: selectedAdvancedModel } : {},
        }),
      });
      if (!response.ok) throw new Error(await readErrorText(response, "Failed to generate DFM review"));
      const payload = (await response.json()) as Record<string, any>;
      setReviewResult(payload);
      writeCachedReview(buildCacheKey(modelId, selectedComponent.nodeName), payload);
      setDetailsVersion((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected DFM review error");
    } finally {
      setSubmitting(false);
    }
  };

  const renderFlowControl = (controlId: string) => {
    const label = (controlsById.get(controlId)?.label as string | undefined) ?? controlId.replaceAll("_", " ");
    if (controlId === "manufacturing_process") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>Process override (optional)</span>
          <select value={processOverrideMode} onChange={(event) => setProcessOverrideMode(event.target.value as ProcessOverrideMode)}>
            <option value="profile">Use profile value</option>
            <option value="auto">Auto from PartFacts/AI</option>
            <option value="force">Force selection</option>
          </select>
          {processOverrideMode === "force" ? (
            <select value={forcedProcessId} onChange={(event) => setForcedProcessId(event.target.value)}>
              {processes.map((process) => (
                <option key={process.process_id} value={process.process_id}>
                  {process.label}
                </option>
              ))}
            </select>
          ) : null}
        </label>
      );
    }
    if (controlId === "analysis_mode") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>Input scope</span>
          <select value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value as AnalysisMode)}>
            <option value="geometry_dfm">Geometry DFM (STEP-only)</option>
            <option value="drawing_spec">Drawing/spec completeness</option>
            <option value="full">Full</option>
          </select>
        </label>
      );
    }
    if (controlId === "industry_overlay") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>Standards profile (optional)</span>
          <select value={standardsProfileSelection} onChange={(event) => setStandardsProfileSelection(event.target.value as StandardsProfileSelection)}>
            <option value="profile_auto">Auto from profile</option>
            <option value="none">None (no overlay)</option>
            <option value="pilot" disabled={!pilotOverlay}>Pilots {pilotOverlay ? "" : "(not available)"}</option>
            {allStandardsOverlayId ? <option value={`overlay:${allStandardsOverlayId}`}>All standards</option> : null}
            {standardsOverlayOptions.map((overlay) => (
              <option key={overlay.overlay_id} value={`overlay:${overlay.overlay_id}`}>
                {overlay.label}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (controlId === "role_lens") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>{label}</span>
          <select value={selectedRoleId} onChange={(event) => setSelectedRoleId(event.target.value)}>
            {roles.map((role) => (
              <option key={role.role_id} value={role.role_id}>
                {role.label}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (controlId === "report_template") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>{label}</span>
          <select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)} disabled={!modelTemplates.length}>
            {modelTemplates.map((template) => (
              <option key={template.template_id} value={template.template_id}>
                {template.label} {template.source === "custom" ? "(custom)" : ""}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (controlId === "advanced_llm_model") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>{label}</span>
          <select value={selectedAdvancedModel} onChange={(event) => setSelectedAdvancedModel(event.target.value)} disabled={!advancedModelOptions.length}>
            {!advancedModelOptions.length ? <option value="">Not configured</option> : null}
            {advancedModelOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (controlId === "run_both_if_mismatch") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step dfm-sidebar__toggle">
          <span>{label}</span>
          <div className="dfm-sidebar__toggle-row">
            <input type="checkbox" checked={runBothIfMismatch} onChange={(event) => setRunBothIfMismatch(event.target.checked)} />
            <span>{runBothIfMismatch ? "Enabled" : "Disabled"}</span>
          </div>
        </label>
      );
    }
    if (controlId === "generate_review") {
      return (
        <div key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <button type="button" className="dfm-sidebar__submit" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Generating..." : "Generate review"}
          </button>
        </div>
      );
    }
    return null;
  };

  const renderFindingItem = (route: Record<string, any>, finding: Record<string, any>) => {
    const routeStandards = new Map<string, Record<string, any>>();
    (route.standards_used_auto ?? []).forEach((standard: Record<string, any>) => routeStandards.set(standard.ref_id, standard));
    (reviewResult?.standards_used_auto_union ?? []).forEach((standard: Record<string, any>) => {
      if (!routeStandards.has(standard.ref_id)) routeStandards.set(standard.ref_id, standard);
    });
    return (
      <li key={`${route.plan_id}-${finding.rule_id}-${finding.pack_id}-${finding.finding_type ?? "unknown"}`}>
        <strong>{finding.rule_id}</strong> [{finding.severity}] {finding.title ?? "Untitled rule"}
        {finding.refs?.length ? (
          <div className="dfm-sidebar__finding-standards">
            Standards:{" "}
            {finding.refs.map((refId: string, index: number) => {
              const standard = routeStandards.get(refId);
              const label = standard?.title ? `${standard.title} (${refId})` : refId;
              return (
                <span key={`${finding.rule_id}-${refId}`}>
                  {index > 0 ? "; " : ""}
                  {standard?.url ? <a href={standard.url}>{label}</a> : label}
                </span>
              );
            })}
          </div>
        ) : null}
        {finding.recommended_action ? <div className="dfm-sidebar__finding-action">{finding.recommended_action}</div> : null}
      </li>
    );
  };

  const geometryEvidence = reviewResult?.geometry_evidence as
    | {
        process_summary?: { effective_process_label?: string | null; ai_process_label?: string | null; reason_tags?: string[] };
        feature_groups?: Array<{ group_id: string; label: string; summary: string; metrics: GeometryMetric[] }>;
        detail_metrics?: GeometryMetric[];
      }
    | undefined;

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="dfm-sidebar">
        <div className="dfm-sidebar__header">
          <h2>DFM Benchmark Bar</h2>
          <button type="button" onClick={onClose} className="dfm-sidebar__close" aria-label="Close DFM Benchmark Bar">x</button>
        </div>
        <div className="dfm-sidebar__field">
          <span>Selected part</span>
          <div className="dfm-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>
        <details open className="dfm-sidebar__plan-summary dfm-sidebar__part-context">
          <summary>Part context (from profile)</summary>
          <div className="dfm-sidebar__compact-meta-list">
            <p className="dfm-sidebar__meta">Manufacturing process: {selectedProfile?.manufacturingProcess || "-"}</p>
            <p className="dfm-sidebar__meta">Material: {selectedProfile?.material || "-"}</p>
            <p className="dfm-sidebar__meta">Industry: {selectedProfile?.industry || "-"}</p>
          </div>
        </details>
        <div className="dfm-sidebar__flow">
          <h3>Analysis controls</h3>
          <div className="dfm-sidebar__flow-controls">{primaryControlIds.map((controlId) => renderFlowControl(controlId))}</div>
          {secondaryControlIds.length ? (
            <details className="dfm-sidebar__details">
              <summary>Advanced controls</summary>
              <div className="dfm-sidebar__flow-controls">{secondaryControlIds.map((controlId) => renderFlowControl(controlId))}</div>
            </details>
          ) : null}
        </div>
        {mismatchBanner ? <p className="dfm-sidebar__banner">{mismatchBanner}</p> : null}
        {reviewResult ? (
          <div className="dfm-sidebar__evidence">
            <h3>Geometry evidence</h3>
            <div className="dfm-sidebar__evidence-grid">
              <article className="dfm-sidebar__evidence-card">
                <header className="dfm-sidebar__evidence-card-header"><strong>Process signals</strong></header>
                <div className="dfm-sidebar__metric-list">
                  <div className="dfm-sidebar__metric-row"><span className="dfm-sidebar__metric-label">Effective process</span><strong className="dfm-sidebar__metric-value">{geometryEvidence?.process_summary?.effective_process_label ?? reviewResult.routes?.[0]?.process_label ?? "Not resolved"}</strong></div>
                  <div className="dfm-sidebar__metric-row"><span className="dfm-sidebar__metric-label">AI recommendation</span><strong className="dfm-sidebar__metric-value">{geometryEvidence?.process_summary?.ai_process_label ?? reviewResult.ai_recommendation?.process_label ?? "Not available"}</strong></div>
                </div>
                {geometryEvidence?.process_summary?.reason_tags?.length ? (
                  <div className="dfm-sidebar__chip-list">
                    {geometryEvidence.process_summary.reason_tags.map((tag) => (
                      <span key={tag} className="dfm-sidebar__chip">{tag}</span>
                    ))}
                  </div>
                ) : <p className="dfm-sidebar__hint">No strong process signals were surfaced for this run.</p>}
              </article>
              <article className="dfm-sidebar__evidence-card">
                <header className="dfm-sidebar__evidence-card-header"><strong>Detected features</strong></header>
                {geometryEvidence?.feature_groups?.length ? (
                  <div className="dfm-sidebar__feature-groups">
                    {geometryEvidence.feature_groups.map((group) => (
                      <section key={group.group_id} className="dfm-sidebar__feature-group">
                        <div className="dfm-sidebar__feature-group-header"><strong>{group.label}</strong></div>
                        <p className="dfm-sidebar__feature-group-summary">{group.summary}</p>
                        <div className="dfm-sidebar__metric-list">
                          {group.metrics.map((metric) => (
                            <div key={`${group.group_id}-${metric.key}`} className="dfm-sidebar__metric-row">
                              <span className="dfm-sidebar__metric-label">{metric.label}</span>
                              <strong className="dfm-sidebar__metric-value">{metricValue(metric)}</strong>
                            </div>
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                ) : <p className="dfm-sidebar__hint">No extracted feature evidence was surfaced for this run.</p>}
              </article>
            </div>
            <details key={`geometry-details-${detailsVersion}`} className="dfm-sidebar__standards-toggle">
              <summary>More detail ({geometryEvidence?.detail_metrics?.length ?? 0})</summary>
              {geometryEvidence?.detail_metrics?.length ? (
                <div className="dfm-sidebar__metric-list">
                  {geometryEvidence.detail_metrics.map((metric) => (
                    <div key={`detail-${metric.key}`} className="dfm-sidebar__metric-row">
                      <span className="dfm-sidebar__metric-label">{metric.label}</span>
                      <strong className="dfm-sidebar__metric-value">{metricValue(metric)}</strong>
                    </div>
                  ))}
                </div>
              ) : <p className="dfm-sidebar__hint">No secondary metrics were surfaced for this run.</p>}
            </details>
          </div>
        ) : null}
        {reviewResult ? (
          <div className="dfm-sidebar__report">
            <h3>Review output</h3>
            <p className="dfm-sidebar__meta">Routes: {reviewResult.route_count} | Findings: {reviewResult.finding_count_total}</p>
            {reviewResult.cost_estimate ? (
              <article className="dfm-sidebar__route">
                <header className="dfm-sidebar__route-header"><strong>Cost</strong></header>
                <p className="dfm-sidebar__meta">
                  {Number(reviewResult.cost_estimate.unit_cost ?? 0).toFixed(2)} {reviewResult.cost_estimate.currency}
                </p>
              </article>
            ) : null}
            {reviewResult.routes?.map((route: Record<string, any>) => {
              const designRiskFindings = (route.findings ?? []).filter((finding: Record<string, any>) => finding.finding_type === "rule_violation");
              const evidenceGapFindings = (route.findings ?? []).filter((finding: Record<string, any>) => finding.finding_type !== "rule_violation");
              return (
                <article key={`${route.plan_id}-${route.process_id}`} className="dfm-sidebar__route">
                  <header className="dfm-sidebar__route-header"><strong>{route.process_label}</strong><span>{designRiskFindings.length + evidenceGapFindings.length} shown</span></header>
                  <p className="dfm-sidebar__meta">Packs: {(route.pack_labels ?? []).filter(Boolean).join(", ") || (route.pack_ids ?? []).join(", ")}</p>
                  <p className="dfm-sidebar__meta">Design risks: {designRiskFindings.length} | Drawing/spec evidence gaps: {evidenceGapFindings.length}</p>
                  <div className="dfm-sidebar__findings-groups">
                    <details className="dfm-sidebar__finding-group">
                      <summary>Design risks ({designRiskFindings.length})</summary>
                      {designRiskFindings.length ? <ul className="dfm-sidebar__findings">{designRiskFindings.slice(0, 20).map((finding: Record<string, any>) => renderFindingItem(route, finding))}</ul> : <p className="dfm-sidebar__hint">No design risk findings in this route.</p>}
                    </details>
                    <details className="dfm-sidebar__finding-group">
                      <summary>Drawing/spec evidence gaps ({evidenceGapFindings.length})</summary>
                      {evidenceGapFindings.length ? <ul className="dfm-sidebar__findings">{evidenceGapFindings.slice(0, 20).map((finding: Record<string, any>) => renderFindingItem(route, finding))}</ul> : <p className="dfm-sidebar__hint">No evidence gaps in this route.</p>}
                    </details>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
        {reviewResult ? (
          <div className="dfm-sidebar__standards">
            <h3>Analysis information</h3>
            <p className="dfm-sidebar__hint">Read-only run context and standards outputs.</p>
            <details key={`effective-context-${detailsVersion}`} className="dfm-sidebar__standards-toggle">
              <summary>Effective analysis context</summary>
              <p className="dfm-sidebar__meta">Input scope: {reviewResult.effective_context?.analysis_mode?.selected_mode ?? analysisMode} (source: {reviewResult.effective_context?.analysis_mode?.source ?? "ui_selection"})</p>
              <p className="dfm-sidebar__meta">Process: {reviewResult.effective_context?.process?.effective_process_label ?? (processOverrideMode === "force" ? processLabelById(processes, forcedProcessId || null) || "None" : processOverrideMode === "auto" ? "Auto (AI recommendation)" : "Profile value")} (source: {reviewResult.effective_context?.process?.source ?? "pending backend resolution"})</p>
              <p className="dfm-sidebar__meta">Rule set: {reviewResult.effective_context?.overlay ? (reviewResult.effective_context.overlay.effective_overlay_id === allStandardsOverlayId ? "All standards" : reviewResult.effective_context.overlay.effective_overlay_label || "None") : standardsProfileSelection === "profile_auto" ? "Profile mapping" : standardsProfileSelection === "none" ? "None" : standardsProfileSelection === "pilot" ? overlayLabelById(overlays, pilotOverlay?.overlay_id ?? null) : overlayLabelById(overlays, standardsProfileSelection.slice("overlay:".length) || null)} (source: {reviewResult.effective_context?.overlay?.source ?? "pending backend resolution"})</p>
            </details>
            <details key={`standards-list-${detailsVersion}`} className="dfm-sidebar__standards-toggle">
              <summary>Standards list ({reviewResult.standards_used_auto_union?.length ?? 0})</summary>
              {reviewResult.standards_used_auto_union?.length ? (
                <ul className="dfm-sidebar__standards-list">
                  {reviewResult.standards_used_auto_union.map((standard: Record<string, any>) => (
                    <li key={standard.ref_id}>
                      <strong>{standard.ref_id}</strong>
                      {standard.url ? <a href={standard.url}>{standard.title ?? standard.ref_id}</a> : <span>{standard.title ?? standard.ref_id}</span>}
                    </li>
                  ))}
                </ul>
              ) : <p className="dfm-sidebar__hint">No standards fired from current findings.</p>}
            </details>
          </div>
        ) : null}
        {error ? <p className="dfm-sidebar__error">{error}</p> : null}
        {!profileComplete ? <p className="dfm-sidebar__hint">Complete material, manufacturing process, and industry in the component profile for stronger DFM results.</p> : null}
        {modelId && !modelTemplates.length ? <p className="dfm-sidebar__hint">No templates found for this model yet.</p> : null}
      </div>
    </aside>
  );
};

export default DfmBenchmarkSidebar;
