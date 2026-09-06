import React from "react";
import { Composition } from "remotion";
import "./fonts.css";
import { VoiceMotion, DirectorProps } from "./Composition";
import { SwissRuntime, SwissRuntimeProps } from "./runtime/SwissRuntime";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="VoiceMotion"
      component={VoiceMotion as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        words: [],
        audioSrc: "",
        profile: "swiss_clean",
        durationInFrames: 300,
      }}
    />
    <Composition
      id="VoitomoSwiss"
      component={SwissRuntime as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        audioSrc: "",
      }}
    />
  </>
);

