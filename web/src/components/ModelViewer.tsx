import { Suspense, useEffect, useRef } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { Center, Environment, GizmoHelper, GizmoViewport, OrbitControls } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Box3, Object3D, Vector2, Vector3 } from "three";
import ReviewPins from "./ReviewPins";
import type { PinPosition, PinnedItem } from "../types/review";

type ModelViewerProps = {
  previewUrl: string | null;
  message?: string;
  onCreateDrawing?: () => void;
  fitTrigger: number;
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
};

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
}) => {
  const gltf = useLoader(GLTFLoader, previewUrl);
  const camera = useThree((state) => state.camera);
  const raycaster = useThree((state) => state.raycaster);
  const gl = useThree((state) => state.gl);
  const controls = useThree((state) => state.controls) as { target: Vector3; update: () => void; enabled: boolean } | null;
  const flyRef = useRef<{
    startPos: Vector3;
    startTarget: Vector3;
    endPos: Vector3;
    endTarget: Vector3;
    startTime: number;
    duration: number;
  } | null>(null);

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
    </>
  );
};

const Placeholder = () => <div className="viewer__placeholder" />;

const ModelViewer = ({
  previewUrl,
  message,
  onCreateDrawing,
  fitTrigger,
  items = [],
  selectedItemId = null,
  onSelectTicket = () => undefined,
  pinMode = "none",
  showReviewCards = true,
  onCommentPin,
  onReviewPin,
}: ModelViewerProps) => {
  const overlayMessage = message ?? (previewUrl ? "Loading preview..." : "Import a STEP file to begin.");

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
      {previewUrl && (
        <button className="viewer__create-drawing" onClick={onCreateDrawing}>
          Create Drawing
        </button>
      )}
      <div className="viewer__title">RapidDraft</div>
    </section>
  );
};

export default ModelViewer;
