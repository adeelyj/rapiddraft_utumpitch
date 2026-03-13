import { MODE_DEFINITIONS, MODE_ORDER, type LaunchMode } from "../modes";

type ModeLauncherProps = {
  onSelectMode: (mode: LaunchMode) => void;
};

const ModeGlyph = ({ mode }: { mode: LaunchMode }) => {
  switch (mode) {
    case "batch":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "drawing":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <path d="M8 13h8" />
          <path d="M8 17h5" />
        </svg>
      );
    case "collaboration":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case "design-review":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 5h16" />
          <path d="M4 12h10" />
          <path d="M4 19h8" />
          <path d="M17 14l2 2 4-4" />
          <circle cx="18" cy="16" r="5" />
        </svg>
      );
    case "expert":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      );
  }
};

const ModeLauncher = ({ onSelectMode }: ModeLauncherProps) => {
  return (
    <div className="mode-screen mode-launcher">
      <header className="mode-launcher__header">
        <div className="mode-brand" aria-label="RapidDraft branding">
          <img src="/rd_logo.png" alt="RapidDraft" className="mode-brand__image" />
        </div>
        <span className="mode-launcher__meta">Startup mode</span>
      </header>

      <main className="mode-launcher__main">
        <section className="mode-launcher__hero">
          <h1>What would you like to work on?</h1>
          <p className="mode-launcher__intro">
            Choose a mode to get started. You can switch between modes at any time from the sidebar.
          </p>
        </section>

        <section className="mode-launcher__grid" aria-label="Available startup modes">
          {MODE_ORDER.map((modeId) => {
            const mode = MODE_DEFINITIONS[modeId];
            return (
              <button
                key={mode.id}
                type="button"
                className={`mode-launcher__card mode-launcher__card--${mode.id}`}
                onClick={() => onSelectMode(mode.id)}
              >
                <div className={`mode-launcher__glyph mode-launcher__glyph--${mode.id}`}>
                  <ModeGlyph mode={mode.id} />
                </div>
                <div className="mode-launcher__card-copy">
                  <span className="mode-launcher__card-eyebrow">{mode.eyebrow}</span>
                  <h2>{mode.title}</h2>
                  <p>{mode.description}</p>
                </div>
                <div className="mode-launcher__card-footer">
                  <span className="mode-launcher__status">{mode.status}</span>
                  <span className="mode-launcher__arrow" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path d="M5 12h14" />
                      <path d="M13 6l6 6-6 6" />
                    </svg>
                  </span>
                </div>
              </button>
            );
          })}
        </section>
      </main>
    </div>
  );
};

export default ModeLauncher;
