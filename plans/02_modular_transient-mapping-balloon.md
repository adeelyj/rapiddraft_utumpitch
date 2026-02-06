# Design Review Feature - Master Plan

## Overview

Five modular plans, each self-contained and executable independently in order.
Ask Claude to "execute Plan A" (or B, C, D, E) when ready.

| Plan | What it delivers | Dependencies |
|------|-----------------|--------------|
| **A** | Backend: Comment tickets + Templates API | None |
| **B** | Frontend: 3D right-click + Comment pins + Review panel (comments only) | Plan A |
| **C** | Backend: Design review session CRUD + checklist endpoints | Plan A |
| **D** | Frontend: Design review UI (template picker, checklist, review pins) | Plans B + C |
| **E** | Polish: Camera fly-to animation, leader lines, click-outside-close | Plans B + D |

## Shared Reference

### Data model, scope, screenshots, risk analysis
See [Full Reference](#full-reference) at the bottom of this file. The reference section contains:
- CoLab screenshot analysis
- Scope (in/out)
- Full TypeScript + Python data models
- Checklist template content
- Storage format (`reviews.json`)
- Risk & clash analysis
- Tech stack notes

---

# Plan A: Backend - Comment Tickets + Templates API

**Goal**: Fully working REST API for comment tickets and checklist templates, testable with curl.

### New files

**1. `server/review_store.py`**
- `ReviewStore` class (mirrors `ModelStore` pattern from `server/model_store.py`)
- Reads/writes `server/data/models/{model_id}/reviews.json`
- Initializes file with `{ "next_rev_id": 1, "next_dr_id": 1, "tickets": [], "design_reviews": [] }` if missing
- Methods (comment tickets only in this plan):
  - `list_tickets(model_id)` → list of ticket dicts
  - `get_ticket(model_id, ticket_id)` → single ticket dict or None
  - `create_ticket(model_id, data)` → assigns `REV-{next_rev_id:03d}`, increments counter, sets timestamps
  - `update_ticket(model_id, ticket_id, fields)` → partial update, sets `updated_at`
  - `delete_ticket(model_id, ticket_id)` → removes from list
  - `add_ticket_reply(model_id, ticket_id, reply_data)` → appends to `replies[]`, generates `r{uuid[:8]}` id
  - `delete_ticket_reply(model_id, ticket_id, reply_id)` → removes from `replies[]`
- Also: `list_templates()` → reads and returns `server/data/review_templates.json`

**2. `server/data/review_templates.json`**
- 3 predefined templates: Design for Assembly (8 items), Manufacturing Review (8 items), Tolerance & Fit Review (7 items)
- See [Full Reference](#predefined-checklist-templates) for exact content

### Modified files

**3. `server/main.py`** - Add 8 endpoints + Pydantic models

Pydantic request models:
```python
class PinPositionBody(BaseModel):
    position: list[float]  # [x, y, z]
    normal: list[float]
    cameraState: dict      # { position: [x,y,z], target: [x,y,z] }

class CreateTicketBody(BaseModel):
    title: str
    description: str = ""
    type: str = "comment"       # "issue" | "idea" | "comment"
    priority: str = "medium"
    author: str
    tag: str = ""
    pin: PinPositionBody

class UpdateTicketBody(BaseModel):
    title: str | None = None
    description: str | None = None
    type: str | None = None
    priority: str | None = None
    status: str | None = None
    tag: str | None = None

class CreateReplyBody(BaseModel):
    author: str
    text: str
```

Endpoints:

| Method | Endpoint | Action |
|--------|----------|--------|
| GET | `/api/review-templates` | List all predefined checklist templates |
| GET | `/api/models/{id}/tickets` | List all comment tickets |
| POST | `/api/models/{id}/tickets` | Create comment ticket |
| GET | `/api/models/{id}/tickets/{ticket_id}` | Get single ticket |
| PATCH | `/api/models/{id}/tickets/{ticket_id}` | Update ticket fields |
| DELETE | `/api/models/{id}/tickets/{ticket_id}` | Delete ticket |
| POST | `/api/models/{id}/tickets/{ticket_id}/replies` | Add reply |
| DELETE | `/api/models/{id}/tickets/{ticket_id}/replies/{reply_id}` | Delete reply |

Instantiate `ReviewStore` alongside existing `ModelStore` at app startup.

### Verification (Plan A)

```bash
# Start backend, upload a model first to get a model_id, then:

# List templates
curl http://localhost:8000/api/review-templates

# Create a ticket
curl -X POST http://localhost:8000/api/models/{id}/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"Fix wall thickness","type":"issue","priority":"high","author":"Engineer A","pin":{"position":[1,2,3],"normal":[0,0,1],"cameraState":{"position":[4,4,4],"target":[0,0,0]}}}'

# List tickets
curl http://localhost:8000/api/models/{id}/tickets

# Add reply
curl -X POST http://localhost:8000/api/models/{id}/tickets/REV-001/replies \
  -H "Content-Type: application/json" \
  -d '{"author":"Engineer B","text":"Agreed, will fix"}'

# Update status
curl -X PATCH http://localhost:8000/api/models/{id}/tickets/REV-001 \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress"}'

# Delete ticket
curl -X DELETE http://localhost:8000/api/models/{id}/tickets/REV-001
```

---

# Plan B: Frontend - 3D Right-Click + Comment Pins + Review Panel

**Goal**: Full comment workflow in the browser. Right-click on model → "Add Comment" → pin appears → manage in sidebar panel.

**Prerequisite**: Plan A complete (backend running with ticket endpoints).

### New files

**1. `web/src/types/review.ts`**
- TypeScript types for Plan B (comment-related only, design review types added in Plan D):
  - `TicketStatus`, `TicketPriority`, `TicketType`
  - `Reply`, `PinPosition`, `ReviewTicket`
  - `ChecklistTemplate` (for fetching templates — used in Plan D but typed here)
  - `PinnedItem` union type (starts as just `ReviewTicket`, extended in Plan D)

**2. `web/src/components/ContextMenu.tsx`**
- Fixed-position overlay appearing at right-click screen coords
- Two buttons: "Add Comment" and "Start Design Review" (review button disabled with "Coming soon" tooltip until Plan D)
- Props: `position: {x, y}`, `onAddComment()`, `onStartReview()`, `onClose()`
- Clicking outside or pressing Escape closes the menu

**3. `web/src/components/CommentForm.tsx`**
- Modal/overlay form for creating a comment ticket
- Fields: title (text), description (textarea), type (dropdown: Issue/Idea/Comment), priority (dropdown), author (text), tag (text, optional)
- Submit button calls parent's `createTicket()` with form data + `pendingPin`
- Cancel button closes form

**4. `web/src/components/ReviewPins.tsx`**
- Renders inside the R3F `<Canvas>` using drei `<Html>`
- For each ticket in `tickets[]`: renders a colored dot at `ticket.pin.position`
  - Color by type: red = Issue, orange = Idea, blue = Comment
- Clicking a dot sets `selectedItemId` and expands the card (shows title, author, type chip, ticket ID, reply count)
- Only one card expanded at a time
- Selected pin gets a highlight ring
- Props: `tickets`, `selectedItemId`, `onSelect(id)`

**5. `web/src/components/ReviewPanel.tsx`**
- Right sidebar panel with two sub-views:
  - **Table view** (default): rows showing Key, Title, Type chip, Status chip, Priority, Author. Filter dropdowns for Type and Status. Clicking a row calls `onSelect(id)`.
  - **Comment detail view**: full ticket info with editable status/priority dropdowns, reply thread, add-reply input, delete button.
- Props: `tickets`, `selectedItemId`, `onSelect`, `onUpdateTicket`, `onDeleteTicket`, `onAddReply`, `onDeleteReply`

**6. `web/src/components/SidebarTabs.tsx`**
- Simple tab toggle: "Views" | "Reviews"
- Renders `ViewsPanel` or `ReviewPanel` based on active tab
- Props: `activeTab`, `onTabChange`, plus pass-through props for both panels

### Modified files

**7. `web/src/App.tsx`** (~120 lines added)
- New state:
  - `tickets: ReviewTicket[]`
  - `selectedItemId: string | null`
  - `pendingPin: PinPosition | null` (set on right-click, consumed by CommentForm)
  - `contextMenu: { x: number, y: number } | null`
  - `sidebarTab: "views" | "reviews"`
- New API functions:
  - `fetchTickets()` — GET, called on model load
  - `createTicket(data)` — POST, appends to tickets, clears pendingPin + contextMenu
  - `updateTicket(id, fields)` — PATCH
  - `deleteTicket(id)` — DELETE
  - `addTicketReply(ticketId, data)` — POST
  - `deleteTicketReply(ticketId, replyId)` — DELETE
- `useEffect` to fetch tickets when `model` changes
- Replace `<ViewsPanel>` with `<SidebarTabs>` wrapping both ViewsPanel and ReviewPanel
- Pass `onContextMenu` handler and `pendingPin`/`contextMenu` state to ModelViewer
- Render `<ContextMenu>` and `<CommentForm>` as overlays outside the canvas

**8. `web/src/components/ModelViewer.tsx`** (~50 lines added)
- Wrap `<primitive object={gltf.scene}>` in `<group onContextMenu={handleContextMenu}>`
- `handleContextMenu`: calls `event.stopPropagation()`, gets `event.intersections[0].point` and `face.normal`, captures camera position and OrbitControls target, calls `props.onContextMenu({ position, normal, cameraState, screenX, screenY })`
- Render `<ReviewPins>` inside the Canvas (sibling to the model group)
- New props: `onContextMenu`, `tickets`, `selectedItemId`, `onSelectTicket`

**9. `web/src/styles.css`** (~150 lines added)
- `.context-menu` — small floating card with two buttons, drop shadow
- `.comment-form` — modal overlay with form fields, submit/cancel buttons
- `.review-pin` — colored dot (12px circle), `.review-pin--selected` highlight
- `.review-pin-card` — expanded card with title, chips, reply count
- `.review-panel` — sidebar panel layout
- `.review-table` — ticket list rows with hover highlight
- `.ticket-detail` — full ticket view with reply thread
- `.chip--issue`, `.chip--idea`, `.chip--comment` — colored type chips
- `.chip--status-*` — status chip variants
- `.sidebar-tabs` — tab toggle buttons

### Verification (Plan B)

1. Load a model in the browser
2. Right-click on the model surface → context menu appears at cursor with "Add Comment" and "Start Design Review" (disabled)
3. Click "Add Comment" → form overlay appears
4. Fill in title, select "Issue" type, enter author → submit
5. Pin appears on the model surface at the click point (red dot for Issue)
6. Click the pin → card expands showing title, author, "REV-001", "Issue" chip
7. Switch to "Reviews" tab in sidebar → table shows the ticket row
8. Click the row → detail view shows full info
9. Add a reply → reply appears in thread
10. Change status to "Resolved" → status chip updates
11. Refresh browser → ticket persists (re-fetched from backend)

---

# Plan C: Backend - Design Review Sessions

**Goal**: REST API for design review sessions with checklist CRUD, testable with curl.

**Prerequisite**: Plan A complete (`review_store.py` exists with ticket methods).

### Modified files

**1. `server/review_store.py`** — Add design review methods
- New methods:
  - `list_reviews(model_id)` → list of review dicts
  - `get_review(model_id, review_id)` → single review dict or None
  - `create_review(model_id, data)` → loads template by `template_id`, copies items into checklist with `status: "pending"` and `note: ""`, assigns `DR-{next_dr_id:03d}`, increments counter
  - `update_review(model_id, review_id, fields)` → partial update (status, title)
  - `delete_review(model_id, review_id)` → removes from `design_reviews[]`
  - `update_checklist_item(model_id, review_id, item_id, fields)` → updates `status` and/or `note` on a specific checklist item
  - `add_review_reply(model_id, review_id, reply_data)` → appends to review's `replies[]`
  - `delete_review_reply(model_id, review_id, reply_id)` → removes from `replies[]`

**2. `server/main.py`** — Add 7 endpoints + Pydantic models

New Pydantic models:
```python
class CreateReviewBody(BaseModel):
    template_id: str
    title: str = ""           # defaults to template name if empty
    author: str
    pin: PinPositionBody

class UpdateReviewBody(BaseModel):
    title: str | None = None
    status: str | None = None  # "in_progress" | "passed" | "failed" | "cancelled"

class UpdateChecklistItemBody(BaseModel):
    status: str | None = None  # "pending" | "pass" | "fail" | "na"
    note: str | None = None
```

Endpoints:

| Method | Endpoint | Action |
|--------|----------|--------|
| GET | `/api/models/{id}/design-reviews` | List all sessions |
| POST | `/api/models/{id}/design-reviews` | Create session (template_id required) |
| GET | `/api/models/{id}/design-reviews/{review_id}` | Get session with full checklist |
| PATCH | `/api/models/{id}/design-reviews/{review_id}` | Update session status/title |
| PATCH | `/api/models/{id}/design-reviews/{review_id}/checklist/{item_id}` | Update checklist item |
| DELETE | `/api/models/{id}/design-reviews/{review_id}` | Delete session |
| POST | `/api/models/{id}/design-reviews/{review_id}/replies` | Add reply |

### Verification (Plan C)

```bash
# Create a design review from the DFA template
curl -X POST http://localhost:8000/api/models/{id}/design-reviews \
  -H "Content-Type: application/json" \
  -d '{"template_id":"dfa","author":"Engineer A","pin":{"position":[5,3,1],"normal":[1,0,0],"cameraState":{"position":[8,3,1],"target":[5,3,1]}}}'

# List reviews
curl http://localhost:8000/api/models/{id}/design-reviews

# Update a checklist item to "pass"
curl -X PATCH http://localhost:8000/api/models/{id}/design-reviews/DR-001/checklist/item-1 \
  -H "Content-Type: application/json" \
  -d '{"status":"pass","note":"Verified top-down assembly"}'

# Mark item as fail with note
curl -X PATCH http://localhost:8000/api/models/{id}/design-reviews/DR-001/checklist/item-2 \
  -H "Content-Type: application/json" \
  -d '{"status":"fail","note":"Needs locating pins added"}'

# Update overall review status
curl -X PATCH http://localhost:8000/api/models/{id}/design-reviews/DR-001 \
  -H "Content-Type: application/json" \
  -d '{"status":"failed"}'

# Add reply to review thread
curl -X POST http://localhost:8000/api/models/{id}/design-reviews/DR-001/replies \
  -H "Content-Type: application/json" \
  -d '{"author":"Engineer B","text":"Item 2 needs redesign before passing"}'
```

---

# Plan D: Frontend - Design Review UI

**Goal**: Full design review workflow in the browser. Right-click → "Start Design Review" → pick template → checklist appears in panel → toggle items pass/fail.

**Prerequisite**: Plans B + C complete.

### Modified files

**1. `web/src/types/review.ts`** — Add design review types
- Add: `ChecklistItemStatus`, `ChecklistItem`, `ReviewSessionStatus`, `DesignReviewSession`
- Update `PinnedItem` union: `ReviewTicket | DesignReviewSession`

**2. `web/src/components/ContextMenu.tsx`**
- Enable the "Start Design Review" button (remove disabled state)

**3. New: `web/src/components/ReviewStartForm.tsx`**
- Modal/overlay form for starting a design review
- Fields: template picker (dropdown of templates fetched from `GET /api/review-templates`), title (pre-filled from selected template name, editable), author (text)
- Displays template description and item count below dropdown as preview
- Submit calls parent's `createReview()` with form data + `pendingPin`
- Cancel closes form

**4. `web/src/components/ReviewPins.tsx`** — Add review pins
- Render design review pins alongside comment pins
- Review pins use a distinct icon/shape (e.g., clipboard icon or square pin vs circle for comments)
- Review pin cards show: title, template name, author, status chip, checklist progress (e.g., "3/8 reviewed")
- Pin color by review status: blue = in_progress, green = passed, red = failed, gray = cancelled

**5. `web/src/components/ReviewPanel.tsx`** — Add review detail view
- Table view: add design review rows (show DR-001 IDs, "Review" kind chip, template name in Type column)
- Add Kind filter dropdown (All / Comments / Design Reviews)
- New **Design Review Detail View** sub-view:
  - Header: title, template name, author, status dropdown, created date
  - Checklist section:
    - Progress bar: X of Y reviewed (non-pending items)
    - Summary: N pass / N fail / N N/A / N pending
    - Each item row: text + 4-state toggle (Pending/Pass/Fail/N/A) + expandable note field
    - Toggling an item calls `PATCH .../checklist/{item_id}`
    - Note field: click to expand, blur to save
  - Overall status dropdown: In Progress / Passed / Failed / Cancelled
    - Auto-suggestion banner: "All items pass/N/A — mark as Passed?" or "Has failing items — mark as Failed?"
  - Reply thread (reuse same component from comment detail)
  - Back to list + Delete review buttons

**6. `web/src/App.tsx`** (~30 lines added on top of Plan B)
- New state: `designReviews: DesignReviewSession[]`, `checklistTemplates: ChecklistTemplate[]`
- New API functions:
  - `fetchTemplates()` — GET `/api/review-templates`, called on mount
  - `fetchDesignReviews()` — GET, called on model load alongside `fetchTickets()`
  - `createReview(data)` — POST
  - `updateReview(id, fields)` — PATCH
  - `deleteReview(id)` — DELETE
  - `updateChecklistItem(reviewId, itemId, fields)` — PATCH
  - `addReviewReply(reviewId, data)` — POST
- Render `<ReviewStartForm>` overlay (same pattern as CommentForm)
- Pass `designReviews` + `checklistTemplates` to ReviewPanel and ReviewPins

**7. `web/src/styles.css`** (~100 lines added on top of Plan B)
- `.review-start-form` — template picker modal
- `.checklist-section` — container for checklist items
- `.checklist-item` — row layout (text + toggle + note)
- `.checklist-toggle` — 4-state button group with color coding
- `.checklist-note` — expandable text field
- `.checklist-progress` — progress bar
- `.checklist-summary` — pass/fail/na/pending counts
- `.auto-suggestion` — banner for status suggestion
- `.review-pin--square` — distinct pin shape for reviews

### Verification (Plan D)

1. Right-click on model → context menu → "Start Design Review" now enabled
2. Click "Start Design Review" → form shows template dropdown with 3 options
3. Select "Design for Assembly" → title pre-fills, see description + "8 items"
4. Submit → review pin appears (distinct shape/color from comment pins)
5. Switch to Reviews tab → table shows DR-001 row with "Review" kind chip
6. Click the row → design review detail view opens
7. See 8 checklist items, all "Pending" (gray)
8. Click "Pass" on item 1 → turns green, progress bar updates to "1/8 reviewed"
9. Click "Fail" on item 2 → turns red, add note "Needs locating pins"
10. Auto-suggestion banner: "Has failing items — mark as Failed?"
11. Add a reply to the review thread → appears below checklist
12. Refresh browser → all checklist states and notes persist

---

# Plan E: Polish

**Goal**: Smooth animations, leader lines, UX refinements.

**Prerequisite**: Plans B + D complete.

### Changes

**1. Camera fly-to animation** (`ModelViewer.tsx`)
- When `selectedItemId` changes to a ticket/review with `cameraState`:
  - Disable OrbitControls (`controls.enabled = false`)
  - Lerp `camera.position` and `controls.target` over ~500ms using `useFrame`
  - Re-enable OrbitControls after animation completes
- Triggered from both ReviewPanel row clicks and pin clicks

**2. Leader lines** (`ReviewPins.tsx`)
- For the currently expanded card, render a drei `<Line>` component from `ticket.pin.position` to a slightly offset position (e.g., `position + normal * 0.3`)
- Dashed style: `dashed={true} dashScale={50} dashSize={0.02} gapSize={0.02}`
- Color matches the pin type color

**3. Click-outside-to-close** (`App.tsx`)
- Context menu: close on any click outside the menu or Escape key
- CommentForm / ReviewStartForm: close on Escape key (but NOT click-outside, since forms have interactive elements)
- ReviewPanel detail view: no auto-close (explicit "Back to list" button)

**4. Auto-suggest review status** (`ReviewPanel.tsx`)
- After each checklist item update, check:
  - All items Pass or N/A → show "Mark as Passed?" banner
  - Any item Fail → show "Has failing items" banner
  - Banner has a "Apply" button that sets the overall status

**5. Auto-fetch on model load** (`App.tsx`)
- `useEffect` on `model` change: fetch tickets + design reviews in parallel
- Clear tickets/reviews when model is null (new upload clears old data)

### Verification (Plan E)

1. Click a ticket in ReviewPanel → camera smoothly animates to saved viewpoint (~500ms)
2. During animation, mouse movement doesn't interfere
3. Click outside context menu → it closes
4. Press Escape while CommentForm is open → form closes
5. Expand a pin card → dashed leader line appears from card to surface point
6. Upload a new model → old tickets/reviews cleared, fresh fetch
7. Toggle all checklist items to Pass → "Mark as Passed?" banner appears → click Apply → status changes

---
---

# Full Reference

## CoLab Screenshots (./media/)

| Screenshot | Key features visible |
|---|---|
| **peerreview.png** | Comment card pinned to 3D geometry showing: author avatar, name, text, status chip ("Equivalent"), ticket ID (BUG-138), reply count. Right sidebar with "Peer Review" panel showing Reviewers + Activity feed. |
| **assignreview.png** | Comment bubble on 3D model with @mention dropdown listing team members. "Add tags" option. |
| **trackissue.png** | "Workspace Feedback" table: columns for Key (MOD-R 1...), Title, Type (Issue/Idea/Comment), Status. Filterable, sortable. |
| **linkswithviews.png** | Threaded conversation pinned to 3D view. Multiple replies with timestamps. Camera view state preserved. |
| **ongeomnotes.png** | Pin with dashed leader line to geometry + dimension callout (5.81mm). Comment card with author role ("Manufacturing Engineer"), text, a **tag chip** ("Assembly Improvements"), reactions, reply count. |
| **crossfunctional.png** | "Cross Functional Design Review" panel: review status (In Progress), description, **review owner**, **reviewer list with roles** and comment counts per reviewer, colored status dots per reviewer. 3D model with threaded comment card. |
| **markup.png** | **2D drawing markup**: engineering drawing (PDF) with red rectangular annotations and arrow markers pointing to specific regions. 3D model inset. File tabs for multiple file types (STL, PDF). |

## Scope

**In scope:**
- Right-click context menu on 3D surface: "Add Comment" or "Start Design Review"
- Comment tickets with type/status/priority, threaded replies, tags
- Design review sessions with predefined checklist templates
- 3D pin markers with expandable comment cards
- Review panel with filterable table, comment detail, review detail with checklist UI
- Camera view state saved/restored per pin
- Leader lines from cards to surface
- JSON-on-disk persistence, sequential IDs (REV-001, DR-001)

**Out of scope:**
- Multi-user auth, @mentions, notifications
- PLM/PDM integration, sharing links
- 2D drawing markup (separate feature)
- Multi-reviewer workflow (requires auth)
- Custom template editor (edit JSON directly in v1)
- Dimension callouts at pin locations
- Reactions on comments
- Image attachments

## Data Model

### TypeScript (`web/src/types/review.ts`)
```typescript
type TicketStatus = "open" | "in_progress" | "resolved" | "closed";
type TicketPriority = "low" | "medium" | "high" | "critical";
type TicketType = "issue" | "idea" | "comment";

type Reply = {
  id: string;
  author: string;
  text: string;
  createdAt: string;
};

type PinPosition = {
  position: [number, number, number];
  normal: [number, number, number];
  cameraState: {
    position: [number, number, number];
    target: [number, number, number];
  };
};

type ReviewTicket = {
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

type ChecklistItemStatus = "pending" | "pass" | "fail" | "na";

type ChecklistItem = {
  id: string;
  text: string;
  status: ChecklistItemStatus;
  note: string;
};

type ReviewSessionStatus = "in_progress" | "passed" | "failed" | "cancelled";

type DesignReviewSession = {
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

type ChecklistTemplate = {
  id: string;
  name: string;
  description: string;
  items: string[];
};

type PinnedItem = ReviewTicket | DesignReviewSession;
```

### Python (`server/review_store.py`)
```python
@dataclass
class Reply:
    id: str; author: str; text: str; created_at: str

@dataclass
class ReviewTicket:
    id: str; kind: str; model_id: str
    title: str; description: str; type: str
    priority: str; status: str; author: str; tag: str
    pin: dict; replies: list
    created_at: str; updated_at: str

@dataclass
class ChecklistItem:
    id: str; text: str; status: str; note: str

@dataclass
class DesignReviewSession:
    id: str; kind: str; model_id: str
    template_id: str; template_name: str; title: str
    author: str; status: str; pin: dict
    checklist: list; replies: list
    created_at: str; updated_at: str
```

### Predefined checklist templates

File: `server/data/review_templates.json`
```json
[
  {
    "id": "dfa",
    "name": "Design for Assembly",
    "description": "Evaluate part design for ease of assembly",
    "items": [
      "Part can be assembled from a single direction (top-down preferred)",
      "Part is self-locating with alignment features (pins, slots, chamfers)",
      "No flexible or tangling components (cables, springs) that complicate handling",
      "Fastener count is minimized (snap-fits preferred over screws)",
      "Part symmetry allows insertion without orientation errors",
      "Assembly sequence avoids obstructed access to fasteners",
      "Adequate clearance for tools and fingers during assembly",
      "Subassemblies can be tested independently before final assembly"
    ]
  },
  {
    "id": "mfg",
    "name": "Manufacturing Review",
    "description": "Evaluate part design for manufacturability",
    "items": [
      "Wall thickness is uniform and meets minimum for chosen process",
      "Draft angles are sufficient for mold release (1-3 degrees minimum)",
      "Undercuts are eliminated or can be formed with simple side actions",
      "Corner radii are adequate to prevent stress concentration",
      "Tolerances are achievable with the intended manufacturing process",
      "Material selection is compatible with the manufacturing method",
      "Surface finish requirements are specified and achievable",
      "Part can be fixtured/held securely during machining operations"
    ]
  },
  {
    "id": "tolerance",
    "name": "Tolerance & Fit Review",
    "description": "Review dimensional tolerances and mating features",
    "items": [
      "Critical dimensions have explicit tolerances specified",
      "GD&T callouts use appropriate feature control frames",
      "Datum features are accessible for inspection",
      "Stack-up analysis completed for mating assemblies",
      "Fit types (clearance/transition/interference) are appropriate",
      "Thermal expansion has been considered for mating parts",
      "Surface roughness is specified for mating surfaces"
    ]
  }
]
```

### Storage format: `server/data/models/{model_id}/reviews.json`
```json
{
  "next_rev_id": 3,
  "next_dr_id": 2,
  "tickets": [ ... ],
  "design_reviews": [ ... ]
}
```

## Risk & Clash Analysis

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Right-click conflicts with OrbitControls pan** | Medium | OrbitControls uses right-click for pan. Intercept `contextmenu` on the `<group>` with `stopPropagation()` before OrbitControls gets it. Fallback: add "Pin mode" toggle that disables OrbitControls right-click. |
| **drei `<Html>` cards + OrbitControls** | Low | DOM overlays sit above canvas; mouse events won't trigger OrbitControls. Mitigate many-card blocking by only expanding one card at a time. |
| **Camera fly-to vs OrbitControls** | Low | Temporarily disable OrbitControls during ~500ms lerp animation. |

## Tech Stack Notes

| Concern | Assessment |
|---|---|
| **drei `<Html>` performance** | Fine for <50 pins. Would need instanced sprites for 50+. |
| **No new npm deps** | Uses existing three, @react-three/fiber, @react-three/drei. |
| **No new Python deps** | JSON read/write + Pydantic (already in FastAPI). |
| **Leader lines** | drei `<Line>` component from ticket position to offset. Dashed style. |
