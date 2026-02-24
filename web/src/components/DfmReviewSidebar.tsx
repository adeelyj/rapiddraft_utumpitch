import { useEffect, useMemo, useState } from "react";

type DfmConfigProcess = {
  process_id: string;
  label: string;
};

type DfmConfigOverlay = {
  overlay_id: string;
  label: string;
};

type DfmConfigRole = {
  role_id: string;
  label: string;
};

type DfmConfigTemplate = {
  template_id: string;
  label: string;
};

type DfmConfigControl = {
  control_id: string;
  label?: string;
  type?: string;
  default_mode?: string;
  default?: string | boolean;
  options?: string[];
};

type DfmReviewPanelBindings = {
  flow_order?: string[];
  controls?: DfmConfigControl[];
  standards_used_auto?: {
    label?: string;
    read_only?: boolean;
    data_source?: string;
    deduplicate?: boolean;
    sort?: string;
  };
  cost_outputs?: {
    label?: string;
    read_only?: boolean;
    data_source?: string;
    route_compare_data_source?: string;
    show_route_delta_on_mismatch?: boolean;
  };
};

type DfmConfigResponse = {
  processes: DfmConfigProcess[];
  overlays: DfmConfigOverlay[];
  roles: DfmConfigRole[];
  templates: DfmConfigTemplate[];
  ui_bindings?: {
    screens?: {
      dfm_review_panel?: DfmReviewPanelBindings;
    };
  };
};

type DfmModelTemplate = {
  template_id: string;
  label: string;
  source: "bundle" | "custom";
};

type DfmModelTemplateListResponse = {
  templates: DfmModelTemplate[];
  count: number;
};

type DfmPlanProcessRef = {
  process_id: string;
  process_label: string;
};

type DfmAiRecommendation = {
  process_id: string;
  process_label: string;
  confidence: number;
  confidence_level: string;
  reasons: string[];
};

type DfmMismatch = {
  has_mismatch: boolean;
  user_selected_process: DfmPlanProcessRef | null;
  ai_process: DfmPlanProcessRef | null;
  run_both_requested: boolean;
  policy_allows_run_both: boolean;
  run_both_executed: boolean;
  banner: string | null;
};

type DfmEffectiveProcessContext = {
  selection_mode: string;
  source: string;
  profile_value?: string | null;
  profile_mapped_process_id?: string | null;
  requested_override?: string | null;
  effective_process_id?: string | null;
  effective_process_label?: string | null;
};

type DfmEffectiveOverlayContext = {
  selection_mode: string;
  source: string;
  profile_value?: string | null;
  profile_mapped_overlay_id?: string | null;
  requested_override?: string | null;
  effective_overlay_id?: string | null;
  effective_overlay_label?: string | null;
};

type DfmEffectiveAnalysisModeContext = {
  selected_mode: "geometry_dfm" | "drawing_spec" | "full";
  source?: string;
};

type DfmStandardRef = {
  ref_id: string;
  title?: string;
  url?: string;
  type?: string;
  notes?: string;
};

type DfmStandardTrace = {
  ref_id: string;
  title?: string;
  url?: string;
  type?: string;
  notes?: string;
  active_in_mode: boolean;
  rules_considered: number;
  design_risk_findings: number;
  evidence_gap_findings: number;
  blocked_by_missing_inputs: number;
  checks_passed: number;
  checks_unresolved: number;
};

type DfmFindingExpectedImpact = {
  impact_type?: string;
  risk_reduction?: string;
  cost_impact?: string;
  lead_time_impact?: string;
  rationale?: string;
};

type DfmReviewFinding = {
  rule_id: string;
  pack_id: string;
  finding_type?: "evidence_gap" | "rule_violation";
  severity: string;
  title?: string;
  refs: string[];
  standard_clause?: string;
  source_rule_id?: string;
  evidence_quality?: string;
  recommended_action?: string;
  expected_impact?: DfmFindingExpectedImpact;
};

type DfmCostEstimate = {
  currency: string;
  quantity: number;
  unit_cost: number;
  total_cost: number;
  cost_range: {
    unit_low: number;
    unit_high: number;
    total_low: number;
    total_high: number;
  };
  confidence: number;
  confidence_level: string;
  assumptions: string[];
};

type DfmCostCompareRoutes = {
  currency: string;
  baseline_plan_id: string;
  compare_plan_id: string;
  baseline_process_id: string;
  compare_process_id: string;
  baseline_unit_cost: number;
  compare_unit_cost: number;
  unit_cost_delta: number;
  unit_cost_delta_percent: number;
  baseline_total_cost: number;
  compare_total_cost: number;
  total_cost_delta: number;
  total_cost_delta_percent: number;
  cheaper_plan_id: string;
  cheaper_process_id: string;
};

type DfmReviewRoute = {
  plan_id: string;
  route_source: string;
  process_id: string;
  process_label: string;
  pack_ids: string[];
  pack_labels: (string | null)[];
  finding_count: number;
  findings: DfmReviewFinding[];
  standards_used_auto: DfmStandardRef[];
  standards_trace?: DfmStandardTrace[];
  cost_estimate?: DfmCostEstimate | null;
};

type DfmReviewV2Response = {
  model_id: string;
  effective_context?: {
    process?: DfmEffectiveProcessContext;
    overlay?: DfmEffectiveOverlayContext;
    analysis_mode?: DfmEffectiveAnalysisModeContext;
  } | null;
  ai_recommendation: DfmAiRecommendation | null;
  mismatch: DfmMismatch;
  route_count: number;
  finding_count_total: number;
  standards_used_auto_union: DfmStandardRef[];
  standards_trace_union?: DfmStandardTrace[];
  cost_estimate: DfmCostEstimate | null;
  cost_estimate_by_route: Array<
    DfmCostEstimate & {
      plan_id: string;
      route_source: string;
      process_id: string;
      process_label: string;
    }
  >;
  cost_compare_routes: DfmCostCompareRoutes | null;
  routes: DfmReviewRoute[];
};

type DfmReviewSidebarProps = {
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

type ProcessOverrideMode = "profile" | "auto" | "force";
type AnalysisModeRuntime = "geometry_dfm" | "drawing_spec" | "full";
type AnalysisMode = AnalysisModeRuntime;
type StandardsProfileSelection = "profile_auto" | "none" | "pilot" | `overlay:${string}`;
const PILOT_OVERLAY_ID = "pilot_prototype";
const ALL_STANDARDS_OVERLAY_WITH_PILOT_ID = "all_standards_with_pilot";
const ALL_STANDARDS_OVERLAY_NON_PILOT_ID = "all_standards_non_pilot";
const PILOT_STRICT_ESSENTIAL_RULE_IDS = new Set<string>([
  "CNC-005",
  "CNC-006",
  "CNC-013",
  "FOOD-002",
  "FOOD-004",
]);

const processLabelById = (processes: DfmConfigProcess[], processId: string | null) => {
  if (!processId) return "";
  return processes.find((process) => process.process_id === processId)?.label ?? processId;
};

const overlayLabelById = (overlays: DfmConfigOverlay[], overlayId: string | null) => {
  if (!overlayId) return "None";
  return overlays.find((overlay) => overlay.overlay_id === overlayId)?.label ?? overlayId;
};

const DfmReviewSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  selectedProfile,
  profileComplete,
  onClose,
}: DfmReviewSidebarProps) => {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dfmConfig, setDfmConfig] = useState<DfmConfigResponse | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("geometry_dfm");
  const [processOverrideMode, setProcessOverrideMode] = useState<ProcessOverrideMode>("auto");
  const [forcedProcessId, setForcedProcessId] = useState("");
  const [standardsProfileSelection, setStandardsProfileSelection] =
    useState<StandardsProfileSelection>("profile_auto");
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [modelTemplates, setModelTemplates] = useState<DfmModelTemplate[]>([]);
  const [loadingModelTemplates, setLoadingModelTemplates] = useState(false);
  const [selectedAdvancedModel, setSelectedAdvancedModel] = useState("");
  const [runBothIfMismatch, setRunBothIfMismatch] = useState(true);
  const [showEvidenceGaps, setShowEvidenceGaps] = useState(false);
  const [pilotStrictFilter, setPilotStrictFilter] = useState(false);
  const [reviewV2Result, setReviewV2Result] = useState<DfmReviewV2Response | null>(null);

  const panelBindings = useMemo(() => {
    return dfmConfig?.ui_bindings?.screens?.dfm_review_panel ?? null;
  }, [dfmConfig]);

  const controlsById = useMemo(() => {
    const controls = panelBindings?.controls ?? [];
    const map = new Map<string, DfmConfigControl>();
    controls.forEach((control) => {
      if (control?.control_id) map.set(control.control_id, control);
    });
    return map;
  }, [panelBindings]);

  const flowOrder = useMemo(() => {
    const configured = panelBindings?.flow_order;
    if (!configured?.length) return DEFAULT_FLOW_ORDER;
    return configured;
  }, [panelBindings]);

  const primaryControlIds = useMemo(
    () =>
      flowOrder.filter((controlId) =>
        [
          "analysis_mode",
          "industry_overlay",
          "generate_review",
        ].includes(controlId)
      ),
    [flowOrder]
  );

  const secondaryControlIds = useMemo(
    () =>
      flowOrder.filter((controlId) =>
        [
          "manufacturing_process",
          "run_both_if_mismatch",
          "role_lens",
          "report_template",
          "advanced_llm_model",
        ].includes(controlId)
      ),
    [flowOrder]
  );

  const advancedModelOptions = useMemo(() => {
    const values = controlsById.get("advanced_llm_model")?.options;
    if (!Array.isArray(values)) return [];
    return values.filter((value): value is string => typeof value === "string" && value.trim().length > 0);
  }, [controlsById]);

  const standardsLabel = useMemo(() => {
    return panelBindings?.standards_used_auto?.label ?? "Standards used (auto)";
  }, [panelBindings]);

  const costLabel = useMemo(() => {
    return panelBindings?.cost_outputs?.label ?? "Should-cost (auto)";
  }, [panelBindings]);

  const pilotOverlay = useMemo(() => {
    return dfmConfig?.overlays.find((overlay) => overlay.overlay_id === PILOT_OVERLAY_ID) ?? null;
  }, [dfmConfig]);

  const allStandardsOverlayId = useMemo(() => {
    const overlays = dfmConfig?.overlays ?? [];
    if (overlays.some((overlay) => overlay.overlay_id === ALL_STANDARDS_OVERLAY_WITH_PILOT_ID)) {
      return ALL_STANDARDS_OVERLAY_WITH_PILOT_ID;
    }
    if (overlays.some((overlay) => overlay.overlay_id === ALL_STANDARDS_OVERLAY_NON_PILOT_ID)) {
      return ALL_STANDARDS_OVERLAY_NON_PILOT_ID;
    }
    return null;
  }, [dfmConfig]);

  const standardsOverlayOptions = useMemo(() => {
    if (!dfmConfig?.overlays?.length) return [];
    return dfmConfig.overlays.filter(
      (overlay) =>
        overlay.overlay_id !== PILOT_OVERLAY_ID &&
        overlay.overlay_id !== ALL_STANDARDS_OVERLAY_WITH_PILOT_ID &&
        overlay.overlay_id !== ALL_STANDARDS_OVERLAY_NON_PILOT_ID
    );
  }, [dfmConfig]);

  const mismatchBanner = useMemo(() => {
    if (!reviewV2Result?.mismatch?.has_mismatch) return null;
    if (reviewV2Result.mismatch.banner) return reviewV2Result.mismatch.banner;
    const user = reviewV2Result.mismatch.user_selected_process?.process_label;
    const ai = reviewV2Result.mismatch.ai_process?.process_label;
    if (!user || !ai) return null;
    return `User selected ${user}, AI recommended ${ai}.`;
  }, [reviewV2Result]);

  useEffect(() => {
    setError(null);
    setReviewV2Result(null);
    setPilotStrictFilter(false);
  }, [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    setSelectedTemplateId("");
  }, [modelId]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const loadConfig = async () => {
      setLoadingConfig(true);
      setError(null);
      try {
        const response = await fetch(`${apiBase}/api/dfm/config`);
        if (!response.ok) throw new Error("Failed to load DFM config");
        const payload = (await response.json()) as DfmConfigResponse;
        if (cancelled) return;
        setDfmConfig(payload);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unexpected error while loading DFM config");
        }
      } finally {
        if (!cancelled) setLoadingConfig(false);
      }
    };
    loadConfig();
    return () => {
      cancelled = true;
    };
  }, [apiBase, open]);

  useEffect(() => {
    if (!open || !modelId) {
      setModelTemplates([]);
      return;
    }
    let cancelled = false;
    const loadTemplates = async () => {
      setLoadingModelTemplates(true);
      setError(null);
      try {
        const response = await fetch(`${apiBase}/api/models/${modelId}/dfm/templates`);
        if (!response.ok) throw new Error(await readErrorText(response, "Failed to load model templates"));
        const payload = (await response.json()) as DfmModelTemplateListResponse;
        if (cancelled) return;
        setModelTemplates(payload.templates ?? []);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unexpected error while loading model templates");
          setModelTemplates([]);
        }
      } finally {
        if (!cancelled) setLoadingModelTemplates(false);
      }
    };
    loadTemplates();
    return () => {
      cancelled = true;
    };
  }, [apiBase, modelId, open]);

  useEffect(() => {
    if (!dfmConfig) return;

    const roleControlDefault = controlsById.get("role_lens")?.default;
    const roleFallback =
      typeof roleControlDefault === "string"
        ? roleControlDefault
        : dfmConfig.roles[0]?.role_id ?? "";
    setSelectedRoleId((current) => current || roleFallback);

    const templateFallback = modelTemplates[0]?.template_id ?? "";
    setSelectedTemplateId((current) => current || templateFallback);

    const firstProcess = dfmConfig.processes[0]?.process_id ?? "";
    setForcedProcessId((current) => current || firstProcess);

    const runBothDefault = controlsById.get("run_both_if_mismatch")?.default;
    if (typeof runBothDefault === "boolean") {
      setRunBothIfMismatch(runBothDefault);
    }
    const analysisModeDefault = controlsById.get("analysis_mode")?.default;
    if (
      typeof analysisModeDefault === "string" &&
      (analysisModeDefault === "geometry_dfm" || analysisModeDefault === "drawing_spec" || analysisModeDefault === "full")
    ) {
      setAnalysisMode(analysisModeDefault as AnalysisMode);
    }
    const processDefaultMode = controlsById.get("manufacturing_process")?.default_mode;
    if (
      typeof processDefaultMode === "string" &&
      (processDefaultMode === "auto" || processDefaultMode === "profile" || processDefaultMode === "force")
    ) {
      setProcessOverrideMode(processDefaultMode as ProcessOverrideMode);
    }

    if (!selectedAdvancedModel && advancedModelOptions.length) {
      setSelectedAdvancedModel(advancedModelOptions[0]);
    }
  }, [advancedModelOptions, controlsById, dfmConfig, modelTemplates, selectedAdvancedModel]);

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
    if (!dfmConfig) {
      setError("DFM config is not loaded yet.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const contextPayload: Record<string, unknown> = {};
      if (selectedAdvancedModel) {
        contextPayload.advanced_llm_model = selectedAdvancedModel;
      }
      let selectedOverlayId: string | null = null;
      let overlaySelectionMode: "none" | "profile" | "override" = "profile";
      if (standardsProfileSelection === "none") {
        overlaySelectionMode = "none";
      } else if (standardsProfileSelection === "pilot") {
        overlaySelectionMode = "override";
        selectedOverlayId = pilotOverlay?.overlay_id ?? null;
      } else if (standardsProfileSelection.startsWith("overlay:")) {
        overlaySelectionMode = "override";
        selectedOverlayId = standardsProfileSelection.slice("overlay:".length) || null;
      }

      const planningInputs = {
        extracted_part_facts: {},
        analysis_mode: analysisMode as AnalysisModeRuntime,
        selected_process_override: processOverrideMode === "force" ? forcedProcessId || null : null,
        selected_overlay: selectedOverlayId,
        process_selection_mode: processOverrideMode === "force" ? "override" : processOverrideMode,
        overlay_selection_mode: overlaySelectionMode,
        selected_role: selectedRoleId,
        selected_template: selectedTemplateId,
        run_both_if_mismatch: runBothIfMismatch,
      };

      const reviewResponse = await fetch(`${apiBase}/api/models/${modelId}/dfm/review-v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          planning_inputs: planningInputs,
          context_payload: contextPayload,
        }),
      });
      if (!reviewResponse.ok) {
        throw new Error(await readErrorText(reviewResponse, "Failed to generate DFM review v2"));
      }
      const reviewPayload = (await reviewResponse.json()) as DfmReviewV2Response;
      setReviewV2Result(reviewPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error while generating DFM review");
    } finally {
      setSubmitting(false);
    }
  };

  const renderFlowControl = (controlId: string) => {
    const control = controlsById.get(controlId);
    const label = control?.label ?? controlId.replaceAll("_", " ");

    if (!dfmConfig) return null;

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
            <select
              value={forcedProcessId}
              onChange={(event) => setForcedProcessId(event.target.value)}
              disabled={loadingConfig || !dfmConfig.processes.length}
            >
              {dfmConfig.processes.map((process) => (
                <option key={process.process_id} value={process.process_id}>
                  {process.label}
                </option>
              ))}
            </select>
          ) : (
            <p className="dfm-sidebar__meta">Profile process: {selectedProfile?.manufacturingProcess || "-"}</p>
          )}
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
          <p className="dfm-sidebar__meta">
            {analysisMode === "geometry_dfm"
              ? "Designer-first mode. Excludes drawing-only checks."
              : analysisMode === "drawing_spec"
              ? "Documentation-focused mode. Highlights drawing/spec gaps."
              : "Full mode. Includes geometry and documentation checks."}
          </p>
        </label>
      );
    }

    if (controlId === "industry_overlay") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>Standards profile (optional)</span>
          <select
            value={standardsProfileSelection}
            onChange={(event) => setStandardsProfileSelection(event.target.value as StandardsProfileSelection)}
          >
            <option value="profile_auto">Auto from profile</option>
            <option value="none">None (no overlay)</option>
            <option value="pilot" disabled={!pilotOverlay}>
              Pilots {pilotOverlay ? "" : "(not available)"}
            </option>
            {allStandardsOverlayId ? <option value={`overlay:${allStandardsOverlayId}`}>All standards</option> : null}
            {standardsOverlayOptions.map((overlay) => (
              <option key={overlay.overlay_id} value={`overlay:${overlay.overlay_id}`}>
                {overlay.label}
              </option>
            ))}
          </select>
          <p className="dfm-sidebar__meta">
            {standardsProfileSelection === "profile_auto"
              ? `Profile industry mapping: ${selectedProfile?.industry || "-"}`
              : standardsProfileSelection === "none"
              ? "No overlay selected."
              : standardsProfileSelection === "pilot"
              ? `Pilots: ${pilotOverlay?.label ?? "Overlay not available in bundle"}`
              : `Custom overlay: ${
                  standardsProfileSelection.slice("overlay:".length) === allStandardsOverlayId
                    ? "All standards"
                    : overlayLabelById(dfmConfig?.overlays ?? [], standardsProfileSelection.slice("overlay:".length) || null)
                }`}
          </p>
        </label>
      );
    }

    if (controlId === "role_lens") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>{label}</span>
          <select value={selectedRoleId} onChange={(event) => setSelectedRoleId(event.target.value)}>
            {dfmConfig.roles.map((role) => (
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
          <select
            value={selectedTemplateId}
            onChange={(event) => setSelectedTemplateId(event.target.value)}
            disabled={loadingModelTemplates || !modelTemplates.length}
          >
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
          <select
            value={selectedAdvancedModel}
            onChange={(event) => setSelectedAdvancedModel(event.target.value)}
            disabled={!advancedModelOptions.length}
          >
            {!advancedModelOptions.length ? (
              <option value="">Not configured</option>
            ) : null}
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
            <input
              type="checkbox"
              checked={runBothIfMismatch}
              onChange={(event) => setRunBothIfMismatch(event.target.checked)}
            />
            <span>{runBothIfMismatch ? "Enabled" : "Disabled"}</span>
          </div>
        </label>
      );
    }

    if (controlId === "generate_review") {
      return (
        <div key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>{label}</span>
          <button
            type="button"
            className="dfm-sidebar__submit"
            onClick={handleSubmit}
            disabled={submitting || loadingConfig || loadingModelTemplates}
          >
            {submitting ? "Generating..." : "Generate review"}
          </button>
        </div>
      );
    }

    return null;
  };

  const renderFindingItem = (route: DfmReviewRoute, finding: DfmReviewFinding) => {
    const standardsByRefId = new Map<string, DfmStandardRef>();
    route.standards_used_auto.forEach((standard) => {
      standardsByRefId.set(standard.ref_id, standard);
    });
    reviewV2Result?.standards_used_auto_union.forEach((standard) => {
      if (!standardsByRefId.has(standard.ref_id)) {
        standardsByRefId.set(standard.ref_id, standard);
      }
    });
    return (
      <li key={`${route.plan_id}-${finding.rule_id}-${finding.pack_id}-${finding.finding_type ?? "unknown"}`}>
        <strong>{finding.rule_id}</strong> [{finding.severity}] {finding.title ?? "Untitled rule"}
        {finding.refs.length ? (
          <div className="dfm-sidebar__finding-standards">
            Standards:{" "}
            {finding.refs.map((refId, index) => {
              const standard = standardsByRefId.get(refId);
              const label = standard?.title ? `${standard.title} (${refId})` : refId;
              return (
                <span key={`${finding.rule_id}-${refId}`}>
                  {index > 0 ? "; " : ""}
                  {standard?.url ? (
                    <a href={standard.url} target="_blank" rel="noreferrer">
                      {label}
                    </a>
                  ) : (
                    label
                  )}
                </span>
              );
            })}
          </div>
        ) : null}
        {finding.standard_clause ? <div className="dfm-sidebar__finding-clause">Clause: {finding.standard_clause}</div> : null}
        {finding.source_rule_id ? (
          <div className="dfm-sidebar__finding-clause">Source rule: {finding.source_rule_id}</div>
        ) : null}
        {finding.evidence_quality ? (
          <div className="dfm-sidebar__finding-clause">Evidence basis: {finding.evidence_quality}</div>
        ) : null}
        {finding.recommended_action ? <div className="dfm-sidebar__finding-action">{finding.recommended_action}</div> : null}
        {finding.expected_impact ? (
          <div className="dfm-sidebar__finding-impact">
            Impact: risk {finding.expected_impact.risk_reduction ?? "-"}, cost {finding.expected_impact.cost_impact ?? "-"},
            lead-time {finding.expected_impact.lead_time_impact ?? "-"}.
          </div>
        ) : null}
      </li>
    );
  };

  const standardsTraceStatus = (entry: DfmStandardTrace): string => {
    if (entry.design_risk_findings > 0) {
      return `finding (${entry.design_risk_findings})`;
    }
    if (entry.evidence_gap_findings > 0) {
      return `blocked by missing evidence (${entry.evidence_gap_findings})`;
    }
    if (entry.active_in_mode && entry.checks_passed > 0) {
      return `checked/no finding (${entry.checks_passed})`;
    }
    if (entry.active_in_mode && entry.checks_unresolved > 0) {
      return `active/no evaluator (${entry.checks_unresolved})`;
    }
    if (entry.active_in_mode) {
      return "active";
    }
    return "not active in this mode";
  };

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="dfm-sidebar">
        <div className="dfm-sidebar__header">
          <h2>Simple DFM Review</h2>
          <button type="button" onClick={onClose} className="dfm-sidebar__close" aria-label="Close DFM template">
            x
          </button>
        </div>

        <div className="dfm-sidebar__field">
          <span>Selected part</span>
          <div className="dfm-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>

        <div className="dfm-sidebar__plan-summary">
          <h3>Part context (from profile)</h3>
          <p className="dfm-sidebar__meta">Manufacturing process: {selectedProfile?.manufacturingProcess || "-"}</p>
          <p className="dfm-sidebar__meta">Material: {selectedProfile?.material || "-"}</p>
          <p className="dfm-sidebar__meta">Industry: {selectedProfile?.industry || "-"}</p>
        </div>

        <div className="dfm-sidebar__flow">
          <h3>Analysis controls</h3>
          <p className="dfm-sidebar__hint">
            Simplified mode: choose input scope and standards profile. Process override and mismatch settings are in
            Advanced controls.
          </p>
          <div className="dfm-sidebar__flow-controls">
            {primaryControlIds.map((controlId) => renderFlowControl(controlId))}
          </div>
          {secondaryControlIds.length ? (
            <details className="dfm-sidebar__details">
              <summary>Advanced controls</summary>
              <div className="dfm-sidebar__flow-controls">
                {secondaryControlIds.map((controlId) => renderFlowControl(controlId))}
              </div>
            </details>
          ) : null}
        </div>

        <div className="dfm-sidebar__plan-summary">
          <h3>Effective analysis context</h3>
          <p className="dfm-sidebar__meta">
            Input scope:{" "}
            {reviewV2Result?.effective_context?.analysis_mode
              ? reviewV2Result.effective_context.analysis_mode.selected_mode
              : analysisMode}{" "}
            (source: {reviewV2Result?.effective_context?.analysis_mode?.source ?? "ui_selection"})
          </p>
          {reviewV2Result?.effective_context?.process ? (
            <p className="dfm-sidebar__meta">
              Process: {reviewV2Result.effective_context.process.effective_process_label || "Auto (AI recommendation)"}{" "}
              (source: {reviewV2Result.effective_context.process.source})
            </p>
          ) : (
            <p className="dfm-sidebar__meta">
              Process:{" "}
              {processOverrideMode === "force"
                ? processLabelById(dfmConfig?.processes ?? [], forcedProcessId || null) || "None"
                : processOverrideMode === "auto"
                ? "Auto (AI recommendation)"
                : "Profile value"}{" "}
              (source: pending backend resolution)
            </p>
          )}
          {reviewV2Result?.effective_context?.overlay ? (
            <p className="dfm-sidebar__meta">
              Rule set:{" "}
              {reviewV2Result.effective_context.overlay.effective_overlay_id === allStandardsOverlayId
                ? "All standards"
                : reviewV2Result.effective_context.overlay.effective_overlay_label || "None"}{" "}
              (source:{" "}
              {reviewV2Result.effective_context.overlay.source})
            </p>
          ) : (
            <p className="dfm-sidebar__meta">
              Rule set:{" "}
              {standardsProfileSelection === "profile_auto"
                ? "Profile mapping"
                : standardsProfileSelection === "none"
                ? "None"
                : standardsProfileSelection === "pilot"
                ? overlayLabelById(dfmConfig?.overlays ?? [], pilotOverlay?.overlay_id ?? null)
                : overlayLabelById(
                    dfmConfig?.overlays ?? [],
                    standardsProfileSelection.slice("overlay:".length) || null
                  )}{" "}
              (source: pending backend resolution)
            </p>
          )}
          <p className="dfm-sidebar__meta">Part facts: Auto-loaded from selected part</p>
        </div>

        {reviewV2Result ? (
          <div className="dfm-sidebar__plan-summary">
            <h3>Plan summary</h3>
            <p className="dfm-sidebar__meta">
              AI recommendation:{" "}
              {reviewV2Result.ai_recommendation
                ? `${reviewV2Result.ai_recommendation.process_label} (${reviewV2Result.ai_recommendation.confidence_level}, ${reviewV2Result.ai_recommendation.confidence.toFixed(2)})`
                : "Not available"}
            </p>
            <p className="dfm-sidebar__meta">
              Selected packs:{" "}
              {reviewV2Result.routes[0]?.pack_ids?.length
                ? reviewV2Result.routes[0].pack_ids.join(", ")
                : "None"}
            </p>
            <p className="dfm-sidebar__meta">
              Route count: {reviewV2Result.route_count}{" "}
              {reviewV2Result.mismatch.run_both_executed ? "(run-both)" : ""}
            </p>
          </div>
        ) : null}

        {mismatchBanner ? <p className="dfm-sidebar__banner">{mismatchBanner}</p> : null}

        {reviewV2Result ? (
          <>
            <div className="dfm-sidebar__standards">
              <h3>{standardsLabel}</h3>
              <p className="dfm-sidebar__hint">Read-only. Derived from findings references only.</p>
              <details className="dfm-sidebar__standards-toggle">
                <summary>Standards list ({reviewV2Result.standards_used_auto_union.length})</summary>
                {reviewV2Result.standards_used_auto_union.length ? (
                  <ul className="dfm-sidebar__standards-list">
                    {reviewV2Result.standards_used_auto_union.map((standard) => (
                      <li key={standard.ref_id}>
                        <strong>{standard.ref_id}</strong>
                        {standard.url ? (
                          <a href={standard.url} target="_blank" rel="noreferrer">
                            {standard.title ?? standard.ref_id}
                          </a>
                        ) : (
                          <span>{standard.title ?? standard.ref_id}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="dfm-sidebar__hint">No standards fired from current findings.</p>
                )}
              </details>
              <details className="dfm-sidebar__standards-toggle">
                <summary>Standards trace (all in scope) ({reviewV2Result.standards_trace_union?.length ?? 0})</summary>
                {reviewV2Result.standards_trace_union?.length ? (
                  <ul className="dfm-sidebar__standards-list dfm-sidebar__standards-trace">
                    {reviewV2Result.standards_trace_union.map((standard) => (
                      <li key={`trace-${standard.ref_id}`}>
                        <strong>{standard.ref_id}</strong>
                        <span>
                          {standard.url ? (
                            <a href={standard.url} target="_blank" rel="noreferrer">
                              {standard.title ?? standard.ref_id}
                            </a>
                          ) : (
                            <span>{standard.title ?? standard.ref_id}</span>
                          )}
                        </span>
                        <span className="dfm-sidebar__trace-status">Status: {standardsTraceStatus(standard)}</span>
                        <span className="dfm-sidebar__trace-meta">
                          Rules considered: {standard.rules_considered} | Missing-evidence blocks:{" "}
                          {standard.blocked_by_missing_inputs}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="dfm-sidebar__hint">No standards trace available for this run.</p>
                )}
              </details>
            </div>

            <div className="dfm-sidebar__cost">
              <details className="dfm-sidebar__cost-toggle">
                <summary>{costLabel}</summary>
                <p className="dfm-sidebar__hint">Read-only. System-derived should-cost estimate.</p>
                {reviewV2Result.cost_estimate ? (
                  <>
                    <p className="dfm-sidebar__meta">
                      Unit: {reviewV2Result.cost_estimate.currency} {reviewV2Result.cost_estimate.unit_cost.toFixed(2)} | Total:{" "}
                      {reviewV2Result.cost_estimate.currency} {reviewV2Result.cost_estimate.total_cost.toFixed(2)}
                    </p>
                    <p className="dfm-sidebar__meta">
                      Confidence: {reviewV2Result.cost_estimate.confidence_level} ({reviewV2Result.cost_estimate.confidence.toFixed(2)})
                    </p>
                  </>
                ) : (
                  <p className="dfm-sidebar__hint">Cost estimation is disabled.</p>
                )}
                {reviewV2Result.cost_compare_routes ? (
                  <p className="dfm-sidebar__cost-delta">
                    Route delta: {reviewV2Result.cost_compare_routes.currency}{" "}
                    {reviewV2Result.cost_compare_routes.unit_cost_delta.toFixed(2)} per unit (
                    {reviewV2Result.cost_compare_routes.unit_cost_delta_percent.toFixed(2)}%).
                  </p>
                ) : null}
              </details>
            </div>

            <div className="dfm-sidebar__report">
              <h3>Review output</h3>
              <p className="dfm-sidebar__meta">
                Routes: {reviewV2Result.route_count} | Findings: {reviewV2Result.finding_count_total}
              </p>
              <label className="dfm-sidebar__field dfm-sidebar__toggle">
                <span>Show drawing/spec evidence gaps</span>
                <div className="dfm-sidebar__toggle-row">
                  <input
                    type="checkbox"
                    checked={showEvidenceGaps}
                    onChange={(event) => setShowEvidenceGaps(event.target.checked)}
                  />
                  <span>{showEvidenceGaps ? "Visible" : "Hidden by default"}</span>
                </div>
              </label>
              <label className="dfm-sidebar__field dfm-sidebar__toggle">
                <span>Pilot strict filter (PSTD + essential geometry)</span>
                <div className="dfm-sidebar__toggle-row">
                  <input
                    type="checkbox"
                    checked={pilotStrictFilter}
                    onChange={(event) => setPilotStrictFilter(event.target.checked)}
                  />
                  <span>{pilotStrictFilter ? "Enabled" : "Disabled"}</span>
                </div>
              </label>
              <p className="dfm-sidebar__hint">Display filter only; analysis run unchanged.</p>
              {reviewV2Result.routes.map((route) => {
                const allDesignRiskFindings = route.findings.filter((finding) => finding.finding_type === "rule_violation");
                const designRiskFindings =
                  pilotStrictFilter
                    ? allDesignRiskFindings.filter(
                        (finding) =>
                          finding.rule_id.startsWith("PSTD-") ||
                          PILOT_STRICT_ESSENTIAL_RULE_IDS.has(finding.rule_id)
                      )
                    : allDesignRiskFindings;
                const evidenceGapFindings = route.findings.filter((finding) => finding.finding_type !== "rule_violation");
                const shownFindingCount = designRiskFindings.length + (showEvidenceGaps ? evidenceGapFindings.length : 0);
                return (
                  <article key={`${route.plan_id}-${route.process_id}`} className="dfm-sidebar__route">
                    <header className="dfm-sidebar__route-header">
                      <strong>{route.process_label}</strong>
                      <span>
                        {shownFindingCount} shown
                        {shownFindingCount !== route.finding_count ? ` / ${route.finding_count} total` : ""}
                      </span>
                    </header>
                    <p className="dfm-sidebar__meta">
                      Packs:{" "}
                      {route.pack_labels.filter((label): label is string => Boolean(label)).join(", ") || route.pack_ids.join(", ")}
                    </p>
                    <p className="dfm-sidebar__meta">
                      Design risks: {designRiskFindings.length} | Drawing/spec evidence gaps: {evidenceGapFindings.length}
                    </p>
                    {route.cost_estimate ? (
                      <p className="dfm-sidebar__meta">
                        Cost: {route.cost_estimate.currency} {route.cost_estimate.unit_cost.toFixed(2)} / unit (
                        {route.cost_estimate.confidence_level})
                      </p>
                    ) : null}
                    {route.findings.length ? (
                      <div className="dfm-sidebar__findings-groups">
                        <details className="dfm-sidebar__finding-group" open={designRiskFindings.length > 0}>
                          <summary>Design risks ({designRiskFindings.length})</summary>
                          {designRiskFindings.length ? (
                            <ul className="dfm-sidebar__findings">
                              {designRiskFindings.slice(0, 20).map((finding) => renderFindingItem(route, finding))}
                            </ul>
                          ) : (
                            <p className="dfm-sidebar__hint">No design risk findings in this route.</p>
                          )}
                        </details>
                        {showEvidenceGaps ? (
                          <details className="dfm-sidebar__finding-group">
                            <summary>Drawing/spec evidence gaps ({evidenceGapFindings.length})</summary>
                            {evidenceGapFindings.length ? (
                              <ul className="dfm-sidebar__findings">
                                {evidenceGapFindings.slice(0, 20).map((finding) => renderFindingItem(route, finding))}
                              </ul>
                            ) : (
                              <p className="dfm-sidebar__hint">No evidence gaps in this route.</p>
                            )}
                          </details>
                        ) : (
                          <p className="dfm-sidebar__hint">
                            Drawing/spec evidence gaps hidden ({evidenceGapFindings.length}). Enable above to inspect.
                          </p>
                        )}
                      </div>
                    ) : (
                      <p className="dfm-sidebar__hint">No findings for this route.</p>
                    )}
                  </article>
                );
              })}
            </div>
          </>
        ) : null}

        {error ? <p className="dfm-sidebar__error">{error}</p> : null}
        {!profileComplete ? (
          <p className="dfm-sidebar__hint">
            Complete material, manufacturing process, and industry in the component profile for stronger DFM results.
          </p>
        ) : null}
        {modelId && !modelTemplates.length && !loadingModelTemplates ? (
          <p className="dfm-sidebar__hint">No templates found for this model yet.</p>
        ) : null}
      </div>
    </aside>
  );
};

export default DfmReviewSidebar;
