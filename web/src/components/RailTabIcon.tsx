import { useEffect, useState } from "react";

type RailTabIconProps = {
  iconId: string;
  fallbackGlyph: string;
};

const RAIL_ICON_ASSET_VERSION = "20260228-e";

const RailTabIcon = ({ iconId, fallbackGlyph }: RailTabIconProps) => {
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    setShowFallback(false);
  }, [iconId]);

  if (showFallback) {
    return (
      <span className="sidebar-rail__icon sidebar-rail__icon-fallback" aria-hidden="true">
        {fallbackGlyph}
      </span>
    );
  }

  return (
    <span className="sidebar-rail__icon" aria-hidden="true">
      <img
        className="sidebar-rail__icon-image"
        src={`/icons/rail/v1/${iconId}.png?v=${RAIL_ICON_ASSET_VERSION}`}
        alt=""
        loading="lazy"
        decoding="async"
        onError={() => setShowFallback(true)}
      />
    </span>
  );
};

export default RailTabIcon;
