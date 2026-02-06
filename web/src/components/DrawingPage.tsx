import React, { useEffect, useRef, useState } from "react";
import { DrawingZone as Zone, Dimension } from "../App";

type Props = {
  zones: Zone[];
  onSelectZone: (id: string) => void;
  onUpdateZone: (id: string, layout: { x: number; y: number; w: number; h: number }) => void;
  onCreateZone: (layout: { x: number; y: number; w: number; h: number }) => void;
  onBack: () => void;
  onExport: (format?: string) => void;
  dimensions: Dimension[];
  onAddDimension: (d: Dimension) => void;
  onDeleteDimension: (id: string) => void;
  onUndoLastDimension: () => void;
  onDeleteZone: (id: string) => void;
  pendingZone?: string | null;
  templateUrl?: string | null;
};

const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000";

const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max);

const DrawingPage = ({
  zones,
  onSelectZone,
  onUpdateZone,
  onCreateZone,
  onBack,
  onExport,
  onAddDimension,
  onDeleteDimension,
  onUndoLastDimension,
  onDeleteZone,
  dimensions,
  pendingZone,
  templateUrl: externalTemplateUrl,
}: Props) => {
  const [localTemplateUrl, setLocalTemplateUrl] = useState<string | null>(null);
  const templateUrl = externalTemplateUrl ?? localTemplateUrl;
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [editLayout, setEditLayout] = useState(false);
  const [inserting, setInserting] = useState(false);
  const [draftRect, setDraftRect] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [dragState, setDragState] = useState<{
    zone: string;
    mode: "move" | "resize";
    startX: number;
    startY: number;
    origin: { x: number; y: number; w: number; h: number };
  } | null>(null);
  const [measureMode, setMeasureMode] = useState(false);
  const [imageSizes, setImageSizes] = useState<Record<string, { w: number; h: number }>>({});
  const [overlaySizes, setOverlaySizes] = useState<Record<string, { w: number; h: number }>>({});
  const [metadataCache, setMetadataCache] = useState<Record<string, { points: SnapPoint[] }>>({});
  const [measureState, setMeasureState] = useState<{
    zoneId?: string;
    first?: SnapPoint;
    second?: SnapPoint;
    hover?: SnapPoint;
    firstPx?: [number, number];
    secondPx?: [number, number];
    hoverPx?: [number, number];
    rect?: { w: number; h: number };
    distance?: number;
  }>({});
  const [selectedDimId, setSelectedDimId] = useState<string | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);

  const loadImage = (src: string) =>
    new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = (e) => reject(e);
      img.src = src;
    });

  type SnapPoint = { norm: [number, number]; world: [number, number]; kind: "vertex" | "midpoint" };

  const parseMetadata = (raw: any): { points: SnapPoint[] } => {
    if (!raw) return { points: [] };
    const bounds = raw.bounds;
    const min = bounds?.min ?? [0, 0];
    const max = bounds?.max ?? [1, 1];
    const span = [max[0] - min[0], max[1] - min[1]];

    const toWorld = (norm: [number, number]): [number, number] => [min[0] + norm[0] * span[0], min[1] + norm[1] * span[1]];

    const points: SnapPoint[] = [];
    const seen = new Set<string>();
    const addPoint = (norm: [number, number], kind: "vertex" | "midpoint") => {
      const key = `${norm[0].toFixed(5)},${norm[1].toFixed(5)}`;
      if (seen.has(key)) return;
      seen.add(key);
      points.push({ norm, world: toWorld(norm), kind });
    };

    if (raw.projected_vertices) {
      const verts: [number, number][] = raw.projected_vertices;
      verts.forEach((v) => addPoint([v[0], v[1]], "vertex"));
      if (raw.edges) {
        raw.edges.forEach(([a, b]: [number, number]) => {
          const va = verts[a] ?? [0, 0];
          const vb = verts[b] ?? [0, 0];
          addPoint([(va[0] + vb[0]) / 2, (va[1] + vb[1]) / 2], "midpoint");
        });
      }
    } else if (raw.segments) {
      const segments: [[number, number], [number, number]][] = raw.segments;
      segments.forEach(([a, b]) => {
        addPoint([a[0], a[1]], "vertex");
        addPoint([b[0], b[1]], "vertex");
        addPoint([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], "midpoint");
      });
    }

    return { points };
  };

  const ensureMetadata = async (zone: Zone) => {
    if (!zone.metadataUrl) return null;
    if (metadataCache[zone.metadataUrl]) return metadataCache[zone.metadataUrl];
    try {
      const res = await fetch(zone.metadataUrl);
      if (!res.ok) return null;
      const json = await res.json();
      const parsed = parseMetadata(json);
      setMetadataCache((prev) => ({ ...prev, [zone.metadataUrl!]: parsed }));
      return parsed;
    } catch {
      return null;
    }
  };

  type RectLike = { width: number; height: number; left?: number; top?: number };

  const toPx = (norm: [number, number], rect: RectLike, nat?: { w: number; h: number }): [number, number] => {
    const left = rect.left ?? 0;
    const top = rect.top ?? 0;
    if (nat && nat.w > 0 && nat.h > 0) {
      const scale = Math.min(rect.width / nat.w, rect.height / nat.h);
      const drawW = nat.w * scale;
      const drawH = nat.h * scale;
      const offX = (rect.width - drawW) / 2;
      const offY = (rect.height - drawH) / 2;
      return [offX + norm[0] * drawW, offY + norm[1] * drawH];
    }
    return [left + norm[0] * rect.width, top + norm[1] * rect.height];
  };

  const fromClientToNorm = (clientX: number, clientY: number, rect: RectLike, nat?: { w: number; h: number }): { x: number; y: number } => {
    const left = rect.left ?? 0;
    const top = rect.top ?? 0;
    if (nat && nat.w > 0 && nat.h > 0) {
      const scale = Math.min(rect.width / nat.w, rect.height / nat.h);
      const drawW = nat.w * scale;
      const drawH = nat.h * scale;
      const offX = (rect.width - drawW) / 2;
      const offY = (rect.height - drawH) / 2;
      return {
        x: (clientX - left - offX) / drawW,
        y: (clientY - top - offY) / drawH,
      };
    }
    return {
      x: (clientX - left) / rect.width,
      y: (clientY - top) / rect.height,
    };
  };

  const findNearestSnap = (points: SnapPoint[], normX: number, normY: number) => {
    let best: SnapPoint | null = null;
    let bestDist = Infinity;
    points.forEach((p) => {
      const dx = p.norm[0] - normX;
      const dy = p.norm[1] - normY;
      const d = Math.hypot(dx, dy);
      if (d < bestDist) {
        bestDist = d;
        best = p;
      }
    });
    return bestDist <= 0.08 ? best : null; // threshold
  };

  const updateOverlaySize = (zoneId: string, el: HTMLDivElement | null) => {
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setOverlaySizes((prev) => {
      const current = prev[zoneId];
      if (current && current.w === rect.width && current.h === rect.height) return prev;
      return { ...prev, [zoneId]: { w: rect.width, h: rect.height, left: rect.left, top: rect.top } as any };
    });
  };

  const handleExport = async () => {
    if (!templateUrl) {
      alert("Template not loaded yet");
      return;
    }

    try {
      const tmpl = await loadImage(templateUrl);
      const width = tmpl.naturalWidth || tmpl.width || 2480;
      const height = tmpl.naturalHeight || tmpl.height || 1754;

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas unsupported");

      ctx.drawImage(tmpl, 0, 0, width, height);

      for (const zone of zones) {
        if (!zone.src) continue;
        const { x, y, w, h } = zone.layout;
        try {
          const zoneImg = await loadImage(zone.src);
          const px = x * width;
          const py = y * height;
          const pw = w * width;
          const ph = h * height;
          const scale = Math.min(pw / zoneImg.width, ph / zoneImg.height);
          const drawW = zoneImg.width * scale;
          const drawH = zoneImg.height * scale;
          const dx = px + (pw - drawW) / 2;
          const dy = py + (ph - drawH) / 2;
          ctx.drawImage(zoneImg, dx, dy, drawW, drawH);

          // draw dimensions for this zone
          const zoneDims = dimensions.filter((d) => d.zoneId === zone.id);
          zoneDims.forEach((d) => {
            const aPx = [dx + d.a.norm[0] * drawW, dy + d.a.norm[1] * drawH];
            const bPx = [dx + d.b.norm[0] * drawW, dy + d.b.norm[1] * drawH];
            const vx = bPx[0] - aPx[0];
            const vy = bPx[1] - aPx[1];
            const len = Math.max(Math.hypot(vx, vy), 1e-6);
            const offset = 14;
            const orthX = -vy / len;
            const orthY = vx / len;
            const midX = (aPx[0] + bPx[0]) / 2 + orthX * offset;
            const midY = (aPx[1] + bPx[1]) / 2 + orthY * offset;

            ctx.save();
            ctx.strokeStyle = "#0a4db5";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(aPx[0], aPx[1]);
            ctx.lineTo(bPx[0], bPx[1]);
            ctx.stroke();

            ctx.fillStyle = "#0a4db5";
            ctx.beginPath();
            ctx.arc(aPx[0], aPx[1], 3, 0, Math.PI * 2);
            ctx.arc(bPx[0], bPx[1], 3, 0, Math.PI * 2);
            ctx.fill();

            const label = d.label || `${d.distance.toFixed(2)}${d.units ? " " + d.units : ""}`;
            ctx.font = "12px Segoe UI, sans-serif";
            const textMetrics = ctx.measureText(label);
            const padX = 6;
            const padY = 4;
            const boxW = textMetrics.width + padX * 2;
            const boxH = 18;
            const boxX = midX - boxW / 2;
            const boxY = midY - boxH / 2;

            ctx.fillStyle = "rgba(10, 77, 181, 0.12)";
            ctx.strokeStyle = "rgba(10, 77, 181, 0.6)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(boxX, boxY, boxW, boxH, 4);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = "#0a4db5";
            ctx.textBaseline = "middle";
            ctx.textAlign = "center";
            ctx.fillText(label, midX, midY + 0.5);

            ctx.restore();
          });
        } catch (e) {
          console.warn("Failed to load zone image", zone.id, e);
        }
      }

      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `drawing_${Date.now()}.png`;
        a.click();
        URL.revokeObjectURL(url);
      }, "image/png");

      if (onExport) onExport("png");
    } catch (err) {
      console.error(err);
      alert("Failed to export drawing: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  useEffect(() => {
    if (externalTemplateUrl || localTemplateUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/template/drawing`);
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        setLocalTemplateUrl(url);
      } catch (e) {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [externalTemplateUrl, localTemplateUrl]);

  useEffect(
    () => () => {
      if (localTemplateUrl) URL.revokeObjectURL(localTemplateUrl);
    },
    [localTemplateUrl]
  );

  useEffect(() => {
    if (!measureMode) {
      setMeasureState({});
    } else {
      setSelectedDimId(null);
    }
  }, [measureMode]);

  useEffect(() => {
    if (selectedDimId && !dimensions.find((d) => d.id === selectedDimId)) {
      setSelectedDimId(null);
    }
  }, [selectedDimId, dimensions]);

  useEffect(() => {
    const handleMove = (e: PointerEvent) => {
      if (inserting && draftRect && canvasRef.current) {
        const rect = canvasRef.current.getBoundingClientRect();
        setDraftRect((prev) => {
          if (!prev) return prev;
          return { ...prev, x1: (e.clientX - rect.left) / rect.width, y1: (e.clientY - rect.top) / rect.height };
        });
      }

      if (measureMode || !dragState || !canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const dxPct = (e.clientX - dragState.startX) / rect.width;
      const dyPct = (e.clientY - dragState.startY) / rect.height;
      const origin = dragState.origin;
      if (dragState.mode === "move") {
        const x = clamp(origin.x + dxPct, 0, 1 - origin.w);
        const y = clamp(origin.y + dyPct, 0, 1 - origin.h);
        onUpdateZone(dragState.zone, { ...origin, x, y });
      } else {
        const minSize = 0.02;
        const w = clamp(origin.w + dxPct, minSize, 1 - origin.x);
        const h = clamp(origin.h + dyPct, minSize, 1 - origin.y);
        onUpdateZone(dragState.zone, { ...origin, w, h });
      }
    };
    const handleUp = () => {
      if (inserting && draftRect && canvasRef.current) {
        const x0 = clamp(Math.min(draftRect.x0, draftRect.x1), 0, 1);
        const y0 = clamp(Math.min(draftRect.y0, draftRect.y1), 0, 1);
        const x1 = clamp(Math.max(draftRect.x0, draftRect.x1), 0, 1);
        const y1 = clamp(Math.max(draftRect.y0, draftRect.y1), 0, 1);
        const w = clamp(x1 - x0, 0.02, 1);
        const h = clamp(y1 - y0, 0.02, 1);
        onCreateZone({ x: x0, y: y0, w, h });
        setDraftRect(null);
        setInserting(false);
      }
      setDragState(null);
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, [dragState, onUpdateZone, onCreateZone, inserting, draftRect, measureMode]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      if (selectedDimId) {
        onDeleteDimension(selectedDimId);
        setSelectedDimId(null);
        e.preventDefault();
        return;
      }
      if (selectedZoneId) {
        onDeleteZone(selectedZoneId);
        setSelectedZoneId(null);
        setMeasureState({});
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [selectedDimId, selectedZoneId, onDeleteDimension, onDeleteZone]);

  const startDrag = (zoneId: string, mode: "move" | "resize") => (e: React.PointerEvent) => {
    e.stopPropagation();
    if (measureMode || inserting) return;
    if (!editLayout) {
      onSelectZone(zoneId);
      setSelectedZoneId(zoneId);
      return;
    }
    e.preventDefault();
    const zone = zones.find((z) => z.id === zoneId);
    if (!zone) return;
    setDragState({
      zone: zoneId,
      mode,
      startX: e.clientX,
      startY: e.clientY,
      origin: zone.layout,
    });
  };

  const beginInsert = () => {
    setMeasureMode(false);
    setInserting(true);
    setDraftRect(null);
    setEditLayout(false);
  };

  const handleCanvasPointerDown = (e: React.PointerEvent) => {
    if (!inserting || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setDraftRect({ x0: x, y0: y, x1: x, y1: y });
  };

  const distanceBetween = (a: SnapPoint, b: SnapPoint) => {
    const dx = b.world[0] - a.world[0];
    const dy = b.world[1] - a.world[1];
    return Math.hypot(dx, dy);
  };

  const handleMeasureHover = async (zone: Zone, e: React.PointerEvent) => {
    if (!measureMode) return;
    const rectEl = e.currentTarget as HTMLDivElement | null;
    if (!rectEl) return;
    const rectDom = rectEl.getBoundingClientRect();
    const nat = imageSizes[zone.id];
    const rect: RectLike = { width: rectDom.width, height: rectDom.height, left: rectDom.left, top: rectDom.top };
    const clientX = e.clientX;
    const clientY = e.clientY;
    const metadata = await ensureMetadata(zone);
    if (!metadata || metadata.points.length === 0) return;
    const { x, y } = fromClientToNorm(clientX, clientY, rect, nat);
    const snap = findNearestSnap(metadata.points, x, y);
    if (!snap) {
      setMeasureState((prev) => (prev.zoneId === zone.id ? { ...prev, hover: undefined, hoverPx: undefined } : prev));
      return;
    }
    const snapPx = toPx(snap.norm, rect, nat);
    setMeasureState((prev) => ({
      ...prev,
      zoneId: zone.id,
      hover: snap,
      hoverPx: snapPx,
      rect: { w: rect.width, h: rect.height },
    }));
  };

  const handleMeasureClick = async (zone: Zone, e: React.MouseEvent) => {
    if (!measureMode) return;
    e.stopPropagation();
    const rectEl = e.currentTarget as HTMLDivElement | null;
    if (!rectEl) return;
    const rectDom = rectEl.getBoundingClientRect();
    const rect: RectLike = { width: rectDom.width, height: rectDom.height, left: rectDom.left, top: rectDom.top };
    const nat = imageSizes[zone.id];
    const clientX = e.clientX;
    const clientY = e.clientY;
    const metadata = await ensureMetadata(zone);
    if (!metadata || metadata.points.length === 0) return;
    const { x, y } = fromClientToNorm(clientX, clientY, rect, nat);
    const snap = findNearestSnap(metadata.points, x, y);
    if (!snap) return;
    const snapPx = toPx(snap.norm, rect, nat);

    setMeasureState((prev) => {
      // reset if switching zones
      const firstPoint = prev.zoneId === zone.id ? prev.first : undefined;
      if (!firstPoint) {
        return {
          zoneId: zone.id,
          first: snap,
          firstPx: snapPx,
          hover: snap,
          hoverPx: snapPx,
          rect: { w: rect.width, h: rect.height },
          distance: undefined,
          second: undefined,
          secondPx: undefined,
        };
      }
      const distance = distanceBetween(firstPoint, snap);
      const nextState = {
        zoneId: zone.id,
        first: firstPoint,
        firstPx: prev.firstPx,
        second: snap,
        secondPx: snapPx,
        hover: snap,
        hoverPx: snapPx,
        rect: { w: rect.width, h: rect.height },
        distance,
      };
      const newDim: Dimension = {
        id: `dim-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
        zoneId: zone.id,
        a: { norm: firstPoint.norm, world: firstPoint.world },
        b: { norm: snap.norm, world: snap.world },
        distance,
        units: "units",
        scale: 1,
        label: `${distance.toFixed(2)}`,
      };
      onAddDimension(newDim);
      setSelectedDimId(newDim.id);
      return nextState;
    });
  };

  const renderZones = () =>
    zones.map((zone) => {
      const { x, y, w, h } = zone.layout;
      const style = {
        left: `${x * 100}%`,
        top: `${y * 100}%`,
        width: `${w * 100}%`,
        height: `${h * 100}%`,
      };
      const activeMeasure = measureState.zoneId === zone.id && measureState.rect;
      const overlayRectRaw = measureState.zoneId === zone.id && measureState.rect ? measureState.rect : overlaySizes[zone.id];
      const overlayRect: RectLike = overlayRectRaw
        ? { width: overlayRectRaw.w ?? overlayRectRaw.width, height: overlayRectRaw.h ?? overlayRectRaw.height }
        : { width: 100, height: 100 };
      return (
        <div
          key={zone.id}
          className="drawing-zone"
          style={style}
          ref={(el) => updateOverlaySize(zone.id, el)}
          onPointerDown={startDrag(zone.id, "move")}
          onPointerMove={(e) => handleMeasureHover(zone, e)}
          onClick={(e) => handleMeasureClick(zone, e)}
          aria-label={`Zone ${zone.id}`}
        >
          {zone.src ? (
            <img
              src={zone.src}
              alt={zone.id}
              onLoad={(e) => {
                const img = e.currentTarget;
                setImageSizes((prev) => ({ ...prev, [zone.id]: { w: img.naturalWidth, h: img.naturalHeight } }));
              }}
            />
          ) : (
            <span>Click to assign</span>
          )}
          {editLayout && <div className="drawing-zone__handle" onPointerDown={startDrag(zone.id, "resize")} />}
          {overlayRect && (
            <svg className="drawing-measure-overlay" viewBox={`0 0 ${overlayRect.width} ${overlayRect.height}`} aria-hidden>
              {activeMeasure && measureState.firstPx && <circle cx={measureState.firstPx[0]} cy={measureState.firstPx[1]} r={4} className="drawing-measure-point" />}
              {activeMeasure && measureState.secondPx && <circle cx={measureState.secondPx[0]} cy={measureState.secondPx[1]} r={4} className="drawing-measure-point" />}
              {activeMeasure && measureState.hoverPx && <circle cx={measureState.hoverPx[0]} cy={measureState.hoverPx[1]} r={3} className="drawing-measure-hover" />}
              {activeMeasure && measureState.firstPx && measureState.hoverPx && !measureState.secondPx && (
                <line
                  x1={measureState.firstPx[0]}
                  y1={measureState.firstPx[1]}
                  x2={measureState.hoverPx[0]}
                  y2={measureState.hoverPx[1]}
                  className="drawing-measure-line"
                />
              )}
              {activeMeasure && measureState.firstPx && measureState.secondPx && (
                <line
                  x1={measureState.firstPx[0]}
                  y1={measureState.firstPx[1]}
                  x2={measureState.secondPx[0]}
                  y2={measureState.secondPx[1]}
                  className="drawing-measure-line"
                />
              )}
              {dimensions
                .filter((d) => d.zoneId === zone.id)
                .map((d) => {
          const aPx = toPx(d.a.norm, overlayRect, imageSizes[zone.id]);
          const bPx = toPx(d.b.norm, overlayRect, imageSizes[zone.id]);
          const dx = bPx[0] - aPx[0];
          const dy = bPx[1] - aPx[1];
          const len = Math.max(Math.hypot(dx, dy), 1e-6);
                  const offset = 12;
                  const mid = [
                    (aPx[0] + bPx[0]) / 2 + (-dy / len) * offset,
                    (aPx[1] + bPx[1]) / 2 + (dx / len) * offset,
                  ];
                  const isSelected = selectedDimId === d.id;
                  return (
                    <g key={d.id} onClick={() => { setSelectedDimId(d.id); setSelectedZoneId(null); }}>
                      <line x1={aPx[0]} y1={aPx[1]} x2={bPx[0]} y2={bPx[1]} className={isSelected ? "drawing-dim-line drawing-dim-line--selected" : "drawing-dim-line"} />
                      <circle cx={aPx[0]} cy={aPx[1]} r={3} className="drawing-dim-point" />
                      <circle cx={bPx[0]} cy={bPx[1]} r={3} className="drawing-dim-point" />
                      <rect
                        x={mid[0] - 28}
                        y={mid[1] - 12}
                        width={56}
                        height={18}
                        className={isSelected ? "drawing-dim-label drawing-dim-label--selected" : "drawing-dim-label"}
                        rx={3}
                        ry={3}
                      />
                      <text x={mid[0]} y={mid[1]} dominantBaseline="middle" textAnchor="middle" className="drawing-dim-label__text">
                        {d.label || `${d.distance.toFixed(2)}${d.units ? " " + d.units : ""}`}
                      </text>
                    </g>
                  );
                })}
            </svg>
          )}
        </div>
      );
    });

  const renderDraft = () => {
    if (!inserting || !draftRect) return null;
    const x = Math.min(draftRect.x0, draftRect.x1);
    const y = Math.min(draftRect.y0, draftRect.y1);
    const w = Math.abs(draftRect.x1 - draftRect.x0);
    const h = Math.abs(draftRect.y1 - draftRect.y0);
    return (
      <div
        className="drawing-zone drawing-zone--draft"
        style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}
      />
    );
  };

  return (
    <section className="drawing-page">
      <div className="drawing-toolbar">
        <button onClick={onBack}>Back to model view</button>
        <button onClick={() => handleExport()}>Export PNG</button>
        <button onClick={() => setEditLayout((v) => !v)}>{editLayout ? "Done Editing Zones" : "Edit Zones"}</button>
        <button onClick={beginInsert}>{inserting ? "Click and drag to draw zone..." : "Insert Zone"}</button>
        <button onClick={() => setMeasureMode((v) => !v)}>{measureMode ? "Done Measuring" : "Measure"}</button>
        <button onClick={onUndoLastDimension} disabled={dimensions.length === 0}>
          Undo last dim
        </button>
        {measureMode && measureState.distance !== undefined && (
          <span className="drawing__hint">Measured: {measureState.distance.toFixed(2)} (model units)</span>
        )}
        {measureMode && measureState.first && measureState.hover && !measureState.second && (
          <span className="drawing__hint">
            Preview: {distanceBetween(measureState.first, measureState.hover).toFixed(2)} (model units)
          </span>
        )}
        {selectedDimId && (
          <button
            onClick={() => {
              onDeleteDimension(selectedDimId);
              setSelectedDimId(null);
            }}
            className="drawing__delete-dim"
          >
            Delete dimension
          </button>
        )}
        {pendingZone && <span className="drawing__hint">Select a thumbnail to assign to {pendingZone}</span>}
      </div>

      <div
        className={`drawing-canvas${editLayout ? " drawing-canvas--editing" : ""}${inserting ? " drawing-canvas--inserting" : ""}`}
        id="drawing-canvas"
        ref={canvasRef}
        style={templateUrl ? { backgroundImage: `url(${templateUrl})` } : {}}
        onPointerDown={handleCanvasPointerDown}
      >
        {!templateUrl && <div className="drawing-template--loading">Loading template...</div>}
        {renderZones()}
        {renderDraft()}
      </div>
    </section>
  );
};

export default DrawingPage;
