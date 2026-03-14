import { Component, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { Center, Environment, GizmoHelper, GizmoViewport, Html, Line, OrbitControls } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";
import { Box3, BoxGeometry, EdgesGeometry, MOUSE, Object3D, Vector2, Vector3 } from "three";
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
  onFitView?: () => void;
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
  showInspectorPanels?: boolean;
  chromeDensity?: "default" | "compact";
};

type CameraSnapshot = {
  position: [number, number, number];
  target: [number, number, number];
};

type ViewerErrorBoundaryProps = {
  resetKey: string | null;
  children: ReactNode;
};

type ViewerErrorBoundaryState = {
  error: Error | null;
};

type OrbitControlsLike = {
  target: Vector3;
  update: () => void;
  enabled: boolean;
  dollyIn?: (scale: number) => void;
  dollyOut?: (scale: number) => void;
};

class ViewerErrorBoundary extends Component<ViewerErrorBoundaryProps, ViewerErrorBoundaryState> {
  state: ViewerErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ViewerErrorBoundaryState {
    return { error };
  }

  componentDidUpdate(prevProps: ViewerErrorBoundaryProps): void {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="viewer__error" role="alert">
          <strong>Model preview could not be rendered.</strong>
          <p>{this.state.error.message || "The preview loader failed before the 3D view could be displayed."}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

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


const analysisToneColor = (tone: "critical" | "warning" | "caution" | "info"): string => {
  if (tone === "critical") return "#e4573e";
  if (tone === "warning") return "#f29122";
  if (tone === "caution") return "#f6a94a";
  return "#516da4";
};

const isFiniteTuple = (value: unknown, length: number): value is number[] =>
  Array.isArray(value) &&
  value.length === length &&
  value.every((entry) => typeof entry === "number" && Number.isFinite(entry));

const analysisFocusCenter = (
  analysisFocus: AnalysisFocusPayload | null | undefined,
  fallbackObject: Object3D,
): { center: Vector3; extent: number } | null => {
  if (analysisFocus && isFiniteTuple(analysisFocus.bbox_bounds_mm, 6)) {
    const bounds = analysisFocus.bbox_bounds_mm;
    const center = new Vector3(
      (bounds[0] + bounds[3]) * 0.5,
      (bounds[1] + bounds[4]) * 0.5,
      (bounds[2] + bounds[5]) * 0.5,
    );
    const extent = Math.max(
      new Vector3(bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2]).length(),
      1,
    );
    return { center, extent };
  }

  if (analysisFocus && isFiniteTuple(analysisFocus.position_mm, 3)) {
    const center = new Vector3(
      analysisFocus.position_mm[0],
      analysisFocus.position_mm[1],
      analysisFocus.position_mm[2],
    );
    return { center, extent: 1 };
  }

  const bounds = new Box3().setFromObject(fallbackObject);
  if (!Number.isFinite(bounds.max.x) || !Number.isFinite(bounds.min.x)) {
    return null;
  }
  return {
    center: bounds.getCenter(new Vector3()),
    extent: Math.max(bounds.getSize(new Vector3()).length(), 1),
  };
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

const FitCamera = ({
  object,
  trigger,
  onFitted,
}: {
  object: Object3D;
  trigger: number;
  onFitted?: (snapshot: CameraSnapshot) => void;
}) => {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as OrbitControlsLike | null;

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
    onFitted?.({
      position: [newPosition.x, newPosition.y, newPosition.z],
      target: [center.x, center.y, center.z],
    });
    // Only re-run when the object changes. camera/controls identities may change
    // between renders and cause repeated camera adjustments leading to a continuous zoom.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [object, trigger, onFitted]);

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
  zoomInTrigger,
  zoomOutTrigger,
  homeTrigger,
  homeView,
  onFitCaptured,
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
  zoomInTrigger: number;
  zoomOutTrigger: number;
  homeTrigger: number;
  homeView: CameraSnapshot | null;
  onFitCaptured?: (snapshot: CameraSnapshot) => void;
}) => {
  const gltf = useLoader(GLTFLoader, previewUrl);
  const scene = useMemo(() => clone(gltf.scene), [gltf.scene]);
  const camera = useThree((state) => state.camera);
  const raycaster = useThree((state) => state.raycaster);
  const gl = useThree((state) => state.gl);
  const controls = useThree((state) => state.controls) as OrbitControlsLike | null;
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
    setAnalysisMarkerExpanded(analysisFocus.overlay_variant !== "compact");
  }, [analysisFocus?.id]);

  useEffect(() => {
    if (!analysisFocus) return;
    if (analysisFocus.camera_behavior === "preserve") {
      flyRef.current = null;
      if (controls) {
        controls.enabled = pinMode === "none";
      }
      return;
    }
    const requestedNode = analysisFocus.component_node_name || null;
    const fallbackNode = components[0]?.nodeName ?? null;
    const targetNodeName = requestedNode || fallbackNode;
    const targetObject = targetNodeName ? scene.getObjectByName(targetNodeName) : null;
    const focusTarget = analysisFocusCenter(analysisFocus, targetObject || scene);
    if (!focusTarget) return;
    if (!analysisFocus.position_mm && !analysisFocus.bbox_bounds_mm) return;

    const startTarget = (controls?.target ?? new Vector3()).clone();
    const direction = camera.position.clone().sub(startTarget);
    if (direction.lengthSq() < 1e-6) {
      direction.copy(camera.position.clone().sub(focusTarget.center));
    }
    if (direction.lengthSq() < 1e-6) {
      direction.set(1, 1, 1);
    }
    direction.normalize();

    const endDistance = Math.max(focusTarget.extent * 1.35, 1.6);
    const endPosition = focusTarget.center.clone().add(direction.multiplyScalar(endDistance));

    flyRef.current = {
      startPos: camera.position.clone(),
      startTarget,
      endPos: endPosition,
      endTarget: focusTarget.center,
      startTime: performance.now(),
      duration: 520,
    };
    if (controls) {
      controls.enabled = false;
    }
  }, [analysisFocus?.id, analysisFocus, camera, components, controls, pinMode, scene]);

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
      const hits = raycaster.intersectObject(scene, true);
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
  }, [pinMode, onCommentPin, onReviewPin, gl, camera, raycaster, controls, scene]);

  useEffect(() => {
    if (!controls || zoomInTrigger <= 0 || typeof controls.dollyIn !== "function") return;
    controls.dollyIn(1.18);
    controls.update();
  }, [zoomInTrigger, controls]);

  useEffect(() => {
    if (!controls || zoomOutTrigger <= 0 || typeof controls.dollyOut !== "function") return;
    controls.dollyOut(1.18);
    controls.update();
  }, [zoomOutTrigger, controls]);

  useEffect(() => {
    if (!controls || !homeView || homeTrigger <= 0) return;
    camera.position.set(homeView.position[0], homeView.position[1], homeView.position[2]);
    controls.target.set(homeView.target[0], homeView.target[1], homeView.target[2]);
    controls.update();
  }, [homeTrigger, homeView, controls, camera]);

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
      const node = scene.getObjectByName(component.nodeName);
      if (!node) return;
      node.visible = componentVisibility[component.nodeName] ?? true;
    });
  }, [components, componentVisibility, scene]);

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
    const targetObject = targetNodeName ? scene.getObjectByName(targetNodeName) : null;
    const focusTarget = analysisFocusCenter(analysisFocus, targetObject || scene);
    if (!focusTarget) return null;
    const center = focusTarget.center;
    const extent = focusTarget.extent;
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
  }, [analysisFocus, camera, components, scene]);

  const analysisBoundsOverlay = useMemo(() => {
    if (!analysisFocus || !isFiniteTuple(analysisFocus.bbox_bounds_mm, 6)) return null;
    const bounds = analysisFocus.bbox_bounds_mm;
    const size: [number, number, number] = [
      Math.max(bounds[3] - bounds[0], 0.05),
      Math.max(bounds[4] - bounds[1], 0.05),
      Math.max(bounds[5] - bounds[2], 0.05),
    ];
    const center: [number, number, number] = [
      (bounds[0] + bounds[3]) * 0.5,
      (bounds[1] + bounds[4]) * 0.5,
      (bounds[2] + bounds[5]) * 0.5,
    ];
    return {
      center,
      size,
      tone: analysisTone(analysisFocus.severity),
    };
  }, [analysisFocus]);

  const analysisBoundsEdges = useMemo(() => {
    if (!analysisBoundsOverlay) return null;
    const geometry = new BoxGeometry(
      analysisBoundsOverlay.size[0],
      analysisBoundsOverlay.size[1],
      analysisBoundsOverlay.size[2],
    );
    const edges = new EdgesGeometry(geometry);
    geometry.dispose();
    return edges;
  }, [analysisBoundsOverlay]);

  useEffect(() => {
    return () => {
      analysisBoundsEdges?.dispose();
    };
  }, [analysisBoundsEdges]);

  return (
    <>
      <FitCamera object={scene} trigger={fitTrigger} onFitted={onFitCaptured} />
      <Center disableY>
        <group>
          <primitive object={scene} dispose={null} />
        </group>
      </Center>
      <ReviewPins
        items={items}
        selectedItemId={selectedItemId}
        onSelect={onSelectTicket}
        showCards={showReviewCards}
      />
      {analysisBoundsOverlay && analysisBoundsEdges ? (
        <group key={`analysis-focus-bounds-${analysisFocus?.id}`}>
          <mesh
            position={analysisBoundsOverlay.center}
            renderOrder={1}
          >
            <boxGeometry args={analysisBoundsOverlay.size} />
            <meshBasicMaterial
              color={analysisToneColor(analysisBoundsOverlay.tone)}
              transparent
              opacity={0.12}
              depthWrite={false}
              depthTest={false}
            />
          </mesh>
          <lineSegments position={analysisBoundsOverlay.center} renderOrder={2}>
            <primitive object={analysisBoundsEdges} attach="geometry" />
            <lineBasicMaterial
              color={analysisToneColor(analysisBoundsOverlay.tone)}
              transparent
              opacity={0.94}
              depthTest={false}
            />
          </lineSegments>
        </group>
      ) : null}
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
                <div
                  className={`analysis-pin-card${
                    analysisFocus.overlay_variant === "compact" ? " analysis-pin-card--compact" : ""
                  }`}
                >
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
  onFitView = () => undefined,
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
  showInspectorPanels = true,
  chromeDensity = "default",
}: ModelViewerProps) => {
  const resolvedPreviewUrl = useMemo(() => (previewUrl ? joinApiUrl(apiBase, previewUrl) : null), [apiBase, previewUrl]);
  const overlayMessage = message ?? (resolvedPreviewUrl ? "Loading preview..." : "Import a STEP file to begin.");
  const hasLeftPanels = Boolean(showInspectorPanels && resolvedPreviewUrl && components.length > 0);
  const showViewerOverlay = !resolvedPreviewUrl || (!hasLeftPanels && (components.length === 0 || Boolean(message?.trim())));
  const panelStatusMessage = message?.trim() ?? "";
  const [navigationMode, setNavigationMode] = useState<"rotate" | "pan">("rotate");
  const [zoomInTrigger, setZoomInTrigger] = useState(0);
  const [zoomOutTrigger, setZoomOutTrigger] = useState(0);
  const [homeTrigger, setHomeTrigger] = useState(0);
  const [homeView, setHomeView] = useState<CameraSnapshot | null>(null);
  const selectedComponent =
    components.find((component) => component.nodeName === selectedComponentNodeName) ?? components[0] ?? null;
  const visibleComponentCount = useMemo(
    () => components.filter((component) => componentVisibility[component.nodeName] ?? true).length,
    [components, componentVisibility],
  );
  const orbitMouseButtons = useMemo(
    () =>
      navigationMode === "pan"
        ? { LEFT: MOUSE.PAN, MIDDLE: MOUSE.DOLLY, RIGHT: MOUSE.ROTATE }
        : { LEFT: MOUSE.ROTATE, MIDDLE: MOUSE.DOLLY, RIGHT: MOUSE.PAN },
    [navigationMode],
  );
  const profile = selectedComponentProfile ?? { material: "", manufacturingProcess: "", industry: "" };
  const [partFacts, setPartFacts] = useState<PartFactsResponse | null>(null);
  const [partFactsLoading, setPartFactsLoading] = useState(false);
  const [partFactsRefreshing, setPartFactsRefreshing] = useState(false);
  const [partFactsError, setPartFactsError] = useState<string | null>(null);
  const useCompactAnalysisOverlay =
    chromeDensity === "compact" || analysisFocus?.overlay_variant === "compact";
  const handleFitCaptured = useCallback((snapshot: CameraSnapshot) => {
    setHomeView((previous) => previous ?? snapshot);
  }, []);
  const viewerControlsDisabled = pinMode !== "none";

  useEffect(() => {
    setNavigationMode("rotate");
    setZoomInTrigger(0);
    setZoomOutTrigger(0);
    setHomeTrigger(0);
    setHomeView(null);
  }, [resolvedPreviewUrl]);

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
    if (!showInspectorPanels || !resolvedPreviewUrl || !selectedComponent?.nodeName || !modelId) {
      setPartFacts(null);
      setPartFactsError(null);
      return;
    }
    fetchPartFacts(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedPreviewUrl, selectedComponent?.nodeName, modelId, apiBase, showInspectorPanels]);

  return (
    <section className={`viewer-area ${chromeDensity === "compact" ? "viewer-area--compact" : ""}`}>
      {resolvedPreviewUrl ? (
        <>
          <ViewerErrorBoundary resetKey={resolvedPreviewUrl}>
            <Canvas camera={{ position: [4, 4, 4], fov: 45 }}>
              <ambientLight intensity={0.7} />
              <directionalLight position={[5, 5, 5]} intensity={0.9} />
              <Suspense fallback={null}>
                <ModelContents
                  previewUrl={resolvedPreviewUrl}
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
                  zoomInTrigger={zoomInTrigger}
                  zoomOutTrigger={zoomOutTrigger}
                  homeTrigger={homeTrigger}
                  homeView={homeView}
                  onFitCaptured={handleFitCaptured}
                />
              </Suspense>
              <Environment preset="city" />
              <OrbitControls makeDefault enabled={pinMode === "none"} mouseButtons={orbitMouseButtons} />
              <GizmoHelper alignment="bottom-right" margin={[128, 128]}>
                <GizmoViewport axisColors={["#ef4444", "#22c55e", "#3b82f6"]} labelColor="#0f172a" />
              </GizmoHelper>
            </Canvas>
          </ViewerErrorBoundary>
        </>
      ) : (
        <Placeholder />
      )}
      {resolvedPreviewUrl ? (
        <div
          className={`viewer-nav-controls ${chromeDensity === "compact" ? "viewer-nav-controls--compact" : ""}`}
          role="toolbar"
          aria-label="3D view controls"
        >
          <button
            type="button"
            className={`viewer-nav-controls__button ${navigationMode === "rotate" ? "viewer-nav-controls__button--active" : ""}`}
            onClick={() => setNavigationMode("rotate")}
            aria-pressed={navigationMode === "rotate"}
            aria-label="Rotate mode"
            disabled={viewerControlsDisabled}
          >
            Rotate
          </button>
          <button
            type="button"
            className={`viewer-nav-controls__button ${navigationMode === "pan" ? "viewer-nav-controls__button--active" : ""}`}
            onClick={() => setNavigationMode("pan")}
            aria-pressed={navigationMode === "pan"}
            aria-label="Pan mode"
            disabled={viewerControlsDisabled}
          >
            Pan
          </button>
          <button
            type="button"
            className="viewer-nav-controls__button"
            onClick={() => setZoomInTrigger((prev) => prev + 1)}
            aria-label="Zoom in"
            disabled={viewerControlsDisabled}
          >
            +
          </button>
          <button
            type="button"
            className="viewer-nav-controls__button"
            onClick={() => setZoomOutTrigger((prev) => prev + 1)}
            aria-label="Zoom out"
            disabled={viewerControlsDisabled}
          >
            -
          </button>
          <button
            type="button"
            className="viewer-nav-controls__button"
            onClick={onFitView}
            aria-label="Fit to screen"
            disabled={viewerControlsDisabled}
          >
            Fit
          </button>
          <button
            type="button"
            className="viewer-nav-controls__button"
            onClick={() => setHomeTrigger((prev) => prev + 1)}
            disabled={viewerControlsDisabled || !homeView}
            aria-label="Reset to home view"
          >
            Home
          </button>
        </div>
      ) : null}
      {showViewerOverlay ? <div className={`viewer-overlay ${chromeDensity === "compact" ? "viewer-overlay--compact" : ""}`}>{overlayMessage}</div> : null}
      {resolvedPreviewUrl && analysisFocus ? (
        <div
          className={`analysis-focus-overlay analysis-focus-overlay--${analysisTone(analysisFocus.severity)} ${
            useCompactAnalysisOverlay ? "analysis-focus-overlay--compact" : ""
          }`}
        >
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
      {hasLeftPanels && (
        <div className="viewer-left-panels">
          <section className="assembly-tree assembly-card" aria-label="Assembly tree">
            <header className="assembly-tree__header">
              <div className="assembly-tree__title">
                <h3>Assembly</h3>
                <span className="assembly-tree__count">
                  Visible {visibleComponentCount}/{components.length}
                </span>
              </div>
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
              {visibleComponentCount === 0 ? (
                <div className="assembly-tree__empty">
                  <p>All parts are hidden.</p>
                  <button type="button" onClick={onShowAllComponents}>
                    Show all
                  </button>
                </div>
              ) : null}
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
                  <span className="assembly-tree__item-label" title={component.displayName}>
                    {component.displayName}
                  </span>
                </div>
              ))}
            </div>
          </section>
          {selectedComponent && (
            <>
              <section className="component-profile-panel summary-card" aria-label="Component profile summary">
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
                {profileError ? <p className="component-profile-panel__error">{profileError}</p> : null}
              </section>
              <section className="part-facts-card" aria-label="Part facts">
                <header className="part-facts-card__header">
                  <h4>Part Facts</h4>
                  <button
                    type="button"
                    onClick={() => fetchPartFacts(true)}
                    disabled={partFactsRefreshing || partFactsLoading || !modelId || !selectedComponent?.nodeName}
                  >
                    {partFactsRefreshing ? "Refreshing..." : "Refresh"}
                  </button>
                </header>
                <div className="part-facts-card__body">
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
                </div>
              </section>
            </>
          )}
          {panelStatusMessage ? <div className="viewer-left-panels__status">{panelStatusMessage}</div> : null}
        </div>
      )}
    </section>
  );
};

export default ModelViewer;
