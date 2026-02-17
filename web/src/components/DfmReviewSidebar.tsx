import { ClipboardEvent, useEffect, useMemo, useState } from "react";

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

type DfmExecutionPlan = {
  plan_id: string;
  route_source: string;
  process_id: string;
  process_label: string;
  pack_ids: string[];
  pack_labels: (string | null)[];
  overlay_id: string | null;
  overlay_label: string | null;
  role_id: string;
  role_label: string;
  template_id: string;
  template_label: string;
  template_sections: string[];
  suppressed_template_sections: string[];
};

type DfmPlanResponse = {
  ai_recommendation: {
    process_id: string;
    process_label: string;
    confidence: number;
    confidence_level: string;
    reasons: string[];
  };
  selected_process: {
    process_id: string;
    process_label: string;
    selected_via: string;
  };
  selected_packs: string[];
  mismatch: {
    has_mismatch: boolean;
    user_selected_process: DfmPlanProcessRef | null;
    ai_process: DfmPlanProcessRef | null;
    run_both_requested: boolean;
    policy_allows_run_both: boolean;
    run_both_executed: boolean;
    banner: string | null;
  };
  execution_plans: DfmExecutionPlan[];
};

type DfmStandardRef = {
  ref_id: string;
  title?: string;
  url?: string;
  type?: string;
  notes?: string;
};

type DfmReviewFinding = {
  rule_id: string;
  pack_id: string;
  severity: string;
  title?: string;
  refs: string[];
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
  cost_estimate?: DfmCostEstimate | null;
};

type DfmReviewV2Response = {
  model_id: string;
  route_count: number;
  finding_count_total: number;
  standards_used_auto_union: DfmStandardRef[];
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
  "manufacturing_process",
  "industry_overlay",
  "role_lens",
  "report_template",
  "advanced_llm_model",
  "run_both_if_mismatch",
  "generate_review",
];

const DfmReviewSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  selectedProfile,
  profileComplete,
  onClose,
}: DfmReviewSidebarProps) => {
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dfmConfig, setDfmConfig] = useState<DfmConfigResponse | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [selectedProcessOverride, setSelectedProcessOverride] = useState("auto");
  const [selectedOverlayId, setSelectedOverlayId] = useState("");
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [modelTemplates, setModelTemplates] = useState<DfmModelTemplate[]>([]);
  const [loadingModelTemplates, setLoadingModelTemplates] = useState(false);
  const [selectedAdvancedModel, setSelectedAdvancedModel] = useState("");
  const [runBothIfMismatch, setRunBothIfMismatch] = useState(true);
  const [planResult, setPlanResult] = useState<DfmPlanResponse | null>(null);
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

  const mismatchBanner = useMemo(() => {
    if (!planResult?.mismatch?.has_mismatch) return null;
    if (planResult.mismatch.banner) return planResult.mismatch.banner;
    const user = planResult.mismatch.user_selected_process?.process_label;
    const ai = planResult.mismatch.ai_process?.process_label;
    if (!user || !ai) return null;
    return `User selected ${user}, AI recommended ${ai}.`;
  }, [planResult]);

  useEffect(() => {
    setError(null);
    setPlanResult(null);
    setReviewV2Result(null);
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

    const processMode = controlsById.get("manufacturing_process")?.default_mode;
    if (processMode === "auto") {
      setSelectedProcessOverride((current) => current || "auto");
    } else {
      const firstProcess = dfmConfig.processes[0]?.process_id ?? "auto";
      setSelectedProcessOverride((current) => current || firstProcess);
    }

    const runBothDefault = controlsById.get("run_both_if_mismatch")?.default;
    if (typeof runBothDefault === "boolean") {
      setRunBothIfMismatch(runBothDefault);
    }

    if (!selectedAdvancedModel && advancedModelOptions.length) {
      setSelectedAdvancedModel(advancedModelOptions[0]);
    }
  }, [advancedModelOptions, controlsById, dfmConfig, modelTemplates, selectedAdvancedModel]);

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = event.clipboardData.files;
    if (!files || files.length === 0) return;
    const imageFile = Array.from(files).find((file) => file.type.startsWith("image/"));
    if (!imageFile) return;
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setImageDataUrl(reader.result);
      }
    };
    reader.readAsDataURL(imageFile);
  };

  const buildExtractedPartFacts = (): Record<string, unknown> => {
    const facts: Record<string, unknown> = {};
    const processLabel = selectedProfile?.manufacturingProcess?.toLowerCase() ?? "";

    if (processLabel.includes("sheet")) {
      facts.bends_present = true;
      facts.constant_thickness = true;
      facts.sheet_thickness = 2.0;
    }
    if (processLabel.includes("turn")) {
      facts.rotational_symmetry = true;
      facts.turned_faces_present = true;
    }
    if (processLabel.includes("weld")) {
      facts.weld_symbols_detected = true;
      facts.multi_part_joined = true;
    }
    if (processLabel.includes("cnc") || processLabel.includes("mill")) {
      facts.pockets_present = true;
      facts.threaded_holes_count = 2;
      facts.feature_complexity_score = 1;
    }
    if (imageDataUrl) {
      facts.manual_context = true;
    }
    return facts;
  };

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
      const planningInputs = {
        extracted_part_facts: buildExtractedPartFacts(),
        selected_process_override:
          selectedProcessOverride === "auto" ? null : selectedProcessOverride,
        selected_overlay: selectedOverlayId || null,
        selected_role: selectedRoleId,
        selected_template: selectedTemplateId,
        run_both_if_mismatch: runBothIfMismatch,
      };

      const planResponse = await fetch(`${apiBase}/api/models/${modelId}/dfm/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(planningInputs),
      });
      if (!planResponse.ok) {
        throw new Error(await readErrorText(planResponse, "Failed to create DFM plan"));
      }
      const planPayload = (await planResponse.json()) as DfmPlanResponse;
      setPlanResult(planPayload);

      const contextPayload: Record<string, unknown> = {};
      if (selectedAdvancedModel) {
        contextPayload.advanced_llm_model = selectedAdvancedModel;
      }
      if (imageDataUrl) {
        contextPayload.manual_context = true;
      }

      const reviewResponse = await fetch(`${apiBase}/api/models/${modelId}/dfm/review-v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          execution_plans: planPayload.execution_plans,
          screenshot_data_url: imageDataUrl || null,
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
          <span>{label}</span>
          <select
            value={selectedProcessOverride}
            onChange={(event) => setSelectedProcessOverride(event.target.value)}
            disabled={loadingConfig || !dfmConfig.processes.length}
          >
            <option value="auto">Auto (AI recommendation)</option>
            {dfmConfig.processes.map((process) => (
              <option key={process.process_id} value={process.process_id}>
                {process.label}
              </option>
            ))}
          </select>
        </label>
      );
    }

    if (controlId === "industry_overlay") {
      return (
        <label key={controlId} className="dfm-sidebar__field dfm-sidebar__flow-step">
          <span>{label}</span>
          <select value={selectedOverlayId} onChange={(event) => setSelectedOverlayId(event.target.value)}>
            <option value="">None</option>
            {dfmConfig.overlays.map((overlay) => (
              <option key={overlay.overlay_id} value={overlay.overlay_id}>
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

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="dfm-sidebar">
        <div className="dfm-sidebar__header">
          <h2>DFM Review v2</h2>
          <button type="button" onClick={onClose} className="dfm-sidebar__close" aria-label="Close DFM template">
            x
          </button>
        </div>

        <div className="dfm-sidebar__field">
          <span>Selected part</span>
          <div className="dfm-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>
        <div className="dfm-sidebar__field">
          <span>Profile process</span>
          <div className="dfm-sidebar__readonly">{selectedProfile?.manufacturingProcess || "-"}</div>
        </div>
        <div className="dfm-sidebar__field">
          <span>Material</span>
          <div className="dfm-sidebar__readonly">{selectedProfile?.material || "-"}</div>
        </div>
        <div className="dfm-sidebar__field">
          <span>Industry</span>
          <div className="dfm-sidebar__readonly">{selectedProfile?.industry || "-"}</div>
        </div>

        <label className="dfm-sidebar__field">
          <span>Paste screenshot</span>
          <textarea
            className="dfm-sidebar__paste"
            onPaste={handlePaste}
            placeholder="Click here and paste image from clipboard (Ctrl/Cmd + V)."
          />
        </label>

        {imageDataUrl ? <img src={imageDataUrl} alt="Pasted screenshot preview" className="dfm-sidebar__image-preview" /> : null}

        <div className="dfm-sidebar__flow">
          <h3>Flow order</h3>
          <div className="dfm-sidebar__flow-controls">
            {flowOrder.map((controlId) => renderFlowControl(controlId))}
          </div>
        </div>

        {planResult ? (
          <div className="dfm-sidebar__plan-summary">
            <h3>Plan summary</h3>
            <p className="dfm-sidebar__meta">
              AI recommendation: {planResult.ai_recommendation.process_label} ({planResult.ai_recommendation.confidence_level},{" "}
              {planResult.ai_recommendation.confidence.toFixed(2)})
            </p>
            <p className="dfm-sidebar__meta">
              Selected packs: {planResult.selected_packs.length ? planResult.selected_packs.join(", ") : "None"}
            </p>
            <p className="dfm-sidebar__meta">
              Route count: {planResult.execution_plans.length}{" "}
              {planResult.mismatch.run_both_executed ? "(run-both)" : ""}
            </p>
          </div>
        ) : null}

        {mismatchBanner ? <p className="dfm-sidebar__banner">{mismatchBanner}</p> : null}

        {reviewV2Result ? (
          <>
            <div className="dfm-sidebar__standards">
              <h3>{standardsLabel}</h3>
              <p className="dfm-sidebar__hint">Read-only. Derived from findings references only.</p>
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
            </div>

            <div className="dfm-sidebar__cost">
              <h3>{costLabel}</h3>
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
            </div>

            <div className="dfm-sidebar__report">
              <h3>Review output</h3>
              <p className="dfm-sidebar__meta">
                Routes: {reviewV2Result.route_count} | Findings: {reviewV2Result.finding_count_total}
              </p>
              {reviewV2Result.routes.map((route) => (
                <article key={`${route.plan_id}-${route.process_id}`} className="dfm-sidebar__route">
                  <header className="dfm-sidebar__route-header">
                    <strong>{route.process_label}</strong>
                    <span>{route.finding_count} findings</span>
                  </header>
                  <p className="dfm-sidebar__meta">
                    Packs:{" "}
                    {route.pack_labels.filter((label): label is string => Boolean(label)).join(", ") || route.pack_ids.join(", ")}
                  </p>
                  {route.cost_estimate ? (
                    <p className="dfm-sidebar__meta">
                      Cost: {route.cost_estimate.currency} {route.cost_estimate.unit_cost.toFixed(2)} / unit (
                      {route.cost_estimate.confidence_level})
                    </p>
                  ) : null}
                  {route.findings.length ? (
                    <ul className="dfm-sidebar__findings">
                      {route.findings.slice(0, 20).map((finding) => (
                        <li key={`${route.plan_id}-${finding.rule_id}`}>
                          <strong>{finding.rule_id}</strong> [{finding.severity}] {finding.title ?? "Untitled rule"}
                          {finding.refs.length ? <span> refs: {finding.refs.join(", ")}</span> : null}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="dfm-sidebar__hint">No findings for this route.</p>
                  )}
                </article>
              ))}
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
