import { AudioMultibandFeatures, OnsetKind } from "../types/manifest";

/**
 * Resonant Bodies model: each stem is drawn as the kind of object that makes the sound, vibrating in
 * modes whose strength is that stem's own spectrum. A stem that is missing is not drawn, and the full
 * mix only appears (named "mix") when there are no stems at all. Pure functions of the manifest.
 */
export const MODE_COUNT = 12;
export type BodyKind = "string" | "heavyString" | "skin" | "column";

export interface Body {
  stem: string;
  kind: BodyKind;
  label: string;
  /** frames x MODE_COUNT, 0..1 */
  bands: number[][];
  /** Strike strength per frame (a pluck or a hit), 0..1.5 */
  strike: Float32Array;
  /** Strike decay time in seconds */
  decaySeconds: number;
}

export interface BodiesModel {
  fps: number;
  frameCount: number;
  bodies: Body[];
  /** True when only the full mix was available */
  mixOnly: boolean;
}

const KINDS: Record<string, { kind: BodyKind; label: string; order: number; decay: number }> = {
  bass: { kind: "heavyString", label: "BASS · HEAVY STRING", order: 0, decay: 0.9 },
  drums: { kind: "skin", label: "DRUMS · SKIN", order: 1, decay: 0.35 },
  vocals: { kind: "column", label: "VOCALS · AIR COLUMN", order: 2, decay: 0.5 },
  guitar: { kind: "string", label: "GUITAR · STRING", order: 3, decay: 0.7 },
  other: { kind: "string", label: "OTHER · STRING", order: 4, decay: 0.7 },
  instrumental: { kind: "string", label: "MUSIC · STRING", order: 5, decay: 0.7 },
  mix: { kind: "string", label: "FULL MIX · STRING", order: 6, decay: 0.6 },
};
const STRIKE_CAP = 1.5;
const HIT_FOR_SKIN: Record<OnsetKind, number> = { kick: 1, snare: 0.9, cymbal: 0.3, other: 0.5 };

export function compileBodies(features: AudioMultibandFeatures, fps: number, frameCount: number): BodiesModel {
  const present = Object.keys(features.bodyBands ?? {}).filter(stem => KINDS[stem]);
  present.sort((a, b) => KINDS[a].order - KINDS[b].order);
  const bodies: Body[] = present.slice(0, 4).map(stem => {
    const spec = KINDS[stem];
    const strike = new Float32Array(frameCount);
    const decay = Math.exp(-1 / (fps * spec.decay));
    const events = new Map<number, number>();
    if (stem === "drums") {
      for (const o of features.onsets ?? []) events.set(o.frame, (events.get(o.frame) ?? 0) + o.strength * HIT_FOR_SKIN[o.kind]);
    } else if (stem === "bass") {
      for (const n of features.notes ?? []) if (n.stem === "bass" || n.stem === "mix-low") events.set(n.startFrame, Math.max(events.get(n.startFrame) ?? 0, n.confidence ?? 0.7));
    } else if (stem !== "vocals") {
      for (const o of features.onsets ?? []) events.set(o.frame, (events.get(o.frame) ?? 0) + o.strength * 0.5);
    }
    let level = 0;
    for (let f = 0; f < frameCount; f++) {
      level = Math.min(STRIKE_CAP, level * decay + (events.get(f) ?? 0));
      strike[f] = level;
    }
    return { stem, kind: spec.kind, label: spec.label, bands: features.bodyBands![stem], strike, decaySeconds: spec.decay };
  });
  return { fps, frameCount, bodies, mixOnly: bodies.length === 1 && bodies[0].stem === "mix" };
}

/** Visual oscillation rate of mode k (rad/s). Real frequencies are far too fast to see, so they scale with the mode number. */
export const modeRate = (k: number) => 2 * Math.PI * (0.55 + 0.42 * k);

/**
 * Mode amplitudes at `frame`, 0..~1: the stem's spectrum in that band plus a pluck/strike that excites the
 * low modes most (1/(k+1)^2, like a plucked string).
 */
export function modeAmplitudes(body: Body, frame: number): number[] {
  const f = Math.max(0, Math.min(body.bands.length - 1, frame));
  const row = body.bands[f] ?? [];
  const strike = body.strike[Math.min(body.strike.length - 1, Math.max(0, frame))] ?? 0;
  return Array.from({ length: MODE_COUNT }, (_, k) => {
    const spectrum = (row[k] ?? 0) ** 1.4;
    return Math.min(1.4, spectrum + strike / ((k + 1) * (k + 1)) * 2.4);
  });
}

/** Displacement of a string at u in [0,1]: sum of its standing-wave modes. */
export function stringDisplacement(amplitudes: number[], u: number, seconds: number): number {
  let y = 0;
  for (let k = 0; k < amplitudes.length; k++) {
    y += amplitudes[k] * Math.sin((k + 1) * Math.PI * u) * Math.sin(modeRate(k) * seconds + k * 1.7) / (1 + 0.28 * k);
  }
  return y;
}

/** Radial displacement of a drum skin at angle `theta` (angular modes 2..13). */
export function skinDisplacement(amplitudes: number[], theta: number, seconds: number): number {
  let r = 0;
  for (let k = 0; k < amplitudes.length; k++) {
    r += amplitudes[k] * Math.cos((k + 2) * theta + k * 0.9) * Math.sin(modeRate(k) * seconds + k * 2.3) / (1 + 0.45 * k);
  }
  return r;
}
