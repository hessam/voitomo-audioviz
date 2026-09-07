import React from "react";
import { Composition } from "remotion";
import "./fonts.css";
import { AudiovizRuntime, AudiovizRuntimeProps } from "./visualizers/AudiovizRuntime";
import { ParticleSphereVisualizer } from "./visualizers/ParticleSphereVisualizer";
import { QuantumIrisVisualizer } from "./visualizers/QuantumIrisVisualizer";
import { NeuralSynapseVisualizer } from "./visualizers/NeuralSynapseVisualizer";
import { MonolithFieldVisualizer } from "./visualizers/MonolithFieldVisualizer";

const defaultEmptyFeatures = {
  bass: new Array(300).fill(0.2),
  mids: new Array(300).fill(0.3),
  treble: new Array(300).fill(0.1),
  transients: [30, 90, 150, 210, 270],
};

const defaultEmptyManifest: any = {
  schemaVersion: 1,
  jobId: "demo-preview",
  seed: 42,
  preset: {
    id: "sphere",
    version: "1.0.0",
    parameters: {},
  },
  video: {
    width: 1080,
    height: 1080,
    fpsNumerator: 30,
    fpsDenominator: 1,
    frameCount: 300,
  },
  audio: {
    masterUri: "",
    sha256: "preview-demo",
    sampleRate: 44100,
    features: defaultEmptyFeatures,
  },
  lyrics: {
    lines: [
      { text: "فرکانس‌های صوتی در مدار کوانتومی", startFrame: 15, endFrame: 85 },
      { text: "سفر در کیهان با ضرباهنگ موسیقی", startFrame: 90, endFrame: 160 },
      { text: "همگام‌سازی امواج و تجسم سه بعدی", startFrame: 165, endFrame: 260 },
    ],
  },
};

export const RemotionRoot: React.FC = () => (
  <>
    {/* Master Audioviz Composition driven by Manifest */}
    <Composition
      id="AudiovizMaster"
      component={AudiovizRuntime as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        manifest: defaultEmptyManifest,
      }}
    />

    {/* Style 1: Particle Sphere */}
    <Composition
      id="ParticleSphereViz"
      component={ParticleSphereVisualizer as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        features: defaultEmptyFeatures,
      }}
    />

    {/* Style 2: Quantum Iris */}
    <Composition
      id="QuantumIrisViz"
      component={QuantumIrisVisualizer as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        features: defaultEmptyFeatures,
      }}
    />

    {/* Style 3: Neural Synapse */}
    <Composition
      id="NeuralSynapseViz"
      component={NeuralSynapseVisualizer as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        features: defaultEmptyFeatures,
      }}
    />

    {/* Style 4: Monolith Field */}
    <Composition
      id="MonolithFieldViz"
      component={MonolithFieldVisualizer as any}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1080}
      defaultProps={{
        features: defaultEmptyFeatures,
      }}
    />
  </>
);
