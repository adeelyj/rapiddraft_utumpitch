import { useEffect, useMemo, useState } from "react";
import type { AnalysisFocusPayload } from "../types/analysis";

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
  onFocusInModel?: (payload: AnalysisFocusPayload) => void;
  onClose: () => void;
};

type ProcessOverrideMode = "profile" | "auto" | "force";
type AnalysisMode = "geometry_dfm" | "drawing_spec" | "full";

type GeometryMetric = {
  key: string;
  label: string;
  value: string | number | boolean;
  unit?: string | null;
  geometry_anchor?: GeometryAnchor | null;
};

type GeometryAnchor = {
  anchor_id: string;
  component_node_name?: string | null;
  anchor_kind?: "point" | "region" | "multi" | "part";
  position_mm?: [number, number, number] | null;
  normal?: [number, number, number] | null;
  bbox_bounds_mm?: [number, number, number, number, number, number] | null;
  face_indices?: number[];
  label?: string | null;
};

type GeometryFeatureGroup = {
  group_id: string;
  label: string;
  summary: string;
  metrics: GeometryMetric[];
  geometry_anchor?: GeometryAnchor | null;
  localized_features?: GeometryFeatureItem[];
};

type GeometryFeatureItem = {
  feature_id: string;
  label: string;
  summary?: string | null;
  geometry_anchor?: GeometryAnchor | null;
  feature_type?: string | null;
  feature_subtype?: string | null;
};

type DfmFindingAnchor = GeometryAnchor;

type DfmFindingBlameMap = {
  localization_status?: "exact_feature" | "region" | "multi" | "part_level" | "unlocalized";
  primary_anchor?: DfmFindingAnchor | null;
  secondary_anchors?: DfmFindingAnchor[];
  source_fact_keys?: string[];
  source_feature_refs?: string[];
  explanation?: string | null;
};

type DfmViolatingInstance = {
  instance_id: string;
  edge_index?: number | null;
  subtype?: string | null;
  location_description?: string | null;
  radius_mm?: number | null;
  diameter_mm?: number | null;
  depth_mm?: number | null;
  thickness_mm?: number | null;
  status?: string | null;
  recommendation?: string | null;
  pocket_depth_mm?: number | null;
  depth_to_radius_ratio?: number | null;
  depth_to_diameter_ratio?: number | null;
  aggravating_factor?: boolean;
  position_mm?: [number, number, number] | null;
  bbox_bounds_mm?: [number, number, number, number, number, number] | null;
  face_indices?: number[];
  violation_reasons?: string[];
};

const DFM_BENCHMARK_CACHE_PREFIX = "dfm_benchmark_sidebar_review_last_v1";
const LOCALIZED_FEATURE_PREVIEW_LIMIT = 4;
const DEFAULT_FLOW_ORDER = [
  "analysis_mode",
  "manufacturing_process",
  "role_lens",
  "report_template",
  "advanced_llm_model",
  "run_both_if_mismatch",
  "generate_review",
];

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

const formatCompactNumber = (value: number, digits = 1): string =>
  Number.isInteger(value) ? value.toString() : value.toFixed(digits);

const compactOverlayTitle = (value: string): string => {
  const normalized = value.replace(/\s+/g, " ").trim();
  const withoutParenthetical = normalized.replace(/\s*\([^)]*\)/g, "").trim();
  const firstClause = withoutParenthetical
    .split("→")[0]
    ?.split(";")[0]
    ?.trim();
  const compact = firstClause || withoutParenthetical || normalized;
  return compact.length > 52 ? `${compact.slice(0, 49).trimEnd()}...` : compact;
};

const compactOverlayLocation = (...values: Array<string | null | undefined>): string | undefined => {
  const candidate = values.find((value) => typeof value === "string" && value.trim());
  if (!candidate) return undefined;
  const compact = candidate
    .split("|")[0]
    .replace(/^Primary mapped region for [^:]+:\s*/i, "")
    .trim();
  return compact || undefined;
};

const formatViolationReason = (value: string): string => {
  if (value.startsWith("radius_below_")) {
    return `Radius below ${value.replace("radius_below_", "").replace("_mm", "")} mm`;
  }
  if (value.startsWith("pocket_depth_above_")) {
    return `Pocket depth above ${value.replace("pocket_depth_above_", "").replace("_mm", "")} mm`;
  }
  if (value.startsWith("depth_to_radius_ratio_above_")) {
    return `Depth/radius above ${value.replace("depth_to_radius_ratio_above_", "")}`;
  }
  if (value.startsWith("radius_variation_ratio_above_")) {
    return `Radius variation above ${value.replace("radius_variation_ratio_above_", "")}`;
  }
  if (value === "non_dominant_corner_radius") {
    return "Non-dominant corner radius";
  }
  if (value === "long_reach_tool_risk") {
    return "Long-reach tool risk";
  }
  if (value === "critical_corner_crevice") {
    return "Critical crevice-prone corner";
  }
  if (value === "zero_or_negative_radius") {
    return "Zero-radius corner";
  }
  return value.replaceAll("_", " ");
};

const instanceMetricFragments = (instance: DfmViolatingInstance): string[] =>
  [
    typeof instance.radius_mm === "number" ? `R${formatCompactNumber(instance.radius_mm, 2)} mm` : null,
    typeof instance.diameter_mm === "number" ? `Dia ${formatCompactNumber(instance.diameter_mm, 2)} mm` : null,
    typeof instance.depth_mm === "number" ? `Depth ${formatCompactNumber(instance.depth_mm, 2)} mm` : null,
    typeof instance.thickness_mm === "number" ? `Thickness ${formatCompactNumber(instance.thickness_mm, 2)} mm` : null,
    typeof instance.pocket_depth_mm === "number" ? `Depth ${formatCompactNumber(instance.pocket_depth_mm, 2)} mm` : null,
    typeof instance.depth_to_radius_ratio === "number"
      ? `Ratio ${formatCompactNumber(instance.depth_to_radius_ratio, 2)}`
      : null,
    typeof instance.depth_to_diameter_ratio === "number"
      ? `D/D ${formatCompactNumber(instance.depth_to_diameter_ratio, 2)}`
      : null,
  ].filter((value): value is string => Boolean(value && value.trim()));

const hasAnchorFocusData = (anchor: GeometryAnchor | null | undefined): anchor is GeometryAnchor =>
  Boolean(
    anchor &&
      ((anchor.position_mm && anchor.position_mm.length === 3) ||
        (anchor.bbox_bounds_mm && anchor.bbox_bounds_mm.length === 6) ||
        anchor.component_node_name),
  );

const blameMapLabel = (blameMap: DfmFindingBlameMap | undefined): string | null => {
  switch (blameMap?.localization_status) {
    case "multi":
      return "Multi-location focus";
    case "region":
      return "Regional focus";
    case "exact_feature":
      return "Feature focus";
    case "part_level":
      return "Whole-part focus";
    default:
      return null;
  }
};

const DfmBenchmarkSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  selectedProfile,
  profileComplete,
  onFocusInModel,
  onClose,
}: DfmBenchmarkSidebarProps) => {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dfmConfig, setDfmConfig] = useState<Record<string, any> | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("geometry_dfm");
  const [processOverrideMode, setProcessOverrideMode] = useState<ProcessOverrideMode>("auto");
  const [forcedProcessId, setForcedProcessId] = useState("");
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
    () => flowOrder.filter((controlId) => ["generate_review"].includes(controlId)),
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
  const roles = (dfmConfig?.roles ?? []) as Array<{ role_id: string; label: string }>;
  const advancedModelOptions = ((controlsById.get("advanced_llm_model")?.options as string[] | undefined) ?? []).filter(Boolean);

  useEffect(() => {
    setError(null);
    setReviewResult(readCachedReview(buildCacheKey(modelId, selectedComponent?.nodeName)));
    setDetailsVersion((current) => current + 1);
  }, [modelId, selectedComponent?.nodeName]);

  useEffect(() => {
    setSelectedTemplateId("");
  }, [modelId]);

  const readErrorText = async (response: Response, fallback: string) => {
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      return payload.detail ?? payload.message ?? fallback;
    } catch {
      return fallback;
    }
  };

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
          const templatePayload = (await templateResponse.json()) as {
            templates?: Array<{ template_id: string; label: string; source: string }>;
          };
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
      const response = await fetch(`${apiBase}/api/models/${modelId}/dfm/review-v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: selectedComponent.nodeName,
          planning_inputs: {
            extracted_part_facts: {},
            analysis_mode: analysisMode,
            selected_process_override: processOverrideMode === "force" ? forcedProcessId || null : null,
            selected_overlay: null,
            process_selection_mode: processOverrideMode === "force" ? "override" : processOverrideMode,
            overlay_selection_mode: "none",
            selected_role: selectedRoleId,
            selected_template: selectedTemplateId,
            run_both_if_mismatch: runBothIfMismatch,
          },
          context_payload: {
            ...(selectedAdvancedModel ? { advanced_llm_model: selectedAdvancedModel } : {}),
            include_geometry_anchors: true,
          },
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
    const impact = finding.expected_impact
      ? `Risk ${finding.expected_impact.risk_reduction ?? "-"} | Cost ${finding.expected_impact.cost_impact ?? "-"} | Lead time ${finding.expected_impact.lead_time_impact ?? "-"}`
      : null;
    const violatingInstances = Array.isArray(finding.evidence?.violating_instances)
      ? (finding.evidence.violating_instances as DfmViolatingInstance[])
      : [];
    const routeLabel = reviewRoutes.length > 1 ? (route.process_label ?? route.process_id ?? "Unknown route") : null;
    const blameMap = finding.blame_map as DfmFindingBlameMap | undefined;
    const blameMapHint = blameMapLabel(blameMap);
    const primaryFindingAnchor =
      blameMap?.primary_anchor &&
      (((blameMap.primary_anchor.position_mm && blameMap.primary_anchor.position_mm.length === 3) ||
        (blameMap.primary_anchor.bbox_bounds_mm && blameMap.primary_anchor.bbox_bounds_mm.length === 6)) ||
        Boolean(blameMap.primary_anchor.component_node_name))
        ? blameMap.primary_anchor
        : null;
    const primaryFindingInstance = violatingInstances.find(
      (instance) =>
        (instance.position_mm && instance.position_mm.length === 3) ||
        (instance.bbox_bounds_mm && instance.bbox_bounds_mm.length === 6),
    );
    const previewInstances = violatingInstances.slice(0, violatingInstances.length > 4 ? 2 : 3);

    const focusFindingAnchor = (anchor: DfmFindingAnchor, explanation?: string | null) => {
      if (!onFocusInModel) return;
      const details = [
        routeLabel,
        explanation || null,
        anchor.label || null,
      ].filter((value): value is string => Boolean(value && value.trim()));

      onFocusInModel({
        id: `dfm-benchmark-${finding.rule_id ?? "issue"}-${anchor.anchor_id || "primary"}`,
        source: "dfm_benchmark",
        title: finding.title ?? finding.rule_id ?? "DFM issue",
        details: details.join(" | "),
        severity: finding.severity ?? "info",
        camera_behavior: "preserve",
        overlay_variant: "compact",
        overlay_title: compactOverlayTitle(finding.title ?? finding.rule_id ?? "DFM issue"),
        overlay_location: compactOverlayLocation(anchor.label, blameMap?.explanation),
        component_node_name: anchor.component_node_name ?? selectedComponent?.nodeName ?? null,
        anchor_kind: anchor.anchor_kind,
        position_mm: anchor.position_mm ?? null,
        normal: anchor.normal ?? null,
        bbox_bounds_mm: anchor.bbox_bounds_mm ?? null,
        face_indices: anchor.face_indices ?? [],
      });
    };

    const focusFindingInstance = (instance: DfmViolatingInstance) => {
      if (!onFocusInModel) return;
      if (
        (!instance.position_mm || instance.position_mm.length !== 3) &&
        (!instance.bbox_bounds_mm || instance.bbox_bounds_mm.length !== 6)
      ) {
        return;
      }

      const details = [
        instance.location_description || instance.instance_id,
        routeLabel,
        instanceMetricFragments(instance)[0] ?? null,
      ].filter((value): value is string => Boolean(value && value.trim()));

      onFocusInModel({
        id: `dfm-benchmark-${finding.rule_id ?? "issue"}-${instance.instance_id}`,
        source: "dfm_benchmark",
        title: finding.title ?? finding.rule_id ?? "DFM issue",
        details: details.join(" | "),
        severity: finding.severity ?? "info",
        camera_behavior: "preserve",
        overlay_variant: "compact",
        overlay_title: compactOverlayTitle(finding.title ?? finding.rule_id ?? "DFM issue"),
        overlay_location: compactOverlayLocation(instance.location_description, instance.instance_id),
        component_node_name: selectedComponent?.nodeName ?? null,
        anchor_kind:
          instance.bbox_bounds_mm && instance.bbox_bounds_mm.length === 6 ? "region" : "point",
        position_mm: instance.position_mm ?? null,
        normal: null,
        bbox_bounds_mm: instance.bbox_bounds_mm ?? null,
        face_indices: [],
      });
    };

    return (
      <li key={`${route.plan_id}-${finding.rule_id}-${finding.pack_id}-${finding.finding_type ?? "unknown"}`} className="dfm-sidebar__issue-card">
        <div className="dfm-sidebar__issue-card-header">
          <strong>{finding.title ?? finding.rule_id ?? "Untitled issue"}</strong>
          <div className="dfm-sidebar__issue-actions">
            {primaryFindingAnchor || primaryFindingInstance ? (
              <button
                type="button"
                className="dfm-sidebar__issue-focus-button"
                onClick={() =>
                  primaryFindingAnchor
                    ? focusFindingAnchor(primaryFindingAnchor, blameMap?.explanation)
                    : primaryFindingInstance
                      ? focusFindingInstance(primaryFindingInstance)
                      : undefined
                }
                title="Show primary mapped location in model"
              >
                Show in model
              </button>
            ) : null}
            <span className="dfm-sidebar__issue-badge">{finding.severity ?? "info"}</span>
          </div>
        </div>
        {routeLabel ? <p className="dfm-sidebar__issue-rule">{routeLabel}</p> : null}
        {finding.description ? <p className="dfm-sidebar__issue-description">{finding.description}</p> : null}
        {finding.recommended_action ? <div className="dfm-sidebar__finding-action">{finding.recommended_action}</div> : null}
        {blameMapHint ? <div className="dfm-sidebar__issue-focus-hint">{blameMapHint}</div> : null}
        {violatingInstances.length ? (
          <>
            <div className="dfm-sidebar__issue-location-preview">
              <div className="dfm-sidebar__issue-location-preview-header">
                <strong>Key locations</strong>
                <span>
                  {violatingInstances.length} mapped location{violatingInstances.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="dfm-sidebar__issue-location-preview-list">
                {previewInstances.map((instance) => {
                  const interactive = Boolean(
                    onFocusInModel &&
                      ((instance.position_mm && instance.position_mm.length === 3) ||
                        (instance.bbox_bounds_mm && instance.bbox_bounds_mm.length === 6)),
                  );
                  const previewContent = (
                    <>
                      <strong className="dfm-sidebar__issue-location-preview-label">
                        {instance.location_description || instance.instance_id}
                      </strong>
                      <span className="dfm-sidebar__issue-location-preview-meta">
                        {instanceMetricFragments(instance).slice(0, 2).join(" | ") || "Mapped feature region"}
                      </span>
                    </>
                  );

                  if (!interactive) {
                    return (
                      <div key={`preview-${instance.instance_id}`} className="dfm-sidebar__issue-location-preview-item">
                        {previewContent}
                      </div>
                    );
                  }

                  return (
                    <button
                      key={`preview-${instance.instance_id}`}
                      type="button"
                      className="dfm-sidebar__issue-location-preview-item dfm-sidebar__issue-location-preview-item--interactive"
                      onClick={() => focusFindingInstance(instance)}
                      title={`Show ${instance.location_description || instance.instance_id} in model`}
                    >
                      {previewContent}
                    </button>
                  );
                })}
              </div>
            </div>
            <details className="dfm-sidebar__issue-instances">
            <summary>
              {violatingInstances.length > previewInstances.length
                ? `Show all ${violatingInstances.length} mapped locations`
                : `Mapped locations detail`}
            </summary>
            <div className="dfm-sidebar__issue-instance-list">
              {violatingInstances.map((instance) => {
                const interactive = Boolean(
                  onFocusInModel &&
                    ((instance.position_mm && instance.position_mm.length === 3) ||
                      (instance.bbox_bounds_mm && instance.bbox_bounds_mm.length === 6)),
                );
                const content = (
                  <>
                    <div className="dfm-sidebar__issue-instance-copy">
                      <strong className="dfm-sidebar__issue-instance-label">
                        {instance.location_description || instance.instance_id}
                      </strong>
                      <span className="dfm-sidebar__issue-instance-meta">
                        {instanceMetricFragments(instance).join(" | ")}
                      </span>
                    </div>
                    {Array.isArray(instance.violation_reasons) && instance.violation_reasons.length ? (
                      <span className="dfm-sidebar__issue-instance-reasons">
                        {instance.violation_reasons.map(formatViolationReason).join(" • ")}
                      </span>
                    ) : null}
                  </>
                );

                if (!interactive) {
                  return (
                    <div key={instance.instance_id} className="dfm-sidebar__issue-instance">
                      {content}
                    </div>
                  );
                }

                return (
                  <button
                    key={instance.instance_id}
                    type="button"
                    className="dfm-sidebar__issue-instance dfm-sidebar__issue-instance--interactive"
                    onClick={() => focusFindingInstance(instance)}
                    title={`Show ${instance.location_description || instance.instance_id} in model`}
                  >
                    {content}
                  </button>
                );
              })}
            </div>
          </details>
          </>
        ) : null}
        {impact ? <div className="dfm-sidebar__issue-impact">{impact}</div> : null}
      </li>
    );
  };

  const renderEvidenceGapItem = (route: Record<string, any>, finding: Record<string, any>) => (
    <li key={`${route.plan_id}-${finding.rule_id}-${finding.pack_id}-${finding.finding_type ?? "gap"}`} className="dfm-sidebar__gap-card">
      <strong>{finding.title ?? finding.rule_id ?? "Untitled gap"}</strong>
      {reviewRoutes.length > 1 ? (
        <p className="dfm-sidebar__issue-rule">{route.process_label ?? route.process_id ?? "Unknown route"}</p>
      ) : null}
      {finding.recommended_action ? <p className="dfm-sidebar__hint">{finding.recommended_action}</p> : null}
    </li>
  );

  const geometryEvidence = reviewResult?.geometry_evidence as
    | {
        process_summary?: { effective_process_label?: string | null; ai_process_label?: string | null };
        feature_groups?: GeometryFeatureGroup[];
        detail_metrics?: GeometryMetric[];
      }
    | undefined;

  const focusFeatureGroup = (group: GeometryFeatureGroup) => {
    if (!onFocusInModel) return;

    const anchor = hasAnchorFocusData(group.geometry_anchor) ? group.geometry_anchor : null;
    const componentNodeName = anchor?.component_node_name ?? selectedComponent?.nodeName ?? null;
    if (!anchor && !componentNodeName) return;

    const details = [group.summary, anchor?.label]
      .filter((value): value is string => Boolean(value && value.trim()))
      .filter((value, index, array) => array.indexOf(value) === index);

    onFocusInModel({
      id: anchor?.anchor_id || `dfm-benchmark-feature-group-${group.group_id}`,
      source: "dfm_benchmark",
      title: group.label,
      details: details.join(" | ") || undefined,
      severity: "info",
      overlay_location: compactOverlayLocation(anchor?.label),
      component_node_name: componentNodeName,
      anchor_kind: anchor?.anchor_kind ?? "part",
      position_mm: anchor?.position_mm ?? null,
      normal: anchor?.normal ?? null,
      bbox_bounds_mm: anchor?.bbox_bounds_mm ?? null,
      face_indices: anchor?.face_indices ?? [],
    });
  };

  const focusLocalizedFeature = (group: GeometryFeatureGroup, feature: GeometryFeatureItem) => {
    if (!onFocusInModel) return;

    const anchor = hasAnchorFocusData(feature.geometry_anchor) ? feature.geometry_anchor : null;
    const componentNodeName = anchor?.component_node_name ?? selectedComponent?.nodeName ?? null;
    if (!anchor && !componentNodeName) return;

    const details = [group.label, feature.summary]
      .filter((value): value is string => Boolean(value && value.trim()))
      .filter((value, index, array) => array.indexOf(value) === index);

    onFocusInModel({
      id: anchor?.anchor_id || feature.feature_id,
      source: "dfm_benchmark",
      title: feature.label,
      details: details.join(" | ") || undefined,
      severity: "info",
      overlay_location: compactOverlayLocation(anchor?.label),
      component_node_name: componentNodeName,
      anchor_kind: anchor?.anchor_kind ?? "part",
      position_mm: anchor?.position_mm ?? null,
      normal: anchor?.normal ?? null,
      bbox_bounds_mm: anchor?.bbox_bounds_mm ?? null,
      face_indices: anchor?.face_indices ?? [],
    });
  };

  const focusGeometryMetric = (
    metric: GeometryMetric,
    options: {
      groupLabel?: string;
      groupSummary?: string;
      fallbackComponentNodeName?: string | null;
    } = {},
  ) => {
    if (!onFocusInModel || !metric.geometry_anchor) return;
    const anchor = metric.geometry_anchor;
    const detailsFragments = [options.groupLabel, options.groupSummary, anchor.label]
      .filter((value): value is string => Boolean(value && value.trim()))
      .filter((value, index, array) => array.indexOf(value) === index);

    onFocusInModel({
      id: anchor.anchor_id || `dfm-benchmark-${metric.key}`,
      source: "dfm_benchmark",
      title: metric.label,
      details: detailsFragments.join(" | ") || undefined,
      severity: "info",
      component_node_name:
        anchor.component_node_name ?? options.fallbackComponentNodeName ?? selectedComponent?.nodeName ?? null,
      anchor_kind: anchor.anchor_kind,
      position_mm: anchor.position_mm ?? null,
      normal: anchor.normal ?? null,
      bbox_bounds_mm: anchor.bbox_bounds_mm ?? null,
      face_indices: anchor.face_indices ?? [],
    });
  };

  const renderMetricRow = (
    metric: GeometryMetric,
    options: {
      key: string;
      groupLabel?: string;
      groupSummary?: string;
    },
  ) => {
    const interactive = Boolean(metric.geometry_anchor && onFocusInModel);
    const className = `dfm-sidebar__metric-row${interactive ? " dfm-sidebar__metric-row--interactive" : ""}`;
    const content = (
      <>
        <span className="dfm-sidebar__metric-label">{metric.label}</span>
        <strong className="dfm-sidebar__metric-value">{metricValue(metric)}</strong>
      </>
    );

    if (!interactive) {
      return (
        <div key={options.key} className={className}>
          {content}
        </div>
      );
    }

    return (
      <button
        key={options.key}
        type="button"
        className={className}
        onClick={() =>
          focusGeometryMetric(metric, {
            groupLabel: options.groupLabel,
            groupSummary: options.groupSummary,
            fallbackComponentNodeName: selectedComponent?.nodeName ?? null,
          })
        }
        title={`Show ${metric.label.toLowerCase()} in model`}
      >
        {content}
      </button>
    );
  };

  const renderLocalizedFeatureItem = (
    group: GeometryFeatureGroup,
    feature: GeometryFeatureItem,
  ) => {
    const interactive = Boolean(onFocusInModel && (hasAnchorFocusData(feature.geometry_anchor) || selectedComponent?.nodeName));
    const className = `dfm-sidebar__localized-feature${interactive ? " dfm-sidebar__localized-feature--interactive" : ""}`;
    const content = (
      <>
        <strong className="dfm-sidebar__localized-feature-title">{feature.label}</strong>
        {feature.summary ? <span className="dfm-sidebar__localized-feature-summary">{feature.summary}</span> : null}
      </>
    );

    if (!interactive) {
      return (
        <div key={feature.feature_id} className={className}>
          {content}
        </div>
      );
    }

    return (
      <button
        key={feature.feature_id}
        type="button"
        className={className}
        onClick={() => focusLocalizedFeature(group, feature)}
        title={`Show ${feature.label.toLowerCase()} in model`}
        aria-label={`Show ${feature.label.toLowerCase()} in model`}
      >
        {content}
      </button>
    );
  };

  const reviewRoutes = (reviewResult?.routes ?? []) as Array<Record<string, any>>;
  const routeFindings = reviewRoutes.map((route) => {
    const designRiskFindings = (route.findings ?? []).filter((finding: Record<string, any>) => finding.finding_type === "rule_violation");
    const evidenceGapFindings = (route.findings ?? []).filter((finding: Record<string, any>) => finding.finding_type !== "rule_violation");
    return { route, designRiskFindings, evidenceGapFindings };
  });
  const totalDesignRiskCount = routeFindings.reduce((sum, entry) => sum + entry.designRiskFindings.length, 0);
  const totalEvidenceGapCount = routeFindings.reduce((sum, entry) => sum + entry.evidenceGapFindings.length, 0);
  const localizedFeatureCount =
    geometryEvidence?.feature_groups?.reduce((sum, group) => sum + (group.localized_features?.length ?? 0), 0) ?? 0;
  const featureRecognitionCount =
    (geometryEvidence?.feature_groups?.length ?? 0) + (geometryEvidence?.detail_metrics?.length ?? 0) + localizedFeatureCount;

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="dfm-sidebar">
        <div className="dfm-sidebar__top">
          <div className="dfm-sidebar__header">
            <h2>DFM Benchmark Bar</h2>
            <button type="button" onClick={onClose} className="dfm-sidebar__close" aria-label="Close DFM Benchmark Bar">
              x
            </button>
          </div>

          <div className="dfm-sidebar__selected-part dfm-sidebar__panel--compact">
            <span className="dfm-sidebar__selected-part-label">Selected part</span>
            <strong>{selectedComponent?.displayName ?? "Select a part to review"}</strong>
          </div>

          <details className="dfm-sidebar__plan-summary dfm-sidebar__part-context dfm-sidebar__panel--compact">
            <summary>Profile context</summary>
            <div className="dfm-sidebar__compact-meta-list">
              <p className="dfm-sidebar__meta">Manufacturing process: {selectedProfile?.manufacturingProcess || "-"}</p>
              <p className="dfm-sidebar__meta">Material: {selectedProfile?.material || "-"}</p>
              <p className="dfm-sidebar__meta">Industry: {selectedProfile?.industry || "-"}</p>
            </div>
          </details>

          <div className="dfm-sidebar__flow dfm-sidebar__panel--compact">
            <h3>Run review</h3>
            <div className="dfm-sidebar__flow-controls">{primaryControlIds.map((controlId) => renderFlowControl(controlId))}</div>
            {secondaryControlIds.length ? (
              <details className="dfm-sidebar__details">
                <summary>Review settings</summary>
                <div className="dfm-sidebar__flow-controls">{secondaryControlIds.map((controlId) => renderFlowControl(controlId))}</div>
              </details>
            ) : null}
          </div>
        </div>

        {mismatchBanner ? <p className="dfm-sidebar__banner">{mismatchBanner}</p> : null}
        {error ? <p className="dfm-sidebar__error">{error}</p> : null}

        {!reviewResult ? (
          <div className="dfm-sidebar__report">
            <h3>DFM issues</h3>
            <p className="dfm-sidebar__hint">Run a review to see design issues first, with feature recognition tucked into a collapsible section below.</p>
          </div>
        ) : null}

        {reviewResult ? (
          <div className="dfm-sidebar__report">
            <h3>DFM issues</h3>
            <p className="dfm-sidebar__meta">
              {totalDesignRiskCount} design issue{totalDesignRiskCount === 1 ? "" : "s"}
              {totalEvidenceGapCount ? ` | ${totalEvidenceGapCount} input gap${totalEvidenceGapCount === 1 ? "" : "s"} hidden below` : ""}
            </p>

            {totalDesignRiskCount ? (
              routeFindings.map(({ route, designRiskFindings }) =>
                designRiskFindings.length ? (
                  <article key={`${route.plan_id}-${route.process_id}`} className="dfm-sidebar__route">
                    {reviewRoutes.length > 1 ? (
                      <header className="dfm-sidebar__route-header">
                        <strong>{route.process_label}</strong>
                        <span>{designRiskFindings.length} issue{designRiskFindings.length === 1 ? "" : "s"}</span>
                      </header>
                    ) : null}
                    <ul className="dfm-sidebar__issue-list">
                      {designRiskFindings.slice(0, 20).map((finding: Record<string, any>) => renderFindingItem(route, finding))}
                    </ul>
                  </article>
                ) : null,
              )
            ) : (
              <p className="dfm-sidebar__hint">No DFM design issues were raised for this run.</p>
            )}

            {totalEvidenceGapCount ? (
              <details className="dfm-sidebar__details">
                <summary>Input gaps ({totalEvidenceGapCount})</summary>
                <div className="dfm-sidebar__findings-groups">
                  {routeFindings.map(({ route, evidenceGapFindings }) =>
                    evidenceGapFindings.length ? (
                      <article key={`${route.plan_id}-${route.process_id}-gaps`} className="dfm-sidebar__route">
                        {reviewRoutes.length > 1 ? (
                          <header className="dfm-sidebar__route-header">
                            <strong>{route.process_label}</strong>
                            <span>{evidenceGapFindings.length} gap{evidenceGapFindings.length === 1 ? "" : "s"}</span>
                          </header>
                        ) : null}
                        <ul className="dfm-sidebar__issue-list">
                          {evidenceGapFindings.slice(0, 20).map((finding: Record<string, any>) => renderEvidenceGapItem(route, finding))}
                        </ul>
                      </article>
                    ) : null,
                  )}
                </div>
              </details>
            ) : null}
          </div>
        ) : null}

        {reviewResult ? (
          <details key={`feature-recognition-${detailsVersion}`} className="dfm-sidebar__evidence">
            <summary>Feature recognition ({featureRecognitionCount})</summary>
            <div className="dfm-sidebar__feature-summary">
              <p className="dfm-sidebar__meta">
                Likely process: {geometryEvidence?.process_summary?.effective_process_label ?? reviewRoutes[0]?.process_label ?? "Not resolved"}
              </p>
            </div>

            {geometryEvidence?.feature_groups?.length ? (
              <div className="dfm-sidebar__feature-groups">
                {geometryEvidence.feature_groups.map((group) => (
                  <section key={group.group_id} className="dfm-sidebar__feature-group">
                    {onFocusInModel && (hasAnchorFocusData(group.geometry_anchor) || selectedComponent?.nodeName) ? (
                      <button
                        type="button"
                        className="dfm-sidebar__feature-group-focus"
                        onClick={() => focusFeatureGroup(group)}
                        aria-label={`Show ${group.label.toLowerCase()} in model`}
                        title={`Show ${group.label.toLowerCase()} in model`}
                      >
                        <div className="dfm-sidebar__feature-group-header">
                          <strong>{group.label}</strong>
                          <span className="dfm-sidebar__feature-group-action">Show in model</span>
                        </div>
                        <p className="dfm-sidebar__feature-group-summary">{group.summary}</p>
                      </button>
                    ) : (
                      <>
                        <div className="dfm-sidebar__feature-group-header">
                          <strong>{group.label}</strong>
                        </div>
                        <p className="dfm-sidebar__feature-group-summary">{group.summary}</p>
                      </>
                    )}
                    {group.localized_features?.length ? (
                      <div className="dfm-sidebar__localized-features">
                        <p className="dfm-sidebar__localized-features-label">
                          Localized features ({group.localized_features.length})
                        </p>
                        <div className="dfm-sidebar__localized-feature-list">
                          {group.localized_features
                            .slice(0, LOCALIZED_FEATURE_PREVIEW_LIMIT)
                            .map((feature) => renderLocalizedFeatureItem(group, feature))}
                        </div>
                        {group.localized_features.length > LOCALIZED_FEATURE_PREVIEW_LIMIT ? (
                          <details className="dfm-sidebar__details dfm-sidebar__details--nested">
                            <summary>More localized features ({group.localized_features.length - LOCALIZED_FEATURE_PREVIEW_LIMIT})</summary>
                            <div className="dfm-sidebar__localized-feature-list">
                              {group.localized_features
                                .slice(LOCALIZED_FEATURE_PREVIEW_LIMIT)
                                .map((feature) => renderLocalizedFeatureItem(group, feature))}
                            </div>
                          </details>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="dfm-sidebar__metric-list">
                      {group.metrics.map((metric) =>
                        renderMetricRow(metric, {
                          key: `${group.group_id}-${metric.key}`,
                          groupLabel: group.label,
                          groupSummary: group.summary,
                        }),
                      )}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <p className="dfm-sidebar__hint">No extracted feature-recognition signals were surfaced for this run.</p>
            )}

            {geometryEvidence?.detail_metrics?.length ? (
              <details className="dfm-sidebar__details dfm-sidebar__details--nested">
                <summary>More detail ({geometryEvidence.detail_metrics.length})</summary>
                <div className="dfm-sidebar__metric-list">
                  {geometryEvidence.detail_metrics.map((metric) =>
                    renderMetricRow(metric, {
                      key: `detail-${metric.key}`,
                      groupLabel: "Feature recognition detail",
                    }),
                  )}
                </div>
              </details>
            ) : null}
          </details>
        ) : null}

        {!profileComplete ? (
          <p className="dfm-sidebar__hint">Complete material, manufacturing process, and industry in the component profile for stronger DFM results.</p>
        ) : null}
        {modelId && !modelTemplates.length ? <p className="dfm-sidebar__hint">No templates found for this model yet.</p> : null}
      </div>
    </aside>
  );
};

export default DfmBenchmarkSidebar;
