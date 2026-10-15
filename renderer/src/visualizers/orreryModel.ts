import { AudioMultibandFeatures, OnsetKind } from "../types/manifest";

/**
 * Polymeter Orrery model: where every hit sits inside the beat, the bar, and the riff cycle.
 * Pure functions of the manifest, so any frame (seek, parallel worker) gives the same answer.
 * Nothing here is invented: no beats means no bar ring, no cycle means no riff ring.
 */
export const STEPS_PER_BEAT = 4;
const DEFAULT_DECAY_SECONDS: Record<OnsetKind, number> = { kick: 0.55, snare: 0.4, cymbal: 0.9, other: 0.4 };
const MIN_DECAY_SECONDS = 0.12;
const MAX_DECAY_SECONDS = 2.0;
/** Faint residue so the repeating pattern stays readable between hits. */
export const RESIDUE_SECONDS = 12;
export const RESIDUE_LEVEL = 0.22;

export interface OrreryMark {
  frame: number;
  kind: OnsetKind;
  strength: number;
  /** Position inside the beat, 0..1 */
  beatFraction: number;
  /** Position inside the bar, 0..1, or null when there is no bar ring */
  barPosition: number | null;
  /** Position inside the riff cycle, 0..1, or null when there is no riff ring */
  riffPosition: number | null;
}

export interface OrreryModel {
  fps: number;
  frameCount: number;
  beatFrames: number[];
  /** Beats per bar, or null: show only the beat ring */
  beatsPerBar: number | null;
  /** True when the bar length is only "4/4 assumed", not measured */
  barAssumed: boolean;
  /** Beat index (modulo beatsPerBar) at which the bar starts */
  barPhaseBeat: number;
  riff: { lengthSteps: number; phaseSteps: number; confidence: number } | null;
  decaySeconds: Record<OnsetKind, number>;
  marks: OrreryMark[];
  /** False when no beat grid exists: the rings free-run and the scene says so */
  synced: boolean;
}

const mod = (a: number, n: number) => ((a % n) + n) % n;

/** Continuous beat index at `frame`. Extrapolates with the nearest beat interval outside the grid. */
export function beatPosition(beatFrames: number[], frame: number): number {
  const n = beatFrames.length;
  if (n === 0) return NaN;
  if (n === 1) return (frame - beatFrames[0]) / 15;
  if (frame <= beatFrames[0]) return (frame - beatFrames[0]) / (beatFrames[1] - beatFrames[0]);
  if (frame >= beatFrames[n - 1]) return n - 1 + (frame - beatFrames[n - 1]) / (beatFrames[n - 1] - beatFrames[n - 2]);
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (beatFrames[mid] <= frame) lo = mid; else hi = mid;
  }
  return lo + (frame - beatFrames[lo]) / (beatFrames[hi] - beatFrames[lo]);
}

export function barPosition(model: OrreryModel, frame: number): number | null {
  if (!model.synced || model.beatsPerBar === null) return null;
  return mod((beatPosition(model.beatFrames, frame) - model.barPhaseBeat) / model.beatsPerBar, 1);
}

export function riffPosition(model: OrreryModel, frame: number): number | null {
  if (!model.synced || !model.riff) return null;
  const steps = beatPosition(model.beatFrames, frame) * STEPS_PER_BEAT - model.riff.phaseSteps;
  return mod(steps / model.riff.lengthSteps, 1);
}

export function beatFraction(model: OrreryModel, frame: number): number {
  if (!model.synced) return mod(frame / (model.fps * 0.5), 1);
  return mod(beatPosition(model.beatFrames, frame), 1);
}

/** Median time (seconds) for the drums envelope to fall to 1/e of its post-hit peak, per kind. */
export function measureDecay(drums: number[] | undefined, onsets: { frame: number; kind: OnsetKind }[], fps: number):
  Record<OnsetKind, number> {
  const out = { ...DEFAULT_DECAY_SECONDS };
  if (!drums?.length) return out;
  const byKind: Record<string, number[]> = {};
  for (const o of onsets) {
    let peak = 0, peakAt = o.frame;
    for (let f = o.frame; f < Math.min(drums.length, o.frame + 4); f++) {
      if (drums[f] > peak) { peak = drums[f]; peakAt = f; }
    }
    if (peak < 0.2) continue;
    let f = peakAt;
    while (f < drums.length - 1 && drums[f] > peak / Math.E && f - peakAt < fps * MAX_DECAY_SECONDS) f++;
    (byKind[o.kind] ||= []).push((f - peakAt) / fps);
  }
  for (const kind of Object.keys(byKind)) {
    const values = byKind[kind].sort((a, b) => a - b);
    if (values.length >= 3) {
      out[kind as OnsetKind] = Math.max(MIN_DECAY_SECONDS, Math.min(MAX_DECAY_SECONDS, values[values.length >> 1]));
    }
  }
  return out;
}

export function compileOrrery(features: AudioMultibandFeatures, fps: number, frameCount: number): OrreryModel {
  const beatFrames = (features.beatFrames ?? []).slice();
  const synced = beatFrames.length >= 4;
  let beatsPerBar: number | null = null;
  let barAssumed = false;
  if (synced && features.meterBeats) {
    beatsPerBar = features.meterBeats;
  } else if (synced && features.downbeatsAssumed && (features.downbeatFrames?.length ?? 0) > 0) {
    beatsPerBar = 4;
    barAssumed = true;
  }
  let barPhaseBeat = 0;
  if (synced && beatsPerBar !== null && features.downbeatFrames?.length) {
    const first = features.downbeatFrames[0];
    let nearest = 0;
    for (let i = 1; i < beatFrames.length; i++) {
      if (Math.abs(beatFrames[i] - first) < Math.abs(beatFrames[nearest] - first)) nearest = i;
    }
    barPhaseBeat = mod(nearest, beatsPerBar);
  }
  const onsets = features.onsets ?? [];
  const model: OrreryModel = {
    fps, frameCount, beatFrames, beatsPerBar, barAssumed, barPhaseBeat, riff: null,
    decaySeconds: measureDecay(features.drumsEnergy, onsets, fps), marks: [], synced,
  };
  if (synced && features.riffCycle && features.riffCycle.lengthSteps > STEPS_PER_BEAT) {
    // Phase: the step position where hits cluster most, so the cycle "starts" on its strongest step.
    const length = features.riffCycle.lengthSteps;
    const bins = new Array(length).fill(0);
    for (const o of onsets) {
      bins[Math.round(mod(beatPosition(beatFrames, o.frame) * STEPS_PER_BEAT, length)) % length] += o.strength;
    }
    model.riff = { lengthSteps: length, phaseSteps: bins.indexOf(Math.max(...bins)), confidence: features.riffCycle.confidence };
  }
  model.marks = onsets.map(o => ({
    frame: o.frame, kind: o.kind, strength: o.strength,
    beatFraction: beatFraction(model, o.frame),
    barPosition: barPosition(model, o.frame),
    riffPosition: riffPosition(model, o.frame),
  }));
  return model;
}

/** Visible intensity of a mark at `frame`: a hit flash that decays at the measured release, plus faint residue. */
export function markLevel(model: OrreryModel, mark: OrreryMark, frame: number): number {
  const age = (frame - mark.frame) / model.fps;
  if (age < 0) return 0;
  const flash = Math.exp(-age / model.decaySeconds[mark.kind]);
  const residue = RESIDUE_LEVEL * Math.exp(-age / (RESIDUE_SECONDS / 3));
  return mark.strength * Math.min(1, flash + (age < RESIDUE_SECONDS ? residue : 0));
}

/** Marks that can still be visible at `frame` (a window of the sorted mark list). */
export function visibleMarks(model: OrreryModel, frame: number): OrreryMark[] {
  const marks = model.marks;
  let lo = 0, hi = marks.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (marks[mid].frame <= frame) lo = mid + 1; else hi = mid; }
  const oldest = frame - RESIDUE_SECONDS * model.fps;
  let start = lo;
  while (start > 0 && marks[start - 1].frame >= oldest) start--;
  return marks.slice(start, lo);
}
