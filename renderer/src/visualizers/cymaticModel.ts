import { AudioMultibandFeatures, OnsetKind } from "../types/manifest";

/**
 * Cymatic Plate model. Notes choose the vibration pattern of an idealized square free plate,
 *   Z(n, m)(x, y) = cos(n·π·x)·cos(m·π·y) − cos(m·π·x)·cos(n·π·y),   x, y in [0, 1],
 * and sand collects where Z = 0 (the still, "nodal" lines). Chords superpose patterns; hits throw
 * the sand up before it settles. A standard idealization, not a model of a particular plate.
 * Pure functions of the manifest: any frame (seek, parallel worker) gives the same answer.
 */
export const MAX_MODES = 4;
export const MODE_LIMIT = 12;
const PITCH_LOW_HZ = 30;
const PITCH_HIGH_HZ = 1200;
const ATTACK_SECONDS = 0.04;
const RELEASE_SECONDS = 0.16;
const AGITATION_DECAY_SECONDS = 0.35;
const HIT_WEIGHT: Record<OnsetKind, number> = { kick: 1, snare: 0.8, cymbal: 0.35, other: 0.5 };

export interface ModePair { n: number; m: number }

/** All mode pairs n < m, ordered by n² + m² (ideal plate mode frequency order), low to high. */
export const MODE_TABLE: ModePair[] = (() => {
  const all: ModePair[] = [];
  for (let n = 1; n <= MODE_LIMIT; n++) for (let m = n + 1; m <= MODE_LIMIT; m++) all.push({ n, m });
  return all.sort((a, b) => (a.n * a.n + a.m * a.m) - (b.n * b.n + b.m * b.m) || a.n - b.n);
})();

/** Design mapping (monotonic): higher pitch gives a higher-order pattern, so low notes make few large cells. */
export function modeIndexForPitch(hz: number): number {
  const t = (Math.log2(Math.max(hz, 1)) - Math.log2(PITCH_LOW_HZ)) / (Math.log2(PITCH_HIGH_HZ) - Math.log2(PITCH_LOW_HZ));
  return Math.round(Math.max(0, Math.min(1, t)) * (MODE_TABLE.length - 1));
}

export interface CymaticTimeline {
  frameCount: number;
  /** MAX_MODES triples (n, m, weight) per frame */
  modes: Float32Array;
  /** Hit agitation per frame, 0..1.5 */
  agitation: Float32Array;
  /** Pitch of the strongest sounding note per frame, 0 when none */
  dominantHz: Float32Array;
  /** False when the clip has no usable pitch events: the plate reacts to hits only */
  hasNotes: boolean;
}

export function compileCymatic(features: AudioMultibandFeatures, fps: number, frameCount: number): CymaticTimeline {
  const notes = (features.notes ?? []).filter(n => n.pitchHz > 0 && n.endFrame > n.startFrame);
  const targets: Array<Map<number, { w: number; hz: number }>> = Array.from({ length: frameCount }, () => new Map());
  const envelope = (stem: string | undefined, frame: number) => {
    const pick = stem === "vocals" ? features.vocalEnergy : stem === "bass" || stem === "mix-low" ? features.bass : features.mids;
    return pick?.[frame] ?? 0.5;
  };
  for (const note of notes) {
    const index = modeIndexForPitch(note.pitchHz);
    for (let f = Math.max(0, note.startFrame); f < Math.min(frameCount, note.endFrame); f++) {
      const w = Math.max(0, Math.min(1, (note.confidence ?? 0.7) * (0.3 + 0.7 * envelope(note.stem, f))));
      const slot = targets[f].get(index);
      if (!slot || slot.w < w) targets[f].set(index, { w, hz: note.pitchHz });
    }
  }
  const modes = new Float32Array(frameCount * MAX_MODES * 3);
  const dominantHz = new Float32Array(frameCount);
  const agitation = new Float32Array(frameCount);
  const attack = 1 - Math.exp(-1 / (fps * ATTACK_SECONDS));
  const release = 1 - Math.exp(-1 / (fps * RELEASE_SECONDS));
  const weights = new Map<number, number>();
  const pitchOf = new Map<number, number>();
  const hitDecay = Math.exp(-1 / (fps * AGITATION_DECAY_SECONDS));
  const hitsAt = new Map<number, number>();
  for (const o of features.onsets ?? []) hitsAt.set(o.frame, (hitsAt.get(o.frame) ?? 0) + o.strength * HIT_WEIGHT[o.kind]);
  if (!(features.onsets?.length)) for (const f of features.transients) hitsAt.set(f, (hitsAt.get(f) ?? 0) + 0.8);
  let hit = 0;
  for (let f = 0; f < frameCount; f++) {
    for (const [index, slot] of targets[f]) {
      pitchOf.set(index, slot.hz);
      if (!weights.has(index)) weights.set(index, 0);
    }
    for (const [index, w] of Array.from(weights)) {
      const target = targets[f].get(index)?.w ?? 0;
      const next = w + (target - w) * (target > w ? attack : release);
      if (next < 0.01 && target === 0) weights.delete(index); else weights.set(index, next);
    }
    const top = Array.from(weights).sort((a, b) => b[1] - a[1]).slice(0, MAX_MODES);
    top.forEach(([index, w], k) => {
      const base = (f * MAX_MODES + k) * 3;
      modes[base] = MODE_TABLE[index].n; modes[base + 1] = MODE_TABLE[index].m; modes[base + 2] = w;
    });
    dominantHz[f] = top.length && top[0][1] > 0.05 ? (pitchOf.get(top[0][0]) ?? 0) : 0;
    hit = Math.min(1.5, hit * hitDecay + (hitsAt.get(f) ?? 0));
    agitation[f] = hit;
  }
  return { frameCount, modes, agitation, dominantHz, hasNotes: notes.length > 0 };
}

/** The (n, m, weight) triples of one frame, strongest first, zero-weight slots removed. */
export function modesAt(timeline: CymaticTimeline, frame: number): Array<{ n: number; m: number; w: number }> {
  const f = Math.max(0, Math.min(timeline.frameCount - 1, frame));
  const out = [];
  for (let k = 0; k < MAX_MODES; k++) {
    const base = (f * MAX_MODES + k) * 3;
    if (timeline.modes[base + 2] > 0) out.push({ n: timeline.modes[base], m: timeline.modes[base + 1], w: timeline.modes[base + 2] });
  }
  return out;
}

/** Plate displacement at (x, y) for a mode set: the same maths the shader uses. */
export function plateValue(modes: Array<{ n: number; m: number; w: number }>, x: number, y: number): number {
  let z = 0;
  for (const { n, m, w } of modes) {
    z += w * (Math.cos(n * Math.PI * x) * Math.cos(m * Math.PI * y) - Math.cos(m * Math.PI * x) * Math.cos(n * Math.PI * y));
  }
  return z;
}
