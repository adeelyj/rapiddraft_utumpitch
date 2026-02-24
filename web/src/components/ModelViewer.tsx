import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { Center, Environment, GizmoHelper, GizmoViewport, OrbitControls } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Box3, Object3D, Vector2, Vector3 } from "three";
import ReviewPins from "./ReviewPins";
import type { AnalysisFocusPayload } from "../types/analysis";
import type { PinPosition, PinnedItem } from "../types/review";
import type { PartFactMetric, PartFactsResponse } from "../types/partFacts";

type ModelComponent = {
  id: string;
  nodeName: string;
  displayName: string;
  triangleCount: number;
};

type DfmProfileOption = {
  id: string;
  label: string;
};

type DfmIndustryOption = DfmProfileOption & {
  standards: string[];
};

type DfmProfileOptions = {
  materials: DfmProfileOption[];
  manufacturingProcesses: DfmProfileOption[];
  industries: DfmIndustryOption[];
};

type ComponentProfile = {
  material: string;
  manufacturingProcess: string;
  industry: string;
};

type ModelViewerProps = {
  apiBase: string;
  modelId: string | null;
  previewUrl: string | null;
  message?: string;
  onCreateDrawing?: () => void;
  fitTrigger: number;
  components?: ModelComponent[];
  componentVisibility?: Record<string, boolean>;
  onToggleComponent?: (nodeName: string) => void;
  onShowAllComponents?: () => void;
  onHideAllComponents?: () => void;
  selectedComponentNodeName?: string | null;
  onSelectComponent?: (nodeName: string) => void;
  profileOptions?: DfmProfileOptions | null;
  selectedComponentProfile?: ComponentProfile | null;
  selectedIndustryStandards?: string[];
  profileSaving?: boolean;
  profileError?: string | null;
  onChangeComponentProfile?: (field: keyof ComponentProfile, value: string) => void;
  items?: PinnedItem[];
  selectedItemId?: string | null;
  onSelectTicket?: (id: string) => void;
  pinMode?: "none" | "comment" | "review";
  showReviewCards?: boolean;
  onCommentPin?: (payload: {
    position: PinPosition["position"];
    normal: PinPosition["normal"];
    cameraState: PinPosition["cameraState"];
    screenX: number;
    screenY: number;
  }) => void;
  onReviewPin?: (payload: {
    position: PinPosition["position"];
    normal: PinPosition["normal"];
    cameraState: PinPosition["cameraState"];
    screenX: number;
    screenY: number;
  }) => void;
  analysisFocus?: AnalysisFocusPayload | null;
  onClearAnalysisFocus?: () => void;
};

const joinApiUrl = (base: string, path: string): string => {
  const normalizedBase = base.replace(/\/$/, "");
  if (!normalizedBase) return path;
  if (path.startsWith("http")) return path;
  return `${normalizedBase}${path}`;
};

const analysisTone = (severity: string | undefined): "critical" | "warning" | "caution" | "info" => {
  const value = String(severity || "").trim().toLowerCase();
  if (value === "critical" || value === "major") return "critical";
  if (value === "warning") return "warning";
  if (value === "caution" || value === "minor") return "caution";
  return "info";
};

const metricStateClass = (state: string): string => {
  if (state === "measured") return "part-facts__state part-facts__state--measured";
  if (state === "inferred") return "part-facts__state part-facts__state--inferred";
  if (state === "declared") return "part-facts__state part-facts__state--declared";
  if (state === "failed") return "part-facts__state part-facts__state--failed";
  if (state === "not_applicable") return "part-facts__state part-facts__state--na";
  return "part-facts__state part-facts__state--unknown";
};

const formatMetricValue = (metric: PartFactMetric): string => {
  if (metric.value === null || metric.value === undefined) return "-";
  if (typeof metric.value === "boolean") return metric.value ? "Yes" : "No";
  if (typeof metric.value === "number") {
    const rendered = Number.isInteger(metric.value) ? metric.value.toString() : metric.value.toFixed(4);
    return metric.unit ? `${rendered} ${metric.unit}` : rendered;
  }
  const value = String(metric.value);
  return metric.unit ? `${value} ${metric.unit}` : value;
};

const sortedMetrics = (metrics: Record<string, PartFactMetric>): Array<[string, PartFactMetric]> =>
  Object.entries(metrics).sort((a, b) => a[1].label.localeCompare(b[1].label));

const FitCamera = ({ object, trigger }: { object: Object3D; trigger: number }) => {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as { target: Vector3; update: () => void } | null;

  useEffect(() => {
    if (!object) return;
    const box = new Box3().setFromObject(object);
    if (!isFinite(box.max.x)) return;

    const size = box.getSize(new Vector3());
    const center = box.getCenter(new Vector3());
    const maxSize = Math.max(size.x, size.y, size.z);
    const distance = maxSize / (2 * Math.tan((camera.fov * Math.PI) / 360));
    const direction = new Vector3(1, 1, 1).normalize();

    const newPosition = center.clone().add(direction.multiplyScalar(distance * 1.5 || 5));
    camera.position.copy(newPosition);
    camera.near = Math.max(maxSize / 100, 0.01);
    camera.far = Math.max(maxSize * 100, 1000);
    camera.updateProjectionMatrix();

    if (controls) {
      controls.target.copy(center);
      controls.update();
    }
    // Only re-run when the object changes. camera/controls identities may change
    // between renders and cause repeated camera adjustments leading to a continuous zoom.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [object, trigger]);

  return null;
};

const ModelContents = ({
  previewUrl,
  fitTrigger,
  items,
  selectedItemId,
  onSelectTicket,
  pinMode,
  onCommentPin,
  onReviewPin,
  showReviewCards,
  components,
  componentVisibility,
  analysisFocus,
}: {
  previewUrl: string;
  fitTrigger: number;
  items: PinnedItem[];
  selectedItemId: string | null;
  onSelectTicket: (id: string) => void;
  pinMode: "none" | "comment" | "review";
  onCommentPin?: ModelViewerProps["onCommentPin"];
  onReviewPin?: ModelViewerProps["onReviewPin"];
  showReviewCards: boolean;
  components: ModelComponent[];
  componentVisibility: Record<string, boolean>;
  analysisFocus?: AnalysisFocusPayload | null;
}) => {
  const gltf = useLoader(GLTFLoader, previewUrl);
  const camera = useThree((state) => state.camera);
  const raycaster = useThree((state) => state.raycaster);
  const gl = useThree((state) => state.gl);
  const controls = useThree((state) => state.controls) as { target: Vector3; update: () => void; enabled: boolean } | null;
  const [analysisMarkerExpanded, setAnalysisMarkerExpanded] = useState(true);
  const flyRef = useRef<{
    startPos: Vector3;
    startTarget: Vector3;
    endPos: Vector3;
    endTarget: Vector3;
    startTime: number;
    duration: number;
  } | null>(null);

  useEffect(() => {
    if (!analysisFocus) return;
    setAnalysisMarkerExpanded(true);
  }, [analysisFocus?.id]);

  useEffect(() => {
    if (pinMode === "none" || (!onCommentPin && !onReviewPin)) {
      gl.domElement.style.cursor = "default";
      return;
    }
    const handlePointerUp = (event: PointerEvent) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const rect = gl.domElement.getBoundingClientRect();
      const ndc = new Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(ndc, camera);
      const hits = raycaster.intersectObject(gltf.scene, true);
      if (!hits.length) return;
      const hit = hits[0];
      const point = hit.point;
      const faceNormal = hit.face?.normal?.clone() ?? new Vector3(0, 1, 0);
      const worldNormal = faceNormal.transformDirection(hit.object.matrixWorld);
      const camPos = camera.position;
      const target = controls?.target ?? new Vector3(0, 0, 0);
      const payload = {
        position: [point.x, point.y, point.z],
        normal: [worldNormal.x, worldNormal.y, worldNormal.z],
        cameraState: {
          position: [camPos.x, camPos.y, camPos.z],
          target: [target.x, target.y, target.z],
        },
        screenX: event.clientX,
        screenY: event.clientY,
      };
      if (pinMode === "comment") {
        onCommentPin?.(payload);
      } else if (pinMode === "review") {
        onReviewPin?.(payload);
      }
    };
    gl.domElement.style.cursor = "crosshair";
    gl.domElement.addEventListener("pointerup", handlePointerUp);
    return () => {
      gl.domElement.removeEventListener("pointerup", handlePointerUp);
      gl.domElement.style.cursor = "default";
    };
  }, [pinMode, onCommentPin, onReviewPin, gl, camera, raycaster, controls, gltf.scene]);

  useEffect(() => {
    if (!selectedItemId) return;
    const item = items.find((entry) => entry.id === selectedItemId);
    if (!item?.pin?.cameraState) return;
    const { position, target } = item.pin.cameraState;
    flyRef.current = {
      startPos: camera.position.clone(),
      startTarget: (controls?.target ?? new Vector3()).clone(),
      endPos: new Vector3(position[0], position[1], position[2]),
      endTarget: new Vector3(target[0], target[1], target[2]),
      startTime: performance.now(),
      duration: 500,
    };
    if (controls) {
      controls.enabled = false;
    }
  }, [selectedItemId, items, camera, controls]);

  useEffect(() => {
    if (!components.length) return;
    components.forEach((component) => {
      const node = gltf.scene.getObjectByName(component.nodeName);
      if (!node) return;
      node.visible = componentVisibility[component.nodeName] ?? true;
    });
  }, [components, componentVisibility, gltf.scene]);

  useFrame(() => {
    const animation = flyRef.current;
    if (!animation) return;
    const elapsed = performance.now() - animation.startTime;
    const t = Math.min(1, elapsed / animation.duration);
    camera.position.lerpVectors(animation.startPos, animation.endPos, t);
    if (controls) {
      controls.target.lerpVectors(animation.startTarget, animation.endTarget, t);
      controls.update();
    } else {
      camera.lookAt(animation.endTarget);
    }
    if (t >= 1) {
      flyRef.current = null;
      if (controls) {
        controls.enabled = pinMode === "none";
      }
    }
  });

  const analysisMarker = useMemo(() => {
    if (!analysisFocus) return null;
    const requestedNode = analysisFocus.component_node_name || null;
    const fallbackNode = components[0]?.nodeName ?? null;
    const targetNodeName = requestedNode || fallbackNode;
    const targetObject = targetNodeName ? gltf.scene.getObjectByName(targetNodeName) : null;
    const boundsTarget = targetObject || gltf.scene;
    const bounds = new Box3().setFromObject(boundsTarget);
    if (!Number.isFinite(bounds.max.x) || !Number.isFinite(bounds.min.x)) {
      return null;
    }
    const center = bounds.getCenter(new Vector3());
    const extents = bounds.getSize(new Vector3());
    const extent = Math.max(extents.length(), 1);
    const offsetDirection = camera.position.clone().sub(center);
    if (offsetDirection.lengthSq() < 1e-6) {
      offsetDirection.set(0, 1, 0);
    }
    offsetDirection.normalize();
    const markerPosition = center.clone().add(offsetDirection.multiplyScalar(Math.max(0.035 * extent, 0.09)));

    return {
      position: [markerPosition.x, markerPosition.y, markerPosition.z] as [number, number, number],
      lineEnd: [center.x, center.y, center.z] as [number, number, number],
      tone: analysisTone(analysisFocus.severity),
    };
  }, [analysisFocus, camera, components, gltf.scene]);

  return (
    <>
      <FitCamera object={gltf.scene} trigger={fitTrigger} />
      <Center disableY>
        <group>
          <primitive object={gltf.scene} dispose={null} />
        </group>
      </Center>
      <ReviewPins
        items={items}
        selectedItemId={selectedItemId}
        onSelect={onSelectTicket}
        showCards={showReviewCards}
      />
      {analysisFocus && analysisMarker ? (
        <group key={`analysis-focus-${analysisFocus.id}`}>
          <Line points={[analysisMarker.position, analysisMarker.lineEnd]} color="#ef651a" lineWidth={1.2} />
          <Html position={analysisMarker.position} center>
            <div className={`analysis-pin analysis-pin--${analysisMarker.tone}`}>
              <button
                className="analysis-pin__dot"
                onClick={() => setAnalysisMarkerExpanded((prev) => !prev)}
                aria-label={`Focus marker: ${analysisFocus.title}`}
              />
              {analysisMarkerExpanded ? (
                <div className="analysis-pin-card">
                  <div className="analysis-pin-card__title">{analysisFocus.title}</div>
                  <div className="analysis-pin-card__meta">
                    <span>{analysisFocus.source.toUpperCase()}</span>
                    <span>{analysisMarker.tone}</span>
                  </div>
                </div>
              ) : null}
            </div>
          </Html>
        </group>
      ) : null}
    </>
  );
};

const Placeholder = () => <div className="viewer__placeholder" />;

const ModelViewer = ({
  apiBase,
  modelId,
  previewUrl,
  message,
  onCreateDrawing,
  fitTrigger,
  components = [],
  componentVisibility = {},
  onToggleComponent = () => undefined,
  onShowAllComponents = () => undefined,
  onHideAllComponents = () => undefined,
  selectedComponentNodeName = null,
  onSelectComponent = () => undefined,
  profileOptions = null,
  selectedComponentProfile = null,
  selectedIndustryStandards = [],
  profileSaving = false,
  profileError = null,
  onChangeComponentProfile = () => undefined,
  items = [],
  selectedItemId = null,
  onSelectTicket = () => undefined,
  pinMode = "none",
  showReviewCards = true,
  onCommentPin,
  onReviewPin,
  analysisFocus = null,
  onClearAnalysisFocus = () => undefined,
}: ModelViewerProps) => {
  const overlayMessage = message ?? (previewUrl ? "Loading preview..." : "Import a STEP file to begin.");
  const selectedComponent =
    components.find((component) => component.nodeName === selectedComponentNodeName) ?? components[0] ?? null;
  const profile = selectedComponentProfile ?? { material: "", manufacturingProcess: "", industry: "" };
  const [partFacts, setPartFacts] = useState<PartFactsResponse | null>(null);
  const [partFactsLoading, setPartFactsLoading] = useState(false);
  const [partFactsRefreshing, setPartFactsRefreshing] = useState(false);
  const [partFactsError, setPartFactsError] = useState<string | null>(null);

  const fetchPartFacts = async (refresh: boolean) => {
    if (!modelId || !selectedComponent?.nodeName) {
      setPartFacts(null);
      setPartFactsError(null);
      return;
    }

    if (refresh) setPartFactsRefreshing(true);
    else setPartFactsLoading(true);
    setPartFactsError(null);

    const path = refresh
      ? `/api/models/${modelId}/components/${selectedComponent.nodeName}/part-facts/refresh`
      : `/api/models/${modelId}/components/${selectedComponent.nodeName}/part-facts`;

    try {
      const response = await fetch(joinApiUrl(apiBase, path), {
        method: refresh ? "POST" : "GET",
      });
      if (!response.ok) {
        let detail = "Failed to load part facts";
        try {
          const payload = (await response.json()) as { detail?: string; message?: string };
          detail = payload.detail ?? payload.message ?? detail;
        } catch {
          // Keep fallback text.
        }
        throw new Error(`${detail} (HTTP ${response.status})`);
      }
      const payload = (await response.json()) as PartFactsResponse;
      setPartFacts(payload);
    } catch (err) {
      setPartFactsError(err instanceof Error ? err.message : "Unexpected error while loading part facts");
      if (!refresh) setPartFacts(null);
    } finally {
      if (refresh) setPartFactsRefreshing(false);
      else setPartFactsLoading(false);
    }
  };

  useEffect(() => {
    if (!previewUrl || !selectedComponent?.nodeName || !modelId) {
      setPartFacts(null);
      setPartFactsError(null);
      return;
    }
    fetchPartFacts(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewUrl, selectedComponent?.nodeName, modelId, apiBase]);

  return (
    <section className="viewer-area">
      {previewUrl ? (
        <>
          <Canvas camera={{ position: [4, 4, 4], fov: 45 }}>
            <ambientLight intensity={0.7} />
            <directionalLight position={[5, 5, 5]} intensity={0.9} />
            <Suspense fallback={null}>
              <ModelContents
                previewUrl={previewUrl}
                fitTrigger={fitTrigger}
                items={items}
                selectedItemId={selectedItemId}
                onSelectTicket={onSelectTicket}
                pinMode={pinMode}
                onCommentPin={onCommentPin}
                onReviewPin={onReviewPin}
                showReviewCards={showReviewCards}
                components={components}
                componentVisibility={componentVisibility}
                analysisFocus={analysisFocus}
              />
            </Suspense>
            <Environment preset="city" />
            <OrbitControls makeDefault enabled={pinMode === "none"} />
            <GizmoHelper alignment="bottom-right" margin={[128, 128]}>
              <GizmoViewport axisColors={["#ef4444", "#22c55e", "#3b82f6"]} labelColor="#0f172a" />
            </GizmoHelper>
          </Canvas>
        </>
      ) : (
        <Placeholder />
      )}
      <div className="viewer-overlay">{overlayMessage}</div>
      {previewUrl && analysisFocus ? (
        <div className={`analysis-focus-overlay analysis-focus-overlay--${analysisTone(analysisFocus.severity)}`}>
          <div className="analysis-focus-overlay__header">
            <span className="analysis-focus-overlay__source">{analysisFocus.source.toUpperCase()} finding</span>
            <button type="button" onClick={onClearAnalysisFocus}>
              Clear
            </button>
          </div>
          <p className="analysis-focus-overlay__title">{analysisFocus.title}</p>
          {analysisFocus.details ? <p className="analysis-focus-overlay__details">{analysisFocus.details}</p> : null}
        </div>
      ) : null}
      {previewUrl && components.length > 0 && (
        <div className="viewer-left-panels">
          <section className="assembly-tree" aria-label="Assembly tree">
            <header className="assembly-tree__header">
              <h3>Assembly</h3>
              <div className="assembly-tree__actions">
                <button type="button" onClick={onShowAllComponents}>
                  Show all
                </button>
                <button type="button" onClick={onHideAllComponents}>
                  Hide all
                </button>
              </div>
            </header>
            <div className="assembly-tree__list" role="list">
              {components.map((component) => (
                <div
                  key={component.id}
                  className={`assembly-tree__item ${
                    selectedComponentNodeName === component.nodeName ? "assembly-tree__item--selected" : ""
                  }`}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectComponent(component.nodeName)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectComponent(component.nodeName);
                    }
                  }}
                >
                  <input
                    type="checkbox"
                    checked={componentVisibility[component.nodeName] ?? true}
                    onClick={(event) => event.stopPropagation()}
                    onChange={() => onToggleComponent(component.nodeName)}
                  />
                  <span>{component.displayName}</span>
                </div>
              ))}
            </div>
          </section>
          {selectedComponent && (
            <section className="component-profile-panel" aria-label="Component profile">
              <header className="component-profile-panel__header">
                <h3>{selectedComponent.displayName}</h3>
                <span className="component-profile-panel__status">{profileSaving ? "Saving..." : "Saved"}</span>
              </header>
              <label className="component-profile-panel__field">
                <span>Material</span>
                <select
                  value={profile.material}
                  onChange={(event) => onChangeComponentProfile("material", event.target.value)}
                  disabled={!profileOptions}
                >
                  <option value="">Select material</option>
                  {(profileOptions?.materials ?? []).map((option) => (
                    <option key={option.id} value={option.label}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="component-profile-panel__field">
                <span>Manufacturing process</span>
                <select
                  value={profile.manufacturingProcess}
                  onChange={(event) => onChangeComponentProfile("manufacturingProcess", event.target.value)}
                  disabled={!profileOptions}
                >
                  <option value="">Select process</option>
                  {(profileOptions?.manufacturingProcesses ?? []).map((option) => (
                    <option key={option.id} value={option.label}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="component-profile-panel__field">
                <span>Industry</span>
                <select
                  value={profile.industry}
                  onChange={(event) => onChangeComponentProfile("industry", event.target.value)}
                  disabled={!profileOptions}
                >
                  <option value="">Select industry</option>
                  {(profileOptions?.industries ?? []).map((option) => (
                    <option key={option.id} value={option.label}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="component-profile-panel__standards">
                <span>Standards:</span>
                <p>{selectedIndustryStandards.length ? selectedIndustryStandards.join(", ") : "None"}</p>
              </div>
              <section className="part-facts" aria-label="Part facts">
                <header className="part-facts__header">
                  <h4>Part Facts</h4>
                  <button
                    type="button"
                    onClick={() => fetchPartFacts(true)}
                    disabled={partFactsRefreshing || partFactsLoading || !modelId || !selectedComponent?.nodeName}
                  >
                    {partFactsRefreshing ? "Refreshing..." : "Refresh"}
                  </button>
                </header>
                {partFacts ? (
                  <>
                    <p className="part-facts__meta">
                      Core extraction: {partFacts.coverage.core_extraction_coverage.percent.toFixed(1)}% (
                      {partFacts.coverage.core_extraction_coverage.known_metrics}/
                      {partFacts.coverage.core_extraction_coverage.applicable_metrics} applicable,{" "}
                      {partFacts.coverage.core_extraction_coverage.not_applicable_metrics} N/A)
                    </p>
                    <p className="part-facts__meta">
                      Full rule readiness: {partFacts.coverage.full_rule_readiness_coverage.percent.toFixed(1)}% (
                      {partFacts.coverage.full_rule_readiness_coverage.known_metrics}/
                      {partFacts.coverage.full_rule_readiness_coverage.applicable_metrics} applicable,{" "}
                      {partFacts.coverage.full_rule_readiness_coverage.not_applicable_metrics} N/A)
                    </p>
                    <p className="part-facts__meta">
                      Confidence: {partFacts.overall_confidence}
                    </p>
                    <div className="part-facts__section">
                      <h5>Geometry</h5>
                      <div className="part-facts__metrics">
                        {sortedMetrics(partFacts.sections.geometry).map(([key, metric]) => (
                          <div key={key} className="part-facts__metric">
                            <div className="part-facts__metric-main">
                              <span>{metric.label}</span>
                              <strong>{formatMetricValue(metric)}</strong>
                            </div>
                            <div className="part-facts__metric-meta">
                              <span className={metricStateClass(metric.state)}>{metric.state}</span>
                              <span>{Math.round(metric.confidence * 100)}%</span>
                            </div>
                            {metric.reason ? <p className="part-facts__reason">{metric.reason}</p> : null}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="part-facts__section">
                      <h5>Manufacturing Signals</h5>
                      <div className="part-facts__metrics">
                        {sortedMetrics(partFacts.sections.manufacturing_signals).map(([key, metric]) => (
                          <div key={key} className="part-facts__metric">
                            <div className="part-facts__metric-main">
                              <span>{metric.label}</span>
                              <strong>{formatMetricValue(metric)}</strong>
                            </div>
                            <div className="part-facts__metric-meta">
                              <span className={metricStateClass(metric.state)}>{metric.state}</span>
                              <span>{Math.round(metric.confidence * 100)}%</span>
                            </div>
                            {metric.reason ? <p className="part-facts__reason">{metric.reason}</p> : null}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="part-facts__section">
                      <h5>Declared Context</h5>
                      <div className="part-facts__metrics">
                        {sortedMetrics(partFacts.sections.declared_context).map(([key, metric]) => (
                          <div key={key} className="part-facts__metric">
                            <div className="part-facts__metric-main">
                              <span>{metric.label}</span>
                              <strong>{formatMetricValue(metric)}</strong>
                            </div>
                            <div className="part-facts__metric-meta">
                              <span className={metricStateClass(metric.state)}>{metric.state}</span>
                              <span>{Math.round(metric.confidence * 100)}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <details className="part-facts__details">
                      <summary>Downstream Input Coverage</summary>
                      <p className="part-facts__meta">
                        Missing inputs: {partFacts.missing_inputs.length ? partFacts.missing_inputs.join(", ") : "None"}
                      </p>
                      <div className="part-facts__section">
                        <h5>Process Inputs</h5>
                        <div className="part-facts__metrics">
                          {sortedMetrics(partFacts.sections.process_inputs).map(([key, metric]) => (
                            <div key={key} className="part-facts__metric">
                              <div className="part-facts__metric-main">
                                <span>{metric.label}</span>
                                <strong>{formatMetricValue(metric)}</strong>
                              </div>
                              <div className="part-facts__metric-meta">
                                <span className={metricStateClass(metric.state)}>{metric.state}</span>
                                <span>{Math.round(metric.confidence * 100)}%</span>
                              </div>
                              {metric.reason ? <p className="part-facts__reason">{metric.reason}</p> : null}
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="part-facts__section">
                        <h5>Rule Inputs</h5>
                        <div className="part-facts__metrics">
                          {sortedMetrics(partFacts.sections.rule_inputs).map(([key, metric]) => (
                            <div key={key} className="part-facts__metric">
                              <div className="part-facts__metric-main">
                                <span>{metric.label}</span>
                                <strong>{formatMetricValue(metric)}</strong>
                              </div>
                              <div className="part-facts__metric-meta">
                                <span className={metricStateClass(metric.state)}>{metric.state}</span>
                                <span>{Math.round(metric.confidence * 100)}%</span>
                              </div>
                              {metric.reason ? <p className="part-facts__reason">{metric.reason}</p> : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    </details>
                    {partFacts.errors.length ? (
                      <p className="part-facts__error">Errors: {partFacts.errors.join(" | ")}</p>
                    ) : null}
                  </>
                ) : (
                  <p className="part-facts__meta">
                    {partFactsLoading ? "Extracting part facts..." : "Part facts not loaded yet."}
                  </p>
                )}
                {partFactsError ? <p className="part-facts__error">{partFactsError}</p> : null}
              </section>
              {profileError ? <p className="component-profile-panel__error">{profileError}</p> : null}
            </section>
          )}
        </div>
      )}
      {previewUrl && (
        <button className="viewer__create-drawing" onClick={onCreateDrawing}>
          Create Drawing
        </button>
      )}
    </section>
  );
};

export default ModelViewer;
