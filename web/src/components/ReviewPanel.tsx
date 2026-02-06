import { useEffect, useMemo, useState } from "react";

import type {

  ChecklistItemStatus,

  DesignReviewSession,

  Reply,

  ReviewTicket,

  ReviewSessionStatus,

  TicketPriority,

  TicketStatus,

  TicketType,

} from "../types/review";



type ReviewPanelProps = {

  tickets: ReviewTicket[];

  designReviews: DesignReviewSession[];

  selectedItemId: string | null;

  mode: "reviews" | "com" | "dfm" | "km" | "req";

  onSelect: (id: string | null) => void;

  onUpdateTicket: (id: string, fields: Partial<ReviewTicket>) => void;

  onDeleteTicket: (id: string) => void;

  onAddReply: (ticketId: string, data: { author: string; text: string }) => void;

  onDeleteReply: (ticketId: string, replyId: string) => void;

  onUpdateReview: (id: string, fields: Partial<DesignReviewSession>) => void;

  onDeleteReview: (id: string) => void;

  onUpdateChecklistItem: (reviewId: string, itemId: string, fields: { status?: string; note?: string }) => void;

  onAddReviewReply: (reviewId: string, data: { author: string; text: string }) => void;

  onStartReview: () => void;

};



type LibraryCard = {

  title: string;

  summary: string;

  tags: string[];

  meta: {

    priority?: string;

    severity?: string;

    status: string;

    source: string;

    owner: string;

  };

};



const statusOptions: TicketStatus[] = ["open", "in_progress", "resolved", "closed"];

const priorityOptions: TicketPriority[] = ["low", "medium", "high", "critical"];

const typeOptions: TicketType[] = ["issue", "idea", "comment"];

const reviewStatusOptions: ReviewSessionStatus[] = ["in_progress", "passed", "failed", "cancelled"];

const checklistStatusOptions: ChecklistItemStatus[] = ["pending", "pass", "fail", "na"];



const DFM_CARDS: LibraryCard[] = [

  {

    title: "Minimum wall thickness risk",

    summary: "Thin rib section near hinge boss; risk of sink/warpage in injection molding.",

    tags: ["Injection Molding", "Warpage", "Sink"],

    meta: { severity: "High", status: "Open", source: "DFM checklist", owner: "Manufacturing Eng" },

  },

  {

    title: "Draft angle missing on vertical faces",

    summary: "Several near-vertical faces appear <1°; may cause ejection marks.",

    tags: ["Draft", "Ejection"],

    meta: { severity: "High", status: "In Review", source: "Tooling", owner: "Tooling Eng" },

  },

  {

    title: "Sharp internal corner at load path",

    summary: "Internal fillet too small; stress concentration + poor tool life.",

    tags: ["Fillet", "Tool Wear", "Stress"],

    meta: { severity: "Med", status: "Open", source: "CAE feedback", owner: "Design Eng" },

  },

  {

    title: "Hole-to-edge distance too small",

    summary: "Mounting hole close to edge; risk of cracking during assembly torque.",

    tags: ["Fasteners", "Cracking"],

    meta: { severity: "High", status: "Open", source: "Assembly trial", owner: "ME" },

  },

  {

    title: "Undercut requiring side action",

    summary: "Feature creates undercut; needs slider or redesign.",

    tags: ["Undercut", "Tooling Cost"],

    meta: { severity: "High", status: "Open", source: "Supplier DFM", owner: "Supplier Eng" },

  },

  {

    title: "Unsupported thin cantilever",

    summary: "Long thin tab may vibrate and break during handling.",

    tags: ["Handling", "Robustness"],

    meta: { severity: "Med", status: "Open", source: "DFM checklist", owner: "Design Eng" },

  },

  {

    title: "Tolerance stack risk on mating features",

    summary: "Slot + pin alignment likely to bind at worst-case tolerance.",

    tags: ["Tolerance Stack", "Fit"],

    meta: { severity: "High", status: "In Review", source: "GD&T review", owner: "QA" },

  },

  {

    title: "Non-standard drill size",

    summary: "Uses uncommon diameter; increases tooling complexity and cost.",

    tags: ["Machining", "Standardization"],

    meta: { severity: "Low", status: "Accepted", source: "Supplier", owner: "Manufacturing Eng" },

  },

  {

    title: "Deburr access limited",

    summary: "Pocket geometry restricts deburring tool access; burrs may remain.",

    tags: ["Deburr", "Machining"],

    meta: { severity: "Med", status: "Open", source: "Machining feedback", owner: "Supplier Eng" },

  },

  {

    title: "Surface finish mismatch for sealing area",

    summary: "Spec too rough for sealing; may leak unless refined.",

    tags: ["Surface Finish", "Sealing"],

    meta: { severity: "High", status: "Open", source: "Requirements", owner: "Systems Eng" },

  },

];



const KM_CARDS: LibraryCard[] = [

  {

    title: "Prevent scratches on Class-A surfaces",

    summary: "Use protective film + dedicated trays after first operation to avoid cosmetic damage.",

    tags: ["Handling", "Quality"],

    meta: { priority: "P1", status: "Closed", source: "Shopfloor", owner: "Quality Eng" },

  },

  {

    title: "Avoid over-torque on plastic bosses",

    summary: "Introduce torque-limiting driver + screw spec; boss cracking reduced.",

    tags: ["Assembly", "Fasteners"],

    meta: { priority: "P0", status: "Closed", source: "Line issue", owner: "ME" },

  },

  {

    title: "Align datum strategy to inspection",

    summary: "If inspection fixtures reference B/C, don't dimension critical features to A-only.",

    tags: ["Metrology", "Datums"],

    meta: { priority: "P1", status: "Accepted", source: "CMM report", owner: "QA" },

  },

  {

    title: "Add lead-in chamfers for repeatable assembly",

    summary: "Small chamfers on pins/slots reduced cycle time and misbuilds.",

    tags: ["Assembly", "Ergonomics"],

    meta: { priority: "P1", status: "Closed", source: "Assembly pilot", owner: "ME" },

  },

  {

    title: "Tool access clearance rule",

    summary: "Maintain >=12mm clearance for common socket access around M6 heads in tight pockets.",

    tags: ["Serviceability", "Tooling"],

    meta: { priority: "P2", status: "Accepted", source: "Service feedback", owner: "Service Eng" },

  },

  {

    title: "Control warp by gate location",

    summary: "Gate near rib cluster increased warp; relocating gate stabilized flatness.",

    tags: ["Injection Molding", "Warpage"],

    meta: { priority: "P1", status: "Closed", source: "Tool trial", owner: "Tooling Eng" },

  },

  {

    title: "Avoid sharp edges for operator safety",

    summary: "Break edges on stamped parts to reduce glove tears and minor injuries.",

    tags: ["Safety", "Deburr"],

    meta: { priority: "P0", status: "Closed", source: "EHS", owner: "Manufacturing Eng" },

  },

  {

    title: "Thread-forming screws outperform inserts in thin walls",

    summary: "Inserts caused sink + longer cycle time; switching improved yield.",

    tags: ["Fasteners", "Cost"],

    meta: { priority: "P2", status: "Accepted", source: "Supplier", owner: "ME" },

  },

  {

    title: "Define paint mask zones early",

    summary: "Late mask changes drove rework; lock mask boundaries at design freeze.",

    tags: ["Finish", "Process"],

    meta: { priority: "P1", status: "In Review", source: "Rework analysis", owner: "PM" },

  },

  {

    title: "Standardize part orientation in trays",

    summary: "Mixed orientation drove wrong-side assembly; add poka-yoke tray features.",

    tags: ["Poka-Yoke", "Assembly"],

    meta: { priority: "P0", status: "Closed", source: "Line issue", owner: "ME" },

  },

];



const REQ_CARDS: LibraryCard[] = [

  {

    title: "REQ-STR-001: Minimum factor of safety",

    summary: "Structural FoS >= 1.5 under peak load case LC-07.",

    tags: ["Structural", "Safety"],

    meta: { priority: "P0", status: "Approved", source: "Teamcenter", owner: "Systems Eng" },

  },

  {

    title: "REQ-MFG-014: Draft angle",

    summary: "All molded vertical faces must have draft >= 1.0° unless justified.",

    tags: ["Molding", "DFM"],

    meta: { priority: "P1", status: "Approved", source: "Integrity", owner: "Manufacturing Eng" },

  },

  {

    title: "REQ-ASSY-022: Max assembly torque",

    summary: "Fastener torque for M4 into plastic: 1.2 +/- 0.2 Nm.",

    tags: ["Assembly", "Fasteners"],

    meta: { priority: "P0", status: "Approved", source: "Teamcenter", owner: "ME" },

  },

  {

    title: "REQ-QLT-008: Cosmetic surface",

    summary: "No visible sink/flow lines on customer-facing surface at 0.5m viewing distance.",

    tags: ["Cosmetic", "Quality"],

    meta: { priority: "P1", status: "In Review", source: "Integrity", owner: "Quality Eng" },

  },

  {

    title: "REQ-ENV-003: Temperature range",

    summary: "Operate -20°C to +60°C without functional degradation.",

    tags: ["Environment"],

    meta: { priority: "P0", status: "Approved", source: "Requirements DB", owner: "Systems Eng" },

  },

  {

    title: "REQ-REL-011: Cycle durability",

    summary: "Survive 20,000 actuation cycles without crack initiation.",

    tags: ["Reliability", "Fatigue"],

    meta: { priority: "P0", status: "Draft", source: "Integrity", owner: "Reliability Eng" },

  },

  {

    title: "REQ-MAT-006: Material specification",

    summary: "Polymer must be UL94 V-0 and RoHS compliant.",

    tags: ["Material", "Compliance"],

    meta: { priority: "P1", status: "Approved", source: "Teamcenter", owner: "Compliance" },

  },

  {

    title: "REQ-INT-019: Interface envelope",

    summary: "Must not violate keep-out zone KZ-02 around connector.",

    tags: ["Interfaces", "Packaging"],

    meta: { priority: "P0", status: "Approved", source: "Systems ICD", owner: "Systems Eng" },

  },

  {

    title: "REQ-INS-010: Inspection method",

    summary: "Critical hole position verified by CMM; CpK >= 1.33 at SOP.",

    tags: ["Inspection", "SPC"],

    meta: { priority: "P1", status: "In Review", source: "Quality plan", owner: "QA" },

  },

  {

    title: "REQ-DOC-004: Traceability",

    summary: "Each requirement links to at least one verification artifact (test/report/analysis) with version.",

    tags: ["Traceability", "PLM"],

    meta: { priority: "P0", status: "Draft", source: "Integrity", owner: "Systems Eng" },

  },

];



const ReviewPanel = ({

  tickets,

  designReviews,

  selectedItemId,

  mode,

  onSelect,

  onUpdateTicket,

  onDeleteTicket,

  onAddReply,

  onDeleteReply,

  onUpdateReview,

  onDeleteReview,

  onUpdateChecklistItem,

  onAddReviewReply,

  onStartReview,

}: ReviewPanelProps) => {

  const [typeFilter, setTypeFilter] = useState<TicketType | "all">("all");

  const [statusFilter, setStatusFilter] = useState<TicketStatus | "all">("all");

  const [replyAuthor, setReplyAuthor] = useState("");

  const [replyText, setReplyText] = useState("");

  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});



  const selectedTicket = useMemo(

    () => tickets.find((ticket) => ticket.id === selectedItemId) ?? null,

    [tickets, selectedItemId]

  );

  const selectedReview = useMemo(

    () => designReviews.find((review) => review.id === selectedItemId) ?? null,

    [designReviews, selectedItemId]

  );



  useEffect(() => {

    if (!selectedReview) return;

    const nextDrafts: Record<string, string> = {};

    selectedReview.checklist.forEach((item) => {

      nextDrafts[item.id] = item.note ?? "";

    });

    setNoteDrafts(nextDrafts);

  }, [selectedReview?.id]);



  const filteredTickets = useMemo(() => {

    return tickets.filter((ticket) => {

      if (typeFilter !== "all" && ticket.type !== typeFilter) return false;

      if (statusFilter !== "all" && ticket.status !== statusFilter) return false;

      return true;

    });

  }, [tickets, typeFilter, statusFilter]);



  const filteredReviews = useMemo(() => {

    return designReviews;

  }, [designReviews]);



  const rows = useMemo(() => {

    if (mode === "com") {

      return filteredTickets.map((ticket) => ({

        id: ticket.id,

        kind: "comment" as const,

        title: ticket.title,

        type: ticket.type,

        status: ticket.status,

        priority: ticket.priority,

        author: ticket.author,

      }));

    }

    if (mode === "reviews") {

      return filteredReviews.map((review) => ({

        id: review.id,

        kind: "design_review" as const,

        title: review.title,

        type: review.templateName,

        status: review.status,

        priority: "-",

        author: review.author,

      }));

    }

    return [];

  }, [filteredTickets, filteredReviews, mode]);



  const checklistSummary = useMemo(() => {

    if (!selectedReview) return null;

    const total = selectedReview.checklist.length;

    const pass = selectedReview.checklist.filter((i) => i.status === "pass").length;

    const fail = selectedReview.checklist.filter((i) => i.status === "fail").length;

    const na = selectedReview.checklist.filter((i) => i.status === "na").length;

    const pending = selectedReview.checklist.filter((i) => i.status === "pending").length;

    const reviewed = total - pending;

    return { total, pass, fail, na, pending, reviewed };

  }, [selectedReview]);



  const statusSuggestion = useMemo(() => {

    if (!selectedReview || !checklistSummary) return null;

    const { total, pass, na, fail } = checklistSummary;

    if (!total) return null;

    if (fail > 0 && selectedReview.status !== "failed") {

      return { label: "Has failing items — mark as Failed+/-", nextStatus: "failed" as ReviewSessionStatus };

    }

    if (pass + na === total && selectedReview.status !== "passed") {

      return { label: "All items pass or N/A — mark as Passed+/-", nextStatus: "passed" as ReviewSessionStatus };

    }

    return null;

  }, [selectedReview, checklistSummary]);



  const handleAddReply = () => {

    const author = replyAuthor.trim();

    const text = replyText.trim();

    if (!author || !text) return;

    if (selectedTicket) {

      onAddReply(selectedTicket.id, { author, text });

    }

    if (selectedReview) {

      onAddReviewReply(selectedReview.id, { author, text });

    }

    setReplyText("");

  };



  const renderReplies = (replies: Reply[], deleteHandler?: (replyId: string) => void) => {

    if (!replies.length) {

      return <p className="review-detail__empty">No replies yet.</p>;

    }

    return (

      <ul className="review-detail__replies">

        {replies.map((reply) => (

          <li key={reply.id}>

            <div className="review-detail__reply-header">

              <strong>{reply.author}</strong>

              <span>{new Date(reply.createdAt).toLocaleString()}</span>

              {deleteHandler && <button onClick={() => deleteHandler(reply.id)}>Delete</button>}

            </div>

            <p>{reply.text}</p>

          </li>

        ))}

      </ul>

    );

  };



  const renderLibrary = (cards: LibraryCard[]) => {

    return (

      <div className="review-library">

        <div className="review-library__grid">

          {cards.map((card) => (

            <article key={card.title} className="insight-card">

              <div className="insight-card__title">{card.title}</div>

              <p className="insight-card__summary">{card.summary}</p>

              <div className="insight-card__tags">

                {card.tags.map((tag) => (

                  <span key={tag} className="insight-card__tag">

                    {tag}

                  </span>

                ))}

              </div>

              <div className="insight-card__meta">

                {card.meta.severity && <span>Severity: {card.meta.severity}</span>}

                {card.meta.priority && <span>Priority: {card.meta.priority}</span>}

                <span>Status: {card.meta.status}</span>

                <span>Source: {card.meta.source}</span>

                <span>Owner: {card.meta.owner}</span>

              </div>

            </article>

          ))}

        </div>

      </div>

    );

  };



  const isLibraryMode = mode === "dfm" || mode === "km" || mode === "req";

  const panelTitle = useMemo(() => {

    switch (mode) {

      case "reviews":

        return "Reviews";

      case "com":

        return "COM";

      case "dfm":

        return "DFM (Design for Manufacturing)";

      case "km":

        return "KM (Lessons Learned)";

      case "req":

        return "REQ (Requirements)";

      default:

        return "Reviews";

    }

  }, [mode]);

  const panelCount = useMemo(() => {

    switch (mode) {

      case "reviews":

        return designReviews.length;

      case "com":

        return filteredTickets.length;

      case "dfm":

        return DFM_CARDS.length;

      case "km":

        return KM_CARDS.length;

      case "req":

        return REQ_CARDS.length;

      default:

        return 0;

    }

  }, [mode, designReviews.length, filteredTickets.length]);



  return (

    <section className="review-panel">

      <header className="review-panel__header">

        <div>

          <h2>{panelTitle}</h2>

          <span className="review-panel__count">{panelCount} items</span>

        </div>

        {mode === "reviews" && (

          <button className="review-panel__start" onClick={onStartReview}>

            Start Review

          </button>

        )}

      </header>

      {isLibraryMode ? (

        renderLibrary(mode === "dfm" ? DFM_CARDS : mode === "km" ? KM_CARDS : REQ_CARDS)

      ) : ((mode === "com" && selectedTicket) || (mode === "reviews" && selectedReview)) ? (

        <div className="review-detail">

          <button className="review-detail__back" onClick={() => onSelect(null)}>

            ← Back to list

          </button>

          {mode === "com" && selectedTicket && (

            <>

              <div className="review-detail__title">

                <h3>{selectedTicket.title}</h3>

                <span className="review-detail__id">{selectedTicket.id}</span>

              </div>

              <p className="review-detail__description">{selectedTicket.description || "No description."}</p>

              <div className="review-detail__meta">

                <span className={`chip chip--${selectedTicket.type}`}>{selectedTicket.type}</span>

                <span className="review-detail__author">{selectedTicket.author}</span>

                {selectedTicket.tag && <span className="chip chip--tag">{selectedTicket.tag}</span>}

              </div>

              <div className="review-detail__controls">

                <label>

                  Status

                  <select

                    value={selectedTicket.status}

                    onChange={(e) => onUpdateTicket(selectedTicket.id, { status: e.target.value as TicketStatus })}

                  >

                    {statusOptions.map((status) => (

                      <option key={status} value={status}>

                        {status.replace("_", " ")}

                      </option>

                    ))}

                  </select>

                </label>

                <label>

                  Priority

                  <select

                    value={selectedTicket.priority}

                    onChange={(e) =>

                      onUpdateTicket(selectedTicket.id, { priority: e.target.value as TicketPriority })

                    }

                  >

                    {priorityOptions.map((priority) => (

                      <option key={priority} value={priority}>

                        {priority}

                      </option>

                    ))}

                  </select>

                </label>

              </div>

              <section className="review-detail__section">

                <h4>Replies</h4>

                {renderReplies(selectedTicket.replies ?? [], (replyId) => onDeleteReply(selectedTicket.id, replyId))}

                <div className="review-detail__reply-form">

                  <input

                    placeholder="Your name"

                    value={replyAuthor}

                    onChange={(e) => setReplyAuthor(e.target.value)}

                  />

                  <textarea

                    placeholder="Write a reply"

                    rows={3}

                    value={replyText}

                    onChange={(e) => setReplyText(e.target.value)}

                  />

                  <button onClick={handleAddReply} className="review-detail__reply-submit">

                    Add reply

                  </button>

                </div>

              </section>

              <button className="review-detail__delete" onClick={() => onDeleteTicket(selectedTicket.id)}>

                Delete ticket

              </button>

            </>

          )}

          {mode === "reviews" && selectedReview && (

            <>

              <div className="review-detail__title">

                <h3>{selectedReview.title || selectedReview.templateName}</h3>

                <span className="review-detail__id">{selectedReview.id}</span>

              </div>

              <p className="review-detail__description">{selectedReview.templateName}</p>

              <div className="review-detail__meta">

                <span className="chip chip--review">Review</span>

                <span className="review-detail__author">{selectedReview.author}</span>

              </div>

              <div className="review-detail__controls">

                <label>

                  Status

                  <select

                    value={selectedReview.status}

                    onChange={(e) =>

                      onUpdateReview(selectedReview.id, { status: e.target.value as ReviewSessionStatus })

                    }

                  >

                    {reviewStatusOptions.map((status) => (

                      <option key={status} value={status}>

                        {status.replace("_", " ")}

                      </option>

                    ))}

                  </select>

                </label>

              </div>

              {statusSuggestion && (

                <div className="auto-suggestion">

                  <span>{statusSuggestion.label}</span>

                  <button

                    onClick={() => onUpdateReview(selectedReview.id, { status: statusSuggestion.nextStatus })}

                  >

                    Apply

                  </button>

                </div>

              )}

              <section className="checklist-section">

                <h4>Checklist</h4>

                {checklistSummary && (

                  <div className="checklist-progress">

                    <div

                      className="checklist-progress__bar"

                      style={{

                        width: `${(checklistSummary.reviewed / Math.max(1, checklistSummary.total)) * 100}%`,

                      }}

                    />

                    <div className="checklist-summary">

                      <span>{checklistSummary.reviewed}/{checklistSummary.total} reviewed</span>

                      <span>{checklistSummary.pass} pass</span>

                      <span>{checklistSummary.fail} fail</span>

                      <span>{checklistSummary.na} n/a</span>

                      <span>{checklistSummary.pending} pending</span>

                    </div>

                  </div>

                )}

                {selectedReview.checklist.map((item) => (

                  <div key={item.id} className="checklist-item">

                    <div className="checklist-item__text">{item.text}</div>

                    <div className="checklist-toggle">

                      {checklistStatusOptions.map((status) => (

                        <button

                          key={status}

                          className={`checklist-toggle__button ${

                            item.status === status ? "checklist-toggle__button--active" : ""

                          } checklist-toggle__button--${status}`}

                          onClick={() => onUpdateChecklistItem(selectedReview.id, item.id, { status })}

                        >

                          {status}

                        </button>

                      ))}

                    </div>

                    <input

                      className="checklist-note"

                      placeholder="Add note"

                      value={noteDrafts[item.id] ?? item.note ?? ""}

                      onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}

                      onBlur={() => {

                        const nextNote = noteDrafts[item.id] ?? "";

                        if (nextNote !== item.note) {

                          onUpdateChecklistItem(selectedReview.id, item.id, { note: nextNote });

                        }

                      }}

                    />

                  </div>

                ))}

              </section>

              <section className="review-detail__section">

                <h4>Replies</h4>

                {renderReplies(selectedReview.replies ?? [])}

                <div className="review-detail__reply-form">

                  <input

                    placeholder="Your name"

                    value={replyAuthor}

                    onChange={(e) => setReplyAuthor(e.target.value)}

                  />

                  <textarea

                    placeholder="Write a reply"

                    rows={3}

                    value={replyText}

                    onChange={(e) => setReplyText(e.target.value)}

                  />

                  <button onClick={handleAddReply} className="review-detail__reply-submit">

                    Add reply

                  </button>

                </div>

              </section>

              <button className="review-detail__delete" onClick={() => onDeleteReview(selectedReview.id)}>

                Delete review

              </button>

            </>

          )}

        </div>

      ) : (

        <>

          {mode === "com" && (

            <div className="review-panel__filters">

              <label>

                Type

                <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as TicketType | "all")}>

                  <option value="all">All</option>

                  {typeOptions.map((type) => (

                    <option key={type} value={type}>

                      {type}

                    </option>

                  ))}

                </select>

              </label>

              <label>

                Status

                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as TicketStatus | "all")}>

                  <option value="all">All</option>

                  {statusOptions.map((status) => (

                    <option key={status} value={status}>

                      {status.replace("_", " ")}

                    </option>

                  ))}

                </select>

              </label>

            </div>

          )}

          <div className="review-table">

            <div className="review-table__header">

              <span>Key</span>

              <span>Title</span>

              <span>Kind</span>

              <span>Type/Template</span>

              <span>Status</span>

              <span>Priority</span>

              <span>Author</span>

            </div>

            {rows.length === 0 ? (

              <p className="review-table__empty">No items yet.</p>

            ) : (

              rows.map((row) => (

                <button key={row.id} className="review-table__row" onClick={() => onSelect(row.id)}>

                  <span>{row.id}</span>

                  <span className="review-table__title">{row.title}</span>

                  <span className="chip chip--kind">{row.kind === "comment" ? "Comment" : "Review"}</span>

                  <span>{row.type}</span>

                  <span className={`chip chip--status-${row.status}`}>{row.status.replace("_", " ")}</span>

                  <span>{row.priority}</span>

                  <span>{row.author}</span>

                </button>

              ))

            )}

          </div>

        </>

      )}

    </section>

  );

};



export default ReviewPanel;

