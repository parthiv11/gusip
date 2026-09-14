import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = spring({ frame, fps, config: { damping: 200 } });
  const rise = interpolate(opacity, [0, 1], [18, 0]);

  return (
    <AbsoluteFill
      style={{
        background: "#0a0704",
        fontFamily: "Georgia, serif",
        color: "#f4e6c0",
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        opacity,
      }}
    >
      <div style={{ transform: `translateY(${rise}px)` }}>
        <h1 style={{ fontSize: 52, margin: "0 0 18px", fontWeight: 600 }}>Video stays on the NVR.</h1>
        <p style={{ font: "22px/1.5 system-ui, sans-serif", color: "#d9ccb0", maxWidth: "34em", margin: "0 auto" }}>
          Hits, stills, and the GIS line come here.
          <br />
          <span style={{ color: "#c9a227", fontWeight: 600 }}>localhost:8080</span> · operator / GUSIP@ops2026
        </p>
      </div>
    </AbsoluteFill>
  );
};
