type ToolbarProps = {
  brandPaneActive: boolean;
  onBrandToggle: () => void;
  busyAction?: string;
  statusMessage?: string;
  logMessage?: string;
};

const Toolbar = ({
  brandPaneActive,
  onBrandToggle,
  busyAction,
  statusMessage,
  logMessage,
}: ToolbarProps) => {
  return (
    <header className="toolbar">
      <div className="toolbar__brand">
        <button className="toolbar__brand-button" onClick={onBrandToggle} aria-label="Toggle left pane">
          <img
            src={brandPaneActive ? "/rd_icon.png" : "/rd_logo.png"}
            alt="RapidDraft"
            className={`toolbar__brand-image ${brandPaneActive ? "toolbar__brand-image--icon" : "toolbar__brand-image--logo"}`}
          />
        </button>
        <span className="toolbar__status">{statusMessage ?? "Ready"}</span>
      </div>
      <div className="toolbar__actions">
        {logMessage && <span className="toolbar__log">{logMessage}</span>}
        {busyAction && <span className="toolbar__busy-chip">Working: {busyAction}</span>}
      </div>
    </header>
  );
};

export default Toolbar;
