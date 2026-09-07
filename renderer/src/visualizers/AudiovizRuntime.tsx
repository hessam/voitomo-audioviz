import React from "react";
import { AbsoluteFill, Audio } from "remotion";
import { RenderManifest } from "../types/manifest";
import { ParticleSphereVisualizer } from "./ParticleSphereVisualizer";
import { QuantumIrisVisualizer } from "./QuantumIrisVisualizer";
import { NeuralSynapseVisualizer } from "./NeuralSynapseVisualizer";
import { MonolithFieldVisualizer } from "./MonolithFieldVisualizer";
import { TypographyOverlay } from "../components/TypographyOverlay";

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
  const resolvedAudio = audioSrc || manifest?.audio?.masterUri;

  const renderVisualizer = () => {
    switch (presetId) {
      case "iris":
        return <QuantumIrisVisualizer features={features} />;
      case "neural":
        return <NeuralSynapseVisualizer features={features} />;
      case "monolith":
        return <MonolithFieldVisualizer features={features} />;
      case "sphere":
      default:
        return <ParticleSphereVisualizer features={features} />;
    }
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "#030305" }}>
      {/* 1. 3D WebGL Audio-Reactive Canvas */}
      {renderVisualizer()}

      {/* 2. Unified 3-Line Clamped Kinetic Typography Overlay */}
      <TypographyOverlay lines={lyricLines} />

      {/* 3. Audio Track */}
      {resolvedAudio && <Audio src={resolvedAudio} />}
    </AbsoluteFill>
  );
};
