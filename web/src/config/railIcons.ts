export type LeftRailTab = "views" | "reviews" | "com" | "dfm" | "km" | "req";

export type RightRailTab = "dfm" | "rep" | "cnc" | "vision" | "fusion" | "draftlint";

export type RailIconId =
  | "nav_views"
  | "nav_comments"
  | "nav_reviews"
  | "nav_dfm"
  | "nav_knowledge"
  | "nav_requirements"
  | "nav_vision"
  | "nav_draftlint"
  | "nav_cnc"
  | "nav_fusion"
  | "nav_fusion2"
  | "nav_rep";

export type RailTabSpec = {
  label: string;
  iconId: RailIconId;
  fallbackGlyph: string;
};

export const LEFT_RAIL_TAB_ORDER: LeftRailTab[] = ["views", "com", "reviews", "dfm", "km", "req"];

export const RIGHT_RAIL_TAB_ORDER: RightRailTab[] = ["vision", "draftlint", "cnc", "dfm", "fusion", "rep"];

export const LEFT_RAIL_TAB_SPECS: Record<LeftRailTab, RailTabSpec> = {
  views: {
    label: "Views",
    iconId: "nav_views",
    fallbackGlyph: "V",
  },
  com: {
    label: "Comments",
    iconId: "nav_comments",
    fallbackGlyph: "C",
  },
  reviews: {
    label: "Reviews",
    iconId: "nav_reviews",
    fallbackGlyph: "R",
  },
  dfm: {
    label: "Design For Manufacturing",
    iconId: "nav_dfm",
    fallbackGlyph: "M",
  },
  km: {
    label: "Knowledge Management",
    iconId: "nav_knowledge",
    fallbackGlyph: "K",
  },
  req: {
    label: "Requirements",
    iconId: "nav_requirements",
    fallbackGlyph: "Q",
  },
};

export const RIGHT_RAIL_TAB_SPECS: Record<RightRailTab, RailTabSpec> = {
  vision: {
    label: "Vision",
    iconId: "nav_vision",
    fallbackGlyph: "V",
  },
  draftlint: {
    label: "DraftLint",
    iconId: "nav_draftlint",
    fallbackGlyph: "L",
  },
  cnc: {
    label: "CNC",
    iconId: "nav_cnc",
    fallbackGlyph: "C",
  },
  dfm: {
    label: "DFM (AI)",
    iconId: "nav_dfm",
    fallbackGlyph: "D",
  },
  fusion: {
    label: "Fusion",
    iconId: "nav_fusion2",
    fallbackGlyph: "F",
  },
  rep: {
    label: "REP",
    iconId: "nav_rep",
    fallbackGlyph: "R",
  },
};
