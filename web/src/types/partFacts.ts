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
  sections: {
    geometry: PartFactsSectionMap;
    manufacturing_signals: PartFactsSectionMap;
    declared_context: PartFactsSectionMap;
    process_inputs: PartFactsSectionMap;
    rule_inputs: PartFactsSectionMap;
  };
};
