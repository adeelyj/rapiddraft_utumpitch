type ToolbarProps = {
  busyAction?: string;
  logMessage?: string;
};

const Toolbar = ({
  busyAction,
  logMessage,
}: ToolbarProps) => {
  return (
    <header className="toolbar">
      <div className="toolbar__actions">
        {logMessage && <span className="toolbar__log">{logMessage}</span>}
        {busyAction && <span className="toolbar__busy-chip">Working: {busyAction}</span>}
        <div className="toolbar__logo" aria-label="RapidDraft branding">
          <img src="/rd_logo.png" alt="RapidDraft" className="toolbar__brand-image toolbar__brand-image--logo" />
        </div>
      </div>
    </header>
  );
};

export default Toolbar;
