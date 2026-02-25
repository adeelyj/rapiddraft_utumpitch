import { useEffect, useMemo, useRef, useState } from "react";
import {
  createDraftLintSession,
  getDraftLintReport,
  getDraftLintSession,
  resolveDraftLintAssetUrl,
} from "../services/draftlintClient";
import type {
  DraftLintIssue,
  DraftLintReportResponse,
  DraftLintSessionResponse,
  DraftLintSeverity,
} from "../types/draftlint";

type DraftLintSidebarProps = {
  open: boolean;
  apiBase: string;
  report: DraftLintReportResponse | null;
  selectedIssueId: string | null;
  onSelectIssue: (issueId: string | null) => void;
  onReportChange: (report: DraftLintReportResponse | null) => void;
  onSourceChange: (payload: { sourceUrl: string | null; sourceMimeType: string | null; sourceName: string | null }) => void;
  onClose: () => void;
};

type SeverityFilter = "all" | DraftLintSeverity;

const STANDARD_PROFILES = [
  "ISO 1101 + ISO 5457",
  "ISO 8015 + ISO 2768",
  "ASME Y14.5",
] as const;

const severityClass = (severity: DraftLintSeverity): string => `draftlint-sidebar__severity draftlint-sidebar__severity--${severity}`;

const formatPercent = (value: number): string => `${Math.max(0, Math.min(100, Math.round(value)))}%`;

const formatConfidence = (value: number): string => `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;

const DraftLintSidebar = ({
  open,
  apiBase,
  report,
  selectedIssueId,
  onSelectIssue,
  onReportChange,
  onSourceChange,
  onClose,
}: DraftLintSidebarProps) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [standardProfile, setStandardProfile] = useState<string>(STANDARD_PROFILES[0]);
  const [session, setSession] = useState<DraftLintSessionResponse | null>(null);
  const [scanRunning, setScanRunning] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [activeApiBase, setActiveApiBase] = useState(apiBase);

  const pollTimerRef = useRef<number | null>(null);
  const localPreviewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    setActiveApiBase(apiBase);
  }, [apiBase]);

  const clearPollTimer = () => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const revokeLocalPreviewUrl = () => {
    if (localPreviewUrlRef.current) {
      window.URL.revokeObjectURL(localPreviewUrlRef.current);
      localPreviewUrlRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearPollTimer();
      revokeLocalPreviewUrl();
    };
  }, []);

  useEffect(() => {
    if (!report) return;
    if (selectedIssueId && report.issues.some((issue) => issue.issue_id === selectedIssueId)) {
      return;
    }
    onSelectIssue(report.issues[0]?.issue_id ?? null);
  }, [onSelectIssue, report, selectedIssueId]);

  const activeBaseForAssets = activeApiBase || apiBase;

  const artifactUrls = useMemo(() => {
    if (!report) return null;
    return {
      annotatedPng: resolveDraftLintAssetUrl(activeBaseForAssets, report.artifacts.annotated_png_url),
      reportJson: resolveDraftLintAssetUrl(activeBaseForAssets, report.artifacts.report_json_url),
      reportHtml: resolveDraftLintAssetUrl(activeBaseForAssets, report.artifacts.report_html_url),
      issuesCsv: resolveDraftLintAssetUrl(activeBaseForAssets, report.artifacts.issues_csv_url),
    };
  }, [activeBaseForAssets, report]);

  const visibleIssues = useMemo(() => {
    if (!report) return [];
    if (severityFilter === "all") return report.issues;
    return report.issues.filter((issue) => issue.severity === severityFilter);
  }, [report, severityFilter]);

  const selectedIssue = useMemo(() => {
    if (!report || !selectedIssueId) return null;
    return report.issues.find((issue) => issue.issue_id === selectedIssueId) ?? null;
  }, [report, selectedIssueId]);

  const countBySeverity = useMemo(() => {
    if (!report) {
      return { critical: 0, major: 0, minor: 0 };
    }
    return {
      critical: report.issues.filter((issue) => issue.severity === "critical").length,
      major: report.issues.filter((issue) => issue.severity === "major").length,
      minor: report.issues.filter((issue) => issue.severity === "minor").length,
    };
  }, [report]);

  const setLocalPreviewFromFile = (file: File) => {
    revokeLocalPreviewUrl();
    const objectUrl = window.URL.createObjectURL(file);
    localPreviewUrlRef.current = objectUrl;
    onSourceChange({
      sourceUrl: objectUrl,
      sourceMimeType: file.type || null,
      sourceName: file.name,
    });
  };

  const loadReportPayload = async (reportId: string, baseForRun: string) => {
    const { payload, usedApiBase } = await getDraftLintReport(baseForRun, reportId);
    setActiveApiBase(usedApiBase);
    onReportChange(payload);
    onSelectIssue(payload.issues[0]?.issue_id ?? null);
    setScanRunning(false);
  };

  const pollSessionUntilComplete = (sessionId: string, baseForRun: string, delayMs: number) => {
    clearPollTimer();
    const nextDelay = Math.max(300, delayMs);
    pollTimerRef.current = window.setTimeout(async () => {
      try {
        const { payload, usedApiBase } = await getDraftLintSession(baseForRun, sessionId);
        setActiveApiBase(usedApiBase);
        setSession((previous) => ({
          ...payload,
          source_url: previous?.source_url,
          source_original_name: previous?.source_original_name,
          source_mime_type: previous?.source_mime_type,
        }));

        if (payload.status === "completed" && payload.report_id) {
          await loadReportPayload(payload.report_id, usedApiBase);
          return;
        }

        pollSessionUntilComplete(payload.session_id, usedApiBase, payload.poll_after_ms || 900);
      } catch (pollError) {
        clearPollTimer();
        setScanRunning(false);
        setError(pollError instanceof Error ? pollError.message : "DraftLint scan polling failed.");
      }
    }, nextDelay);
  };

  const handleSelectFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setError(null);
    setSession(null);
    setSeverityFilter("all");
    onReportChange(null);
    onSelectIssue(null);
    clearPollTimer();

    if (!file) {
      revokeLocalPreviewUrl();
      onSourceChange({ sourceUrl: null, sourceMimeType: null, sourceName: null });
      return;
    }

    setLocalPreviewFromFile(file);
  };

  const handleRunScan = async () => {
    if (!selectedFile) {
      setError("Choose a drawing file before starting scan.");
      return;
    }

    clearPollTimer();
    setError(null);
    setScanRunning(true);
    setSeverityFilter("all");
    setSession(null);
    onReportChange(null);
    onSelectIssue(null);

    try {
      const { payload, usedApiBase } = await createDraftLintSession(apiBase, selectedFile, standardProfile);
      setActiveApiBase(usedApiBase);
      setSession(payload);

      const sessionSourceUrl = payload.source_url ? resolveDraftLintAssetUrl(usedApiBase, payload.source_url) : null;
      onSourceChange({
        sourceUrl: sessionSourceUrl,
        sourceMimeType: payload.source_mime_type ?? selectedFile.type ?? null,
        sourceName: payload.source_original_name ?? selectedFile.name,
      });

      if (payload.status === "completed" && payload.report_id) {
        await loadReportPayload(payload.report_id, usedApiBase);
        return;
      }

      pollSessionUntilComplete(payload.session_id, usedApiBase, payload.poll_after_ms || 900);
    } catch (scanError) {
      setScanRunning(false);
      setError(scanError instanceof Error ? scanError.message : "DraftLint scan failed.");
    }
  };

  const isScanInProgress = scanRunning || session?.status === "running";

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="draftlint-sidebar">
        <div className="draftlint-sidebar__header">
          <h2>DraftLint</h2>
          <button type="button" onClick={onClose} className="draftlint-sidebar__close" aria-label="Close DraftLint panel">
            x
          </button>
        </div>

        <label className="draftlint-sidebar__field">
          <span>Drawing file</span>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={handleSelectFile}
            disabled={isScanInProgress}
          />
        </label>

        <div className="draftlint-sidebar__file-meta">{selectedFile?.name ?? "No file selected"}</div>

        <label className="draftlint-sidebar__field">
          <span>Standards profile</span>
          <select
            value={standardProfile}
            onChange={(event) => setStandardProfile(event.target.value)}
            disabled={isScanInProgress}
          >
            {STANDARD_PROFILES.map((profile) => (
              <option key={profile} value={profile}>
                {profile}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="draftlint-sidebar__submit"
          onClick={handleRunScan}
          disabled={!selectedFile || isScanInProgress}
        >
          {isScanInProgress ? "Scanning drawing..." : "Scan drawing"}
        </button>

        <p className="draftlint-sidebar__hint">Upload PDF/PNG/JPG, then run scan.</p>

        {error ? <p className="draftlint-sidebar__error">{error}</p> : null}

        {session ? (
          <section className="draftlint-sidebar__timeline-card">
            <div className="draftlint-sidebar__progress-row">
              <strong>{session.status === "completed" ? "Scan complete" : "Scanning"}</strong>
              <span>{formatPercent(session.progress_percent)}</span>
            </div>
            <div className="draftlint-sidebar__progress-bar" aria-label="DraftLint scan progress">
              <span style={{ width: formatPercent(session.progress_percent) }} />
            </div>
            <ol className="draftlint-sidebar__timeline">
              {session.stages.map((stage) => (
                <li key={stage.stage_id} className={`draftlint-sidebar__stage draftlint-sidebar__stage--${stage.status}`}>
                  <div className="draftlint-sidebar__stage-top">
                    <span>{stage.label}</span>
                    <span>{formatPercent(stage.progress_percent)}</span>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        {report ? (
          <>
            <section className="draftlint-sidebar__summary">
              <div className="draftlint-sidebar__chip">Issues: {report.summary.total_issues}</div>
              <div className="draftlint-sidebar__chip">Critical: {report.summary.critical_count}</div>
              <div className="draftlint-sidebar__chip">Major: {report.summary.major_count}</div>
              <div className="draftlint-sidebar__chip">Minor: {report.summary.minor_count}</div>
            </section>

            {report.customer_summary ? (
              <section className="draftlint-sidebar__customer-summary">
                <h3>Customer summary</h3>
                <p>{report.customer_summary.headline}</p>
                <p>{report.customer_summary.priority_message}</p>
                <p>{report.customer_summary.next_step}</p>
              </section>
            ) : null}

            <section className="draftlint-sidebar__filters">
              <button
                type="button"
                className={`draftlint-sidebar__filter ${severityFilter === "all" ? "draftlint-sidebar__filter--active" : ""}`}
                onClick={() => setSeverityFilter("all")}
              >
                All ({report.issues.length})
              </button>
              <button
                type="button"
                className={`draftlint-sidebar__filter ${severityFilter === "critical" ? "draftlint-sidebar__filter--active" : ""}`}
                onClick={() => setSeverityFilter("critical")}
              >
                Critical ({countBySeverity.critical})
              </button>
              <button
                type="button"
                className={`draftlint-sidebar__filter ${severityFilter === "major" ? "draftlint-sidebar__filter--active" : ""}`}
                onClick={() => setSeverityFilter("major")}
              >
                Major ({countBySeverity.major})
              </button>
              <button
                type="button"
                className={`draftlint-sidebar__filter ${severityFilter === "minor" ? "draftlint-sidebar__filter--active" : ""}`}
                onClick={() => setSeverityFilter("minor")}
              >
                Minor ({countBySeverity.minor})
              </button>
            </section>

            <section className="draftlint-sidebar__issues">
              <h3>Findings</h3>
              <div className="draftlint-sidebar__issue-list">
                {visibleIssues.length ? (
                  visibleIssues.map((issue) => (
                    <button
                      key={issue.issue_id}
                      type="button"
                      className={`draftlint-sidebar__issue ${selectedIssueId === issue.issue_id ? "draftlint-sidebar__issue--active" : ""}`}
                      onClick={() => onSelectIssue(issue.issue_id)}
                    >
                      <div className="draftlint-sidebar__issue-head">
                        <span className={severityClass(issue.severity)}>{issue.severity.toUpperCase()}</span>
                        <strong>{issue.title}</strong>
                      </div>
                      <p>{issue.description}</p>
                      <p className="draftlint-sidebar__issue-meta">
                        {issue.rule_id} | {issue.standard} | Confidence {formatConfidence(issue.confidence)}
                      </p>
                    </button>
                  ))
                ) : (
                  <p className="draftlint-sidebar__empty">No findings in this filter.</p>
                )}
              </div>
            </section>

            {selectedIssue ? (
              <section className="draftlint-sidebar__selected-issue">
                <h3>Recommended action</h3>
                <p>{selectedIssue.recommended_action}</p>
              </section>
            ) : null}

            {artifactUrls ? (
              <section className="draftlint-sidebar__artifacts">
                <h3>Artifacts</h3>
                <div className="draftlint-sidebar__artifact-grid">
                  <a href={artifactUrls.annotatedPng} target="_blank" rel="noreferrer" className="draftlint-sidebar__artifact-link">
                    Annotated image
                  </a>
                  <a href={artifactUrls.reportHtml} target="_blank" rel="noreferrer" className="draftlint-sidebar__artifact-link">
                    HTML report
                  </a>
                  <a href={artifactUrls.reportJson} target="_blank" rel="noreferrer" className="draftlint-sidebar__artifact-link">
                    JSON report
                  </a>
                  <a href={artifactUrls.issuesCsv} target="_blank" rel="noreferrer" className="draftlint-sidebar__artifact-link">
                    Issues CSV
                  </a>
                </div>
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </aside>
  );
};

export default DraftLintSidebar;
