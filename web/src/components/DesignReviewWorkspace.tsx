import { useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import ModelViewer from "./ModelViewer";
import type { AnalysisFocusPayload } from "../types/analysis";

type DesignReviewWorkspaceProps = {
  apiBase: string;
  onBack: () => void;
  onEnterExpert: () => void;
};

type ModelComponent = {
  id: string;
  nodeName: string;
  displayName: string;
  triangleCount: number;
};

type ComponentProfile = {
  material: string;
  manufacturingProcess: string;
  industry: string;
};

type DfmOption = {
  id: string;
  label: string;
};

type DfmIndustryOption = DfmOption & {
  standards: string[];
};

type DfmRoleOption = {
  role_id: string;
  label: string;
};

type DfmTemplateOption = {
  template_id: string;
  label: string;
};

type ReviewDfmConfig = {
  materials: DfmOption[];
  manufacturingProcesses: DfmOption[];
  industries: DfmIndustryOption[];
  roles: DfmRoleOption[];
  templates: DfmTemplateOption[];
};

type DfmFindingExpectedImpact = {
  risk_reduction?: string;
  cost_impact?: string;
  lead_time_impact?: string;
};

type DfmFindingAnchor = {
  anchor_id: string;
  component_node_name?: string | null;
  anchor_kind?: "point" | "region" | "multi" | "part";
  position_mm?: [number, number, number] | null;
  normal?: [number, number, number] | null;
  bbox_bounds_mm?: [number, number, number, number, number, number] | null;
  face_indices?: number[];
  label?: string | null;
};

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
  location_description?: string | null;
  radius_mm?: number | null;
  diameter_mm?: number | null;
  depth_mm?: number | null;
  thickness_mm?: number | null;
  pocket_depth_mm?: number | null;
  depth_to_radius_ratio?: number | null;
  depth_to_diameter_ratio?: number | null;
  position_mm?: [number, number, number] | null;
  bbox_bounds_mm?: [number, number, number, number, number, number] | null;
};

type DfmFindingEvidence = {
  violating_instances?: DfmViolatingInstance[];
};

type DfmGeometryMetric = {
  key: string;
  label: string;
  value: string | number | boolean;
  unit?: string | null;
  geometry_anchor?: DfmFindingAnchor | null;
};

type DfmGeometryEvidence = {
  process_summary?: {
    effective_process_label?: string | null;
    ai_process_label?: string | null;
  };
  feature_groups?: Array<{
    group_id: string;
    label: string;
    summary: string;
    metrics: DfmGeometryMetric[];
  }>;
  detail_metrics?: DfmGeometryMetric[];
};

type DfmFinding = {
  rule_id: string;
  pack_id: string;
  finding_type?: "evidence_gap" | "rule_violation";
  severity: string;
  title?: string;
  description?: string;
  refs: string[];
  standard_clause?: string;
  recommended_action?: string;
  evidence_quality?: string;
  expected_impact?: DfmFindingExpectedImpact;
  blame_map?: DfmFindingBlameMap;
  evidence?: DfmFindingEvidence;
};

type DfmCoverageSummary = {
  checks_evaluated: number;
  rules_considered: number;
  checks_passed: number;
  design_risk_findings: number;
  blocked_by_missing_inputs: number;
  checks_unresolved: number;
};

type DfmStandardRef = {
  ref_id: string;
  title?: string;
  url?: string;
};

type DfmAiRecommendation = {
  process_label: string;
  confidence: number;
  confidence_level: string;
};

type DfmReviewRoute = {
  plan_id: string;
  process_id: string;
  process_label: string;
  pack_ids: string[];
  pack_labels: (string | null)[];
  finding_count: number;
  findings: DfmFinding[];
  coverage_summary?: DfmCoverageSummary;
};

type DfmReviewV2Response = {
  model_id: string;
  effective_context?: {
    process?: {
      effective_process_label?: string | null;
      source?: string;
    } | null;
    overlay?: {
      effective_overlay_label?: string | null;
      source?: string;
    } | null;
    analysis_mode?: {
      selected_mode?: string;
      source?: string;
    } | null;
  } | null;
  ai_recommendation: DfmAiRecommendation | null;
  mismatch: {
    has_mismatch?: boolean;
    banner?: string | null;
    run_both_executed?: boolean;
    user_selected_process?: {
      process_label?: string | null;
    } | null;
    ai_process?: {
      process_label?: string | null;
    } | null;
  };
  route_count: number;
  finding_count_total: number;
  standards_used_auto_union: DfmStandardRef[];
  routes: DfmReviewRoute[];
  geometry_evidence?: DfmGeometryEvidence | null;
};

type DesignReviewStatus = "idle" | "uploading" | "needs_input" | "ready" | "running" | "passed" | "partial" | "failed";

type DesignReviewSession = {
  file: File | null;
  originalName: string;
  modelId: string | null;
  previewUrl: string | null;
  components: ModelComponent[];
  componentVisibility: Record<string, boolean>;
  selectedComponentNodeName: string | null;
  autoSelectedComponent: boolean;
  componentProfiles: Record<string, ComponentProfile>;
  status: DesignReviewStatus;
  statusMessage: string;
  error: string | null;
  result: DfmReviewV2Response | null;
};

type ReviewFindingCard = {
  id: string;
  routeId: string;
  processLabel: string;
  routeLabel: string;
  kind: "design_risk" | "evidence_gap";
  tone: "critical" | "warning" | "caution" | "info";
  title: string;
  summary: string;
  description?: string;
  severity: string;
  refs: string[];
  standardClause?: string;
  recommendedAction?: string;
  evidenceQuality?: string;
  expectedImpact?: DfmFindingExpectedImpact;
  locationHint?: string | null;
  locationSummary?: string | null;
  mappedLocationCount: number;
  focusPayload: AnalysisFocusPayload;
};

type TimelineTone = "accent" | "neutral" | "warning";

type TimelineItem = {
  id: string;
  title: string;
  detail: string;
  tone: TimelineTone;
  timestamp: string;
};

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  text: string;
  timestamp: string;
};

const DEFAULT_ROLE_ID = "general_dfm";
const DEFAULT_TEMPLATE_ID = "executive_1page";
const EMPTY_PROFILE: ComponentProfile = {
  material: "",
  manufacturingProcess: "",
  industry: "",
};

const EMPTY_REVIEW_SESSION: DesignReviewSession = {
  file: null,
  originalName: "No model loaded",
  modelId: null,
  previewUrl: null,
  components: [],
  componentVisibility: {},
  selectedComponentNodeName: null,
  autoSelectedComponent: false,
  componentProfiles: {},
  status: "idle",
  statusMessage: "Import a STEP file to begin.",
  error: null,
  result: null,
};

const GENERIC_COMPONENT_NAME_PREFIX = "open cascade step translator";

const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === "object");

const normalizeWhitespace = (value: string): string => value.replace(/\s+/g, " ").trim();

const normalizeModelNameStem = (modelOriginalName?: string | null): string => {
  if (typeof modelOriginalName !== "string" || !modelOriginalName.trim()) return "";
  const fileName = modelOriginalName.trim().split(/[\\/]/).pop() ?? modelOriginalName.trim();
  const stem = fileName.replace(/\.[^./\\]+$/, "");
  return normalizeWhitespace(stem);
};

const isTranslatorPlaceholderName = (value: string): boolean =>
  normalizeWhitespace(value).toLowerCase().startsWith(GENERIC_COMPONENT_NAME_PREFIX);

const normalizeComponents = (raw: unknown, modelOriginalName?: string | null): ModelComponent[] => {
  if (!Array.isArray(raw)) return [];
  type ParsedComponent = {
    id: string;
    nodeName: string;
    rawDisplayName: string;
    triangleCount: number;
    componentNumber: number;
  };

  const parsed: ParsedComponent[] = raw.flatMap((entry, index) => {
    if (!isRecord(entry)) return [];
    const componentNumber = index + 1;
    const fallbackNodeName = `component_${componentNumber}`;
    const nodeName = typeof entry.nodeName === "string" && entry.nodeName.trim() ? entry.nodeName : fallbackNodeName;
    const id = typeof entry.id === "string" && entry.id.trim() ? entry.id : nodeName;
    const rawDisplayName = typeof entry.displayName === "string" ? normalizeWhitespace(entry.displayName) : "";
    const triangleCount = typeof entry.triangleCount === "number" && Number.isFinite(entry.triangleCount) ? entry.triangleCount : 0;
    return [{ id, nodeName, rawDisplayName, triangleCount, componentNumber }];
  });

  const fallbackBaseName = normalizeModelNameStem(modelOriginalName);
  const fallbackNameCount = parsed.reduce((count, component) => {
    if (!component.rawDisplayName || isTranslatorPlaceholderName(component.rawDisplayName)) {
      return count + 1;
    }
    return count;
  }, 0);

  return parsed.map((component) => {
    if (component.rawDisplayName && !isTranslatorPlaceholderName(component.rawDisplayName)) {
      return {
        id: component.id,
        nodeName: component.nodeName,
        displayName: component.rawDisplayName,
        triangleCount: component.triangleCount,
      };
    }

    if (fallbackBaseName) {
      return {
        id: component.id,
        nodeName: component.nodeName,
        displayName: fallbackNameCount > 1 ? `${fallbackBaseName} - Part ${component.componentNumber}` : fallbackBaseName,
        triangleCount: component.triangleCount,
      };
    }

    return {
      id: component.id,
      nodeName: component.nodeName,
      displayName: `Part ${component.componentNumber}`,
      triangleCount: component.triangleCount,
    };
  });
};

const buildComponentVisibility = (components: ModelComponent[], visible: boolean): Record<string, boolean> => {
  const next: Record<string, boolean> = {};
  components.forEach((component) => {
    next[component.nodeName] = visible;
  });
  return next;
};

const normalizeComponentProfiles = (raw: unknown): Record<string, ComponentProfile> => {
  if (!isRecord(raw)) return {};
  const profiles: Record<string, ComponentProfile> = {};
  Object.entries(raw).forEach(([nodeName, payload]) => {
    if (!isRecord(payload)) return;
    profiles[nodeName] = {
      material: typeof payload.material === "string" ? payload.material : "",
      manufacturingProcess: typeof payload.manufacturingProcess === "string" ? payload.manufacturingProcess : "",
      industry: typeof payload.industry === "string" ? payload.industry : "",
    };
  });
  return profiles;
};

const normalizeSimpleOptions = (source: unknown): DfmOption[] => {
  if (!Array.isArray(source)) return [];
  return source.flatMap((entry) => {
    if (!isRecord(entry)) return [];
    const id = typeof entry.id === "string" ? entry.id : "";
    const label = typeof entry.label === "string" ? entry.label : "";
    if (!id || !label) return [];
    return [{ id, label }];
  });
};

const normalizeIndustryOptions = (source: unknown): DfmIndustryOption[] => {
  if (!Array.isArray(source)) return [];
  return source.flatMap((entry) => {
    if (!isRecord(entry)) return [];
    const id = typeof entry.id === "string" ? entry.id : "";
    const label = typeof entry.label === "string" ? entry.label : "";
    const standards = Array.isArray(entry.standards) ? entry.standards.filter((item): item is string => typeof item === "string") : [];
    if (!id || !label) return [];
    return [{ id, label, standards }];
  });
};

const normalizeRoleOptions = (source: unknown): DfmRoleOption[] => {
  const roles = Array.isArray(source)
    ? source.flatMap((entry) => {
        if (!isRecord(entry)) return [];
        const roleId = typeof entry.role_id === "string" ? entry.role_id : "";
        const label = typeof entry.label === "string" ? entry.label : "";
        if (!roleId || !label) return [];
        return [{ role_id: roleId, label }];
      })
    : [];

  if (roles.some((role) => role.role_id === DEFAULT_ROLE_ID)) return roles;
  return [{ role_id: DEFAULT_ROLE_ID, label: "General DFM" }, ...roles];
};

const normalizeTemplateOptions = (source: unknown): DfmTemplateOption[] => {
  const templates = Array.isArray(source)
    ? source.flatMap((entry) => {
        if (!isRecord(entry)) return [];
        const templateId = typeof entry.template_id === "string" ? entry.template_id : "";
        const label = typeof entry.label === "string" ? entry.label : "";
        if (!templateId || !label) return [];
        return [{ template_id: templateId, label }];
      })
    : [];

  if (templates.some((template) => template.template_id === DEFAULT_TEMPLATE_ID)) return templates;
  return [{ template_id: DEFAULT_TEMPLATE_ID, label: "Executive 1-page" }, ...templates];
};

const normalizeDfmConfig = (raw: unknown): ReviewDfmConfig | null => {
  if (!isRecord(raw)) return null;
  const profilePayload = isRecord(raw.profile_options) ? raw.profile_options : raw;
  return {
    materials: normalizeSimpleOptions(profilePayload.materials),
    manufacturingProcesses: normalizeSimpleOptions(profilePayload.manufacturingProcesses),
    industries: normalizeIndustryOptions(profilePayload.industries),
    roles: normalizeRoleOptions(raw.roles),
    templates: normalizeTemplateOptions(raw.templates),
  };
};

const createId = (prefix: string): string =>
  globalThis.crypto?.randomUUID?.() ?? `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

const getSelectedProfile = (session: DesignReviewSession): ComponentProfile =>
  session.selectedComponentNodeName ? session.componentProfiles[session.selectedComponentNodeName] ?? EMPTY_PROFILE : EMPTY_PROFILE;

const isProfileComplete = (profile: ComponentProfile): boolean =>
  Boolean(profile.material && profile.manufacturingProcess && profile.industry);

const getSelectedComponent = (session: DesignReviewSession): ModelComponent | null => {
  if (!session.selectedComponentNodeName) return session.components[0] ?? null;
  return session.components.find((component) => component.nodeName === session.selectedComponentNodeName) ?? session.components[0] ?? null;
};

const pluralize = (count: number, singular: string, plural: string): string => `${count} ${count === 1 ? singular : plural}`;

const resolveIdleState = (
  session: DesignReviewSession,
  result: DfmReviewV2Response | null = session.result,
): Pick<DesignReviewSession, "status" | "statusMessage"> => {
  if (!session.modelId || !session.previewUrl) {
    return {
      status: session.status === "uploading" ? "uploading" : "idle",
      statusMessage: session.status === "uploading" ? "Importing STEP geometry..." : "Import a STEP file to begin.",
    };
  }

  if (!session.selectedComponentNodeName) {
    return {
      status: "failed",
      statusMessage: "No analyzable part was detected in this file.",
    };
  }

  if (!isProfileComplete(getSelectedProfile(session))) {
    return {
      status: "needs_input",
      statusMessage: "Select material, manufacturing process, and industry to run DFM.",
    };
  }

  if (result) {
    return {
      status: "ready",
      statusMessage: "Inputs changed. Ready to run DFM again.",
    };
  }

  return {
    status: "ready",
    statusMessage: "Ready to run DFM.",
  };
};

const findingTone = (severity: string): "critical" | "warning" | "caution" | "info" => {
  const value = severity.trim().toLowerCase();
  if (value === "critical" || value === "major") return "critical";
  if (value === "warning") return "warning";
  if (value === "minor" || value === "caution") return "caution";
  return "info";
};

const formatCompactNumber = (value: number, digits = 1): string =>
  Number.isInteger(value) ? value.toString() : value.toFixed(digits);

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

const hasAnchorFocusData = (anchor: DfmFindingAnchor | null | undefined): anchor is DfmFindingAnchor =>
  Boolean(
    anchor &&
      ((anchor.position_mm && anchor.position_mm.length === 3) ||
        (anchor.bbox_bounds_mm && anchor.bbox_bounds_mm.length === 6) ||
        anchor.component_node_name),
  );

const hasInstanceFocusData = (instance: DfmViolatingInstance | null | undefined): instance is DfmViolatingInstance =>
  Boolean(
    instance &&
      ((instance.position_mm && instance.position_mm.length === 3) ||
        (instance.bbox_bounds_mm && instance.bbox_bounds_mm.length === 6)),
  );

const describeInstance = (instance: DfmViolatingInstance): string =>
  [
    instance.location_description || instance.instance_id,
    typeof instance.radius_mm === "number" ? `R${formatCompactNumber(instance.radius_mm, 2)} mm` : null,
    typeof instance.diameter_mm === "number" ? `Dia ${formatCompactNumber(instance.diameter_mm, 2)} mm` : null,
    typeof instance.depth_mm === "number" ? `Depth ${formatCompactNumber(instance.depth_mm, 2)} mm` : null,
    typeof instance.thickness_mm === "number" ? `Thickness ${formatCompactNumber(instance.thickness_mm, 2)} mm` : null,
    typeof instance.depth_to_radius_ratio === "number"
      ? `Depth/radius ${formatCompactNumber(instance.depth_to_radius_ratio, 2)}`
      : null,
    typeof instance.depth_to_diameter_ratio === "number"
      ? `Depth/diameter ${formatCompactNumber(instance.depth_to_diameter_ratio, 2)}`
      : null,
  ]
    .filter((value): value is string => Boolean(value && value.trim()))
    .join(" | ");

const buildAnchorFocusPayload = (
  id: string,
  finding: DfmFinding,
  route: DfmReviewRoute,
  anchor: DfmFindingAnchor,
  componentNodeName: string | null,
  explanation?: string | null,
): AnalysisFocusPayload => ({
  id,
  source: "dfm_benchmark",
  title: finding.title ?? finding.rule_id,
  details: [route.process_label, explanation || null, anchor.label || null].filter((value): value is string => Boolean(value && value.trim())).join(" | "),
  severity: finding.severity,
  component_node_name: anchor.component_node_name ?? componentNodeName,
  anchor_kind: anchor.anchor_kind,
  position_mm: anchor.position_mm ?? null,
  normal: anchor.normal ?? null,
  bbox_bounds_mm: anchor.bbox_bounds_mm ?? null,
  face_indices: anchor.face_indices ?? [],
});

const buildInstanceFocusPayload = (
  id: string,
  finding: DfmFinding,
  route: DfmReviewRoute,
  instance: DfmViolatingInstance,
  componentNodeName: string | null,
): AnalysisFocusPayload => ({
  id,
  source: "dfm_benchmark",
  title: finding.title ?? finding.rule_id,
  details: [route.process_label, describeInstance(instance)].filter((value): value is string => Boolean(value && value.trim())).join(" | "),
  severity: finding.severity,
  component_node_name: componentNodeName,
  anchor_kind: instance.bbox_bounds_mm && instance.bbox_bounds_mm.length === 6 ? "region" : "point",
  position_mm: instance.position_mm ?? null,
  normal: null,
  bbox_bounds_mm: instance.bbox_bounds_mm ?? null,
  face_indices: [],
});

const buildFallbackFocusPayload = (
  id: string,
  finding: DfmFinding,
  componentNodeName: string | null,
): AnalysisFocusPayload => ({
  id,
  source: "dfm",
  title: finding.title ?? finding.rule_id,
  details:
    finding.description ??
    finding.recommended_action ??
    finding.standard_clause ??
    finding.evidence_quality ??
    "Review this rule in the current part context.",
  severity: finding.severity,
  component_node_name: componentNodeName,
});

const flattenFindings = (
  result: DfmReviewV2Response | null,
  componentNodeName: string | null = null,
): ReviewFindingCard[] =>
  result?.routes.flatMap((route) =>
    route.findings.map((finding, index) => {
      const id = `${route.plan_id}:${finding.rule_id}:${index}`;
      const violatingInstances = Array.isArray(finding.evidence?.violating_instances)
        ? finding.evidence.violating_instances.filter(hasInstanceFocusData)
        : [];
      const primaryAnchor = hasAnchorFocusData(finding.blame_map?.primary_anchor) ? finding.blame_map?.primary_anchor : null;
      const primaryInstance = violatingInstances[0] ?? null;
      const locationHint =
        blameMapLabel(finding.blame_map) ??
        (violatingInstances.length
          ? `${violatingInstances.length} mapped location${violatingInstances.length === 1 ? "" : "s"}`
          : null);
      const locationSummary =
        finding.blame_map?.explanation ??
        primaryAnchor?.label ??
        (primaryInstance ? describeInstance(primaryInstance) : null);
      const focusPayload = primaryAnchor
        ? buildAnchorFocusPayload(id, finding, route, primaryAnchor, componentNodeName, finding.blame_map?.explanation)
        : primaryInstance
          ? buildInstanceFocusPayload(id, finding, route, primaryInstance, componentNodeName)
          : buildFallbackFocusPayload(id, finding, componentNodeName);

      return {
        id,
        routeId: route.plan_id,
        processLabel: route.process_label,
        routeLabel: route.pack_labels.filter((label): label is string => Boolean(label)).join(", ") || route.pack_ids.join(", "),
        kind: finding.finding_type === "evidence_gap" ? "evidence_gap" : "design_risk",
        tone: findingTone(finding.severity),
        title: finding.title ?? finding.rule_id,
        summary:
          finding.recommended_action ??
          finding.description ??
          finding.standard_clause ??
          finding.evidence_quality ??
          "Review this rule in the current part context.",
        description: finding.description,
        severity: finding.severity,
        refs: finding.refs,
        standardClause: finding.standard_clause,
        recommendedAction: finding.recommended_action,
        evidenceQuality: finding.evidence_quality,
        expectedImpact: finding.expected_impact,
        locationHint,
        locationSummary,
        mappedLocationCount: violatingInstances.length + (primaryAnchor ? 1 : 0),
        focusPayload,
      };
    }),
  ) ?? [];

const summarizeResultState = (result: DfmReviewV2Response): Pick<DesignReviewSession, "status" | "statusMessage"> => {
  const findings = flattenFindings(result);
  const evidenceGapCount = findings.filter((finding) => finding.kind === "evidence_gap").length;
  const designRiskCount = findings.length - evidenceGapCount;

  if (designRiskCount > 0) {
    return {
      status: "failed",
      statusMessage: `${pluralize(designRiskCount, "design risk", "design risks")} need attention.`,
    };
  }

  if (evidenceGapCount > 0) {
    return {
      status: "partial",
      statusMessage: `${pluralize(evidenceGapCount, "evidence gap", "evidence gaps")} need follow-up.`,
    };
  }

  return {
    status: "passed",
    statusMessage: "No findings in the current review.",
  };
};

const reviewStatusLabel = (status: DesignReviewStatus): string => {
  switch (status) {
    case "idle":
      return "Waiting";
    case "uploading":
      return "Importing";
    case "needs_input":
      return "Needs input";
    case "ready":
      return "Ready";
    case "running":
      return "Running";
    case "passed":
      return "Passed";
    case "partial":
      return "Partial";
    case "failed":
      return "Attention";
  }
};

const defaultRoleId = (config: ReviewDfmConfig | null): string =>
  config?.roles.find((role) => role.role_id === DEFAULT_ROLE_ID)?.role_id ?? config?.roles[0]?.role_id ?? DEFAULT_ROLE_ID;

const defaultTemplateId = (config: ReviewDfmConfig | null): string =>
  config?.templates.find((template) => template.template_id === DEFAULT_TEMPLATE_ID)?.template_id ??
  config?.templates[0]?.template_id ??
  DEFAULT_TEMPLATE_ID;

const createTimelineItem = (title: string, detail: string, tone: TimelineTone = "neutral"): TimelineItem => ({
  id: createId("design_review_event"),
  title,
  detail,
  tone,
  timestamp: new Date().toISOString(),
});

const createChatMessage = (role: ChatMessage["role"], text: string): ChatMessage => ({
  id: createId(`design_review_${role}`),
  role,
  text,
  timestamp: new Date().toISOString(),
});

const formatClock = (value: string): string =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail ?? payload.message ?? `${fallback} (HTTP ${response.status})`;
  } catch {
    return `${fallback} (HTTP ${response.status})`;
  }
}

const DesignReviewWorkspace = ({ apiBase, onBack, onEnterExpert }: DesignReviewWorkspaceProps) => {
  const [config, setConfig] = useState<ReviewDfmConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [review, setReview] = useState<DesignReviewSession>(EMPTY_REVIEW_SESSION);
  const [analysisFocus, setAnalysisFocus] = useState<AnalysisFocusPayload | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [isSetupExpanded, setIsSetupExpanded] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    createChatMessage(
      "assistant",
      "This chat area is a front-end shell for now. Use it to capture the question or change request you want attached to the next AI-driven revision step.",
    ),
  ]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([
    createTimelineItem("Design Review ready", "Load a STEP file to start the review canvas.", "neutral"),
  ]);
  const [fitTrigger, setFitTrigger] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadConfig = async () => {
      try {
        const response = await fetch(`${apiBase}/api/dfm/config`);
        if (!response.ok) {
          throw new Error(await readErrorDetail(response, "Failed to load DFM config"));
        }
        const payload = normalizeDfmConfig(await response.json());
        if (cancelled) return;
        setConfig(payload);
        setConfigError(null);
      } catch (error) {
        if (cancelled) return;
        setConfigError(error instanceof Error ? error.message : "Unexpected error while loading DFM config");
      }
    };

    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const selectedComponent = useMemo(() => getSelectedComponent(review), [review]);
  const selectedComponentProfile = useMemo(() => getSelectedProfile(review), [review]);
  const selectedIndustryStandards = useMemo(() => {
    if (!selectedComponentProfile.industry || !config) return [];
    return config.industries.find((item) => item.label === selectedComponentProfile.industry)?.standards ?? [];
  }, [config, selectedComponentProfile.industry]);

  const findingCards = useMemo(
    () => flattenFindings(review.result, review.selectedComponentNodeName),
    [review.result, review.selectedComponentNodeName],
  );
  const selectedFinding = useMemo(
    () => findingCards.find((finding) => finding.id === selectedFindingId) ?? null,
    [findingCards, selectedFindingId],
  );

  const designRiskCount = useMemo(() => findingCards.filter((finding) => finding.kind === "design_risk").length, [findingCards]);
  const evidenceGapCount = useMemo(() => findingCards.filter((finding) => finding.kind === "evidence_gap").length, [findingCards]);
  const geometryEvidence = review.result?.geometry_evidence ?? null;
  const featureRecognitionCount = useMemo(
    () => (geometryEvidence?.feature_groups?.length ?? 0) + (geometryEvidence?.detail_metrics?.length ?? 0),
    [geometryEvidence],
  );
  const featureEvidencePreview = useMemo(() => {
    const labels = [
      ...(geometryEvidence?.feature_groups?.slice(0, 3).map((group) => group.label) ?? []),
      ...(geometryEvidence?.detail_metrics?.slice(0, 2).map((metric) => metric.label) ?? []),
    ];
    return labels.filter((label, index, values) => Boolean(label && label.trim()) && values.indexOf(label) === index).slice(0, 4);
  }, [geometryEvidence]);
  const mismatchBanner = useMemo(() => {
    if (!review.result?.mismatch?.has_mismatch) return null;
    if (review.result.mismatch.banner) return review.result.mismatch.banner;
    const user = review.result.mismatch.user_selected_process?.process_label;
    const ai = review.result.mismatch.ai_process?.process_label;
    return user && ai ? `Profile requested ${user}, AI recommended ${ai}.` : "Process mismatch detected during benchmarking.";
  }, [review.result]);
  const canRun = Boolean(
    review.modelId &&
      review.selectedComponentNodeName &&
      isProfileComplete(selectedComponentProfile) &&
      review.status !== "uploading" &&
      review.status !== "running",
  );
  const missingSetupFields = useMemo(() => {
    const missing: string[] = [];
    if (!selectedComponent) missing.push("part");
    if (!selectedComponentProfile.material) missing.push("material");
    if (!selectedComponentProfile.manufacturingProcess) missing.push("process");
    if (!selectedComponentProfile.industry) missing.push("industry");
    return missing;
  }, [selectedComponent, selectedComponentProfile]);
  const missingSetupFieldLabels = useMemo(
    () =>
      missingSetupFields.map((field) => {
        switch (field) {
          case "part":
            return "target part";
          case "material":
            return "material";
          case "process":
            return "process";
          case "industry":
            return "industry";
          default:
            return field;
        }
      }),
    [missingSetupFields],
  );
  const setupSummaryCards = useMemo(
    () => [
      { label: "Part", value: selectedComponent?.displayName ?? "No part" },
      { label: "Material", value: selectedComponentProfile.material || "Not set" },
      { label: "Process", value: selectedComponentProfile.manufacturingProcess || "Not set" },
      { label: "Industry", value: selectedComponentProfile.industry || "Not set" },
    ],
    [selectedComponent, selectedComponentProfile],
  );
  const visibleStandards = useMemo(() => selectedIndustryStandards.slice(0, 3), [selectedIndustryStandards]);
  const hiddenStandardsCount = Math.max(0, selectedIndustryStandards.length - visibleStandards.length);
  const recentChatMessages = useMemo(() => chatMessages.slice(-2), [chatMessages]);
  const latestTimelineItem = timeline[0] ?? null;
  const currentProcessLabel =
    review.result?.effective_context?.process?.effective_process_label ?? selectedComponentProfile.manufacturingProcess ?? "Not set";
  const setupStateLabel = !review.modelId
    ? "Import required"
    : canRun
      ? "Ready to run"
      : missingSetupFields.length
        ? `${missingSetupFields.length} missing`
        : reviewStatusLabel(review.status);
  const setupStateTone = canRun ? "ready" : review.status === "failed" || review.status === "partial" ? "warning" : "pending";

  const pushTimeline = (title: string, detail: string, tone: TimelineTone = "neutral") => {
    setTimeline((current) => [createTimelineItem(title, detail, tone), ...current].slice(0, 12));
  };

  const clearFindingSelection = () => {
    setSelectedFindingId(null);
    setAnalysisFocus(null);
  };

  const handleLoadStepClick = () => {
    fileInputRef.current?.click();
  };

  const importModel = async (file: File) => {
    clearFindingSelection();
    setReview({
      ...EMPTY_REVIEW_SESSION,
      file,
      originalName: file.name,
      status: "uploading",
      statusMessage: "Importing STEP geometry...",
    });
    pushTimeline("STEP import started", `${file.name} is being uploaded into the design review workspace.`, "neutral");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${apiBase}/api/models`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await readErrorDetail(response, `Failed to import ${file.name}`));
      }

      const payload = (await response.json()) as Record<string, unknown>;
      const components = normalizeComponents(payload.components, typeof payload.originalName === "string" ? payload.originalName : file.name);
      const componentProfiles = normalizeComponentProfiles(payload.componentProfiles);
      const selectedComponentNodeName = components[0]?.nodeName ?? null;

      const nextReview: DesignReviewSession = {
        file,
        originalName: typeof payload.originalName === "string" ? payload.originalName : file.name,
        modelId: typeof payload.modelId === "string" ? payload.modelId : null,
        previewUrl: typeof payload.previewUrl === "string" ? payload.previewUrl : null,
        components,
        componentVisibility: buildComponentVisibility(components, true),
        selectedComponentNodeName,
        autoSelectedComponent: Boolean(selectedComponentNodeName),
        componentProfiles,
        status: "ready",
        statusMessage: "Ready to run DFM.",
        error: selectedComponentNodeName ? null : "No analyzable component was detected in this STEP file.",
        result: null,
      };

      setReview({
        ...nextReview,
        ...resolveIdleState(nextReview, null),
      });
      setFitTrigger((current) => current + 1);
      pushTimeline(
        "STEP imported",
        selectedComponentNodeName
          ? `Loaded ${pluralize(components.length, "component", "components")} and auto-selected ${components[0]?.displayName ?? "the first part"}.`
          : "The file imported, but no analyzable part was detected for review.",
        selectedComponentNodeName ? "accent" : "warning",
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to import ${file.name}`;
      setReview({
        ...EMPTY_REVIEW_SESSION,
        file,
        originalName: file.name,
        status: "failed",
        statusMessage: message,
        error: message,
      });
      pushTimeline("Import failed", message, "warning");
    }
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    await importModel(file);
  };

  const handleSelectComponent = (nodeName: string) => {
    clearFindingSelection();
    setReview((current) => {
      const nextReview: DesignReviewSession = {
        ...current,
        selectedComponentNodeName: nodeName,
        autoSelectedComponent: false,
        result: null,
        error: current.modelId ? null : current.error,
      };
      return {
        ...nextReview,
        ...resolveIdleState(nextReview, null),
      };
    });
    const component = review.components.find((entry) => entry.nodeName === nodeName);
    pushTimeline("Target part changed", `Design Review is now focused on ${component?.displayName ?? nodeName}.`, "neutral");
  };

  const handleProfileChange = (field: keyof ComponentProfile, value: string) => {
    clearFindingSelection();
    setReview((current) => {
      if (!current.selectedComponentNodeName) return current;
      const nextReview: DesignReviewSession = {
        ...current,
        componentProfiles: {
          ...current.componentProfiles,
          [current.selectedComponentNodeName]: {
            ...(current.componentProfiles[current.selectedComponentNodeName] ?? EMPTY_PROFILE),
            [field]: value,
          },
        },
        result: null,
        error: current.modelId ? null : current.error,
      };
      return {
        ...nextReview,
        ...resolveIdleState(nextReview, null),
      };
    });
  };

  const handleSelectFinding = (finding: ReviewFindingCard) => {
    setSelectedFindingId(finding.id);
    setAnalysisFocus(finding.focusPayload);
    pushTimeline("Issue focused", `${finding.title} is now highlighted in the review viewer.`, "accent");
  };

  const handleRunReview = async () => {
    if (!review.modelId || !review.selectedComponentNodeName || !isProfileComplete(selectedComponentProfile)) {
      return;
    }

    clearFindingSelection();
    setReview((current) => ({
      ...current,
      status: "running",
      statusMessage: "Saving component context and generating DFM review...",
      error: null,
    }));

    pushTimeline(
      "DFM run started",
      `${selectedComponent?.displayName ?? "Selected part"} is being evaluated for ${selectedComponentProfile.manufacturingProcess}.`,
      "neutral",
    );

    try {
      const profileResponse = await fetch(
        `${apiBase}/api/models/${review.modelId}/component-profiles/${encodeURIComponent(review.selectedComponentNodeName)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            material: selectedComponentProfile.material,
            manufacturing_process: selectedComponentProfile.manufacturingProcess,
            industry: selectedComponentProfile.industry,
          }),
        },
      );
      if (!profileResponse.ok) {
        throw new Error(await readErrorDetail(profileResponse, "Failed to save the component profile"));
      }

      const reviewResponse = await fetch(`${apiBase}/api/models/${review.modelId}/dfm/review-v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: review.selectedComponentNodeName,
          planning_inputs: {
            extracted_part_facts: {},
            analysis_mode: "geometry_dfm",
            selected_process_override: null,
            selected_overlay: null,
            process_selection_mode: "profile",
            overlay_selection_mode: "none",
            selected_role: defaultRoleId(config),
            selected_template: defaultTemplateId(config),
            run_both_if_mismatch: true,
          },
          context_payload: {
            include_geometry_anchors: true,
          },
        }),
      });
      if (!reviewResponse.ok) {
        throw new Error(await readErrorDetail(reviewResponse, "Failed to generate the DFM review"));
      }

      const result = (await reviewResponse.json()) as DfmReviewV2Response;
      const resultState = summarizeResultState(result);
      const nextFindingCards = flattenFindings(result, review.selectedComponentNodeName);
      const firstFinding = nextFindingCards[0] ?? null;

      setReview((current) => ({
        ...current,
        result,
        error: null,
        ...resultState,
      }));

      if (firstFinding) {
        setSelectedFindingId(firstFinding.id);
        setAnalysisFocus(firstFinding.focusPayload);
      }

      pushTimeline(
        resultState.status === "passed"
          ? "DFM review complete"
          : resultState.status === "partial"
            ? "DFM follow-up required"
            : "DFM issues detected",
        resultState.statusMessage,
        resultState.status === "passed" ? "accent" : "warning",
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error while generating the DFM review";
      setReview((current) => ({
        ...current,
        status: "failed",
        statusMessage: message,
        error: message,
      }));
      pushTimeline("DFM run failed", message, "warning");
    }
  };

  const handleSubmitChat = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextPrompt = chatDraft.trim();
    if (!nextPrompt) return;

    const selectedTitle = selectedFinding?.title ?? "the current review context";
    const assistantReply = selectedFinding
      ? `Saved locally. When the revision backend is wired, this prompt will travel with ${selectedTitle} so the AI can propose a concrete design change instead of a generic note.`
      : "Saved locally. When the revision backend is wired, this prompt will travel with the active review context so the AI can respond against the imported part and current DFM state.";

    setChatMessages((current) => [
      ...current,
      createChatMessage("user", nextPrompt),
      createChatMessage("assistant", assistantReply),
    ]);
    setChatDraft("");
    pushTimeline(
      "Chat note captured",
      selectedFinding ? `Stored a local AI prompt for ${selectedFinding.title}.` : "Stored a local AI prompt for the active review session.",
      "accent",
    );
  };

  return (
    <div className="mode-screen design-review-workspace">
      <header className="design-review-workspace__header">
        <div className="mode-brand" aria-label="RapidDraft branding">
          <img src="/rd_logo.png" alt="RapidDraft" className="mode-brand__image" />
        </div>
        <div className="design-review-workspace__header-copy">
          <span>Design Review</span>
          <strong>Live DFM review for imported geometry.</strong>
          <p className="design-review-workspace__header-note">{latestTimelineItem?.detail ?? review.statusMessage}</p>
        </div>
        <div className="design-review-workspace__header-actions">
          <button type="button" className="mode-button mode-button--secondary" onClick={onBack}>
            Back to modes
          </button>
          <button type="button" className="mode-button mode-button--secondary" onClick={onEnterExpert}>
            Open Expert Mode
          </button>
        </div>
      </header>

      <main className="design-review-workspace__main">
        <section className="design-review-workspace__left-column">
          <div className="design-review-workspace__panel design-review-workspace__panel--original">
            <div className="design-review-workspace__panel-header">
              <div>
                <p className="design-review-workspace__eyebrow">Original asset</p>
                <h1 title={review.originalName}>{review.originalName}</h1>
                <p className="design-review-workspace__compact-note">
                  {review.modelId
                    ? "Baseline geometry stays visible while the live review canvas follows the active issue."
                    : "Import one STEP file to ground the review workspace."}
                </p>
              </div>
              <span className={`design-review-workspace__status design-review-workspace__status--${review.status}`}>
                {reviewStatusLabel(review.status)}
              </span>
            </div>

            <div className="design-review-workspace__viewer-shell design-review-workspace__viewer-shell--original">
              <ModelViewer
                apiBase={apiBase}
                modelId={review.modelId}
                previewUrl={review.previewUrl}
                message={review.modelId ? undefined : "Import a STEP file to begin."}
                fitTrigger={fitTrigger}
                components={review.components}
                componentVisibility={review.componentVisibility}
                selectedComponentNodeName={review.selectedComponentNodeName}
                showReviewCards={false}
                showInspectorPanels={false}
                chromeDensity="compact"
              />
            </div>

            <div className="design-review-workspace__primary-actions">
              <input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                accept=".step,.stp,.STEP,.STP"
                onChange={handleFileChange}
              />
              <button type="button" className="mode-button" onClick={handleLoadStepClick} disabled={review.status === "uploading" || review.status === "running"}>
                {review.status === "uploading" ? "Importing STEP..." : "Load STEP"}
              </button>
              <button type="button" className="mode-button mode-button--secondary" onClick={handleRunReview} disabled={!canRun}>
                {review.result ? "Run again" : "Run DFM"}
              </button>
            </div>

            <div className="design-review-workspace__context-card design-review-workspace__context-card--dock">
              <div className="design-review-workspace__context-header">
                <div>
                  <h2>Setup</h2>
                  <p>Compact manufacturing context for the next DFM run.</p>
                </div>
                <div className="design-review-workspace__setup-actions">
                  <span className={`design-review-workspace__setup-state design-review-workspace__setup-state--${setupStateTone}`}>
                    {setupStateLabel}
                  </span>
                  <button
                    type="button"
                    className="design-review-workspace__dock-toggle"
                    onClick={() => setIsSetupExpanded((current) => !current)}
                  >
                    {isSetupExpanded ? "Collapse" : "Edit setup"}
                  </button>
                </div>
              </div>

              <div className="design-review-workspace__setup-summary">
                {setupSummaryCards.map((item) => (
                  <article key={item.label} className="design-review-workspace__setup-card">
                    <span>{item.label}</span>
                    <strong title={item.value}>{item.value}</strong>
                  </article>
                ))}
              </div>

              <div className="design-review-workspace__setup-chip-row">
                {visibleStandards.length ? (
                  <>
                    {visibleStandards.map((standard) => (
                      <span key={standard} className="design-review-workspace__chip">
                        {standard}
                      </span>
                    ))}
                    {hiddenStandardsCount ? <span className="design-review-workspace__chip">+{hiddenStandardsCount} more</span> : null}
                  </>
                ) : (
                  <span className="design-review-workspace__muted-note">Select an industry to load mapped standards.</span>
                )}
              </div>

              {isSetupExpanded ? (
                <>
                  <div className="design-review-workspace__setup-editor">
                    <div className="design-review-workspace__field-grid design-review-workspace__field-grid--stacked">
                      <label className="design-review-workspace__field">
                        <span>Target part</span>
                        <select
                          value={review.selectedComponentNodeName ?? ""}
                          onChange={(event) => handleSelectComponent(event.target.value)}
                          disabled={!review.components.length || review.status === "uploading" || review.status === "running"}
                        >
                          {!review.components.length ? <option value="">No imported parts yet</option> : null}
                          {review.components.map((component) => (
                            <option key={component.id} value={component.nodeName}>
                              {component.displayName}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="design-review-workspace__field">
                        <span>Material</span>
                        <select
                          value={selectedComponentProfile.material}
                          onChange={(event) => handleProfileChange("material", event.target.value)}
                          disabled={!config || !review.modelId || review.status === "uploading" || review.status === "running"}
                        >
                          <option value="">Select material</option>
                          {(config?.materials ?? []).map((option) => (
                            <option key={option.id} value={option.label}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="design-review-workspace__field">
                        <span>Manufacturing process</span>
                        <select
                          value={selectedComponentProfile.manufacturingProcess}
                          onChange={(event) => handleProfileChange("manufacturingProcess", event.target.value)}
                          disabled={!config || !review.modelId || review.status === "uploading" || review.status === "running"}
                        >
                          <option value="">Select process</option>
                          {(config?.manufacturingProcesses ?? []).map((option) => (
                            <option key={option.id} value={option.label}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="design-review-workspace__field">
                        <span>Industry</span>
                        <select
                          value={selectedComponentProfile.industry}
                          onChange={(event) => handleProfileChange("industry", event.target.value)}
                          disabled={!config || !review.modelId || review.status === "uploading" || review.status === "running"}
                        >
                          <option value="">Select industry</option>
                          {(config?.industries ?? []).map((option) => (
                            <option key={option.id} value={option.label}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </div>

                  <div className="design-review-workspace__context-footer design-review-workspace__context-footer--compact">
                    <div className="design-review-workspace__context-notes">
                      {review.autoSelectedComponent ? <p>First part was auto-selected from the imported model.</p> : null}
                      <p>{review.error ?? review.statusMessage}</p>
                      {configError ? <p className="design-review-workspace__error">{configError}</p> : null}
                    </div>
                  </div>
                </>
              ) : (
                <div className="design-review-workspace__setup-collapsed-note">
                  <p>
                    {!review.modelId
                      ? "Import a STEP file to unlock the manufacturing context."
                      : canRun
                        ? "Context is ready. Re-open setup any time to refine material, process, or industry."
                        : missingSetupFieldLabels.length
                          ? `Missing ${missingSetupFieldLabels.join(", ")} before the next DFM run.`
                          : latestTimelineItem?.detail ?? review.statusMessage}
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="design-review-workspace__center-column">
          <div className="design-review-workspace__panel design-review-workspace__panel--review-stage">
            <div className="design-review-workspace__panel-header">
              <div>
                <p className="design-review-workspace__eyebrow">Review canvas</p>
                <h2>{selectedFinding ? "Issue-focused DFM canvas" : "Live DFM review canvas"}</h2>
                <p className="design-review-workspace__compact-note">
                  {selectedFinding
                    ? "The reviewed model stays locked to the active issue so geometry and action stay in one place."
                    : "Run DFM, then move through findings without leaving the main review stage."}
                </p>
              </div>
              <div className="design-review-workspace__metrics">
                <div className="design-review-workspace__metric-card">
                  <span>Findings</span>
                  <strong>{review.result?.finding_count_total ?? 0}</strong>
                </div>
                <div className="design-review-workspace__metric-card">
                  <span>Design risks</span>
                  <strong>{designRiskCount}</strong>
                </div>
                <div className="design-review-workspace__metric-card">
                  <span>Evidence gaps</span>
                  <strong>{evidenceGapCount}</strong>
                </div>
                <div className="design-review-workspace__metric-card">
                  <span>Feature evidence</span>
                  <strong>{featureRecognitionCount}</strong>
                </div>
                <div className="design-review-workspace__metric-card">
                  <span>Process</span>
                  <strong>{currentProcessLabel}</strong>
                </div>
              </div>
            </div>

            {mismatchBanner ? <div className="design-review-workspace__benchmark-banner">{mismatchBanner}</div> : null}

            <div className="design-review-workspace__review-stage-main">
              <div className="design-review-workspace__stage-stack">
                <div className="design-review-workspace__viewer-shell design-review-workspace__viewer-shell--review">
                  <ModelViewer
                    apiBase={apiBase}
                    modelId={review.modelId}
                    previewUrl={review.previewUrl}
                    message={review.modelId ? undefined : "Run the review after importing a STEP file."}
                    fitTrigger={fitTrigger}
                    components={review.components}
                    componentVisibility={review.componentVisibility}
                    selectedComponentNodeName={review.selectedComponentNodeName}
                    analysisFocus={analysisFocus}
                    onClearAnalysisFocus={clearFindingSelection}
                    showReviewCards={false}
                    showInspectorPanels={false}
                    chromeDensity="compact"
                  />
                </div>

                <div
                  className={`design-review-workspace__stage-inspector ${
                    selectedFinding ? "" : "design-review-workspace__stage-inspector--empty"
                  }`}
                >
                  {selectedFinding ? (
                    <>
                      <div className="design-review-workspace__spotlight-header">
                        <div>
                          <span className={`design-review-workspace__finding-kind design-review-workspace__finding-kind--${selectedFinding.kind}`}>
                            {selectedFinding.kind === "design_risk" ? "Design risk" : "Evidence gap"}
                          </span>
                          <h3 title={selectedFinding.title}>{selectedFinding.title}</h3>
                        </div>
                        <span className={`design-review-workspace__severity design-review-workspace__severity--${selectedFinding.tone}`}>
                          {selectedFinding.severity}
                        </span>
                      </div>
                      <p>{selectedFinding.summary}</p>
                      <div className="design-review-workspace__spotlight-meta">
                        <span>{selectedFinding.processLabel}</span>
                        <span>{selectedFinding.routeLabel}</span>
                        {selectedFinding.refs.length ? <span>{selectedFinding.refs.join(", ")}</span> : null}
                      </div>
                      {selectedFinding.locationHint || selectedFinding.mappedLocationCount || selectedFinding.locationSummary ? (
                        <div className="design-review-workspace__benchmark-meta">
                          {selectedFinding.locationHint ? <span>{selectedFinding.locationHint}</span> : null}
                          {selectedFinding.mappedLocationCount ? (
                            <span>
                              {selectedFinding.mappedLocationCount} mapped location
                              {selectedFinding.mappedLocationCount === 1 ? "" : "s"}
                            </span>
                          ) : null}
                          {selectedFinding.locationSummary ? <span>{selectedFinding.locationSummary}</span> : null}
                        </div>
                      ) : null}
                      {selectedFinding.expectedImpact ? (
                        <div className="design-review-workspace__impact-list">
                          {selectedFinding.expectedImpact.risk_reduction ? <span>Risk: {selectedFinding.expectedImpact.risk_reduction}</span> : null}
                          {selectedFinding.expectedImpact.cost_impact ? <span>Cost: {selectedFinding.expectedImpact.cost_impact}</span> : null}
                          {selectedFinding.expectedImpact.lead_time_impact ? <span>Lead time: {selectedFinding.expectedImpact.lead_time_impact}</span> : null}
                        </div>
                      ) : null}
                    </>
                  ) : review.result ? (
                    <div className="design-review-workspace__empty-state design-review-workspace__empty-state--compact">
                      <strong>{review.status === "passed" ? "Clean review stage" : "No issue selected yet"}</strong>
                      <p>
                        {review.status === "passed"
                          ? "This run returned no findings, so the review stage is showing the imported geometry without a focused issue."
                          : "Select an issue card below to lock the review stage to that finding."}
                      </p>
                      {featureEvidencePreview.length ? (
                        <div className="design-review-workspace__benchmark-meta">
                          {featureEvidencePreview.map((label) => (
                            <span key={label}>{label}</span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="design-review-workspace__empty-state design-review-workspace__empty-state--compact">
                      <strong>No DFM output yet</strong>
                      <p>Run DFM to populate this stage with issue-aware geometry and reviewer context.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="design-review-workspace__panel design-review-workspace__panel--review-feed">
            <div className="design-review-workspace__issue-strip-panel">
              <div className="design-review-workspace__issue-strip-header">
                <div>
                  <h3>Issue strip</h3>
                  <p>Move through the active findings without leaving the stage.</p>
                </div>
                {review.result?.ai_recommendation?.process_label ? (
                  <span className="design-review-workspace__ai-pill">AI recommends {review.result.ai_recommendation.process_label}</span>
                ) : null}
              </div>
              <div className="design-review-workspace__issue-strip" role="list" aria-label="DFM findings">
                {findingCards.length ? (
                  findingCards.map((finding) => (
                    <button
                      key={finding.id}
                      type="button"
                      className={`design-review-workspace__issue-card ${
                        selectedFindingId === finding.id ? "design-review-workspace__issue-card--active" : ""
                      }`}
                      onClick={() => handleSelectFinding(finding)}
                    >
                      <span className={`design-review-workspace__issue-tone design-review-workspace__issue-tone--${finding.tone}`} />
                      <span className="design-review-workspace__issue-route">{finding.processLabel}</span>
                      {finding.locationHint ? <span className="design-review-workspace__issue-location">{finding.locationHint}</span> : null}
                      <strong title={finding.title}>{finding.title}</strong>
                      <p>{finding.summary}</p>
                    </button>
                  ))
                ) : (
                  <div className="design-review-workspace__empty-state">
                    <strong>No findings to browse yet</strong>
                    <p>The issue strip will populate after a successful DFM run.</p>
                  </div>
                )}
              </div>
            </div>

            <form className="design-review-workspace__chat-shell" onSubmit={handleSubmitChat}>
              <div className="design-review-workspace__chat-header">
                <div>
                  <h3>AI prompt</h3>
                  <p>Attach the next revision request to this review context.</p>
                </div>
                <span className="design-review-workspace__chat-note">Local shell</span>
              </div>

              <div className="design-review-workspace__chat-preview">
                {recentChatMessages.map((message) => (
                  <article
                    key={message.id}
                    className={`design-review-workspace__chat-message design-review-workspace__chat-message--${message.role}`}
                  >
                    <div className="design-review-workspace__chat-message-meta">
                      <span>{message.role === "assistant" ? "AI shell" : "You"}</span>
                      <time>{formatClock(message.timestamp)}</time>
                    </div>
                    <p>{message.text}</p>
                  </article>
                ))}
              </div>
              <div className="design-review-workspace__chat-compose">
                <textarea
                  value={chatDraft}
                  onChange={(event) => setChatDraft(event.target.value)}
                  placeholder={
                    selectedFinding
                      ? `Ask for a change strategy for "${selectedFinding.title}"...`
                      : "Describe the design change or review question you want the AI to work on next..."
                  }
                  rows={2}
                />
                <button type="submit" className="mode-button" disabled={!chatDraft.trim()}>
                  Capture prompt
                </button>
              </div>
            </form>
          </div>
        </section>

        <aside className="design-review-workspace__history-rail">
          <div className="design-review-workspace__history-header">
            <p className="design-review-workspace__eyebrow">Activity</p>
            <h2>Session trail</h2>
            <p className="design-review-workspace__compact-note">
              {latestTimelineItem ? latestTimelineItem.title : "Review events land here in descending order."}
            </p>
          </div>

          <div className="design-review-workspace__timeline">
            {timeline.map((item) => (
              <article key={item.id} className="design-review-workspace__timeline-item">
                <span className={`design-review-workspace__timeline-dot design-review-workspace__timeline-dot--${item.tone}`} />
                <div className="design-review-workspace__timeline-card">
                  <div className="design-review-workspace__timeline-card-header">
                    <strong>{item.title}</strong>
                    <time>{formatClock(item.timestamp)}</time>
                  </div>
                  <p>{item.detail}</p>
                </div>
              </article>
            ))}
          </div>
        </aside>
      </main>
    </div>
  );
};

export default DesignReviewWorkspace;
