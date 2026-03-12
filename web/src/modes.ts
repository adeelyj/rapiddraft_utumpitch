export type AppMode = "launcher" | "expert" | "batch" | "drawing" | "collaboration";
export type LaunchMode = Exclude<AppMode, "launcher">;
export type PlaceholderMode = Exclude<LaunchMode, "expert">;

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

export const MODE_ORDER: LaunchMode[] = ["batch", "drawing", "collaboration", "expert"];

export const MODE_DEFINITIONS: Record<LaunchMode, ModeDefinition> = {
  batch: {
    id: "batch",
    eyebrow: "Queue",
    label: "Batch Mode",
    title: "Batch Processing",
    description: "Run folders of parts through the same review flow and collect results as one structured job.",
    status: "Front-end shell",
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
    description: "Review technical drawings, PDFs, and annotations in a mode that feels centered on sheets rather than models.",
    status: "Front-end shell",
    placeholderTitle: "Drawing analysis shell",
    placeholderBody:
      "This shell is the future entry point for drawing-first workflows, where uploaded sheets, issue clusters, and standards checks should feel native. It keeps that experience separate from the model-heavy Expert workspace.",
    placeholderNote: "Next backend hook: connect drawing upload, issue summaries, and standards-driven review output.",
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
  value === "collaboration";

export const isPlaceholderMode = (mode: AppMode): mode is PlaceholderMode =>
  mode === "batch" || mode === "drawing" || mode === "collaboration";
