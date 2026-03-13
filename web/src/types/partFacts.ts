export type PartFactState =
  | "measured"
  | "inferred"
  | "declared"
  | "unknown"
  | "failed"
  | "not_applicable";

export type PartFactMetric = {
  label: string;
  value: unknown;
  unit: string | null;
  state: PartFactState;
  confidence: number;
  source: string;
  reason?: string;
};

export type PartFactsSectionMap = Record<string, PartFactMetric>;

export type PartFactsCoverageBlock = {
  known_metrics: number;
  applicable_metrics: number;
  not_applicable_metrics: number;
  total_metrics: number;
  percent: number;
};

export type PartFactInternalRadiusInstance = {
  instance_id: string;
  edge_index: number | null;
  location_description: string;
  radius_mm: number;
  status: string | null;
  recommendation: string | null;
  pocket_depth_mm: number | null;
  depth_to_radius_ratio: number | null;
  aggravating_factor: boolean;
  position_mm: [number, number, number] | null;
  bbox_bounds_mm: [number, number, number, number, number, number] | null;
};

export type PartFactHoleInstance = {
  instance_id: string;
  subtype: string | null;
  location_description: string;
  diameter_mm: number;
  depth_mm: number | null;
  depth_to_diameter_ratio: number | null;
  position_mm: [number, number, number] | null;
  bbox_bounds_mm: [number, number, number, number, number, number] | null;
  face_indices: number[];
};

export type PartFactWallThicknessInstance = {
  instance_id: string;
  location_description: string;
  thickness_mm: number;
  position_mm: [number, number, number] | null;
  bbox_bounds_mm: [number, number, number, number, number, number] | null;
  face_indices: number[];
};

export type PartFactsResponse = {
  schema_version: string;
  model_id: string;
  component_node_name: string;
  component_display_name: string;
  generated_at: string;
  coverage: {
    core_extraction_coverage: PartFactsCoverageBlock;
    full_rule_readiness_coverage: PartFactsCoverageBlock;
  };
  overall_confidence: "low" | "medium" | "high";
  missing_inputs: string[];
  assumptions: string[];
  errors: string[];
  geometry_instances: {
    internal_radius_instances: PartFactInternalRadiusInstance[];
    hole_instances: PartFactHoleInstance[];
    wall_thickness_instances: PartFactWallThicknessInstance[];
  };
  sections: {
    geometry: PartFactsSectionMap;
    manufacturing_signals: PartFactsSectionMap;
    declared_context: PartFactsSectionMap;
    process_inputs: PartFactsSectionMap;
    rule_inputs: PartFactsSectionMap;
  };
};
