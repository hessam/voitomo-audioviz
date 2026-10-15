/**
 * Core Data Contracts for Stem-Aware 3D Audio Visualizer (Audioviz)
 * Incorporates Astra Architectural Guardrails:
 * - Deterministic frame evaluation: timeSeconds = frame * fpsDenominator / fpsNumerator
 * - Immutable Pre-Render Manifest (100% precalculated features before Remotion frame capture)
 */

export type VisualizerPresetId = "sphere" | "orrery" | "cymatic" | "bodies";

export type LyricMode = "off" | "subtitles" | "video";

export type OnsetKind = "kick" | "snare" | "cymbal" | "other";

/** A classified hit. `frame` is the first video frame allowed to show it (never earlier than the sound). */
export interface OnsetEvent {
  frame: number;
  /** 0..1 relative to the strongest onset in the clip */
  strength: number;
  kind: OnsetKind;
}

export interface NoteEvent {
  startFrame: number;
  endFrame: number;
  pitchHz: number;
  stem?: string;
  confidence?: number;
}

/** Repeating pattern length, in subdivision steps (for example 23 sixteenth notes). */
export interface RiffCycle {
  lengthSteps: number;
  stepFrames: number;
  confidence: number;
}

export interface AudioMultibandFeatures {
  /** 30 FPS normalized bass energy array [0.0, 1.0] */
  bass: number[];
  /** 30 FPS normalized mid-frequency energy array [0.0, 1.0] */
  mids: number[];
  /** 30 FPS normalized high/treble energy array [0.0, 1.0] */
  treble: number[];
  /** Frame indices where transient drum kicks or drops occur */
  transients: number[];
  /** Detected musical tempo in BPM; null/undefined when unknown */
  bpm?: number | null;
  /** Exact frame indices of quarter-note beats */
  beatFrames?: number[];
  /** 1st-beat-of-bar downbeats */
  downbeatFrames?: number[];
  /** 30 FPS isolated vocal envelope */
  vocalEnergy?: number[];
  /** 30 FPS isolated drums envelope */
  drumsEnergy?: number[];
  /** 30 FPS structural build-up/drop curve */
  macroEnergy?: number[];
  /** Harmonic key tonality (e.g. "D Minor"); empty when unknown */
  musicalKey?: string;
  /** Where beatFrames came from */
  rhythmSource?: "unknown" | "broker" | "estimated";
  /** True when downbeatFrames is only "every 4th beat", not measured */
  downbeatsAssumed?: boolean;
  /** Beats per bar when measured or estimated */
  meterBeats?: number | null;
  /** Classified hit events */
  onsets?: OnsetEvent[];
  /** Pitched note events (optional) */
  notes?: NoteEvent[];
  /** Repeating riff length, when one was found */
  riffCycle?: RiffCycle | null;
  /** Per-stem spectral bands (frames x 12, 0..1). Only stems that exist are present. */
  bodyBands?: Record<string, number[][]>;
}

export interface LyricWord {
  word: string;
  startFrame: number;
  endFrame: number;
  score?: number;
  isInterpolated?: boolean;
  alignmentSource?: string;
}

export interface LyricLine {
  text: string;
  startFrame: number;
  endFrame: number;
  isHero?: boolean;
  confidence?: number;
  words?: LyricWord[];
}

export interface RenderManifest {
  schemaVersion: 1;
  jobId: string;
  seed: number;
  preset: {
    id: VisualizerPresetId;
    version: string;
    parameters: Record<string, number | string | boolean>;
  };
  video: {
    width: 1080 | 1920;
    height: 1080;
    fpsNumerator: 30;
    fpsDenominator: 1;
    frameCount: number;
  };
  audio: {
    masterUri: string;
    vocalStemUri?: string | null;
    bassStemUri?: string | null;
    sha256: string;
    sampleRate: number;
    features: AudioMultibandFeatures;
  };
  lyrics: {
    lines: LyricLine[];
    /** off: no text; subtitles: lines near the bottom; video: lyrics lead and the style makes room for them */
    mode?: LyricMode;
  };
  environment?: {
    containerDigest?: string;
    threeVersion?: string;
    remotionVersion?: string;
    gpuBackend?: string;
  };
}

export interface VisualReferenceContract {
  presetId: VisualizerPresetId;
  presetVersion: string;
  camera: {
    projection: "perspective" | "orthographic";
    fov: number;
    position: [number, number, number];
    target: [number, number, number];
  };
  composition: {
    width: number;
    height: number;
    fps: number;
    colorSpace: "linear-srgb";
    toneMapping: "ACESFilmic";
    safePaddingPx: number; // 160px safe margin
  };
  goldenFrames: {
    calmTimestampSeconds: number;
    dropTimestampSeconds: number;
    ssimTolerance: number; // >= 0.92
  };
}
