export type AppMode = "launcher" | "expert" | "batch" | "drawing" | "collaboration" | "design-review";
export type LaunchMode = Exclude<AppMode, "launcher">;
export type PlaceholderMode = Exclude<LaunchMode, "expert" | "batch" | "design-review">;

export type ModeDefinition = {
  id: LaunchMode;
  eyebrow: string;
  label: string;
  title: string;
  description: string;
  status: string;
  placeholderTitle: string;
  placeholderBody: string;
  placeholderNote: string;
};

export const MODE_ORDER: LaunchMode[] = ["batch", "drawing", "design-review", "collaboration", "expert"];

export const MODE_DEFINITIONS: Record<LaunchMode, ModeDefinition> = {
  batch: {
    id: "batch",
    eyebrow: "Queue",
    label: "Batch Mode",
    title: "Batch Processing",
    description: "Load multiple STEP files, assign manufacturing context per job, and inspect each DFM result beside the imported model.",
    status: "Available now",
    placeholderTitle: "Batch mode shell",
    placeholderBody:
      "This shell is ready to become the place where folder imports, queued runs, and multi-part summaries live. For now it gives the mode a real front-end home without forcing the Expert workspace to carry that workflow.",
    placeholderNote: "Next backend hook: connect bulk upload, queue state, and aggregated result panels.",
  },
  drawing: {
    id: "drawing",
    eyebrow: "Sheets",
    label: "Drawing Analysis",
    title: "Drawing Analysis",
    description: "Open directly into DraftLint for drawing, PDF, and annotation review with the sheet-analysis workspace ready by default.",
    status: "Available now",
    placeholderTitle: "Drawing analysis shell",
    placeholderBody:
      "This shell is the future entry point for drawing-first workflows, where uploaded sheets, issue clusters, and standards checks should feel native. It keeps that experience separate from the model-heavy Expert workspace.",
    placeholderNote: "Next backend hook: connect drawing upload, issue summaries, and standards-driven review output.",
  },
  "design-review": {
    id: "design-review",
    eyebrow: "Review",
    label: "Design Review",
    title: "Design Review",
    description: "Compare the original part against live DFM findings in a dedicated review canvas with issue browsing and a clean change-history rail.",
    status: "Available now",
    placeholderTitle: "Design review shell",
    placeholderBody:
      "This shell is ready to become the review-first workspace for structured feedback, markup, and decision tracking. For now it gives Design Review its own front-end home while we shape the exact experience with you.",
    placeholderNote: "Next front-end step: define the review canvas, issue rail, and decision workflow.",
  },
  collaboration: {
    id: "collaboration",
    eyebrow: "Team",
    label: "Collaboration Mode",
    title: "Collaboration",
    description: "Open into a shared review workflow built around people, assignments, and follow-through instead of raw analysis tools.",
    status: "Front-end shell",
    placeholderTitle: "Collaboration shell",
    placeholderBody:
      "This shell is meant to become the handoff point for shared reviews, assigned findings, and live teamwork. Right now it gives the collaboration path its own front-end identity while the backend catches up.",
    placeholderNote: "Next backend hook: connect shared sessions, assignments, comments, and presence.",
  },
  expert: {
    id: "expert",
    eyebrow: "Full Suite",
    label: "Expert Mode",
    title: "Expert Workspace",
    description: "Enter the current full RapidDraft environment with the existing sidebars, analysis tools, views, and model workflows.",
    status: "Available now",
    placeholderTitle: "Expert Workspace",
    placeholderBody: "",
    placeholderNote: "",
  },
};

export const isAppMode = (value: string | null | undefined): value is AppMode =>
  value === "launcher" ||
  value === "expert" ||
  value === "batch" ||
  value === "drawing" ||
  value === "collaboration" ||
  value === "design-review";

export const isPlaceholderMode = (mode: AppMode): mode is PlaceholderMode =>
  mode === "drawing" || mode === "collaboration";
