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
  const events = new Set(features.transients);
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
      velocity += (400 * (target - bass) - 28 * velocity) * dt;
      bass += velocity * dt;
    }
    const vocalTarget = sample(hasVocals ? features.vocalEnergy : features.mids, frame);
    vocal += (vocalTarget - vocal) * (1 - Math.exp(-1 / (fps * (vocalTarget > vocal ? 0.025 : 0.12))));
    const drumTarget = sample(hasDrums ? features.drumsEnergy : features.bass, frame);
    drums += (drumTarget - drums) * (1 - Math.exp(-1 / (fps * 0.035)));
    const onset = Math.max(0, drumTarget - previousDrums);
    const explicitHit = events.has(frame) ? (hasDrums ? drumTarget : unit(gain)) : 0;
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
