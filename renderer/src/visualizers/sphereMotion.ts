import { AudioMultibandFeatures } from "../types/manifest";

export interface SphereMotion {
  bass: number;
  mids: number;
  treble: number;
  vocal: number;
  drums: number;
  transient: number;
  shockAge: number;
  flow: number;
  twist: number;
}

/** Bass spring: stiff enough to peak about 2 frames after a hit (was 4), still with a small elastic recoil. */
export const BASS_STIFFNESS = 2500;
export const BASS_DAMPING = 60;
/** A cymbal splash should ripple the surface, not shake it like a kick. */
const CYMBAL_HIT_WEIGHT = 0.5;

const unit = (v: number | undefined) => Number.isFinite(v) ? Math.max(0, Math.min(1, v!)) : 0;

/** Integrate once in timeline order, then sample independently for any rendered frame.
 * This keeps inertial motion identical across seeks and concurrent Chromium workers.
 */
export function compileSphereMotion(features: AudioMultibandFeatures, fps: number, intensity = 1): SphereMotion[] {
  if (!Number.isFinite(fps) || fps <= 0) throw new Error("Sphere motion requires positive fps");
  const gain = Number.isFinite(intensity) ? Math.max(0, Math.min(2, intensity)) : 1;
  const sample = (values: number[] | undefined, frame: number) => unit(unit(values?.[frame]) * gain);
  const count = Math.max(features.bass.length, features.mids.length, features.treble.length,
    features.vocalEnergy?.length || 0, features.drumsEnergy?.length || 0);
  // Hit strength per frame: classified onsets when present, else the bare transient list.
  const hasOnsets = Boolean(features.onsets?.length);
  const hits = new Map<number, number>();
  if (hasOnsets) {
    for (const o of features.onsets!) {
      hits.set(o.frame, Math.max(hits.get(o.frame) ?? 0, unit(o.strength) * (o.kind === "cymbal" ? CYMBAL_HIT_WEIGHT : 1)));
    }
  } else {
    for (const frame of features.transients) hits.set(frame, 1);
  }
  const hasVocals = Boolean(features.vocalEnergy?.length);
  const hasDrums = Boolean(features.drumsEnergy?.length);
  const result: SphereMotion[] = [];
  let bass = 0, velocity = 0, vocal = 0, drums = 0, previousDrums = 0;
  let flow = 0, twist = 0, lastHit = -fps * 10, strength = 0;
  const steps = Math.max(1, Math.ceil(120 / fps));
  const dt = 1 / (fps * steps);
  for (let frame = 0; frame < count; frame++) {
    const target = sample(features.bass, frame);
    // Damped spring: audible attack, a small elastic recoil, then rest.
    for (let step = 0; step < steps; step++) {
      velocity += (BASS_STIFFNESS * (target - bass) - BASS_DAMPING * velocity) * dt;
      bass += velocity * dt;
    }
    const vocalTarget = sample(hasVocals ? features.vocalEnergy : features.mids, frame);
    vocal += (vocalTarget - vocal) * (1 - Math.exp(-1 / (fps * (vocalTarget > vocal ? 0.025 : 0.12))));
    const drumTarget = sample(hasDrums ? features.drumsEnergy : features.bass, frame);
    drums += (drumTarget - drums) * (1 - Math.exp(-1 / (fps * 0.035)));
    const onset = Math.max(0, drumTarget - previousDrums);
    const listed = hits.get(frame);
    const explicitHit = listed === undefined ? 0 : hasOnsets ? unit(listed * gain) : (hasDrums ? drumTarget : unit(gain));
    if ((onset > 0.035 || explicitHit > 0) && frame - lastHit >= fps * 0.065) {
      lastHit = frame;
      strength = unit(Math.max(onset * 3, explicitHit));
    }
    previousDrums = drumTarget;
    const shockAge = (frame - lastHit) / fps;
    // Integrate speed, rather than adding instantaneous energy to a noise phase.
    // A phrase accelerates the flow; its release never rewinds the surface.
    // When singing is present, vocals lead. During instrumental solos, melodic mids smoothly drive flow.
    const currentMids = sample(features.mids, frame);
    const leadMotion = Math.max(vocal, currentMids * 0.75);
    if (frame > 0) {
      flow += (0.22 + leadMotion * 2.8) / fps;
      twist += (vocal * 0.55 + currentMids * 0.25) / fps;
    }
    result.push({ bass: Math.max(-0.08, Math.min(1.08, bass)), vocal, drums,
      mids: currentMids, treble: sample(features.treble, frame),
      transient: strength * Math.exp(-shockAge * 6), shockAge, flow, twist });
  }
  return result;
}
