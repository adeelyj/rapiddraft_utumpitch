export type VisionProviderRoute = "openai" | "claude" | "local";
export type VisionConfidence = "low" | "medium" | "high";
export type VisionSeverity = "critical" | "warning" | "caution" | "info";

export type VisionCriteriaChecks = {
  internal_pocket_tight_corners: boolean;
  tool_access_risk: boolean;
  annotation_note_scan: boolean;
};

export type VisionCriteria = {
  checks: VisionCriteriaChecks;
  sensitivity: VisionConfidence;
  max_flagged_features: number;
  confidence_threshold: VisionConfidence;
};

export type VisionProviderRequest = {
  route: VisionProviderRoute;
  model_override?: string | null;
  base_url_override?: string | null;
  api_key_override?: string | null;
  local_base_url?: string | null;
};

export type VisionPastedImageRequest = {
  name?: string | null;
  data_url: string;
};

export type VisionViewSetRequest = {
  component_node_name?: string | null;
};

export type VisionViewSetResponse = {
  view_set_id: string;
  model_id: string;
  component_node_name: string | null;
  views: {
    x: string;
    y: string;
    z: string;
  };
  generated_at: string;
};

export type VisionProviderAvailability = {
  id: VisionProviderRoute;
  label: string;
  configured: boolean;
  default_model: string;
};

export type VisionProvidersResponse = {
  providers: VisionProviderAvailability[];
  default_provider: VisionProviderRoute;
  provider_defaults?: Partial<
    Record<
      VisionProviderRoute,
      {
        base_url: string;
      }
    >
  >;
  local_defaults: {
    base_url: string;
  };
};

export type VisionFinding = {
  feature_id: string;
  description: string;
  severity: VisionSeverity;
  confidence: VisionConfidence;
  source_views: string[];
  refs?: string[];
  evidence_quality?: VisionConfidence;
};

export type VisionCustomerSummary = {
  status: "clear" | "watch" | "attention" | "critical";
  headline: string;
  confidence: VisionConfidence;
  risk_counts: {
    critical: number;
    warning: number;
    caution: number;
    info: number;
  };
  top_risks: string[];
  recommended_next_step: string;
  analysis_note?: string;
};

export type VisionCustomerFinding = {
  finding_id: string;
  title: string;
  severity: VisionSeverity;
  confidence: VisionConfidence;
  why_it_matters: string;
  recommended_action: string;
  source_views: string[];
  refs?: string[];
};

export type VisionReportResponse = {
  report_id: string;
  model_id: string;
  component_node_name: string | null;
  view_set_id: string;
  summary: {
    flagged_count: number;
    confidence: VisionConfidence;
  };
  findings: VisionFinding[];
  customer_summary?: VisionCustomerSummary;
  customer_findings?: VisionCustomerFinding[];
  general_observations: string;
  raw_output_text?: string;
  prompt_used?: string;
  criteria_applied: VisionCriteria;
  provider_applied: {
    route_requested: VisionProviderRoute;
    route_used: VisionProviderRoute;
    model_used: string;
    base_url_used: string;
  };
  created_at: string;
};

export type VisionReportRequest = {
  component_node_name?: string | null;
  view_set_id: string;
  selected_view_names?: string[];
  pasted_images?: VisionPastedImageRequest[];
  prompt_override?: string | null;
  criteria?: VisionCriteria;
  provider: VisionProviderRequest;
};
