import React from "react";
import { AbsoluteFill, Audio } from "remotion";
import { RenderManifest } from "../types/manifest";
import { ParticleSphereVisualizer } from "./ParticleSphereVisualizer";
import { PolymeterOrreryVisualizer } from "./PolymeterOrreryVisualizer";
import { CymaticPlateVisualizer } from "./CymaticPlateVisualizer";
import { ResonantBodiesVisualizer } from "./ResonantBodiesVisualizer";
import { LyricLayer } from "../components/LyricLayer";

export interface AudiovizRuntimeProps {
  manifest: RenderManifest;
  audioSrc?: string;
}

export const AudiovizRuntime: React.FC<AudiovizRuntimeProps> = ({ manifest, audioSrc }) => {
  const presetId = manifest?.preset?.id || "sphere";
  const features = manifest?.audio?.features || {
    bass: [],
    mids: [],
    treble: [],
    transients: [],
  };
  const lyricLines = manifest?.lyrics?.lines || [];
  const lyricMode = manifest?.lyrics?.mode ?? "subtitles";
  // The Orrery keeps a clear disc in the middle for lyric-video text; every other style uses the lower band.
  const lyricRegion = presetId === "orrery" && lyricMode === "video" ? "center" : "bottom";
  const resolvedAudio = audioSrc || manifest?.audio?.masterUri;

  const renderVisualizer = () => {
    switch (presetId) {
      case "orrery":
        return <PolymeterOrreryVisualizer features={features} />;
      case "cymatic":
        return <CymaticPlateVisualizer features={features} />;
      case "bodies":
        return <ResonantBodiesVisualizer features={features} />;
      case "sphere":
      default:
        return <ParticleSphereVisualizer features={features} />;
    }
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "#030305" }}>
      {/* 1. 3D WebGL Audio-Reactive Canvas */}
      {renderVisualizer()}

      {/* 2. Shared Persian lyric layer: off, subtitles, or lyric video */}
      <LyricLayer lines={lyricLines} mode={lyricMode} region={lyricRegion} />

      {/* 3. Audio Track */}
      {resolvedAudio && <Audio src={resolvedAudio} />}
    </AbsoluteFill>
  );
};
