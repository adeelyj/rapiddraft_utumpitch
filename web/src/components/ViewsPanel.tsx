type ViewsPanelProps = {
  views: Record<string, string>;
  onSelectThumbnail?: (name: string, src: string, metadataUrl?: string) => void;
  shapeViews?: Record<string, string>;
  occViews?: Record<string, string>;
  midViews?: Record<string, string>;
  isometricShape2DViews?: Record<string, string>;
  isometricMatplotlibViews?: Record<string, string>;
  viewMetadata?: Record<string, string>;
  shapeViewMetadata?: Record<string, string>;
  isometricShape2DMetadata?: Record<string, string>;
  isometricMatplotlibMetadata?: Record<string, string>;
  expectedViews?: string[];
  shapeExpectedViews?: string[];
  occExpectedViews?: string[];
  midExpectedViews?: string[];
  isometricShape2DExpectedViews?: string[];
  isometricMatplotlibExpectedViews?: string[];
  onGenerateViews?: () => Promise<void>;
  onGenerateShape2DViews?: () => Promise<void>;
  onGenerateOccViews?: () => Promise<void>;
  onGenerateMidViews?: () => Promise<void>;
  onGenerateIsometricViews?: () => Promise<void>;
  canGenerate?: boolean;
  busyAction?: string;
};

const DEFAULT_VIEWS = ["top", "left", "right", "bottom"];
const DEFAULT_SHAPE_VIEWS = ["top", "side", "bottom"];
const DEFAULT_OCC_VIEWS = ["x", "y", "z"];
const DEFAULT_MID_VIEWS = ["mid_x", "mid_y", "mid_z"];
const DEFAULT_ISO_SHAPE2D_VIEWS = ["isometric_shape2d"];
const DEFAULT_ISO_MATPLOTLIB_VIEWS = ["isometric_matplotlib"];

const ViewCard = ({ label, src, onClick }: { label: string; src?: string; onClick?: () => void }) => {
  return (
    <div className="view-card" onClick={onClick} style={{ cursor: onClick && src ? "pointer" : "default" }}>
      <div className="view-card__header">{label.toUpperCase()}</div>
      {src ? (
        <img src={src} alt={`${label} projection`} className="view-card__image" />
      ) : (
        <div className="view-card__placeholder">Awaiting generation</div>
      )}
    </div>
  );
};

const ViewsPanel = ({
  views,
  onSelectThumbnail,
  shapeViews = {},
  occViews = {},
  midViews = {},
  isometricShape2DViews = {},
  isometricMatplotlibViews = {},
  viewMetadata = {},
  shapeViewMetadata = {},
  isometricShape2DMetadata = {},
  isometricMatplotlibMetadata = {},
  expectedViews = DEFAULT_VIEWS,
  shapeExpectedViews = DEFAULT_SHAPE_VIEWS,
  occExpectedViews = DEFAULT_OCC_VIEWS,
  midExpectedViews = DEFAULT_MID_VIEWS,
  isometricShape2DExpectedViews = DEFAULT_ISO_SHAPE2D_VIEWS,
  isometricMatplotlibExpectedViews = DEFAULT_ISO_MATPLOTLIB_VIEWS,
  onGenerateViews,
  onGenerateShape2DViews,
  onGenerateOccViews,
  onGenerateMidViews,
  onGenerateIsometricViews,
  canGenerate = false,
  busyAction,
}: ViewsPanelProps) => {
  const isBusy = Boolean(busyAction);
  const disableGenerate = !canGenerate || isBusy;

  return (
    <aside className="views-panel">
      <button className="views-panel__section-button" onClick={onGenerateIsometricViews} disabled={disableGenerate}>
        Get Isometric Views
      </button>
      <div className="views-panel__grid">
        {isometricShape2DExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label={isometricShape2DMetadata[name] ? `${name} (with md)` : `${name}`}
            src={isometricShape2DViews[name]}
            onClick={() =>
              onSelectThumbnail &&
              isometricShape2DViews[name] &&
              onSelectThumbnail(name, isometricShape2DViews[name], isometricShape2DMetadata[name])
            }
          />
        ))}
        {isometricMatplotlibExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label={isometricMatplotlibMetadata[name] ? `${name} (with md)` : `${name}`}
            src={isometricMatplotlibViews[name]}
            onClick={() =>
              onSelectThumbnail &&
              isometricMatplotlibViews[name] &&
              onSelectThumbnail(name, isometricMatplotlibViews[name], isometricMatplotlibMetadata[name])
            }
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateViews} disabled={disableGenerate}>
        Get Mesh Views
      </button>
      <div className="views-panel__grid">
        {expectedViews.map((name) => (
          <ViewCard
            key={name}
            label={viewMetadata[name] ? `${name} (with md)` : name}
            src={views[name]}
            onClick={() => onSelectThumbnail && views[name] && onSelectThumbnail(name, views[name], viewMetadata[name])}
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateShape2DViews} disabled={disableGenerate}>
        Get Shape2D Views
      </button>
      <div className="views-panel__grid">
        {shapeExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label={shapeViewMetadata[name] ? `${name} (with md)` : name}
            src={shapeViews[name]}
            onClick={() => onSelectThumbnail && shapeViews[name] && onSelectThumbnail(name, shapeViews[name], shapeViewMetadata[name])}
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateOccViews} disabled={disableGenerate}>
        Get OCC Views
      </button>
      <div className="views-panel__grid">
        {occExpectedViews.map((name) => (
          <ViewCard key={name} label={name} src={occViews[name]} onClick={() => onSelectThumbnail && occViews[name] && onSelectThumbnail(name, occViews[name])} />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateMidViews} disabled={disableGenerate}>
        Get Mid Views
      </button>
      <div className="views-panel__grid">
        {midExpectedViews.map((name) => (
          <ViewCard key={name} label={name} src={midViews[name]} onClick={() => onSelectThumbnail && midViews[name] && onSelectThumbnail(name, midViews[name])} />
        ))}
      </div>
    </aside>
  );
};

export default ViewsPanel;
