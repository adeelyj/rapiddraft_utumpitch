from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ReviewStore:
    def __init__(self, root: Path, templates_path: Path) -> None:
        self.root = root
        self.templates_path = templates_path

    def _model_dir(self, model_id: str) -> Path:
        return self.root / model_id

    def _reviews_path(self, model_id: str) -> Path:
        return self._model_dir(model_id) / "reviews.json"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_store(self, model_id: str) -> Path:
        model_dir = self._model_dir(model_id)
        model_dir.mkdir(parents=True, exist_ok=True)
        reviews_path = self._reviews_path(model_id)
        if not reviews_path.exists():
            payload = {
                "next_rev_id": 1,
                "next_dr_id": 1,
                "tickets": [],
                "design_reviews": [],
            }
            reviews_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return reviews_path

    def _read_store(self, model_id: str) -> Dict[str, Any]:
        reviews_path = self._ensure_store(model_id)
        return json.loads(reviews_path.read_text(encoding="utf-8"))

    def _write_store(self, model_id: str, payload: Dict[str, Any]) -> None:
        reviews_path = self._ensure_store(model_id)
        reviews_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_templates(self) -> List[Dict[str, Any]]:
        if not self.templates_path.exists():
            return []
        return json.loads(self.templates_path.read_text(encoding="utf-8"))

    def _get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        templates = self.list_templates()
        for template in templates:
            if template.get("id") == template_id:
                return template
        return None

    def list_tickets(self, model_id: str) -> List[Dict[str, Any]]:
        payload = self._read_store(model_id)
        return payload.get("tickets", [])

    def get_ticket(self, model_id: str, ticket_id: str) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for ticket in payload.get("tickets", []):
            if ticket.get("id") == ticket_id:
                return ticket
        return None

    def create_ticket(self, model_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._read_store(model_id)
        next_id = int(payload.get("next_rev_id", 1))
        ticket_id = f"REV-{next_id:03d}"
        payload["next_rev_id"] = next_id + 1
        timestamp = self._now_iso()
        ticket = {
            "id": ticket_id,
            "kind": "comment",
            "modelId": model_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "type": data.get("type", "comment"),
            "priority": data.get("priority", "medium"),
            "status": data.get("status", "open"),
            "author": data.get("author", ""),
            "tag": data.get("tag", ""),
            "pin": data.get("pin", {}),
            "replies": [],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        payload.setdefault("tickets", []).append(ticket)
        self._write_store(model_id, payload)
        return ticket

    def update_ticket(self, model_id: str, ticket_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for ticket in payload.get("tickets", []):
            if ticket.get("id") == ticket_id:
                for key, value in fields.items():
                    ticket[key] = value
                ticket["updatedAt"] = self._now_iso()
                self._write_store(model_id, payload)
                return ticket
        return None

    def delete_ticket(self, model_id: str, ticket_id: str) -> bool:
        payload = self._read_store(model_id)
        tickets = payload.get("tickets", [])
        for index, ticket in enumerate(tickets):
            if ticket.get("id") == ticket_id:
                tickets.pop(index)
                self._write_store(model_id, payload)
                return True
        return False

    def add_ticket_reply(self, model_id: str, ticket_id: str, reply_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for ticket in payload.get("tickets", []):
            if ticket.get("id") == ticket_id:
                reply_id = f"r{uuid4().hex[:8]}"
                reply = {
                    "id": reply_id,
                    "author": reply_data.get("author", ""),
                    "text": reply_data.get("text", ""),
                    "createdAt": self._now_iso(),
                }
                replies = ticket.setdefault("replies", [])
                replies.append(reply)
                ticket["updatedAt"] = self._now_iso()
                self._write_store(model_id, payload)
                return reply
        return None

    def delete_ticket_reply(self, model_id: str, ticket_id: str, reply_id: str) -> bool:
        payload = self._read_store(model_id)
        for ticket in payload.get("tickets", []):
            if ticket.get("id") == ticket_id:
                replies = ticket.get("replies", [])
                for index, reply in enumerate(replies):
                    if reply.get("id") == reply_id:
                        replies.pop(index)
                        ticket["updatedAt"] = self._now_iso()
                        self._write_store(model_id, payload)
                        return True
                return False
        return False

    def list_reviews(self, model_id: str) -> List[Dict[str, Any]]:
        payload = self._read_store(model_id)
        return payload.get("design_reviews", [])

    def get_review(self, model_id: str, review_id: str) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for review in payload.get("design_reviews", []):
            if review.get("id") == review_id:
                return review
        return None

    def create_review(self, model_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        template_id = data.get("template_id") or data.get("templateId")
        if not template_id:
            return None
        template = self._get_template(template_id)
        if not template:
            return None

        payload = self._read_store(model_id)
        next_id = int(payload.get("next_dr_id", 1))
        review_id = f"DR-{next_id:03d}"
        payload["next_dr_id"] = next_id + 1
        timestamp = self._now_iso()

        items = []
        for idx, text in enumerate(template.get("items", []), start=1):
            items.append({"id": f"item-{idx}", "text": text, "status": "pending", "note": ""})

        title = data.get("title") or template.get("name", "")
        review = {
            "id": review_id,
            "kind": "design_review",
            "modelId": model_id,
            "templateId": template.get("id"),
            "templateName": template.get("name", ""),
            "title": title,
            "author": data.get("author", ""),
            "status": data.get("status", "in_progress"),
            "pin": data.get("pin", {}),
            "checklist": items,
            "replies": [],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        payload.setdefault("design_reviews", []).append(review)
        self._write_store(model_id, payload)
        return review

    def update_review(self, model_id: str, review_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for review in payload.get("design_reviews", []):
            if review.get("id") == review_id:
                for key, value in fields.items():
                    review[key] = value
                review["updatedAt"] = self._now_iso()
                self._write_store(model_id, payload)
                return review
        return None

    def delete_review(self, model_id: str, review_id: str) -> bool:
        payload = self._read_store(model_id)
        reviews = payload.get("design_reviews", [])
        for index, review in enumerate(reviews):
            if review.get("id") == review_id:
                reviews.pop(index)
                self._write_store(model_id, payload)
                return True
        return False

    def update_checklist_item(
        self, model_id: str, review_id: str, item_id: str, fields: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for review in payload.get("design_reviews", []):
            if review.get("id") != review_id:
                continue
            for item in review.get("checklist", []):
                if item.get("id") == item_id:
                    for key, value in fields.items():
                        item[key] = value
                    review["updatedAt"] = self._now_iso()
                    self._write_store(model_id, payload)
                    return item
        return None

    def add_review_reply(self, model_id: str, review_id: str, reply_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = self._read_store(model_id)
        for review in payload.get("design_reviews", []):
            if review.get("id") == review_id:
                reply_id = f"r{uuid4().hex[:8]}"
                reply = {
                    "id": reply_id,
                    "author": reply_data.get("author", ""),
                    "text": reply_data.get("text", ""),
                    "createdAt": self._now_iso(),
                }
                replies = review.setdefault("replies", [])
                replies.append(reply)
                review["updatedAt"] = self._now_iso()
                self._write_store(model_id, payload)
                return reply
        return None

    def delete_review_reply(self, model_id: str, review_id: str, reply_id: str) -> bool:
        payload = self._read_store(model_id)
        for review in payload.get("design_reviews", []):
            if review.get("id") == review_id:
                replies = review.get("replies", [])
                for index, reply in enumerate(replies):
                    if reply.get("id") == reply_id:
                        replies.pop(index)
                        review["updatedAt"] = self._now_iso()
                        self._write_store(model_id, payload)
                        return True
                return False
        return False
