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
  local_base_url?: string | null;
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
  general_observations: string;
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
  criteria?: VisionCriteria;
  provider: VisionProviderRequest;
};
