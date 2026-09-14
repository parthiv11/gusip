import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { TIMELINE } from "./meta";

const FADE_SEC = 0.35;

export const CaptionOverlay: React.FC<{ rawDurationSec: number }> = ({ rawDurationSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  let idx = -1;
  for (let i = 0; i < TIMELINE.length; i++) {
    if (TIMELINE[i].t <= t) idx = i;
  }
  if (idx === -1) return null;

  const entry = TIMELINE[idx];
  const windowEnd = idx + 1 < TIMELINE.length ? TIMELINE[idx + 1].t : rawDurationSec;
  const localT = t - entry.t;
  const remaining = windowEnd - t;

  const opacity =
    Math.min(interpolate(localT, [0, FADE_SEC], [0, 1], { extrapolateRight: "clamp" }), 1) *
    Math.min(interpolate(remaining, [0, FADE_SEC], [0, 1], { extrapolateLeft: "clamp" }), 1);
  const rise = interpolate(localT, [0, FADE_SEC], [10, 0], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(20,14,6,0.94)",
          color: "#f4e6c0",
          padding: "20px 46px 26px",
          font: "600 30px/1.35 system-ui, Segoe UI, sans-serif",
          borderTop: "4px solid #c9a227",
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        {entry.label}
      </div>
    </AbsoluteFill>
  );
};
