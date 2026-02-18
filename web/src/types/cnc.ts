export type CncCornerStatus = "CRITICAL" | "WARNING" | "CAUTION" | "OK";

export type CncGeometryReportRequest = {
  component_node_name?: string | null;
  include_ok_rows?: boolean;
  criteria?: CncGeometryCriteria;
};

export type CncGeometryThresholds = {
  critical_enabled: boolean;
  critical_max_mm: number;
  warning_enabled: boolean;
  warning_max_mm: number;
  caution_enabled: boolean;
  caution_max_mm: number;
  ok_enabled: boolean;
  ok_min_mm: number;
};

export type CncGeometryFilters = {
  concave_internal_edges_only: boolean;
  pocket_internal_cavity_heuristic: boolean;
  exclude_bbox_exterior_edges: boolean;
  include_ok_rows_in_output?: boolean | null;
};

export type CncGeometryCriteria = {
  thresholds: CncGeometryThresholds;
  filters: CncGeometryFilters;
  aggravating_factor_ratio_threshold: number;
};

export type CncGeometrySummary = {
  critical_count: number;
  warning_count: number;
  caution_count: number;
  ok_count: number;
  machinability_score: number;
  cost_impact: "HIGH" | "MODERATE" | "LOW";
};

export type CncGeometryCorner = {
  corner_id: string;
  edge_index: number;
  location_description: string;
  radius_mm: number | null;
  status: CncCornerStatus;
  minimum_tool_required: string;
  recommendation: string;
  pocket_depth_mm: number | null;
  depth_to_radius_ratio: number | null;
  aggravating_factor: boolean;
};

export type CncGeometryReportResponse = {
  report_id: string;
  model_id: string;
  component_node_name: string | null;
  component_display_name: string;
  summary: CncGeometrySummary;
  corners: CncGeometryCorner[];
  assumptions: string[];
  criteria_applied?: CncGeometryCriteria;
  pdf_url: string;
  created_at: string;
  part_filename?: string | null;
};
