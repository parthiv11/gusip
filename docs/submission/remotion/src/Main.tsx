import { AbsoluteFill, OffthreadVideo, Sequence, staticFile } from "remotion";
import { TitleCard } from "./TitleCard";
import { EndCard } from "./EndCard";
import { CaptionOverlay } from "./CaptionOverlay";
import { RAW_DURATION_SEC } from "./meta";

export const FPS = 30;
export const TITLE_SEC = 3.5;
export const END_SEC = 4;

export const Main: React.FC = () => {
  const titleFrames = Math.round(TITLE_SEC * FPS);
  const videoFrames = Math.round(RAW_DURATION_SEC * FPS);
  const endFrames = Math.round(END_SEC * FPS);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Sequence from={0} durationInFrames={titleFrames}>
        <TitleCard />
      </Sequence>
      <Sequence from={titleFrames} durationInFrames={videoFrames}>
        <AbsoluteFill>
          <OffthreadVideo src={staticFile("walkthrough.mp4")} />
          <CaptionOverlay rawDurationSec={RAW_DURATION_SEC} />
        </AbsoluteFill>
      </Sequence>
      <Sequence from={titleFrames + videoFrames} durationInFrames={endFrames}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
