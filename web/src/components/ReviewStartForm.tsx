import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ChecklistTemplate, PinPosition } from "../types/review";

export type CreateReviewPayload = {
  template_id: string;
  title: string;
  author: string;
  pin: PinPosition;
};

type ReviewStartFormProps = {
  open: boolean;
  pendingPin: PinPosition | null;
  templates: ChecklistTemplate[];
  onSubmit: (payload: CreateReviewPayload) => void;
  onCancel: () => void;
};

const ReviewStartForm = ({ open, pendingPin, templates, onSubmit, onCancel }: ReviewStartFormProps) => {
  const [templateId, setTemplateId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");

  useEffect(() => {
    if (!open) return;
    const firstTemplate = templates[0];
    setTemplateId(firstTemplate?.id ?? "");
    setTitle(firstTemplate?.name ?? "");
    setAuthor("");
  }, [open, templates]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  useEffect(() => {
    const template = templates.find((t) => t.id === templateId);
    if (!template) return;
    setTitle((prev) => (prev.trim().length ? prev : template.name));
  }, [templateId, templates]);

  if (!open) return null;

  const selectedTemplate = templates.find((t) => t.id === templateId);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!pendingPin || !templateId) return;
    onSubmit({
      template_id: templateId,
      title,
      author,
      pin: pendingPin,
    });
  };

  const canSubmit = Boolean(templateId) && Boolean(author.trim()) && Boolean(pendingPin);

  return (
    <div className="comment-form__backdrop">
      <div className="review-start-form" role="dialog" aria-modal="true">
        <div className="comment-form__header">
          <h3>Start Design Review</h3>
          <button className="comment-form__close" onClick={onCancel} aria-label="Close form">
            ×
          </button>
        </div>
        <form className="comment-form__body" onSubmit={handleSubmit}>
          <label>
            Template
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Review title" />
          </label>
          <label>
            Author
            <input value={author} onChange={(e) => setAuthor(e.target.value)} required />
          </label>
          {selectedTemplate && (
            <div className="review-start-form__summary">
              <p>{selectedTemplate.description}</p>
              <span>{selectedTemplate.items.length} checklist items</span>
            </div>
          )}
          <div className="comment-form__actions">
            <button type="button" onClick={onCancel} className="comment-form__cancel">
              Cancel
            </button>
            <button type="submit" className="comment-form__submit" disabled={!canSubmit}>
              Create Review
            </button>
          </div>
        </form>
        {!pendingPin && <p className="comment-form__warning">Click on the model to place the review pin.</p>}
      </div>
    </div>
  );
};

export default ReviewStartForm;
