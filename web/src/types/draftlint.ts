export type DraftLintSeverity = "critical" | "major" | "minor";

export type DraftLintBoundingBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type DraftLintStageStatus = "pending" | "running" | "completed";

export type DraftLintStage = {
  stage_id: string;
  label: string;
  status: DraftLintStageStatus;
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
};

export type DraftLintSessionResponse = {
  session_id: string;
  report_id: string | null;
  status: "running" | "completed";
  progress_percent: number;
  standard_profile: string;
  created_at: string;
  updated_at: string;
  stages: DraftLintStage[];
  poll_after_ms: number;
  source_url?: string;
  source_original_name?: string;
  source_mime_type?: string;
};

export type DraftLintRegion = {
  region_id: string;
  region_type: string;
  bbox: DraftLintBoundingBox;
};

export type DraftLintTextElement = {
  text_id: string;
  region_id?: string;
  text: string;
  confidence: number;
  bbox: DraftLintBoundingBox;
};

export type DraftLintDetectedSymbol = {
  symbol_id: string;
  symbol_type: string;
  confidence: number;
  bbox: DraftLintBoundingBox;
};

export type DraftLintIssue = {
  issue_id: string;
  severity: DraftLintSeverity;
  rule_id: string;
  standard: string;
  category: string;
  title: string;
  description: string;
  recommended_action: string;
  confidence: number;
  bbox: DraftLintBoundingBox;
};

export type DraftLintSummary = {
  total_issues: number;
  critical_count: number;
  major_count: number;
  minor_count: number;
  overall_compliant: boolean;
};

export type DraftLintArtifacts = {
  annotated_png_url: string;
  report_json_url: string;
  report_html_url: string;
  issues_csv_url: string;
};

export type DraftLintReportResponse = {
  report_id: string;
  drawing_id: string;
  drawing_name: string;
  standard_profile: string;
  validation_date: string;
  summary: DraftLintSummary;
  customer_summary?: {
    headline: string;
    priority_message: string;
    next_step: string;
  };
  regions: DraftLintRegion[];
  text_elements: DraftLintTextElement[];
  detected_symbols: DraftLintDetectedSymbol[];
  ai_analysis: Record<string, unknown>;
  issues: DraftLintIssue[];
  artifacts: DraftLintArtifacts;
};
