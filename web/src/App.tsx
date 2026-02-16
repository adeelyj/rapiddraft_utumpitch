import { useEffect, useMemo, useRef, useState } from "react";
import Toolbar from "./components/Toolbar";
import ModelViewer from "./components/ModelViewer";
import ViewsPanel from "./components/ViewsPanel";
import DrawingPage from "./components/DrawingPage";
import CommentForm, { CreateTicketPayload } from "./components/CommentForm";
import ReviewPanel from "./components/ReviewPanel";
import ReviewStartForm, { CreateReviewPayload } from "./components/ReviewStartForm";
import DfmReviewSidebar from "./components/DfmReviewSidebar";
import type {
  ChecklistTemplate,
  DesignReviewSession,
  PinPosition,
  PinnedItem,
  ReviewTicket,
} from "./types/review";

type ModelState = {
  id: string;
  previewUrl: string;
  originalName: string;
};

type ModelComponent = {
  id: string;
  nodeName: string;
  displayName: string;
  triangleCount: number;
};

type ComponentProfile = {
  material: string;
  manufacturingProcess: string;
  industry: string;
};

type DfmProfileOption = {
  id: string;
  label: string;
};

type DfmIndustryOption = DfmProfileOption & {
  standards: string[];
};

type DfmProfileOptions = {
  materials: DfmProfileOption[];
  manufacturingProcesses: DfmProfileOption[];
  industries: DfmIndustryOption[];
};

export type DrawingZone = {
  id: string;
  src?: string;
  layout: { x: number; y: number; w: number; h: number };
  viewName?: string;
  metadataUrl?: string;
};

export type Dimension = {
  id: string;
  zoneId: string;
  a: { norm: [number, number]; world: [number, number] };
  b: { norm: [number, number]; world: [number, number] };
  distance: number;
  units?: string;
  scale?: number;
  label?: string;
};

const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000";
const DRAWING_STORAGE_KEY = "drawingState";
const EMPTY_COMPONENT_PROFILE: ComponentProfile = {
  material: "",
  manufacturingProcess: "",
  industry: "",
};

const normalizeComponents = (raw: unknown): ModelComponent[] => {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((entry, index) => {
    if (!entry || typeof entry !== "object") return [];
    const record = entry as Record<string, unknown>;
    const fallbackNodeName = `component_${index + 1}`;
    const nodeName = typeof record.nodeName === "string" && record.nodeName.trim() ? record.nodeName : fallbackNodeName;
    const id = typeof record.id === "string" && record.id.trim() ? record.id : nodeName;
    const displayName =
      typeof record.displayName === "string" && record.displayName.trim() ? record.displayName : `Part ${index + 1}`;
    const triangleCount = typeof record.triangleCount === "number" && Number.isFinite(record.triangleCount) ? record.triangleCount : 0;
    return [{ id, nodeName, displayName, triangleCount }];
  });
};

const buildComponentVisibility = (components: ModelComponent[], visible: boolean): Record<string, boolean> => {
  const next: Record<string, boolean> = {};
  components.forEach((component) => {
    next[component.nodeName] = visible;
  });
  return next;
};

const normalizeComponentProfiles = (raw: unknown): Record<string, ComponentProfile> => {
  if (!raw || typeof raw !== "object") return {};
  const profiles: Record<string, ComponentProfile> = {};
  Object.entries(raw as Record<string, unknown>).forEach(([nodeName, payload]) => {
    if (!payload || typeof payload !== "object") return;
    const profile = payload as Record<string, unknown>;
    profiles[nodeName] = {
      material: typeof profile.material === "string" ? profile.material : "",
      manufacturingProcess: typeof profile.manufacturingProcess === "string" ? profile.manufacturingProcess : "",
      industry: typeof profile.industry === "string" ? profile.industry : "",
    };
  });
  return profiles;
};

const normalizeProfileOptions = (raw: unknown): DfmProfileOptions | null => {
  if (!raw || typeof raw !== "object") return null;
  const rootPayload = raw as Record<string, unknown>;
  const payload =
    rootPayload.profile_options && typeof rootPayload.profile_options === "object"
      ? (rootPayload.profile_options as Record<string, unknown>)
      : rootPayload;
  const normalizeOptions = (source: unknown): DfmProfileOption[] => {
    if (!Array.isArray(source)) return [];
    return source.flatMap((entry) => {
      if (!entry || typeof entry !== "object") return [];
      const record = entry as Record<string, unknown>;
      const id = typeof record.id === "string" ? record.id : "";
      const label = typeof record.label === "string" ? record.label : "";
      if (!id || !label) return [];
      return [{ id, label }];
    });
  };
  const normalizeIndustries = (source: unknown): DfmIndustryOption[] => {
    if (!Array.isArray(source)) return [];
    return source.flatMap((entry) => {
      if (!entry || typeof entry !== "object") return [];
      const record = entry as Record<string, unknown>;
      const id = typeof record.id === "string" ? record.id : "";
      const label = typeof record.label === "string" ? record.label : "";
      const standards = Array.isArray(record.standards)
        ? record.standards.filter((item): item is string => typeof item === "string")
        : [];
      if (!id || !label) return [];
      return [{ id, label, standards }];
    });
  };
  return {
    materials: normalizeOptions(payload.materials),
    manufacturingProcesses: normalizeOptions(payload.manufacturingProcesses),
    industries: normalizeIndustries(payload.industries),
  };
};

const App = () => {
  const [model, setModel] = useState<ModelState | null>(null);
  const [views, setViews] = useState<Record<string, string>>({});
  const [viewMetadata, setViewMetadata] = useState<Record<string, string>>({});
  const [shapeViews, setShapeViews] = useState<Record<string, string>>({});
  const [shapeViewMetadata, setShapeViewMetadata] = useState<Record<string, string>>({});
  const [occViews, setOccViews] = useState<Record<string, string>>({});
  const [midViews, setMidViews] = useState<Record<string, string>>({});
  const [isometricShape2DViews, setIsometricShape2DViews] = useState<Record<string, string>>({});
  const [isometricShape2DMetadata, setIsometricShape2DMetadata] = useState<Record<string, string>>({});
  const [isometricMatplotlibViews, setIsometricMatplotlibViews] = useState<Record<string, string>>({});
  const [isometricMatplotlibMetadata, setIsometricMatplotlibMetadata] = useState<Record<string, string>>({});
  const [components, setComponents] = useState<ModelComponent[]>([]);
  const [componentVisibility, setComponentVisibility] = useState<Record<string, boolean>>({});
  const [selectedComponentNodeName, setSelectedComponentNodeName] = useState<string | null>(null);
  const [componentProfiles, setComponentProfiles] = useState<Record<string, ComponentProfile>>({});
  const [profileOptions, setProfileOptions] = useState<DfmProfileOptions | null>(null);
  const [profileSavingByNode, setProfileSavingByNode] = useState<Record<string, boolean>>({});
  const [profileError, setProfileError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | undefined>(undefined);
  const [statusMessage, setStatusMessage] = useState<string>("Idle");
  const [logMessage, setLogMessage] = useState<string>("");
  const [tickets, setTickets] = useState<ReviewTicket[]>([]);
  const [designReviews, setDesignReviews] = useState<DesignReviewSession[]>([]);
  const [checklistTemplates, setChecklistTemplates] = useState<ChecklistTemplate[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [pendingPin, setPendingPin] = useState<PinPosition | null>(null);
  const [pendingReviewPin, setPendingReviewPin] = useState<PinPosition | null>(null);
  const [commentFormOpen, setCommentFormOpen] = useState(false);
  const [reviewFormOpen, setReviewFormOpen] = useState(false);
  const [fitTrigger, setFitTrigger] = useState(0);
  const [infoDialog, setInfoDialog] = useState<null | "compare" | "collaborate">(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const [globalPaneOpen, setGlobalPaneOpen] = useState(false);
  const [leftOpen, setLeftOpen] = useState(false);
  const [leftTab, setLeftTab] = useState<"views" | "reviews" | "com" | "dfm" | "km" | "req">("reviews");
  const [rightOpen, setRightOpen] = useState(false);
  const [rightTab, setRightTab] = useState<"dfm" | null>(null);
  const [pinMode, setPinMode] = useState<"none" | "comment" | "review">("none");

  const previewUrl = useMemo(() => {
    if (!model) return null;
    return `${apiBase}${model.previewUrl}`;
  }, [model]);

  const viewUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(views).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [views]);

  const shapeViewUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(shapeViews).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [shapeViews]);

  const occViewUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(occViews).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [occViews]);

  const midViewUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(midViews).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [midViews]);

  const isometricShape2DViewUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(isometricShape2DViews).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [isometricShape2DViews]);

  const isometricMatplotlibViewUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(isometricMatplotlibViews).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [isometricMatplotlibViews]);

  const viewMetadataUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(viewMetadata).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [viewMetadata]);

  const shapeViewMetadataUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(shapeViewMetadata).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [shapeViewMetadata]);

  const isometricShape2DMetadataUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(isometricShape2DMetadata).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [isometricShape2DMetadata]);

  const isometricMatplotlibMetadataUrls = useMemo(() => {
    const mapped: Record<string, string> = {};
    Object.entries(isometricMatplotlibMetadata).forEach(([key, url]) => {
      mapped[key] = url.startsWith("http") ? url : `${apiBase}${url}`;
    });
    return mapped;
  }, [isometricMatplotlibMetadata]);

  const pinnedItems = useMemo<PinnedItem[]>(() => {
    return [...tickets, ...designReviews];
  }, [tickets, designReviews]);

  const selectedComponent = useMemo(() => {
    if (!selectedComponentNodeName) return null;
    return components.find((component) => component.nodeName === selectedComponentNodeName) ?? null;
  }, [components, selectedComponentNodeName]);

  const selectedComponentProfile = useMemo<ComponentProfile | null>(() => {
    if (!selectedComponent) return null;
    return componentProfiles[selectedComponent.nodeName] ?? EMPTY_COMPONENT_PROFILE;
  }, [componentProfiles, selectedComponent]);

  const selectedIndustryStandards = useMemo<string[]>(() => {
    if (!selectedComponentProfile?.industry || !profileOptions) return [];
    const industry = profileOptions.industries.find((item) => item.label === selectedComponentProfile.industry);
    return industry?.standards ?? [];
  }, [profileOptions, selectedComponentProfile]);

  const isSelectedProfileComplete = Boolean(
    selectedComponentProfile?.material && selectedComponentProfile?.manufacturingProcess && selectedComponentProfile?.industry
  );

  const readErrorDetail = async (response: Response, fallback: string) => {
    try {
      const payload = await response.json();
      return (payload?.detail ?? payload?.message ?? fallback) as string;
    } catch {
      return fallback;
    }
  };

  const fetchTickets = async (modelId: string) => {
    try {
      const response = await fetch(`${apiBase}/api/models/${modelId}/tickets`);
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to fetch tickets");
        throw new Error(detail);
      }
      const payload = await response.json();
      setTickets(payload);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${apiBase}/api/review-templates`);
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to fetch templates");
        throw new Error(detail);
      }
      const payload = await response.json();
      setChecklistTemplates(payload);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const fetchProfileOptions = async () => {
    try {
      const response = await fetch(`${apiBase}/api/dfm/config`);
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to fetch DFM config");
        throw new Error(detail);
      }
      const payload = normalizeProfileOptions(await response.json());
      setProfileOptions(payload);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setProfileError(message);
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const fetchComponentProfiles = async (modelId: string) => {
    try {
      const response = await fetch(`${apiBase}/api/models/${modelId}/component-profiles`);
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to fetch component profiles");
        throw new Error(detail);
      }
      const payload = await response.json();
      setComponentProfiles(normalizeComponentProfiles(payload.componentProfiles));
      setProfileError(null);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setProfileError(message);
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const fetchDesignReviews = async (modelId: string) => {
    try {
      const response = await fetch(`${apiBase}/api/models/${modelId}/design-reviews`);
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to fetch design reviews");
        throw new Error(detail);
      }
      const payload = await response.json();
      setDesignReviews(payload);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const createTicket = async (payload: CreateTicketPayload) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to create ticket");
        throw new Error(detail);
      }
      const ticket = (await response.json()) as ReviewTicket;
      setTickets((prev) => [...prev, ticket]);
      setSelectedItemId(ticket.id);
      setLeftOpen(true);
      setLeftTab("reviews");
      setPendingPin(null);
      setCommentFormOpen(false);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const updateTicket = async (id: string, fields: Partial<ReviewTicket>) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/tickets/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to update ticket");
        throw new Error(detail);
      }
      const updated = (await response.json()) as ReviewTicket;
      setTickets((prev) => prev.map((ticket) => (ticket.id === id ? updated : ticket)));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const deleteTicket = async (id: string) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/tickets/${id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to delete ticket");
        throw new Error(detail);
      }
      setTickets((prev) => prev.filter((ticket) => ticket.id !== id));
      setSelectedItemId((prev) => (prev === id ? null : prev));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const addTicketReply = async (ticketId: string, data: { author: string; text: string }) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/tickets/${ticketId}/replies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to add reply");
        throw new Error(detail);
      }
      const reply = await response.json();
      setTickets((prev) =>
        prev.map((ticket) =>
          ticket.id === ticketId ? { ...ticket, replies: [...(ticket.replies ?? []), reply] } : ticket
        )
      );
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const deleteTicketReply = async (ticketId: string, replyId: string) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/tickets/${ticketId}/replies/${replyId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to delete reply");
        throw new Error(detail);
      }
      setTickets((prev) =>
        prev.map((ticket) =>
          ticket.id === ticketId
            ? { ...ticket, replies: ticket.replies.filter((reply) => reply.id !== replyId) }
            : ticket
        )
      );
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const createReview = async (payload: CreateReviewPayload) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/design-reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to create review");
        throw new Error(detail);
      }
      const review = (await response.json()) as DesignReviewSession;
      setDesignReviews((prev) => [...prev, review]);
      setSelectedItemId(review.id);
      setLeftOpen(true);
      setLeftTab("reviews");
      setPendingReviewPin(null);
      setReviewFormOpen(false);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const updateReview = async (id: string, fields: Partial<DesignReviewSession>) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/design-reviews/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to update review");
        throw new Error(detail);
      }
      const updated = (await response.json()) as DesignReviewSession;
      setDesignReviews((prev) => prev.map((review) => (review.id === id ? updated : review)));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const deleteReview = async (id: string) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/design-reviews/${id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to delete review");
        throw new Error(detail);
      }
      setDesignReviews((prev) => prev.filter((review) => review.id !== id));
      setSelectedItemId((prev) => (prev === id ? null : prev));
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const updateChecklistItem = async (
    reviewId: string,
    itemId: string,
    fields: { status?: string; note?: string }
  ) => {
    if (!model) return;
    try {
      const response = await fetch(
        `${apiBase}/api/models/${model.id}/design-reviews/${reviewId}/checklist/${itemId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fields),
        }
      );
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to update checklist item");
        throw new Error(detail);
      }
      const item = await response.json();
      setDesignReviews((prev) =>
        prev.map((review) =>
          review.id === reviewId
            ? {
                ...review,
                checklist: review.checklist.map((entry) => (entry.id === itemId ? { ...entry, ...item } : entry)),
              }
            : review
        )
      );
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const addReviewReply = async (reviewId: string, data: { author: string; text: string }) => {
    if (!model) return;
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/design-reviews/${reviewId}/replies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to add review reply");
        throw new Error(detail);
      }
      const reply = await response.json();
      setDesignReviews((prev) =>
        prev.map((review) =>
          review.id === reviewId ? { ...review, replies: [...(review.replies ?? []), reply] } : review
        )
      );
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    }
  };

  const importModel = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    setBusyAction("Importing");
    setStatusMessage(`Uploading ${file.name}`);
    setComponents([]);
    setComponentVisibility({});
    setSelectedComponentNodeName(null);
    setComponentProfiles({});
    setProfileSavingByNode({});
    setProfileError(null);
    try {
      const response = await fetch(`${apiBase}/api/models`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to import STEP file");
        throw new Error(detail);
      }
      const payload = await response.json();
      setModel({
        id: payload.modelId,
        previewUrl: payload.previewUrl,
        originalName: payload.originalName,
      });
      const loadedComponents = normalizeComponents(payload.components);
      setComponents(loadedComponents);
      setComponentVisibility(buildComponentVisibility(loadedComponents, true));
      setSelectedComponentNodeName(loadedComponents[0]?.nodeName ?? null);
      setComponentProfiles(normalizeComponentProfiles(payload.componentProfiles));
      setTickets([]);
      setDesignReviews([]);
      setSelectedItemId(null);
      setPendingPin(null);
      setPendingReviewPin(null);
      setCommentFormOpen(false);
      setReviewFormOpen(false);
      setPinMode("none");
      setViews({});
      setViewMetadata({});
      setShapeViews({});
      setShapeViewMetadata({});
      setOccViews({});
      setMidViews({});
      setIsometricShape2DViews({});
      setIsometricShape2DMetadata({});
      setIsometricMatplotlibViews({});
      setIsometricMatplotlibMetadata({});
      const successMsg = `Loaded ${payload.originalName}`;
      setStatusMessage(successMsg);
      setLogMessage(successMsg);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateViews = async () => {
    if (!model) return;
    setBusyAction("Generating Mesh Views");
    setStatusMessage("Computing orthographic projections");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/views`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to generate views");
        throw new Error(detail);
      }
      const payload = await response.json();
      setViews(payload.views);
      setViewMetadata(payload.metadata ?? {});
      setStatusMessage("Views updated");
      setLogMessage("Views updated");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateShape2DViews = async () => {
    if (!model) return;
    setBusyAction("Generating Shape2D Views");
    setStatusMessage("Computing Shape2D outlines");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/shape2d`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to generate Shape2D views");
        throw new Error(detail);
      }
      const payload = await response.json();
      setShapeViews(payload.views);
      setShapeViewMetadata(payload.metadata ?? {});
      setStatusMessage("Shape2D views updated");
      setLogMessage("Shape2D views updated");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateOccViews = async () => {
    if (!model) return;
    setBusyAction("Generating OCC Views");
    setStatusMessage("Computing OCC projections");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/occ_views`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to generate OCC views");
        throw new Error(detail);
      }
      const payload = await response.json();
      setOccViews(payload.views);
      setStatusMessage("OCC views updated");
      setLogMessage("OCC views updated");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateMidViews = async () => {
    if (!model) return;
    setBusyAction("Generating Mid Views");
    setStatusMessage("Computing mid-plane sections");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/mid_views`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to generate mid views");
        throw new Error(detail);
      }
      const payload = await response.json();
      setMidViews(payload.views);
      setStatusMessage("Mid views updated");
      setLogMessage("Mid views updated");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateIsometricShape2D = async () => {
    if (!model) return;
    setBusyAction("Generating Isometric Shape2D");
    setStatusMessage("Computing isometric Shape2D view");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/isometric_shape2d`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to generate isometric Shape2D view");
        throw new Error(detail);
      }
      const payload = await response.json();
      setIsometricShape2DViews(payload.views);
      setIsometricShape2DMetadata(payload.metadata ?? {});
      setStatusMessage("Isometric Shape2D updated");
      setLogMessage("Isometric Shape2D updated");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateIsometricMatplotlib = async () => {
    if (!model) return;
    setBusyAction("Generating Isometric Matplotlib");
    setStatusMessage("Computing isometric matplotlib view");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/isometric_matplotlib`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to generate isometric matplotlib view");
        throw new Error(detail);
      }
      const payload = await response.json();
      setIsometricMatplotlibViews(payload.views);
      setIsometricMatplotlibMetadata(payload.metadata ?? {});
      setStatusMessage("Isometric Matplotlib updated");
      setLogMessage("Isometric Matplotlib updated");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  const generateIsometricViews = async () => {
    if (!model || busyAction) return;
    await generateIsometricShape2D();
    await generateIsometricMatplotlib();
  };

  // Drawing page state
  const [isDrawingOpen, setIsDrawingOpen] = useState(false);
  const [drawingZones, setDrawingZones] = useState<DrawingZone[]>([]);
  const [pendingZone, setPendingZone] = useState<string | null>(null);
  const [templateUrl, setTemplateUrl] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState<Dimension[]>([]);

  const handleCreateDrawing = () => {
    try {
      const saved = localStorage.getItem(DRAWING_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        setDrawingZones(parsed.zones ?? []);
        setDimensions(parsed.dimensions ?? []);
      } else {
        setDrawingZones([]);
        setDimensions([]);
      }
    } catch {
      setDrawingZones([]);
      setDimensions([]);
    }
    setPendingZone(null);
    setIsDrawingOpen(true);
  };

  // prefetch template on app start so drawing is ready
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/template/drawing`);
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        setTemplateUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
      } catch (e) {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(
    () => () => {
      if (templateUrl) URL.revokeObjectURL(templateUrl);
    },
    [templateUrl]
  );

  useEffect(() => {
    fetchTemplates();
    fetchProfileOptions();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || target?.isContentEditable) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "c") {
        setPinMode((prev) => (prev === "comment" ? "none" : "comment"));
        setLeftOpen(true);
        setLeftTab("com");
      }
      if (key === "r") {
        setPinMode((prev) => (prev === "review" ? "none" : "review"));
        setLeftOpen(true);
        setLeftTab("reviews");
      }
      if (event.key === "Escape") {
        setPinMode("none");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!model) {
      setTickets([]);
      setDesignReviews([]);
      setSelectedItemId(null);
      setComponents([]);
      setComponentVisibility({});
      setSelectedComponentNodeName(null);
      setComponentProfiles({});
      setProfileSavingByNode({});
      setProfileError(null);
      return;
    }
    fetchTickets(model.id);
    fetchDesignReviews(model.id);
    fetchComponentProfiles(model.id);
  }, [model?.id]);

  useEffect(() => {
    if (!isDrawingOpen) return;
    try {
      const payload = { zones: drawingZones, dimensions };
      localStorage.setItem(DRAWING_STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // ignore persistence errors
    }
  }, [drawingZones, dimensions, isDrawingOpen]);

  useEffect(() => {
    if (!components.length) {
      setSelectedComponentNodeName(null);
      return;
    }
    setSelectedComponentNodeName((current) => {
      if (current && components.some((component) => component.nodeName === current)) {
        return current;
      }
      return components[0].nodeName;
    });
  }, [components]);

  const handleSelectThumbnailForAssignment = (name: string, src: string, metadataUrl?: string) => {
    if (!pendingZone) return;
    setDrawingZones((prev) =>
      prev.map((z) => (z.id === pendingZone ? { ...z, src, viewName: name, metadataUrl } : z))
    );
    setPendingZone(null);
  };

  const handleCreateZone = (layout: { x: number; y: number; w: number; h: number }) => {
    const id = `zone-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
    setDrawingZones((prev) => [...prev, { id, layout }]);
    setPendingZone(id);
  };

  const handleUpdateZoneLayout = (id: string, layout: { x: number; y: number; w: number; h: number }) => {
    setDrawingZones((prev) => prev.map((z) => (z.id === id ? { ...z, layout } : z)));
  };

  const handleDeleteZone = (id: string) => {
    setDrawingZones((prev) => prev.filter((z) => z.id !== id));
    setDimensions((prev) => prev.filter((d) => d.zoneId !== id));
    if (pendingZone === id) setPendingZone(null);
  };

  const handleZoneClick = (id: string) => {
    setPendingZone(id);
  };

  const handleUndoDimension = () => {
    setDimensions((prev) => prev.slice(0, -1));
  };

  const handleLeftRailToggle = (tab: "views" | "reviews" | "com" | "dfm" | "km" | "req") => {
    setLeftOpen((prev) => !(prev && leftTab === tab));
    setLeftTab(tab);
  };

  const handleRightRailToggle = (tab: "dfm") => {
    if (rightOpen && rightTab === tab) {
      setRightOpen(false);
      setRightTab(null);
      return;
    }
    setRightOpen(true);
    setRightTab(tab);
  };

  const handleToggleComponent = (nodeName: string) => {
    setComponentVisibility((prev) => ({
      ...prev,
      [nodeName]: !(prev[nodeName] ?? true),
    }));
  };

  const handleShowAllComponents = () => {
    setComponentVisibility(buildComponentVisibility(components, true));
  };

  const handleHideAllComponents = () => {
    setComponentVisibility(buildComponentVisibility(components, false));
  };

  const handleSelectComponent = (nodeName: string) => {
    setSelectedComponentNodeName(nodeName);
    setProfileError(null);
  };

  const handleChangeComponentProfile = async (field: keyof ComponentProfile, value: string) => {
    if (!model || !selectedComponentNodeName) return;
    const nodeName = selectedComponentNodeName;
    const nextProfile = { ...(componentProfiles[nodeName] ?? EMPTY_COMPONENT_PROFILE), [field]: value };
    setComponentProfiles((prev) => ({
      ...prev,
      [nodeName]: nextProfile,
    }));
    setProfileSavingByNode((prev) => ({ ...prev, [nodeName]: true }));
    setProfileError(null);
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/component-profiles/${nodeName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material: nextProfile.material,
          manufacturing_process: nextProfile.manufacturingProcess,
          industry: nextProfile.industry,
        }),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to save component profile");
        throw new Error(detail);
      }
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setProfileError(message);
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setProfileSavingByNode((prev) => ({ ...prev, [nodeName]: false }));
    }
  };

  const handleImportClick = () => {
    importInputRef.current?.click();
  };

  const handleImportFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await importModel(file);
    event.target.value = "";
  };

  const handleCommentPin = (payload: {
    position: [number, number, number];
    normal: [number, number, number];
    cameraState: { position: [number, number, number]; target: [number, number, number] };
    screenX: number;
    screenY: number;
  }) => {
    if (commentFormOpen) return;
    setPendingPin({
      position: payload.position,
      normal: payload.normal,
      cameraState: payload.cameraState,
    });
    setCommentFormOpen(true);
    setLeftOpen(true);
    setLeftTab("com");
    setPinMode("none");
  };

  const handleReviewPin = (payload: {
    position: [number, number, number];
    normal: [number, number, number];
    cameraState: { position: [number, number, number]; target: [number, number, number] };
    screenX: number;
    screenY: number;
  }) => {
    if (reviewFormOpen) return;
    setPendingReviewPin({
      position: payload.position,
      normal: payload.normal,
      cameraState: payload.cameraState,
    });
    setReviewFormOpen(true);
    setLeftOpen(true);
    setLeftTab("reviews");
    setPinMode("none");
  };

  const handleSelectTicket = (id: string | null) => {
    setSelectedItemId(id);
    setLeftOpen(true);
    if (!id) return;
    if (tickets.some((ticket) => ticket.id === id)) {
      setLeftTab("com");
    } else if (designReviews.some((review) => review.id === id)) {
      setLeftTab("reviews");
    }
  };

  const exportViews = async () => {
    if (!model) return;
    setBusyAction("Packaging Views");
    setStatusMessage("Preparing ZIP archive");
    try {
      const response = await fetch(`${apiBase}/api/models/${model.id}/export`, {
        method: "POST",
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response, "Failed to export views");
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const safeName = model.originalName?.replace(/\.[^.]+$/, "") || "views";
      link.download = `${safeName}-views.zip`;
      link.click();
      window.URL.revokeObjectURL(url);
      setStatusMessage("Download started");
      setLogMessage("Download started");
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unexpected error";
      setStatusMessage(message);
      setLogMessage(message);
    } finally {
      setBusyAction(undefined);
    }
  };

  return (
    <div className="app-shell">
      <Toolbar
        busyAction={busyAction}
        logMessage={logMessage}
      />
      <button
        className="global-menu__trigger"
        aria-label="Toggle general menu"
        aria-expanded={globalPaneOpen}
        aria-controls="general-menu"
        onClick={() => setGlobalPaneOpen((prev) => !prev)}
      >
        <span className="global-menu__trigger-line" />
        <span className="global-menu__trigger-line" />
        <span className="global-menu__trigger-line" />
      </button>
      {globalPaneOpen && <button className="global-pane__backdrop" onClick={() => setGlobalPaneOpen(false)} aria-label="Close global pane" />}
      <aside id="general-menu" className={`global-pane ${globalPaneOpen ? "global-pane--open" : ""}`}>
        <div className="global-pane__content">
          <input
            type="file"
            ref={importInputRef}
            accept=".step,.stp"
            className="sr-only"
            onChange={handleImportFileChange}
          />
          <button className="toolbar__button global-pane__button" onClick={handleImportClick} disabled={Boolean(busyAction)}>
            Import STEP
          </button>
          <button
            className="toolbar__button global-pane__button"
            onClick={exportViews}
            disabled={Object.keys(views).length === 0 || Boolean(busyAction)}
          >
            Export Views
          </button>
          <button className="toolbar__button global-pane__button" onClick={() => setInfoDialog("compare")} disabled={Boolean(busyAction)}>
            Compare Models
          </button>
          <button className="toolbar__button global-pane__button" onClick={() => setInfoDialog("collaborate")} disabled={Boolean(busyAction)}>
            Collaborate
          </button>
        </div>
      </aside>
      <main className={`workspace ${leftOpen ? "" : "workspace--left-collapsed"} ${rightOpen ? "" : "workspace--right-collapsed"}`}>
        <aside className="sidebar-rail sidebar-rail--left">
          <button
            className={`sidebar-rail__button ${leftOpen && leftTab === "views" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleLeftRailToggle("views")}
          >
            <span className="sidebar-rail__icon">V</span>
            <span className="sidebar-rail__label">Views</span>
          </button>
          <button
            className={`sidebar-rail__button ${leftOpen && leftTab === "com" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleLeftRailToggle("com")}
          >
            <span className="sidebar-rail__icon">C</span>
            <span className="sidebar-rail__label">Comments</span>
          </button>
          <button
            className={`sidebar-rail__button ${leftOpen && leftTab === "reviews" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleLeftRailToggle("reviews")}
          >
            <span className="sidebar-rail__icon">R</span>
            <span className="sidebar-rail__label">Reviews</span>
          </button>
          <button
            className={`sidebar-rail__button ${leftOpen && leftTab === "dfm" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleLeftRailToggle("dfm")}
          >
            <span className="sidebar-rail__icon">M</span>
            <span className="sidebar-rail__label">Design For Manufacturing</span>
          </button>
          <button
            className={`sidebar-rail__button ${leftOpen && leftTab === "km" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleLeftRailToggle("km")}
          >
            <span className="sidebar-rail__icon">K</span>
            <span className="sidebar-rail__label">Knowledge Management</span>
          </button>
          <button
            className={`sidebar-rail__button ${leftOpen && leftTab === "req" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleLeftRailToggle("req")}
          >
            <span className="sidebar-rail__icon">Q</span>
            <span className="sidebar-rail__label">Requirements</span>
          </button>
        </aside>
        <aside className={`sidebar-panel sidebar-panel--left ${leftOpen ? "sidebar-panel--open" : ""}`}>
          {leftTab === "views" ? (
            <ViewsPanel
              views={viewUrls}
              viewMetadata={viewMetadataUrls}
              shapeViews={shapeViewUrls}
              shapeViewMetadata={shapeViewMetadataUrls}
              occViews={occViewUrls}
              midViews={midViewUrls}
              isometricShape2DViews={isometricShape2DViewUrls}
              isometricShape2DMetadata={isometricShape2DMetadataUrls}
              isometricMatplotlibViews={isometricMatplotlibViewUrls}
              isometricMatplotlibMetadata={isometricMatplotlibMetadataUrls}
              expectedViews={["top", "bottom", "left", "right", "front", "back"]}
              shapeExpectedViews={["top", "side", "bottom"]}
              occExpectedViews={["x", "y", "z"]}
              midExpectedViews={["mid_x", "mid_y", "mid_z"]}
              isometricShape2DExpectedViews={["isometric_shape2d"]}
              isometricMatplotlibExpectedViews={["isometric_matplotlib"]}
              onSelectThumbnail={handleSelectThumbnailForAssignment}
              onGenerateViews={generateViews}
              onGenerateShape2DViews={generateShape2DViews}
              onGenerateOccViews={generateOccViews}
              onGenerateMidViews={generateMidViews}
              onGenerateIsometricViews={generateIsometricViews}
              canGenerate={Boolean(model)}
              busyAction={busyAction}
            />
          ) : (
            <ReviewPanel
              tickets={tickets}
              designReviews={designReviews}
              selectedItemId={selectedItemId}
              mode={leftTab}
              onSelect={handleSelectTicket}
              onUpdateTicket={updateTicket}
              onDeleteTicket={deleteTicket}
              onAddReply={addTicketReply}
              onDeleteReply={deleteTicketReply}
              onUpdateReview={updateReview}
              onDeleteReview={deleteReview}
              onUpdateChecklistItem={updateChecklistItem}
              onAddReviewReply={addReviewReply}
              onStartReview={() => {
                setPendingReviewPin(null);
                setReviewFormOpen(false);
                setPinMode("review");
                setLeftOpen(true);
                setLeftTab("reviews");
              }}
            />
          )}
        </aside>
        <div className="workspace__main">
          {isDrawingOpen ? (
            <DrawingPage
              zones={drawingZones}
              onBack={() => setIsDrawingOpen(false)}
              onExport={(format) => console.log("Export drawing as", format)}
              onSelectZone={handleZoneClick}
              onUpdateZone={handleUpdateZoneLayout}
              onCreateZone={handleCreateZone}
              dimensions={dimensions}
              onAddDimension={(dim) => setDimensions((prev) => [...prev, dim])}
              onDeleteDimension={(id) => setDimensions((prev) => prev.filter((d) => d.id !== id))}
              onUndoLastDimension={handleUndoDimension}
              onDeleteZone={handleDeleteZone}
              pendingZone={pendingZone}
              templateUrl={templateUrl}
            />
          ) : (
            <div className="viewer-stack">
              <ModelViewer
                previewUrl={previewUrl}
                message={statusMessage}
                onCreateDrawing={handleCreateDrawing}
                fitTrigger={fitTrigger}
                components={components}
                componentVisibility={componentVisibility}
                onToggleComponent={handleToggleComponent}
                onShowAllComponents={handleShowAllComponents}
                onHideAllComponents={handleHideAllComponents}
                selectedComponentNodeName={selectedComponentNodeName}
                onSelectComponent={handleSelectComponent}
                profileOptions={profileOptions}
                selectedComponentProfile={selectedComponentProfile}
                selectedIndustryStandards={selectedIndustryStandards}
                profileSaving={Boolean(selectedComponentNodeName && profileSavingByNode[selectedComponentNodeName])}
                profileError={profileError}
                onChangeComponentProfile={handleChangeComponentProfile}
                items={pinnedItems}
                selectedItemId={selectedItemId}
                onSelectTicket={(id) => handleSelectTicket(id)}
                pinMode={pinMode}
                onCommentPin={handleCommentPin}
                onReviewPin={handleReviewPin}
              showReviewCards={leftOpen && pinMode === "none" && (leftTab === "reviews" || leftTab === "com")}
              />
              <CommentForm
                open={commentFormOpen}
                pendingPin={pendingPin}
                onSubmit={createTicket}
                onCancel={() => {
                  setCommentFormOpen(false);
                  setPendingPin(null);
                  setPinMode("none");
                }}
              />
              <ReviewStartForm
                open={reviewFormOpen}
                pendingPin={pendingReviewPin}
                templates={checklistTemplates}
                onSubmit={createReview}
                onCancel={() => {
                  setReviewFormOpen(false);
                  setPendingReviewPin(null);
                  setPinMode("none");
                }}
              />
              {previewUrl && (
                <div className="viewer__mode-stack">
                  <button
                    className="viewer__fit"
                    onClick={() => setFitTrigger((t) => t + 1)}
                    aria-label="Fit model to view"
                  >
                    Fit to screen
                  </button>
                </div>
              )}
          </div>
        )}
        </div>
        <aside className="sidebar-rail sidebar-rail--right">
          <button
            className={`sidebar-rail__button ${rightOpen && rightTab === "dfm" ? "sidebar-rail__button--active" : ""}`}
            onClick={() => handleRightRailToggle("dfm")}
          >
            <span className="sidebar-rail__icon">D</span>
            <span className="sidebar-rail__label">DFM (AI)</span>
          </button>
        </aside>
        <DfmReviewSidebar
          open={rightOpen && rightTab === "dfm"}
          apiBase={apiBase}
          modelId={model?.id ?? null}
          selectedComponent={
            selectedComponent
              ? { nodeName: selectedComponent.nodeName, displayName: selectedComponent.displayName }
              : null
          }
          selectedProfile={selectedComponentProfile}
          profileComplete={isSelectedProfileComplete}
          onClose={() => {
            setRightOpen(false);
            setRightTab(null);
          }}
        />
        {infoDialog && (
          <div className="modal-backdrop">
            <div className="modal">
              <h3>{infoDialog === "compare" ? "Model compare" : "Collaborate"}</h3>
              <p>
                {infoDialog === "compare"
                  ? "Dummy Feature to load another model and compare with current one"
                  : "Feature to invite another user, and have an interactive collaboration session with them"}
              </p>
              <button className="modal__ok" onClick={() => setInfoDialog(null)}>
                OK
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
