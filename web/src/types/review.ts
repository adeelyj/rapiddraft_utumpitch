export type TicketStatus = "open" | "in_progress" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";
export type TicketType = "issue" | "idea" | "comment";

export type Reply = {
  id: string;
  author: string;
  text: string;
  createdAt: string;
};

export type PinPosition = {
  position: [number, number, number];
  normal: [number, number, number];
  cameraState: {
    position: [number, number, number];
    target: [number, number, number];
  };
};

export type ReviewTicket = {
  id: string;
  kind: "comment";
  modelId: string;
  title: string;
  description: string;
  type: TicketType;
  priority: TicketPriority;
  status: TicketStatus;
  author: string;
  tag?: string;
  pin: PinPosition;
  replies: Reply[];
  createdAt: string;
  updatedAt: string;
};

export type ChecklistItemStatus = "pending" | "pass" | "fail" | "na";

export type ChecklistItem = {
  id: string;
  text: string;
  status: ChecklistItemStatus;
  note: string;
};

export type ReviewSessionStatus = "in_progress" | "passed" | "failed" | "cancelled";

export type DesignReviewSession = {
  id: string;
  kind: "design_review";
  modelId: string;
  templateId: string;
  templateName: string;
  title: string;
  author: string;
  status: ReviewSessionStatus;
  pin: PinPosition;
  checklist: ChecklistItem[];
  replies: Reply[];
  createdAt: string;
  updatedAt: string;
};

export type ChecklistTemplate = {
  id: string;
  name: string;
  description: string;
  items: string[];
};

export type PinnedItem = ReviewTicket | DesignReviewSession;
