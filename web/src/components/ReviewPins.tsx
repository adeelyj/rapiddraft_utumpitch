import { Html, Line } from "@react-three/drei";
import type { DesignReviewSession, PinnedItem } from "../types/review";

type ReviewPinsProps = {
  items: PinnedItem[];
  selectedItemId: string | null;
  onSelect: (id: string) => void;
  showCards?: boolean;
};

const getPinClass = (item: PinnedItem) => {
  if (item.kind === "comment") {
    return `review-pin--${item.type}`;
  }
  const review = item as DesignReviewSession;
  return `review-pin--review review-pin--status-${review.status}`;
};

const getLineColor = (item: PinnedItem) => {
  if (item.kind === "comment") {
    if (item.type === "issue") return "#e4573e";
    if (item.type === "idea") return "#f6a94a";
    return "#3f7dd7";
  }
  const status = (item as DesignReviewSession).status;
  if (status === "passed") return "#4caf6a";
  if (status === "failed") return "#e4573e";
  if (status === "cancelled") return "#8c96a8";
  return "#3f7dd7";
};

const ReviewPins = ({ items, selectedItemId, onSelect, showCards = true }: ReviewPinsProps) => {
  return (
    <>
      {items.map((item) => {
        const selected = item.id === selectedItemId;
        const lineOffset = [
          item.pin.position[0] + item.pin.normal[0] * 0.3,
          item.pin.position[1] + item.pin.normal[1] * 0.3,
          item.pin.position[2] + item.pin.normal[2] * 0.3,
        ] as [number, number, number];
        return (
          <group key={item.id}>
            {showCards && selected && (
              <Line
                points={[item.pin.position, lineOffset]}
                color={getLineColor(item)}
                dashed
                dashScale={50}
                dashSize={0.02}
                gapSize={0.02}
              />
            )}
            <Html position={item.pin.position} center>
              <div className={`review-pin ${getPinClass(item)} ${selected ? "review-pin--selected" : ""}`}>
                <button className="review-pin__dot" onClick={() => onSelect(item.id)} aria-label={item.title} />
                {showCards && selected && item.kind === "comment" && (
                  <div className="review-pin-card" onClick={() => onSelect(item.id)}>
                    <div className="review-pin-card__title">{item.title}</div>
                    <div className="review-pin-card__meta">
                      <span className={`chip chip--${item.type}`}>{item.type}</span>
                      <span className="review-pin-card__author">{item.author}</span>
                    </div>
                    <div className="review-pin-card__footer">
                      <span>{item.id}</span>
                      <span>{item.replies?.length ?? 0} replies</span>
                    </div>
                  </div>
                )}
                {showCards && selected && item.kind === "design_review" && (
                  <div className="review-pin-card" onClick={() => onSelect(item.id)}>
                    <div className="review-pin-card__title">{item.title}</div>
                    <div className="review-pin-card__meta">
                      <span className="chip chip--review">Review</span>
                      <span className="review-pin-card__author">{item.author}</span>
                    </div>
                    <div className="review-pin-card__footer">
                      <span>{item.id}</span>
                      <span>
                        {item.checklist.filter((i) => i.status !== "pending").length}/{item.checklist.length} reviewed
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </Html>
          </group>
        );
      })}
    </>
  );
};

export default ReviewPins;
