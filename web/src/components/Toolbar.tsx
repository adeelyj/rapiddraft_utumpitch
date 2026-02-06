import { useRef } from "react";
import clsx from "clsx";

type ToolbarProps = {
  onImport: (file: File) => Promise<void>;
  onExportViews: () => Promise<void>;
  onOpenCompare: () => void;
  onOpenCollaborate: () => void;
  canExport: boolean;
  busyAction?: string;
  statusMessage?: string;
  logMessage?: string;
};

const Toolbar = ({
  onImport,
  onExportViews,
  onOpenCompare,
  onOpenCollaborate,
  canExport,
  busyAction,
  statusMessage,
  logMessage,
}: ToolbarProps) => {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleImportClick = () => {
    inputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await onImport(file);
    event.target.value = "";
  };

  const busy = Boolean(busyAction);

  return (
    <header className="toolbar">
      <div className="toolbar__brand">
        <span className="toolbar__status">{statusMessage ?? "Ready"}</span>
      </div>
      <div className="toolbar__center">
        <button className="toolbar__button" onClick={onOpenCompare} disabled={busy}>
          Model compare
        </button>
        <button className="toolbar__button" onClick={onOpenCollaborate} disabled={busy}>
          Collaborate
        </button>
      </div>
      <div className="toolbar__actions">
        <input
          type="file"
          ref={inputRef}
          accept=".step,.stp"
          className="sr-only"
          onChange={handleFileChange}
        />
        {logMessage && <span className="toolbar__log">{logMessage}</span>}
        <button className="toolbar__button" onClick={handleImportClick} disabled={busy}>
          Import STEP
        </button>
        <button
          className={clsx("toolbar__button", !canExport && "toolbar__button--disabled")}
          onClick={onExportViews}
          disabled={!canExport || busy}
        >
          Export Views
        </button>
        {busy && <span className="toolbar__busy-chip">Working: {busyAction}</span>}
      </div>
    </header>
  );
};

export default Toolbar;
