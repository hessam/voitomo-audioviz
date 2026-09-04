import React from "react";
import { Composition } from "remotion";
import { VoiceMotion } from "./Composition";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="VoiceMotion"
    component={VoiceMotion}
    durationInFrames={300}
    fps={30}
    width={1080}
    height={1080}
    defaultProps={{
      words: [],
      text: "",
      audioSrc: "",
      profile: "swiss_clean",
      durationInFrames: 300,
    }}
  />
);
