import { type ClipboardEvent, useEffect, useMemo } from "react";

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
  visionViewSelection?: Record<string, boolean>;
  onVisionViewCatalogChange?: (catalog: VisionSelectableView[]) => void;
  onToggleVisionViewSelection?: (source: VisionSelectableView, selected: boolean) => void;
  visionPastedScreenshots?: VisionPastedScreenshotSlot[];
  onAddVisionPastedScreenshotSlot?: () => void;
  onUpdateVisionPastedScreenshot?: (slotId: string, dataUrl: string, label: string) => void;
  onToggleVisionPastedScreenshot?: (slotId: string, selected: boolean) => void;
  onRemoveVisionPastedScreenshot?: (slotId: string) => void;
};

export type VisionSelectableView = {
  id: string;
  label: string;
  src: string;
};

export type VisionPastedScreenshotSlot = {
  id: string;
  label: string;
  dataUrl: string | null;
  selected: boolean;
};

const DEFAULT_VIEWS = ["top", "left", "right", "bottom"];
const DEFAULT_SHAPE_VIEWS = ["top", "side", "bottom"];
const DEFAULT_OCC_VIEWS = ["x", "y", "z"];
const DEFAULT_MID_VIEWS = ["mid_x", "mid_y", "mid_z"];
const DEFAULT_ISO_SHAPE2D_VIEWS = ["isometric_shape2d"];
const DEFAULT_ISO_MATPLOTLIB_VIEWS = ["isometric_matplotlib"];

const normalizeViewName = (name: string): string => name.replace(/_/g, " ").toUpperCase();

const toVisionSource = (params: {
  groupId: string;
  groupLabel: string;
  name: string;
  src?: string;
}): VisionSelectableView | null => {
  const { groupId, groupLabel, name, src } = params;
  if (!src) return null;
  return {
    id: `${groupId}:${name}`,
    label: `${groupLabel} ${normalizeViewName(name)}`,
    src,
  };
};

const appendCatalogGroup = (
  catalog: VisionSelectableView[],
  params: {
    groupId: string;
    groupLabel: string;
    sourceMap: Record<string, string>;
    preferredOrder: string[];
  },
) => {
  const { groupId, groupLabel, sourceMap, preferredOrder } = params;
  const orderedNames = preferredOrder.filter((name) => Boolean(sourceMap[name]));
  Object.keys(sourceMap).forEach((name) => {
    if (sourceMap[name] && !orderedNames.includes(name)) {
      orderedNames.push(name);
    }
  });
  orderedNames.forEach((name) => {
    const source = toVisionSource({
      groupId,
      groupLabel,
      name,
      src: sourceMap[name],
    });
    if (source) catalog.push(source);
  });
};

const ViewCard = ({
  label,
  src,
  onClick,
  visionSource,
  visionSelected = false,
  onToggleVisionSelection,
}: {
  label: string;
  src?: string;
  onClick?: () => void;
  visionSource?: VisionSelectableView | null;
  visionSelected?: boolean;
  onToggleVisionSelection?: (source: VisionSelectableView, selected: boolean) => void;
}) => {
  return (
    <div className="view-card" onClick={onClick} style={{ cursor: onClick && src ? "pointer" : "default" }}>
      <div className="view-card__header-row">
        <div className="view-card__header">{label.toUpperCase()}</div>
        {visionSource ? (
          <label
            className="view-card__vision-toggle"
            onClick={(event) => {
              event.stopPropagation();
            }}
          >
            <input
              type="checkbox"
              checked={visionSelected}
              onChange={(event) => {
                event.stopPropagation();
                onToggleVisionSelection?.(visionSource, event.target.checked);
              }}
            />
            <span>V</span>
          </label>
        ) : null}
      </div>
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
  visionViewSelection = {},
  onVisionViewCatalogChange,
  onToggleVisionViewSelection,
  visionPastedScreenshots = [],
  onAddVisionPastedScreenshotSlot,
  onUpdateVisionPastedScreenshot,
  onToggleVisionPastedScreenshot,
  onRemoveVisionPastedScreenshot,
}: ViewsPanelProps) => {
  const isBusy = Boolean(busyAction);
  const disableGenerate = !canGenerate || isBusy;

  const visionViewCatalog = useMemo(() => {
    const catalog: VisionSelectableView[] = [];
    appendCatalogGroup(catalog, {
      groupId: "iso_shape2d",
      groupLabel: "Isometric Shape2D",
      sourceMap: isometricShape2DViews,
      preferredOrder: isometricShape2DExpectedViews,
    });
    appendCatalogGroup(catalog, {
      groupId: "iso_matplotlib",
      groupLabel: "Isometric Matplotlib",
      sourceMap: isometricMatplotlibViews,
      preferredOrder: isometricMatplotlibExpectedViews,
    });
    appendCatalogGroup(catalog, {
      groupId: "mesh",
      groupLabel: "Mesh",
      sourceMap: views,
      preferredOrder: expectedViews,
    });
    appendCatalogGroup(catalog, {
      groupId: "shape2d",
      groupLabel: "Shape2D",
      sourceMap: shapeViews,
      preferredOrder: shapeExpectedViews,
    });
    appendCatalogGroup(catalog, {
      groupId: "occ",
      groupLabel: "OCC",
      sourceMap: occViews,
      preferredOrder: occExpectedViews,
    });
    appendCatalogGroup(catalog, {
      groupId: "mid",
      groupLabel: "Mid",
      sourceMap: midViews,
      preferredOrder: midExpectedViews,
    });
    return catalog;
  }, [
    expectedViews,
    isometricMatplotlibExpectedViews,
    isometricMatplotlibViews,
    isometricShape2DExpectedViews,
    isometricShape2DViews,
    midExpectedViews,
    midViews,
    occExpectedViews,
    occViews,
    shapeExpectedViews,
    shapeViews,
    views,
  ]);

  useEffect(() => {
    onVisionViewCatalogChange?.(visionViewCatalog);
  }, [onVisionViewCatalogChange, visionViewCatalog]);

  const findVisionSource = (groupId: string, groupLabel: string, name: string, src?: string) =>
    toVisionSource({ groupId, groupLabel, name, src });

  const handlePasteScreenshot = (
    slotId: string,
    fallbackLabel: string,
    event: ClipboardEvent<HTMLTextAreaElement>,
  ) => {
    const items = Array.from(event.clipboardData?.items ?? []);
    const imageItem = items.find((item) => item.type.startsWith("image/"));
    if (!imageItem || !onUpdateVisionPastedScreenshot) return;
    const file = imageItem.getAsFile();
    if (!file) return;

    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") return;
      onUpdateVisionPastedScreenshot(slotId, result, file.name || fallbackLabel);
    };
    reader.readAsDataURL(file);
  };

  return (
    <aside className="views-panel">
      <h2>Views</h2>
      <div className="views-panel__vision-capture">
        <div className="views-panel__vision-capture-header">
          <h3>Vision screenshots</h3>
          <button
            type="button"
            className="views-panel__add-shot"
            onClick={onAddVisionPastedScreenshotSlot}
            title="Add screenshot paste field"
          >
            +
          </button>
        </div>
        {visionPastedScreenshots.length ? (
          <div className="views-panel__vision-shot-list">
            {visionPastedScreenshots.map((slot, index) => (
              <div key={slot.id} className="view-card view-card--vision-shot">
                <div className="view-card__header-row">
                  <div className="view-card__header">{slot.label}</div>
                  <label className="view-card__vision-toggle">
                    <input
                      type="checkbox"
                      checked={Boolean(slot.selected)}
                      disabled={!slot.dataUrl}
                      onChange={(event) => onToggleVisionPastedScreenshot?.(slot.id, event.target.checked)}
                    />
                    <span>V</span>
                  </label>
                </div>
                {slot.dataUrl ? (
                  <img src={slot.dataUrl} alt={slot.label} className="view-card__image" />
                ) : (
                  <textarea
                    className="view-card__paste-input"
                    rows={3}
                    placeholder="Click and paste screenshot (Ctrl+V)"
                    onPaste={(event) => handlePasteScreenshot(slot.id, `Screenshot ${index + 1}`, event)}
                  />
                )}
                <button
                  type="button"
                  className="view-card__remove-btn"
                  onClick={() => onRemoveVisionPastedScreenshot?.(slot.id)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="views-panel__vision-hint">
            Use + to add a paste field, then press Ctrl+V inside it.
          </p>
        )}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateIsometricViews} disabled={disableGenerate}>
        Generate Isometric Views
      </button>
      <div className="views-panel__grid">
        {isometricShape2DExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label="shape 2d"
            src={isometricShape2DViews[name]}
            onClick={() =>
              onSelectThumbnail &&
              isometricShape2DViews[name] &&
              onSelectThumbnail(name, isometricShape2DViews[name], isometricShape2DMetadata[name])
            }
            visionSource={findVisionSource("iso_shape2d", "Isometric Shape2D", name, isometricShape2DViews[name])}
            visionSelected={Boolean(visionViewSelection[`iso_shape2d:${name}`])}
            onToggleVisionSelection={onToggleVisionViewSelection}
          />
        ))}
        {isometricMatplotlibExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label="mathplotlib"
            src={isometricMatplotlibViews[name]}
            onClick={() =>
              onSelectThumbnail &&
              isometricMatplotlibViews[name] &&
              onSelectThumbnail(name, isometricMatplotlibViews[name], isometricMatplotlibMetadata[name])
            }
            visionSource={findVisionSource("iso_matplotlib", "Isometric Matplotlib", name, isometricMatplotlibViews[name])}
            visionSelected={Boolean(visionViewSelection[`iso_matplotlib:${name}`])}
            onToggleVisionSelection={onToggleVisionViewSelection}
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateViews} disabled={disableGenerate}>
        Generate Mesh Views
      </button>
      <div className="views-panel__grid views-panel__grid--mesh">
        {expectedViews.map((name) => (
          <ViewCard
            key={name}
            label={viewMetadata[name] ? `${name} (with md)` : name}
            src={views[name]}
            onClick={() => onSelectThumbnail && views[name] && onSelectThumbnail(name, views[name], viewMetadata[name])}
            visionSource={findVisionSource("mesh", "Mesh", name, views[name])}
            visionSelected={Boolean(visionViewSelection[`mesh:${name}`])}
            onToggleVisionSelection={onToggleVisionViewSelection}
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateShape2DViews} disabled={disableGenerate}>
        Generate Shape2D Views
      </button>
      <div className="views-panel__grid">
        {shapeExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label={shapeViewMetadata[name] ? `${name} (with md)` : name}
            src={shapeViews[name]}
            onClick={() => onSelectThumbnail && shapeViews[name] && onSelectThumbnail(name, shapeViews[name], shapeViewMetadata[name])}
            visionSource={findVisionSource("shape2d", "Shape2D", name, shapeViews[name])}
            visionSelected={Boolean(visionViewSelection[`shape2d:${name}`])}
            onToggleVisionSelection={onToggleVisionViewSelection}
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateOccViews} disabled={disableGenerate}>
        Generate OCC Views
      </button>
      <div className="views-panel__grid">
        {occExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label={name}
            src={occViews[name]}
            onClick={() => onSelectThumbnail && occViews[name] && onSelectThumbnail(name, occViews[name])}
            visionSource={findVisionSource("occ", "OCC", name, occViews[name])}
            visionSelected={Boolean(visionViewSelection[`occ:${name}`])}
            onToggleVisionSelection={onToggleVisionViewSelection}
          />
        ))}
      </div>
      <button className="views-panel__section-button" onClick={onGenerateMidViews} disabled={disableGenerate}>
        Generate Mid Views
      </button>
      <div className="views-panel__grid">
        {midExpectedViews.map((name) => (
          <ViewCard
            key={name}
            label={name.replace(/_/g, " ")}
            src={midViews[name]}
            onClick={() => onSelectThumbnail && midViews[name] && onSelectThumbnail(name, midViews[name])}
            visionSource={findVisionSource("mid", "Mid", name, midViews[name])}
            visionSelected={Boolean(visionViewSelection[`mid:${name}`])}
            onToggleVisionSelection={onToggleVisionViewSelection}
          />
        ))}
      </div>
    </aside>
  );
};

export default ViewsPanel;
