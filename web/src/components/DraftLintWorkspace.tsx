import { useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";
import type {
  DraftLintIssue,
  DraftLintReportResponse,
} from "../types/draftlint";

type DraftLintWorkspaceProps = {
  sourcePreviewUrl: string | null;
  sourceMimeType: string | null;
  sourceName?: string | null;
  report: DraftLintReportResponse | null;
  selectedIssueId: string | null;
  onSelectIssue: (issueId: string | null) => void;
  fallbackAnnotatedImageUrl?: string | null;
};

const MIN_ZOOM = 0.6;
const MAX_ZOOM = 2.4;
const ZOOM_STEP = 0.2;

const issueClass = (issue: DraftLintIssue): string => {
  if (issue.severity === "critical") return "draftlint-workspace__box draftlint-workspace__box--critical";
  if (issue.severity === "major") return "draftlint-workspace__box draftlint-workspace__box--major";
  return "draftlint-workspace__box draftlint-workspace__box--minor";
};

const DraftLintWorkspace = ({
  sourcePreviewUrl,
  sourceMimeType,
  sourceName,
  report,
  selectedIssueId,
  onSelectIssue,
  fallbackAnnotatedImageUrl = null,
}: DraftLintWorkspaceProps) => {
  const [showRegions, setShowRegions] = useState(true);
  const [showText, setShowText] = useState(false);
  const [showSymbols, setShowSymbols] = useState(false);
  const [showIssues, setShowIssues] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);

  const viewportRef = useRef<HTMLDivElement | null>(null);

  const renderUrl = useMemo(() => {
    if (sourcePreviewUrl) return sourcePreviewUrl;
    if (fallbackAnnotatedImageUrl) return fallbackAnnotatedImageUrl;
    return null;
  }, [fallbackAnnotatedImageUrl, sourcePreviewUrl]);

  const isImageSource = useMemo(() => {
    if (!sourceMimeType) return true;
    return sourceMimeType.startsWith("image/");
  }, [sourceMimeType]);

  const selectedIssue = useMemo(
    () => report?.issues.find((issue) => issue.issue_id === selectedIssueId) ?? null,
    [report?.issues, selectedIssueId],
  );

  const zoomPercent = Math.round(zoom * 100);

  useEffect(() => {
    if (!renderUrl) {
      setImageSize(null);
      setZoom(1);
    }
  }, [renderUrl]);

  useEffect(() => {
    if (!selectedIssue || !imageSize || !viewportRef.current || !isImageSource) return;
    const viewport = viewportRef.current;
    const centerX = ((selectedIssue.bbox.x1 + selectedIssue.bbox.x2) / 2) * imageSize.width * zoom;
    const centerY = ((selectedIssue.bbox.y1 + selectedIssue.bbox.y2) / 2) * imageSize.height * zoom;
    const nextLeft = Math.max(0, centerX - viewport.clientWidth / 2);
    const nextTop = Math.max(0, centerY - viewport.clientHeight / 2);
    viewport.scrollTo({ left: nextLeft, top: nextTop, behavior: "smooth" });
  }, [imageSize, isImageSource, selectedIssue, zoom]);

  const imageWrapStyle = useMemo(() => {
    if (!imageSize) return undefined;
    return {
      width: `${Math.max(320, imageSize.width * zoom)}px`,
      height: `${Math.max(220, imageSize.height * zoom)}px`,
    };
  }, [imageSize, zoom]);

  const handleImageLoaded = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    if (!image.naturalWidth || !image.naturalHeight) return;
    setImageSize({
      width: image.naturalWidth,
      height: image.naturalHeight,
    });
  };

  return (
    <section className="draftlint-workspace">
      <header className="draftlint-workspace__header">
        <div>
          <h2>DraftLint Workspace</h2>
          <p>
            {report
              ? `${sourceName ?? report.drawing_name} | ${report.summary.total_issues} issues`
              : "Upload a drawing and run DraftLint scan to see localized findings."}
          </p>
        </div>
        <div className="draftlint-workspace__toolbar">
          <div className="draftlint-workspace__toggles">
            <label>
              <input type="checkbox" checked={showRegions} onChange={(event) => setShowRegions(event.target.checked)} />
              Regions
            </label>
            <label>
              <input type="checkbox" checked={showText} onChange={(event) => setShowText(event.target.checked)} />
              OCR text
            </label>
            <label>
              <input type="checkbox" checked={showSymbols} onChange={(event) => setShowSymbols(event.target.checked)} />
              Symbols
            </label>
            <label>
              <input type="checkbox" checked={showIssues} onChange={(event) => setShowIssues(event.target.checked)} />
              Issues
            </label>
          </div>
          <div className="draftlint-workspace__zoom-controls">
            <button
              type="button"
              onClick={() => setZoom((current) => Math.max(MIN_ZOOM, Number((current - ZOOM_STEP).toFixed(2))))}
              disabled={zoom <= MIN_ZOOM}
            >
              -
            </button>
            <span>{zoomPercent}%</span>
            <button
              type="button"
              onClick={() => setZoom((current) => Math.min(MAX_ZOOM, Number((current + ZOOM_STEP).toFixed(2))))}
              disabled={zoom >= MAX_ZOOM}
            >
              +
            </button>
            <button type="button" onClick={() => setZoom(1)}>
              Fit
            </button>
          </div>
        </div>
      </header>

      <div className="draftlint-workspace__canvas" ref={viewportRef}>
        {!renderUrl ? (
          <div className="draftlint-workspace__empty">
            <strong>Ready for scan</strong>
            <span>Select a drawing file in DraftLint panel, then run scan.</span>
          </div>
        ) : !isImageSource ? (
          <iframe title="Draft drawing preview" src={renderUrl} className="draftlint-workspace__pdf" />
        ) : (
          <div className="draftlint-workspace__image-wrap" style={imageWrapStyle}>
            <img src={renderUrl} alt="Draft drawing input" className="draftlint-workspace__image" onLoad={handleImageLoaded} />

            {showRegions && report?.regions.map((region) => (
              <button
                key={region.region_id}
                type="button"
                className="draftlint-workspace__box draftlint-workspace__box--region"
                style={{
                  left: `${region.bbox.x1 * 100}%`,
                  top: `${region.bbox.y1 * 100}%`,
                  width: `${(region.bbox.x2 - region.bbox.x1) * 100}%`,
                  height: `${(region.bbox.y2 - region.bbox.y1) * 100}%`,
                }}
                title={`${region.region_type} (${region.region_id})`}
                onClick={() => onSelectIssue(null)}
              />
            ))}

            {showText && report?.text_elements.map((text) => (
              <button
                key={text.text_id}
                type="button"
                className="draftlint-workspace__box draftlint-workspace__box--text"
                style={{
                  left: `${text.bbox.x1 * 100}%`,
                  top: `${text.bbox.y1 * 100}%`,
                  width: `${(text.bbox.x2 - text.bbox.x1) * 100}%`,
                  height: `${(text.bbox.y2 - text.bbox.y1) * 100}%`,
                }}
                title={`${text.text} (conf ${Math.round(text.confidence * 100)}%)`}
                onClick={() => onSelectIssue(null)}
              />
            ))}

            {showSymbols && report?.detected_symbols.map((symbol) => (
              <button
                key={symbol.symbol_id}
                type="button"
                className="draftlint-workspace__box draftlint-workspace__box--symbol"
                style={{
                  left: `${symbol.bbox.x1 * 100}%`,
                  top: `${symbol.bbox.y1 * 100}%`,
                  width: `${(symbol.bbox.x2 - symbol.bbox.x1) * 100}%`,
                  height: `${(symbol.bbox.y2 - symbol.bbox.y1) * 100}%`,
                }}
                title={`${symbol.symbol_type} (conf ${Math.round(symbol.confidence * 100)}%)`}
                onClick={() => onSelectIssue(null)}
              />
            ))}

            {showIssues && report?.issues.map((issue) => (
              <button
                key={issue.issue_id}
                type="button"
                className={`${issueClass(issue)} ${selectedIssueId === issue.issue_id ? "draftlint-workspace__box--selected" : ""}`}
                style={{
                  left: `${issue.bbox.x1 * 100}%`,
                  top: `${issue.bbox.y1 * 100}%`,
                  width: `${(issue.bbox.x2 - issue.bbox.x1) * 100}%`,
                  height: `${(issue.bbox.y2 - issue.bbox.y1) * 100}%`,
                }}
                title={`${issue.severity.toUpperCase()} | ${issue.rule_id}`}
                onClick={() => onSelectIssue(issue.issue_id)}
              />
            ))}
          </div>
        )}
      </div>

      {selectedIssue ? (
        <footer className="draftlint-workspace__footer">
          <div className="draftlint-workspace__chip">{selectedIssue.severity.toUpperCase()}</div>
          <div className="draftlint-workspace__issue-text">
            <strong>{selectedIssue.title}</strong>
            <span>{selectedIssue.rule_id} | {selectedIssue.standard}</span>
            <span>{selectedIssue.recommended_action}</span>
          </div>
        </footer>
      ) : null}
    </section>
  );
};

export default DraftLintWorkspace;
