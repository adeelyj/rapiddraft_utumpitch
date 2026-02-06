import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { PinPosition, TicketPriority, TicketType } from "../types/review";

export type CreateTicketPayload = {
  title: string;
  description: string;
  type: TicketType;
  priority: TicketPriority;
  author: string;
  tag?: string;
  pin: PinPosition;
};

type CommentFormProps = {
  open: boolean;
  pendingPin: PinPosition | null;
  onSubmit: (payload: CreateTicketPayload) => void;
  onCancel: () => void;
};

const CommentForm = ({ open, pendingPin, onSubmit, onCancel }: CommentFormProps) => {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<TicketType>("comment");
  const [priority, setPriority] = useState<TicketPriority>("medium");
  const [author, setAuthor] = useState("");
  const [tag, setTag] = useState("");

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDescription("");
    setType("comment");
    setPriority("medium");
    setAuthor("");
    setTag("");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!pendingPin) return;
    onSubmit({
      title,
      description,
      type,
      priority,
      author,
      tag: tag.trim() || undefined,
      pin: pendingPin,
    });
  };

  const canSubmit = Boolean(title.trim()) && Boolean(author.trim()) && Boolean(pendingPin);

  return (
    <div className="comment-form__backdrop">
      <div className="comment-form" role="dialog" aria-modal="true">
        <div className="comment-form__header">
          <h3>Add Comment</h3>
          <button className="comment-form__close" onClick={onCancel} aria-label="Close form">
            ×
          </button>
        </div>
        <form className="comment-form__body" onSubmit={handleSubmit}>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
          </label>
          <div className="comment-form__row">
            <label>
              Type
              <select value={type} onChange={(e) => setType(e.target.value as TicketType)}>
                <option value="issue">Issue</option>
                <option value="idea">Idea</option>
                <option value="comment">Comment</option>
              </select>
            </label>
            <label>
              Priority
              <select value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
          </div>
          <label>
            Author
            <input value={author} onChange={(e) => setAuthor(e.target.value)} required />
          </label>
          <label>
            Tag (optional)
            <input value={tag} onChange={(e) => setTag(e.target.value)} />
          </label>
          <div className="comment-form__actions">
            <button type="button" onClick={onCancel} className="comment-form__cancel">
              Cancel
            </button>
            <button type="submit" className="comment-form__submit" disabled={!canSubmit}>
              Create Ticket
            </button>
          </div>
        </form>
        {!pendingPin && <p className="comment-form__warning">Right-click on the model to place a pin first.</p>}
      </div>
    </div>
  );
};

export default CommentForm;
