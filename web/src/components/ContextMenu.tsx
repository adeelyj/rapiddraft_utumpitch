import { useEffect, useRef } from "react";

type ContextMenuProps = {
  position: { x: number; y: number };
  onAddComment: () => void;
  onStartReview: () => void;
  onClose: () => void;
};

const ContextMenu = ({ position, onAddComment, onStartReview, onClose }: ContextMenuProps) => {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const handleClick = (event: MouseEvent) => {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey);
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="context-menu"
      style={{ left: `${position.x}px`, top: `${position.y}px` }}
      role="menu"
    >
      <button className="context-menu__button" onClick={onAddComment}>
        Add Comment
      </button>
      <button className="context-menu__button context-menu__button--disabled" onClick={onStartReview} disabled>
        Start Design Review
        <span className="context-menu__badge">Coming soon</span>
      </button>
    </div>
  );
};

export default ContextMenu;
