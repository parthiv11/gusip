import { Composition } from "remotion";
import { Main, FPS, TITLE_SEC, END_SEC } from "./Main";
import { RAW_DURATION_SEC } from "./meta";

export const Root: React.FC = () => {
  const totalSec = TITLE_SEC + RAW_DURATION_SEC + END_SEC;
  return (
    <Composition
      id="Main"
      component={Main}
      durationInFrames={Math.round(totalSec * FPS)}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};
