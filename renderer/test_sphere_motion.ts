import assert from "node:assert/strict";
import test from "node:test";
import { compileSphereMotion } from "./src/visualizers/sphereMotion";
import { AudioMultibandFeatures } from "./src/types/manifest";

function signal(): AudioMultibandFeatures {
  return { bass: Array(90).fill(0), mids: Array(90).fill(0), treble: Array(90).fill(0),
    vocalEnergy: Array(90).fill(0), drumsEnergy: Array(90).fill(0), transients: [] };
}

test("silence has no driven displacement or artificial beat shocks", () => {
  const features = signal(); features.beatFrames = [0, 15, 30];
  const motion = compileSphereMotion(features, 30);
  assert.ok(motion.every(m => m.bass === 0 && m.vocal === 0 && m.transient === 0));
});

test("bass impulse attacks immediately and recoils after the source stops", () => {
  const features = signal(); features.bass[10] = 1;
  const motion = compileSphereMotion(features, 30);
  assert.equal(motion[9].bass, 0);
  assert.ok(motion[10].bass > 0.1);
  assert.ok(motion[11].bass > 0.1);
  assert.ok(Math.abs(motion[60].bass) < 0.001);
  assert.ok(motion.every(m => m.vocal === 0));
});

test("sustained vocals accelerate continuous flow without a backwards phase jump", () => {
  const features = signal(); features.vocalEnergy!.fill(1, 10, 30);
  const active = compileSphereMotion(features, 30);
  const silent = compileSphereMotion(signal(), 30);
  assert.ok(active[25].flow - active[15].flow > 3 * (silent[25].flow - silent[15].flow));
  assert.ok(active.slice(1).every((m, i) => m.flow >= active[i].flow));
  assert.ok(active.every(m => m.bass === 0 && m.transient === 0));
});

test("drum attacks launch decaying traveling pulses without requiring beat metadata", () => {
  const features = signal(); features.drumsEnergy![12] = 1;
  const motion = compileSphereMotion(features, 30);
  assert.equal(motion[11].transient, 0);
  assert.ok(motion[12].transient > 0.5);
  assert.equal(motion[12].shockAge, 0);
  assert.ok(motion[15].shockAge > motion[13].shockAge);
  assert.ok(motion[30].transient < motion[13].transient);
});

test("random frame access is reproducible and intensity zero removes driven motion", () => {
  const features = signal(); features.bass.fill(0.7); features.vocalEnergy!.fill(0.8);
  const first = compileSphereMotion(features, 30);
  const second = compileSphereMotion(features, 30);
  for (const frame of [50, 0, 17, 50]) assert.deepEqual(first[frame], second[frame]);
  assert.deepEqual(compileSphereMotion(features, 30, 0), compileSphereMotion(signal(), 30));
});

test("invalid samples stay finite and absent vocal/drum curves use band fallbacks", () => {
  const features = signal(); features.bass[0] = NaN; features.mids.fill(0.5);
  features.vocalEnergy = []; features.drumsEnergy = []; features.transients = [15];
  const motion = compileSphereMotion(features, 30);
  assert.ok(motion[15].vocal > 0 && motion[15].transient > 0);
  assert.ok(motion.every(m => Object.values(m).every(Number.isFinite)));
});
