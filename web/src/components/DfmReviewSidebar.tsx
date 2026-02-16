import { ClipboardEvent, useEffect, useMemo, useState } from "react";

type RuleSet = {
  id: string;
  name: string;
  description: string;
};

type DfmReviewResponse = {
  title: string;
  componentNodeName: string;
  componentDisplayName: string;
  technology: string;
  material: string;
  industry: string;
  ruleSetId: string;
  rolesUsed: string[];
  reportMarkdown: string;
  structured: {
    assumptions: string[];
    highRiskChecks: string[];
    mediumCostDrivers: string[];
    suggestedNextSteps: string[];
  };
};

type DfmReviewSidebarProps = {
  open: boolean;
  apiBase: string;
  modelId: string | null;
  selectedComponent: { nodeName: string; displayName: string } | null;
  selectedProfile: {
    material: string;
    manufacturingProcess: string;
    industry: string;
  } | null;
  profileComplete: boolean;
  onClose: () => void;
};

const DfmReviewSidebar = ({
  open,
  apiBase,
  modelId,
  selectedComponent,
  selectedProfile,
  profileComplete,
  onClose,
}: DfmReviewSidebarProps) => {
  const [ruleSets, setRuleSets] = useState<RuleSet[]>([]);
  const [ruleSetId, setRuleSetId] = useState("");
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [report, setReport] = useState<DfmReviewResponse | null>(null);
  const [loadingRuleSets, setLoadingRuleSets] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const loadRuleSets = async () => {
      setLoadingRuleSets(true);
      setError(null);
      try {
        const response = await fetch(`${apiBase}/api/dfm/rule-sets`);
        if (!response.ok) throw new Error("Failed to load DFM rule sets");
        const payload = (await response.json()) as RuleSet[];
        if (cancelled) return;
        setRuleSets(payload);
        setRuleSetId((current) => current || payload[0]?.id || "");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unexpected error while loading rule sets");
        }
      } finally {
        if (!cancelled) setLoadingRuleSets(false);
      }
    };
    loadRuleSets();
    return () => {
      cancelled = true;
    };
  }, [apiBase, open]);

  useEffect(() => {
    setReport(null);
    setError(null);
  }, [modelId, selectedComponent?.nodeName]);

  const selectedRuleSetDescription = useMemo(() => {
    return ruleSets.find((item) => item.id === ruleSetId)?.description ?? "";
  }, [ruleSetId, ruleSets]);

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = event.clipboardData.files;
    if (!files || files.length === 0) return;
    const imageFile = Array.from(files).find((file) => file.type.startsWith("image/"));
    if (!imageFile) return;
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setImageDataUrl(reader.result);
      }
    };
    reader.readAsDataURL(imageFile);
  };

  const handleSubmit = async () => {
    if (!modelId || !selectedComponent) {
      setError("Select a part from the assembly tree before submitting.");
      return;
    }
    if (!profileComplete) {
      setError("Please fill material, manufacturing process, and industry for the selected part.");
      return;
    }
    if (!ruleSetId) {
      setError("Please select a standards template before submitting.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/api/models/${modelId}/dfm/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_set_id: ruleSetId,
          component_node_name: selectedComponent.nodeName,
          image_data_url: imageDataUrl || null,
        }),
      });
      if (!response.ok) throw new Error("Failed to generate DFM review");
      const payload = (await response.json()) as DfmReviewResponse;
      setReport(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error while generating DFM review");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <aside className={`sidebar-panel sidebar-panel--right ${open ? "sidebar-panel--open" : ""}`}>
      <div className="dfm-sidebar">
        <div className="dfm-sidebar__header">
          <h2>DFM Template</h2>
          <button type="button" onClick={onClose} className="dfm-sidebar__close" aria-label="Close DFM template">
            x
          </button>
        </div>

        <div className="dfm-sidebar__field">
          <span>Selected part</span>
          <div className="dfm-sidebar__readonly">{selectedComponent?.displayName ?? "No part selected"}</div>
        </div>
        <div className="dfm-sidebar__field">
          <span>Manufacturing process</span>
          <div className="dfm-sidebar__readonly">{selectedProfile?.manufacturingProcess || "-"}</div>
        </div>
        <div className="dfm-sidebar__field">
          <span>Material</span>
          <div className="dfm-sidebar__readonly">{selectedProfile?.material || "-"}</div>
        </div>
        <div className="dfm-sidebar__field">
          <span>Industry</span>
          <div className="dfm-sidebar__readonly">{selectedProfile?.industry || "-"}</div>
        </div>

        <label className="dfm-sidebar__field">
          <span>Standards template</span>
          <select
            value={ruleSetId}
            onChange={(event) => setRuleSetId(event.target.value)}
            disabled={loadingRuleSets || ruleSets.length === 0}
          >
            {ruleSets.map((ruleSet) => (
              <option key={ruleSet.id} value={ruleSet.id}>
                {ruleSet.name}
              </option>
            ))}
          </select>
        </label>
        {selectedRuleSetDescription ? <p className="dfm-sidebar__hint">{selectedRuleSetDescription}</p> : null}

        <label className="dfm-sidebar__field">
          <span>Paste screenshot</span>
          <textarea
            className="dfm-sidebar__paste"
            onPaste={handlePaste}
            placeholder="Click here and paste image from clipboard (Ctrl/Cmd + V)."
          />
        </label>

        {imageDataUrl ? <img src={imageDataUrl} alt="Pasted screenshot preview" className="dfm-sidebar__image-preview" /> : null}

        <button type="button" className="dfm-sidebar__submit" onClick={handleSubmit} disabled={submitting || loadingRuleSets}>
          {submitting ? "Generating..." : "Submit for review"}
        </button>

        {error ? <p className="dfm-sidebar__error">{error}</p> : null}
        {!profileComplete ? (
          <p className="dfm-sidebar__hint">Complete the selected part profile in the viewer panel before submitting.</p>
        ) : null}

        {report ? (
          <div className="dfm-sidebar__report">
            <h3>{report.title}</h3>
            <p className="dfm-sidebar__meta">Component: {report.componentDisplayName}</p>
            <p className="dfm-sidebar__meta">Roles used: {report.rolesUsed.join(", ")}</p>
            <pre>{report.reportMarkdown}</pre>
          </div>
        ) : null}
      </div>
    </aside>
  );
};

export default DfmReviewSidebar;
