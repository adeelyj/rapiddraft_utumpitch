# Design Review Feature - Implementation Plan

## Summary

Add a design review capability where users right-click on the 3D model surface to place comment pins, creating review tickets (like Jira) that are persisted per model and managed via a side panel.

---

## Scope (from CoLab PRD, adapted for this app)

**In scope:**
- Pin comments to specific 3D surface positions via right-click
- Review tickets with: title, description, priority, status, author
- Side panel to list/filter/edit/delete tickets
- Visual 3D pins anchored to model geometry
- Clicking a ticket highlights its pin on the model
- JSON-on-disk persistence (no database)

**Out of scope (for now):**
- Multi-user auth, @mentions, notifications
- PLM/PDM integration, sharing links
- Markup tools (arrows, GD&T symbols, feature control frames)
- Image attachments on comments
- Due dates, assignment to team members

---

## Data Model

### TypeScript (`web/src/types/review.ts` - new file)
```typescript
type TicketStatus = "open" | "in_progress" | "resolved" | "closed";
type TicketPriority = "low" | "medium" | "high" | "critical";

type ReviewTicket = {
  id: string;                          // Sequential: "REV-001", "REV-002", etc.
  modelId: string;
  title: string;
  description: string;
  priority: TicketPriority;
  status: TicketStatus;
  author: string;
  position: [number, number, number];  // world XYZ on mesh surface
  normal: [number, number, number];    // surface normal at hit point
  createdAt: string;                   // ISO 8601
  updatedAt: string;
};
```

### Python (`server/review_store.py` - new file)
```python
@dataclass
class ReviewTicket:
    id: str              # Sequential: "REV-001", "REV-002", etc.
    model_id: str
    title: str; description: str
    priority: str; status: str; author: str
    position: list; normal: list
    created_at: str; updated_at: str
```

### Ticket ID format: Sequential per model (`REV-001`, `REV-002`, ...)
- Backend tracks `next_id` counter in `reviews.json`
- Human-readable, easy to reference in conversation

### Storage: `server/data/models/{model_id}/reviews.json`
```json
{
  "next_id": 3,
  "tickets": [ { "id": "REV-001", ... }, { "id": "REV-002", ... } ]
}
```

---

## Backend Changes

### New file: `server/review_store.py`
- `ReviewStore` class (mirrors `ModelStore` pattern)
- Methods: `list_reviews()`, `get_review()`, `create_review()`, `update_review()`, `delete_review()`
- Reads/writes `reviews.json` inside each model's directory

### Modified: `server/main.py` (+5 endpoints)

| Method | Endpoint | Action |
|--------|----------|--------|
| GET | `/api/models/{id}/reviews` | List all tickets |
| POST | `/api/models/{id}/reviews` | Create ticket (JSON body) |
| GET | `/api/models/{id}/reviews/{ticket_id}` | Get single ticket |
| PATCH | `/api/models/{id}/reviews/{ticket_id}` | Update ticket fields |
| DELETE | `/api/models/{id}/reviews/{ticket_id}` | Delete ticket |

Add Pydantic `BaseModel` classes for request body validation (`CreateReviewRequest`, `UpdateReviewRequest`).

---

## Frontend Changes

### Component Hierarchy (additions in bold)

```
App.tsx  (add reviewMode state, ticket state, API functions)
  +-- Toolbar  (add "Review Mode" toggle button)
  +-- <main class="workspace">
        +-- ModelViewer  (add onContextMenu raycasting on GLTF group)
        |     +-- **ReviewPins** (drei <Html> pins inside Canvas)
        |     +-- **ReviewContextMenu** (fixed-position overlay on right-click)
        +-- Right sidebar with **tab toggle** ("Views" | "Reviews")
              +-- ViewsPanel        (shown when Views tab active)
              +-- **ReviewPanel**   (shown when Reviews tab active)
```

### New files (4):
| File | Purpose |
|------|---------|
| `web/src/types/review.ts` | TypeScript types |
| `web/src/components/ReviewPins.tsx` | 3D-anchored pin markers using drei `<Html>` |
| `web/src/components/ReviewContextMenu.tsx` | Right-click form overlay (title, description, priority, author) |
| `web/src/components/ReviewPanel.tsx` | Side panel: ticket list, filter by status, detail view, edit/delete |

### Modified files (4):
| File | Changes |
|------|---------|
| `App.tsx` | Add `reviewTickets`, `selectedTicketId`, `contextMenu`, `sidebarTab` state. Add fetch/create/update/delete async functions. Tab toggle for Views/Reviews sidebar. ~100 lines |
| `ModelViewer.tsx` | Wrap `<primitive>` in `<group onContextMenu>` for raycasting. Render `<ReviewPins>` inside Canvas. Render `<ReviewContextMenu>` as overlay. ~40 lines |
| `Toolbar.tsx` | No changes needed (tab toggle lives in sidebar header instead) |
| `styles.css` | Styles for pins, context menu, review panel, ticket cards, priority badges. ~120 lines |

---

## 3D Interaction: How It Works

1. **Right-click on model surface**: R3F automatically raycasts via the `onContextMenu` event on the `<group>` wrapping the GLTF scene. `event.intersections[0]` gives us `point` (world position) and `face.normal` (surface normal). Browser context menu is suppressed via `preventDefault()`.

2. **Context menu appears**: A fixed-position HTML form renders at (screenX, screenY) with fields for title, description, priority, author. Submit calls `POST /api/models/{id}/reviews`.

3. **Pin rendered**: Each ticket renders as a drei `<Html>` component positioned at the ticket's 3D coordinates. The `<Html>` component auto-projects to screen space as the camera moves. Pins are styled as colored circles (red=critical, orange=high, blue=medium, gray=low).

4. **Pin selection**: Clicking a pin or a ticket in the ReviewPanel sets `selectedTicketId`, which adds a highlight ring/pulse to the pin.

**Why right-click?** Doesn't conflict with OrbitControls (left-drag = rotate, scroll = zoom, middle = pan). No mode toggle needed to place comments.

**Why drei `<Html>` for pins?** Already in dependencies, auto-handles 3D-to-screen projection, allows standard DOM styling/hover/click. Performance is fine for <50 pins.

---

## Implementation Sequence

### Phase 1: Backend (testable with curl)
1. Create `server/review_store.py`
2. Add 5 endpoints to `server/main.py`

### Phase 2: Frontend wiring
3. Create `web/src/types/review.ts`
4. Add review state + API functions to `App.tsx`
5. Add "Views | Reviews" tab toggle to sidebar (wrapping ViewsPanel + ReviewPanel)

### Phase 3: 3D interaction
6. Add `onContextMenu` raycasting to `ModelViewer.tsx`
7. Create `ReviewContextMenu.tsx`
8. Create `ReviewPins.tsx`

### Phase 4: Review panel
9. Create `ReviewPanel.tsx`
10. Wire conditional rendering in `App.tsx`
11. Add all CSS to `styles.css`

### Phase 5: Polish
12. Auto-fetch tickets on model load / review mode enter
13. Click-outside-to-close for context menu

---

## Verification

1. **Backend**: Start backend, upload a STEP file, then use curl to create/list/get/update/delete review tickets
2. **3D Interaction**: Load a model, enable review mode, right-click on surface -> context menu should appear at click position
3. **Pin rendering**: After creating a ticket, a pin should appear at the clicked 3D position and track with camera movement
4. **Review Panel**: Toggle review mode -> panel shows tickets, clicking one highlights its pin
5. **Persistence**: Create tickets, refresh the page, re-load model -> tickets should still appear from the backend
6. **Status workflow**: Change ticket status from open -> in_progress -> resolved -> closed via the panel
