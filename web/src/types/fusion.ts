export type FusionSourceStatus = {
  dfm: "available" | "missing";
  vision: "available" | "missing";
};

export type FusionSourceReports = {
  vision_report_id: string | null;
  vision_available: boolean;
  dfm_route_count: number;
  dfm_finding_count_total: number;
  vision_flagged_count: number;
};

export type FusionTuning = {
  threshold: number;
  weight_semantic: number;
  weight_refs: number;
  weight_geometry: number;
};

export type FusionPrioritySummary = {
  max_priority_score: number;
  confirmed_count: number;
  dfm_only_count: number;
  vision_only_count: number;
  top_actions: string[];
};

export type FusionDfmFinding = {
  route_source?: string;
  process_label?: string;
  rule_id: string;
  title: string;
  description?: string;
  severity: string;
  finding_type: string;
  recommended_action?: string;
};

export type FusionVisionFinding = {
  feature_id: string;
  description: string;
  severity: string;
  confidence: string;
  refs?: string[];
  source_views: string[];
  geometry_anchor?: Record<string, unknown>;
};

export type FusionMatchSignals = {
  semantic_score: number;
  refs_overlap_score: number;
  refs_overlap_count: number;
  shared_refs: string[];
  geometry_anchor_score: number;
  geometry_anchor_considered: boolean;
  matched_anchor_tokens: string[];
  overall_match_score: number;
  threshold: number;
};

export type FusionConfirmedFinding = {
  id: string;
  priority_score: number;
  match_score: number;
  match_signals: FusionMatchSignals;
  match_rationale: string;
  refs: string[];
  dfm: FusionDfmFinding;
  vision: FusionVisionFinding;
};

export type FusionDfmOnlyFinding = {
  id: string;
  priority_score: number;
  match_signals: FusionMatchSignals;
  match_rationale: string;
  refs: string[];
  dfm: FusionDfmFinding;
};

export type FusionVisionOnlyFinding = {
  id: string;
  priority_score: number;
  match_signals: FusionMatchSignals;
  match_rationale: string;
  vision: FusionVisionFinding;
};

export type FusionStandardTrace = {
  ref_id: string;
  title?: string;
  url?: string;
  type?: string;
  notes?: string;
  active_in_mode?: boolean;
  rules_considered?: number;
  design_risk_findings?: number;
  evidence_gap_findings?: number;
  blocked_by_missing_inputs?: number;
  checks_passed?: number;
  checks_unresolved?: number;
};

export type FusionReportResponse = {
  report_id: string;
  analysis_run_id?: string | null;
  model_id: string;
  component_node_name: string | null;
  source_reports: FusionSourceReports;
  source_status: FusionSourceStatus;
  priority_summary: FusionPrioritySummary;
  confirmed_by_both: FusionConfirmedFinding[];
  dfm_only: FusionDfmOnlyFinding[];
  vision_only: FusionVisionOnlyFinding[];
  standards_trace_union: FusionStandardTrace[];
  tuning_applied?: FusionTuning;
  created_at: string;
};

export type FusionCreateRequest = {
  component_node_name: string | null;
  vision_report_id?: string | null;
  fusion_tuning?: Partial<FusionTuning> | null;
};
