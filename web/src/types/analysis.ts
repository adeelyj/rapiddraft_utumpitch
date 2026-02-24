export type AnalysisFocusSource = "vision" | "fusion";

export type AnalysisFocusPayload = {
  id: string;
  source: AnalysisFocusSource;
  title: string;
  details?: string;
  severity?: string;
  component_node_name?: string | null;
};

