import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import ModelViewer from "./ModelViewer";
import type { AnalysisFocusPayload } from "../types/analysis";

type BatchModeWorkspaceProps = {
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

type BatchDfmConfig = {
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

type DfmFinding = {
  rule_id: string;
  pack_id: string;
  finding_type?: "evidence_gap" | "rule_violation";
  severity: string;
  title?: string;
  refs: string[];
  standard_clause?: string;
  recommended_action?: string;
  evidence_quality?: string;
  expected_impact?: DfmFindingExpectedImpact;
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
    run_both_executed?: boolean;
  };
  route_count: number;
  finding_count_total: number;
  standards_used_auto_union: DfmStandardRef[];
  routes: DfmReviewRoute[];
};

type BatchJobStatus = "uploading" | "needs_input" | "ready" | "running" | "passed" | "partial" | "failed";

type BatchJob = {
  id: string;
  file: File | null;
  originalName: string;
  modelId: string | null;
  previewUrl: string | null;
  components: ModelComponent[];
  componentVisibility: Record<string, boolean>;
  selectedComponentNodeName: string | null;
  autoSelectedComponent: boolean;
  profile: ComponentProfile;
  status: BatchJobStatus;
  statusMessage: string;
  error: string | null;
  result: DfmReviewV2Response | null;
};

const DEFAULT_ROLE_ID = "general_dfm";
const DEFAULT_TEMPLATE_ID = "executive_1page";
const EMPTY_PROFILE: ComponentProfile = {
  material: "",
  manufacturingProcess: "",
  industry: "",
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

const normalizeDfmConfig = (raw: unknown): BatchDfmConfig | null => {
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

const isProfileComplete = (profile: ComponentProfile): boolean =>
  Boolean(profile.material && profile.manufacturingProcess && profile.industry);

const createJobId = (): string =>
  globalThis.crypto?.randomUUID?.() ?? `batch_job_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

const createDraftJob = (file: File): BatchJob => ({
  id: createJobId(),
  file,
  originalName: file.name,
  modelId: null,
  previewUrl: null,
  components: [],
  componentVisibility: {},
  selectedComponentNodeName: null,
  autoSelectedComponent: false,
  profile: EMPTY_PROFILE,
  status: "uploading",
  statusMessage: "Importing STEP geometry...",
  error: null,
  result: null,
});

const resolveIdleState = (job: BatchJob, result: DfmReviewV2Response | null = job.result): Pick<BatchJob, "status" | "statusMessage"> => {
  if (!job.modelId || !job.previewUrl) {
    return {
      status: "uploading",
      statusMessage: "Importing STEP geometry...",
    };
  }

  if (!job.selectedComponentNodeName) {
    return {
      status: "failed",
      statusMessage: "No analyzable part was detected in this file.",
    };
  }

  if (!isProfileComplete(job.profile)) {
    return {
      status: "needs_input",
      statusMessage: "Select material, manufacturing process, and industry.",
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

const getSelectedComponent = (job: BatchJob | null): ModelComponent | null => {
  if (!job) return null;
  return job.components.find((component) => component.nodeName === job.selectedComponentNodeName) ?? job.components[0] ?? null;
};

const statusLabel = (status: BatchJobStatus): string => {
  switch (status) {
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
      return "Failed";
  }
};

const pluralize = (count: number, singular: string, plural: string): string => `${count} ${count === 1 ? singular : plural}`;

const flattenFindings = (result: DfmReviewV2Response | null): DfmFinding[] =>
  result?.routes.flatMap((route) => route.findings) ?? [];

const summarizeResultState = (result: DfmReviewV2Response): Pick<BatchJob, "status" | "statusMessage"> => {
  const findings = flattenFindings(result);
  const evidenceGapCount = findings.filter((finding) => finding.finding_type === "evidence_gap").length;
  const designRiskCount = findings.length - evidenceGapCount;

  if (designRiskCount > 0) {
    return {
      status: "failed",
      statusMessage: `${pluralize(designRiskCount, "design risk", "design risks")} found.`,
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

const findingTone = (severity: string): "critical" | "warning" | "caution" | "info" => {
  const value = severity.trim().toLowerCase();
  if (value === "critical" || value === "major") return "critical";
  if (value === "warning") return "warning";
  if (value === "minor" || value === "caution") return "caution";
  return "info";
};

const defaultRoleId = (config: BatchDfmConfig | null): string =>
  config?.roles.find((role) => role.role_id === DEFAULT_ROLE_ID)?.role_id ?? config?.roles[0]?.role_id ?? DEFAULT_ROLE_ID;

const defaultTemplateId = (config: BatchDfmConfig | null): string =>
  config?.templates.find((template) => template.template_id === DEFAULT_TEMPLATE_ID)?.template_id ??
  config?.templates[0]?.template_id ??
  DEFAULT_TEMPLATE_ID;

const BatchModeWorkspace = ({ apiBase, onBack, onEnterExpert }: BatchModeWorkspaceProps) => {
  const [config, setConfig] = useState<BatchDfmConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<BatchJob[]>([]);
  const jobsRef = useRef<BatchJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [globalRoleId, setGlobalRoleId] = useState<string>(DEFAULT_ROLE_ID);
  const [globalTemplateId, setGlobalTemplateId] = useState<string>(DEFAULT_TEMPLATE_ID);
  const [importingFiles, setImportingFiles] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [analysisFocus, setAnalysisFocus] = useState<AnalysisFocusPayload | null>(null);
  const [fitTrigger, setFitTrigger] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

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
        setGlobalRoleId(defaultRoleId(payload));
        setGlobalTemplateId(defaultTemplateId(payload));
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Unexpected error while loading DFM config";
        setConfigError(message);
      }
    };

    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  useEffect(() => {
    if (!selectedJobId && jobs.length) {
      setSelectedJobId(jobs[0].id);
      return;
    }

    if (selectedJobId && !jobs.some((job) => job.id === selectedJobId)) {
      setSelectedJobId(jobs[0]?.id ?? null);
    }
  }, [jobs, selectedJobId]);

  useEffect(() => {
    setAnalysisFocus(null);
    if (selectedJobId) {
      setFitTrigger((current) => current + 1);
    }
  }, [selectedJobId]);

  const selectedJob = useMemo(() => jobs.find((job) => job.id === selectedJobId) ?? null, [jobs, selectedJobId]);
  const selectedComponent = useMemo(() => getSelectedComponent(selectedJob), [selectedJob]);
  const selectedIndustryStandards = useMemo(() => {
    if (!selectedJob?.profile.industry || !config) return [];
    return config.industries.find((item) => item.label === selectedJob.profile.industry)?.standards ?? [];
  }, [config, selectedJob]);

  const queueCounts = useMemo(() => {
    return jobs.reduce(
      (counts, job) => {
        counts.total += 1;
        counts[job.status] += 1;
        return counts;
      },
      {
        total: 0,
        uploading: 0,
        needs_input: 0,
        ready: 0,
        running: 0,
        passed: 0,
        partial: 0,
        failed: 0,
      } satisfies Record<BatchJobStatus | "total", number>,
    );
  }, [jobs]);

  const readyJobIds = useMemo(
    () => jobs.filter((job) => job.status === "ready" && Boolean(job.modelId && job.selectedComponentNodeName)).map((job) => job.id),
    [jobs],
  );

  const updateJob = (jobId: string, updater: (job: BatchJob) => BatchJob) => {
    setJobs((current) => current.map((job) => (job.id === jobId ? updater(job) : job)));
  };

  const handleLoadFilesClick = () => {
    fileInputRef.current?.click();
  };

  const importFileForJob = async (draftJob: BatchJob): Promise<void> => {
    if (!draftJob.file) return;
    const formData = new FormData();
    formData.append("file", draftJob.file);

    try {
      const response = await fetch(`${apiBase}/api/models`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await readErrorDetail(response, `Failed to import ${draftJob.originalName}`));
      }

      const payload = (await response.json()) as Record<string, unknown>;
      const components = normalizeComponents(payload.components, typeof payload.originalName === "string" ? payload.originalName : draftJob.originalName);
      const componentProfiles = normalizeComponentProfiles(payload.componentProfiles);
      const selectedComponentNodeName = components[0]?.nodeName ?? null;
      const profile = (selectedComponentNodeName && componentProfiles[selectedComponentNodeName]) || EMPTY_PROFILE;

      updateJob(draftJob.id, (current) => {
        const nextJob: BatchJob = {
          ...current,
          originalName: typeof payload.originalName === "string" ? payload.originalName : current.originalName,
          modelId: typeof payload.modelId === "string" ? payload.modelId : null,
          previewUrl: typeof payload.previewUrl === "string" ? payload.previewUrl : null,
          components,
          componentVisibility: buildComponentVisibility(components, true),
          selectedComponentNodeName,
          autoSelectedComponent: Boolean(selectedComponentNodeName),
          profile,
          error: selectedComponentNodeName ? null : "No analyzable component was detected in this STEP file.",
          result: null,
        };
        return {
          ...nextJob,
          ...resolveIdleState(nextJob, null),
        };
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to import ${draftJob.originalName}`;
      updateJob(draftJob.id, (current) => ({
        ...current,
        status: "failed",
        statusMessage: message,
        error: message,
        result: null,
      }));
    }
  };

  const handleFilesChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;

    const draftJobs = files.map(createDraftJob);
    setJobs((current) => [...draftJobs, ...current]);
    setSelectedJobId((current) => current ?? draftJobs[0]?.id ?? null);
    setImportingFiles(true);

    for (const draftJob of draftJobs) {
      await importFileForJob(draftJob);
    }

    setImportingFiles(false);
  };

  const handleProfileChange = (jobId: string, field: keyof ComponentProfile, value: string) => {
    updateJob(jobId, (current) => {
      const nextJob: BatchJob = {
        ...current,
        profile: {
          ...current.profile,
          [field]: value,
        },
        error: current.modelId ? null : current.error,
        result: null,
      };
      return {
        ...nextJob,
        ...resolveIdleState(nextJob, null),
      };
    });
  };

  const handleSelectComponent = (jobId: string, nodeName: string) => {
    updateJob(jobId, (current) => {
      const nextJob: BatchJob = {
        ...current,
        selectedComponentNodeName: nodeName,
        autoSelectedComponent: false,
        result: null,
      };
      return {
        ...nextJob,
        ...resolveIdleState(nextJob, null),
      };
    });
  };

  const handleToggleComponentVisibility = (jobId: string, nodeName: string) => {
    updateJob(jobId, (current) => ({
      ...current,
      componentVisibility: {
        ...current.componentVisibility,
        [nodeName]: !current.componentVisibility[nodeName],
      },
    }));
  };

  const handleShowAllComponents = (jobId: string) => {
    updateJob(jobId, (current) => ({
      ...current,
      componentVisibility: buildComponentVisibility(current.components, true),
    }));
  };

  const handleHideAllComponents = (jobId: string) => {
    updateJob(jobId, (current) => ({
      ...current,
      componentVisibility: buildComponentVisibility(current.components, false),
    }));
  };

  const runJob = async (jobId: string): Promise<void> => {
    const job = jobsRef.current.find((entry) => entry.id === jobId);
    if (!job || !job.modelId || !job.selectedComponentNodeName || !isProfileComplete(job.profile)) {
      return;
    }

    if (selectedJobId === jobId) {
      setAnalysisFocus(null);
    }

    updateJob(jobId, (current) => ({
      ...current,
      status: "running",
      statusMessage: "Saving profile and generating DFM review...",
      error: null,
    }));

    try {
      const profileResponse = await fetch(`${apiBase}/api/models/${job.modelId}/component-profiles/${encodeURIComponent(job.selectedComponentNodeName)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material: job.profile.material,
          manufacturing_process: job.profile.manufacturingProcess,
          industry: job.profile.industry,
        }),
      });
      if (!profileResponse.ok) {
        throw new Error(await readErrorDetail(profileResponse, "Failed to save the component profile"));
      }

      const reviewResponse = await fetch(`${apiBase}/api/models/${job.modelId}/dfm/review-v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          component_node_name: job.selectedComponentNodeName,
          planning_inputs: {
            extracted_part_facts: {},
            analysis_mode: "geometry_dfm",
            selected_process_override: null,
            selected_overlay: null,
            process_selection_mode: "profile",
            overlay_selection_mode: "profile",
            selected_role: globalRoleId || DEFAULT_ROLE_ID,
            selected_template: globalTemplateId || DEFAULT_TEMPLATE_ID,
            run_both_if_mismatch: true,
          },
          context_payload: {},
        }),
      });
      if (!reviewResponse.ok) {
        throw new Error(await readErrorDetail(reviewResponse, "Failed to generate the DFM review"));
      }

      const result = (await reviewResponse.json()) as DfmReviewV2Response;
      const resultState = summarizeResultState(result);

      updateJob(jobId, (current) => ({
        ...current,
        result,
        error: null,
        ...resultState,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error while generating the DFM review";
      updateJob(jobId, (current) => ({
        ...current,
        status: "failed",
        statusMessage: message,
        error: message,
      }));
    }
  };

  const handleRunAll = async () => {
    if (runningAll) return;
    const runQueue = jobsRef.current.filter((job) => job.status === "ready" && Boolean(job.modelId && job.selectedComponentNodeName));
    if (!runQueue.length) return;

    setRunningAll(true);
    for (const job of runQueue) {
      setSelectedJobId(job.id);
      await runJob(job.id);
    }
    setRunningAll(false);
  };

  const handleFocusFinding = (route: DfmReviewRoute, finding: DfmFinding, index: number) => {
    if (!selectedJob?.selectedComponentNodeName) return;
    setAnalysisFocus({
      id: `${route.plan_id}:${finding.rule_id}:${index + 1}`,
      source: "dfm",
      title: finding.title ?? finding.rule_id,
      details: finding.recommended_action ?? finding.standard_clause ?? "Review this rule in the selected part context.",
      severity: finding.severity,
      component_node_name: selectedJob.selectedComponentNodeName,
    });
  };

  return (
    <div className="mode-screen batch-workspace">
      <header className="batch-workspace__header">
        <div className="mode-brand" aria-label="RapidDraft branding">
          <img src="/rd_logo.png" alt="RapidDraft" className="mode-brand__image" />
        </div>
        <div className="batch-workspace__header-copy">
          <span>Batch Mode</span>
          <strong>Queue multiple STEP jobs and inspect each result in context.</strong>
        </div>
        <div className="batch-workspace__header-actions">
          <button type="button" className="mode-button mode-button--secondary" onClick={onBack}>
            Back to modes
          </button>
          <button type="button" className="mode-button mode-button--secondary" onClick={onEnterExpert}>
            Open Expert Mode
          </button>
        </div>
      </header>

      <main className="batch-workspace__main">
        <aside className="batch-workspace__sidebar">
          <section className="batch-workspace__intro">
            <p className="batch-workspace__eyebrow">Batch processing</p>
            <h1>Run DFM across a queue of imported STEP files.</h1>
            <p className="batch-workspace__intro-body">
              Load multiple STEP files, set manufacturing context for each job, and either run one review at a time or process every ready job in sequence.
            </p>
          </section>

          <div className="batch-workspace__toolbar">
            <input
              ref={fileInputRef}
              type="file"
              className="sr-only"
              multiple
              accept=".step,.stp,.STEP,.STP"
              onChange={handleFilesChange}
            />
            <button type="button" className="mode-button" onClick={handleLoadFilesClick} disabled={importingFiles || runningAll}>
              {importingFiles ? "Importing files..." : "Load STEP files"}
            </button>
            <button
              type="button"
              className="mode-button mode-button--secondary"
              onClick={handleRunAll}
              disabled={!readyJobIds.length || importingFiles || runningAll}
            >
              {runningAll ? "Running queue..." : "Run all ready jobs"}
            </button>
          </div>

          <section className="batch-workspace__summary" aria-label="Batch queue summary">
            <div className="batch-workspace__summary-card">
              <span>Total jobs</span>
              <strong>{queueCounts.total}</strong>
            </div>
            <div className="batch-workspace__summary-card">
              <span>Ready</span>
              <strong>{queueCounts.ready}</strong>
            </div>
            <div className="batch-workspace__summary-card">
              <span>Passed</span>
              <strong>{queueCounts.passed}</strong>
            </div>
            <div className="batch-workspace__summary-card">
              <span>Attention</span>
              <strong>{queueCounts.failed + queueCounts.partial + queueCounts.needs_input}</strong>
            </div>
          </section>

          <section className="batch-workspace__defaults" aria-label="Batch-wide DFM defaults">
            <div className="batch-workspace__defaults-header">
              <h2>Batch defaults</h2>
              <p>Use one role lens and one report template across the queue.</p>
            </div>
            <div className="batch-workspace__defaults-grid">
              <label className="batch-workspace__field">
                <span>Role lens</span>
                <select
                  value={globalRoleId}
                  onChange={(event) => setGlobalRoleId(event.target.value)}
                  disabled={!config?.roles.length || runningAll}
                >
                  {config?.roles.map((role) => (
                    <option key={role.role_id} value={role.role_id}>
                      {role.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="batch-workspace__field">
                <span>Report template</span>
                <select
                  value={globalTemplateId}
                  onChange={(event) => setGlobalTemplateId(event.target.value)}
                  disabled={!config?.templates.length || runningAll}
                >
                  {config?.templates.map((template) => (
                    <option key={template.template_id} value={template.template_id}>
                      {template.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {configError ? <p className="batch-workspace__error">{configError}</p> : null}
          </section>

          <section className="batch-workspace__jobs" aria-label="Imported batch jobs">
            {!jobs.length ? (
              <div className="batch-workspace__empty">
                <strong>No jobs yet</strong>
                <p>Load one or more STEP files to create a queue and start assigning manufacturing context.</p>
              </div>
            ) : (
              jobs.map((job) => {
                const selected = job.id === selectedJobId;
                const componentLabel = getSelectedComponent(job)?.displayName ?? "No part selected";

                return (
                  <article
                    key={job.id}
                    className={`batch-workspace__job-card ${selected ? "batch-workspace__job-card--selected" : ""}`}
                    onClick={() => setSelectedJobId(job.id)}
                  >
                    <div className="batch-workspace__job-top">
                      <div>
                        <h3>{job.originalName}</h3>
                        <p>
                          {job.components.length
                            ? `${pluralize(job.components.length, "component", "components")} imported`
                            : job.status === "uploading"
                              ? "Importing geometry..."
                              : "No components imported"}
                        </p>
                      </div>
                      <span className={`batch-workspace__status batch-workspace__status--${job.status}`}>{statusLabel(job.status)}</span>
                    </div>

                    <div className="batch-workspace__job-fields">
                      <label className="batch-workspace__field" onClick={(event) => event.stopPropagation()}>
                        <span>Manufacturing process</span>
                        <select
                          value={job.profile.manufacturingProcess}
                          onChange={(event) => handleProfileChange(job.id, "manufacturingProcess", event.target.value)}
                          disabled={!config || job.status === "uploading" || job.status === "running"}
                        >
                          <option value="">Select process</option>
                          {(config?.manufacturingProcesses ?? []).map((option) => (
                            <option key={option.id} value={option.label}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="batch-workspace__field" onClick={(event) => event.stopPropagation()}>
                        <span>Material</span>
                        <select
                          value={job.profile.material}
                          onChange={(event) => handleProfileChange(job.id, "material", event.target.value)}
                          disabled={!config || job.status === "uploading" || job.status === "running"}
                        >
                          <option value="">Select material</option>
                          {(config?.materials ?? []).map((option) => (
                            <option key={option.id} value={option.label}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="batch-workspace__field" onClick={(event) => event.stopPropagation()}>
                        <span>Industry</span>
                        <select
                          value={job.profile.industry}
                          onChange={(event) => handleProfileChange(job.id, "industry", event.target.value)}
                          disabled={!config || job.status === "uploading" || job.status === "running"}
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

                    <div className="batch-workspace__job-note">
                      <span>Target part</span>
                      <strong>{componentLabel}</strong>
                      {job.autoSelectedComponent ? <em>Auto-selected from the imported model. You can switch parts from the viewer.</em> : null}
                    </div>

                    <div className="batch-workspace__job-footer">
                      <p>{job.error ?? job.statusMessage}</p>
                      <button
                        type="button"
                        className="mode-button"
                        onClick={(event) => {
                          event.stopPropagation();
                          void runJob(job.id);
                        }}
                        disabled={job.status === "uploading" || job.status === "running" || !job.modelId || !job.selectedComponentNodeName || !isProfileComplete(job.profile)}
                      >
                        {job.result ? "Run again" : "Run"}
                      </button>
                    </div>
                  </article>
                );
              })
            )}
          </section>
        </aside>

        <section className="batch-workspace__detail">
          <div className="batch-workspace__detail-header">
            <div>
              <p className="batch-workspace__eyebrow">Selected job</p>
              <h2>{selectedJob?.originalName ?? "No job selected"}</h2>
              <p>
                {selectedJob
                  ? selectedJob.error ?? selectedJob.statusMessage
                  : "Choose a job from the queue to inspect the imported model and its DFM results."}
              </p>
            </div>
            {selectedJob ? (
              <div className="batch-workspace__detail-meta">
                <span className={`batch-workspace__status batch-workspace__status--${selectedJob.status}`}>{statusLabel(selectedJob.status)}</span>
                {selectedComponent ? <span>Part: {selectedComponent.displayName}</span> : null}
                {selectedIndustryStandards.length ? <span>{pluralize(selectedIndustryStandards.length, "standard", "standards")} mapped</span> : null}
              </div>
            ) : null}
          </div>
          <div className="batch-workspace__viewer-shell">
            <ModelViewer
              apiBase={apiBase}
              modelId={selectedJob?.modelId ?? null}
              previewUrl={selectedJob?.previewUrl ?? null}
              fitTrigger={fitTrigger}
              components={selectedJob?.components ?? []}
              componentVisibility={selectedJob?.componentVisibility ?? {}}
              onToggleComponent={(nodeName) => selectedJob && handleToggleComponentVisibility(selectedJob.id, nodeName)}
              onShowAllComponents={() => selectedJob && handleShowAllComponents(selectedJob.id)}
              onHideAllComponents={() => selectedJob && handleHideAllComponents(selectedJob.id)}
              selectedComponentNodeName={selectedJob?.selectedComponentNodeName ?? null}
              onSelectComponent={(nodeName) => selectedJob && handleSelectComponent(selectedJob.id, nodeName)}
              message={selectedJob?.statusMessage}
              analysisFocus={analysisFocus}
              onClearAnalysisFocus={() => setAnalysisFocus(null)}
              showReviewCards={false}
            />
          </div>

          <div className="batch-workspace__results">
            {!selectedJob ? (
              <div className="batch-workspace__empty batch-workspace__empty--detail">
                <strong>No job selected</strong>
                <p>Import one or more files, then select a job to inspect its model and run output.</p>
              </div>
            ) : selectedJob.result ? (
              <>
                <div className="batch-workspace__results-summary">
                  <div className="batch-workspace__result-stat">
                    <span>Findings</span>
                    <strong>{selectedJob.result.finding_count_total}</strong>
                  </div>
                  <div className="batch-workspace__result-stat">
                    <span>Routes</span>
                    <strong>{selectedJob.result.route_count}</strong>
                  </div>
                  <div className="batch-workspace__result-stat">
                    <span>Process</span>
                    <strong>
                      {selectedJob.result.effective_context?.process?.effective_process_label ||
                        selectedJob.profile.manufacturingProcess ||
                        "Profile driven"}
                    </strong>
                  </div>
                  <div className="batch-workspace__result-stat">
                    <span>AI recommendation</span>
                    <strong>{selectedJob.result.ai_recommendation?.process_label ?? "Not available"}</strong>
                  </div>
                </div>

                {selectedJob.result.standards_used_auto_union.length ? (
                  <div className="batch-workspace__standards">
                    {selectedJob.result.standards_used_auto_union.slice(0, 6).map((standard) => (
                      <span key={standard.ref_id} className="batch-workspace__standard-chip">
                        {standard.title ?? standard.ref_id}
                      </span>
                    ))}
                  </div>
                ) : null}

                <div className="batch-workspace__routes">
                  {selectedJob.result.routes.map((route) => {
                    const evidenceGapFindings = route.findings.filter((finding) => finding.finding_type === "evidence_gap");
                    const designRiskFindings = route.findings.filter((finding) => finding.finding_type !== "evidence_gap");

                    return (
                      <article key={`${route.plan_id}:${route.process_id}`} className="batch-workspace__route">
                        <header className="batch-workspace__route-header">
                          <div>
                            <h3>{route.process_label}</h3>
                            <p>{route.pack_labels.filter((label): label is string => Boolean(label)).join(", ") || route.pack_ids.join(", ")}</p>
                          </div>
                          <span>{pluralize(route.finding_count, "finding", "findings")}</span>
                        </header>

                        {route.coverage_summary ? (
                          <div className="batch-workspace__coverage">
                            Coverage {route.coverage_summary.checks_evaluated}/{route.coverage_summary.rules_considered}
                            {" | "}Passed {route.coverage_summary.checks_passed}
                            {" | "}Violations {route.coverage_summary.design_risk_findings}
                            {" | "}Blocked {route.coverage_summary.blocked_by_missing_inputs}
                          </div>
                        ) : null}

                        <div className="batch-workspace__route-groups">
                          <section>
                            <div className="batch-workspace__route-group-header">
                              <span>Design risks</span>
                              <strong>{designRiskFindings.length}</strong>
                            </div>
                            {designRiskFindings.length ? (
                              <div className="batch-workspace__finding-list">
                                {designRiskFindings.slice(0, 10).map((finding, index) => (
                                  <button
                                    key={`${route.plan_id}:${finding.rule_id}:${index}`}
                                    type="button"
                                    className="batch-workspace__finding"
                                    onClick={() => handleFocusFinding(route, finding, index)}
                                  >
                                    <span className={`batch-workspace__finding-tone batch-workspace__finding-tone--${findingTone(finding.severity)}`} />
                                    <div>
                                      <strong>{finding.title ?? finding.rule_id}</strong>
                                      <p>{finding.recommended_action ?? finding.standard_clause ?? "Review this rule in the model viewer."}</p>
                                    </div>
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <p className="batch-workspace__hint">No design risk findings in this route.</p>
                            )}
                          </section>

                          <section>
                            <div className="batch-workspace__route-group-header">
                              <span>Evidence gaps</span>
                              <strong>{evidenceGapFindings.length}</strong>
                            </div>
                            {evidenceGapFindings.length ? (
                              <div className="batch-workspace__finding-list">
                                {evidenceGapFindings.slice(0, 10).map((finding, index) => (
                                  <button
                                    key={`${route.plan_id}:${finding.rule_id}:evidence:${index}`}
                                    type="button"
                                    className="batch-workspace__finding"
                                    onClick={() => handleFocusFinding(route, finding, index)}
                                  >
                                    <span className={`batch-workspace__finding-tone batch-workspace__finding-tone--${findingTone(finding.severity)}`} />
                                    <div>
                                      <strong>{finding.title ?? finding.rule_id}</strong>
                                      <p>{finding.recommended_action ?? finding.evidence_quality ?? "This finding needs more evidence or drawing context."}</p>
                                    </div>
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <p className="batch-workspace__hint">No evidence gaps in this route.</p>
                            )}
                          </section>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="batch-workspace__empty batch-workspace__empty--detail">
                <strong>No DFM result yet</strong>
                <p>Import the geometry, complete the job inputs, and run the review to populate this panel.</p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail ?? payload.message ?? `${fallback} (HTTP ${response.status})`;
  } catch {
    return `${fallback} (HTTP ${response.status})`;
  }
}

export default BatchModeWorkspace;
