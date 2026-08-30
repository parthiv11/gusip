import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

type Dir = "horizontal" | "vertical";

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

function readStored(key: string | undefined, fallback: number) {
  if (!key) return fallback;
  try {
    const raw = localStorage.getItem(key);
    const n = raw ? Number(raw) : NaN;
    return Number.isFinite(n) ? n : fallback;
  } catch {
    return fallback;
  }
}

export default function SplitPane({
  direction = "horizontal",
  defaultSize = 70,
  min = 28,
  max = 82,
  storageKey,
  stacked = false,
  children,
}: {
  direction?: Dir;
  defaultSize?: number;
  min?: number;
  max?: number;
  storageKey?: string;
  stacked?: boolean;
  children: [ReactNode, ReactNode];
}) {
  const [first, second] = children;
  const [size, setSize] = useState(() => clamp(readStored(storageKey, defaultSize), min, max));
  const [dragging, setDragging] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const startRef = useRef({ pos: 0, size: 0, span: 1 });
  const horizontal = direction === "horizontal";

  const persist = useCallback(
    (next: number) => {
      const value = clamp(next, min, max);
      setSize(value);
      if (storageKey) localStorage.setItem(storageKey, String(Math.round(value * 10) / 10));
    },
    [min, max, storageKey]
  );

  useEffect(() => {
    if (!dragging) return;
    const cls = horizontal ? "gusip-resizing-col" : "gusip-resizing-row";
    document.body.classList.add(cls);
    const move = (ev: PointerEvent) => {
      const { pos, size: startSize, span } = startRef.current;
      const now = horizontal ? ev.clientX : ev.clientY;
      persist(startSize + ((now - pos) / span) * 100);
    };
    const up = () => {
      setDragging(false);
      window.dispatchEvent(new Event("resize"));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      document.body.classList.remove(cls);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [dragging, horizontal, persist]);

  if (stacked) {
    return (
      <div className="flex flex-col gap-2 min-h-0 flex-1">
        <div className="min-h-[220px] shrink-0">{first}</div>
        <div className="min-h-[200px] flex-1 min-h-0">{second}</div>
      </div>
    );
  }

  return (
    <div
      ref={boxRef}
      className={`flex-1 min-h-0 min-w-0 flex ${horizontal ? "flex-row" : "flex-col"}`}
    >
      <div
        className="min-h-0 min-w-0 overflow-hidden flex flex-col"
        style={horizontal ? { width: `${size}%` } : { height: `${size}%` }}
      >
        <div className="flex-1 min-h-0 min-w-0 flex flex-col">{first}</div>
      </div>
      <button
        type="button"
        aria-label="Resize panels"
        aria-orientation={horizontal ? "vertical" : "horizontal"}
        role="separator"
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={Math.round(size)}
        className={`group shrink-0 z-10 ${
          horizontal ? "w-2 cursor-col-resize" : "h-2 cursor-row-resize"
        } flex items-center justify-center bg-transparent`}
        onPointerDown={(ev) => {
          ev.preventDefault();
          const rect = boxRef.current?.getBoundingClientRect();
          startRef.current = {
            pos: horizontal ? ev.clientX : ev.clientY,
            size,
            span: Math.max(1, horizontal ? rect?.width ?? 1 : rect?.height ?? 1),
          };
          setDragging(true);
          (ev.currentTarget as HTMLButtonElement).setPointerCapture(ev.pointerId);
        }}
        onDoubleClick={() => persist(defaultSize)}
        onKeyDown={(ev) => {
          const step = ev.shiftKey ? 6 : 2;
          if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
            ev.preventDefault();
            persist(size - step);
          }
          if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
            ev.preventDefault();
            persist(size + step);
          }
          if (ev.key === "Home") persist(min);
          if (ev.key === "End") persist(max);
        }}
      >
        <span
          className={`rounded-full transition-colors ${
            horizontal ? "h-8 w-0.5" : "w-8 h-0.5"
          } ${dragging ? "bg-brass-400" : "bg-white/20 group-hover:bg-brass-400/80 group-focus-visible:bg-brass-400"}`}
        />
      </button>
      <div className="flex-1 min-h-0 min-w-0 overflow-hidden flex flex-col">
        <div className="flex-1 min-h-0 min-w-0 flex flex-col">{second}</div>
      </div>
    </div>
  );
}
