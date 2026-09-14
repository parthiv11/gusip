import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const in_ = spring({ frame, fps, config: { damping: 200 } });
  const out = interpolate(frame, [durationInFrames - 15, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = in_ * out;
  const rise = interpolate(in_, [0, 1], [18, 0]);

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
        <p
          style={{
            letterSpacing: ".28em",
            textTransform: "uppercase",
            font: "600 15px system-ui, sans-serif",
            color: "#c9a227",
            margin: "0 0 20px",
          }}
        >
          Gujarat Police Innovation Challenge 2026
        </p>
        <h1 style={{ fontSize: 76, margin: "0 0 14px", fontWeight: 600, letterSpacing: "0.02em" }}>GUSIP</h1>
        <p style={{ font: "22px/1.5 system-ui, sans-serif", color: "#d9ccb0", maxWidth: "38em", margin: "0 auto" }}>
          One wall. The cameras stay where they are.
          <br />
          Official Sentinel feeds + stolen Fortuner GJ 01 ST 0001.
        </p>
      </div>
    </AbsoluteFill>
  );
};
