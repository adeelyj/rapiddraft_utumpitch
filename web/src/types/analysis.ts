export type AnalysisFocusSource = "vision" | "fusion" | "dfm" | "dfm_benchmark";

export type AnalysisFocusAnchorKind = "point" | "region" | "multi" | "part";

export type AnalysisFocusPayload = {
  id: string;
  source: AnalysisFocusSource;
  title: string;
  details?: string;
  severity?: string;
  camera_behavior?: "focus" | "preserve";
  overlay_variant?: "default" | "compact";
  overlay_title?: string;
  overlay_location?: string;
  component_node_name?: string | null;
  anchor_kind?: AnalysisFocusAnchorKind;
  position_mm?: [number, number, number] | null;
  normal?: [number, number, number] | null;
  bbox_bounds_mm?: [number, number, number, number, number, number] | null;
  face_indices?: number[];
};
