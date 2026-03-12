import { MODE_DEFINITIONS, type PlaceholderMode } from "../modes";

type ModePlaceholderProps = {
  mode: PlaceholderMode;
  onBack: () => void;
  onEnterExpert: () => void;
};

const MODE_HINTS: Record<PlaceholderMode, string[]> = {
  batch: ["Folder imports", "Queued jobs", "Aggregated reports"],
  drawing: ["Sheet uploads", "Annotation review", "Standards checks"],
  collaboration: ["Shared sessions", "Assignments", "Live follow-through"],
};

const ModePlaceholder = ({ mode, onBack, onEnterExpert }: ModePlaceholderProps) => {
  const definition = MODE_DEFINITIONS[mode];

  return (
    <div className={`mode-screen mode-placeholder mode-placeholder--${mode}`}>
      <header className="mode-placeholder__header">
        <div className="mode-brand" aria-label="RapidDraft">
          <span className="mode-brand__mark" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <path d="M9 9h6M9 13h4" />
            </svg>
          </span>
          <span className="mode-brand__text">RapidDraft</span>
        </div>
        <button type="button" className="mode-button mode-button--secondary" onClick={onBack}>
          Back to modes
        </button>
      </header>

      <main className="mode-placeholder__main">
        <section className="mode-placeholder__panel">
          <p className="mode-placeholder__eyebrow">{definition.label}</p>
          <h1>{definition.placeholderTitle}</h1>
          <p className="mode-placeholder__body">{definition.placeholderBody}</p>

          <div className="mode-placeholder__status">
            <span className="mode-placeholder__status-label">Current state</span>
            <strong>Front-end shell ready</strong>
            <span>{definition.placeholderNote}</span>
          </div>

          <div className="mode-placeholder__actions">
            <button type="button" className="mode-button" onClick={onEnterExpert}>
              Open Expert Mode
            </button>
            <button type="button" className="mode-button mode-button--secondary" onClick={onBack}>
              Choose another mode
            </button>
          </div>
        </section>

        <aside className="mode-placeholder__aside" aria-label={`${definition.label} context`}>
          <div className="mode-placeholder__info-card">
            <span className="mode-placeholder__info-label">Planned focus</span>
            <p>{definition.description}</p>
          </div>
          <div className="mode-placeholder__hint-strip">
            {MODE_HINTS[mode].map((hint) => (
              <span key={hint} className="mode-placeholder__hint">
                {hint}
              </span>
            ))}
          </div>
        </aside>
      </main>
    </div>
  );
};

export default ModePlaceholder;
