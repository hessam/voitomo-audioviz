import assert from "node:assert/strict";
import test from "node:test";
import { compileBodies, modeAmplitudes, stringDisplacement, MODE_COUNT } from "./src/visualizers/bodiesModel";
import { AudioMultibandFeatures } from "./src/types/manifest";

const FPS = 30;
const rows = (frames: number, fill: number[]) => Array.from({ length: frames }, () => fill.slice());
function features(over: Partial<AudioMultibandFeatures> = {}, frames = 120): AudioMultibandFeatures {
  return { bass: Array(frames).fill(0), mids: Array(frames).fill(0), treble: Array(frames).fill(0), transients: [], ...over };
}
const flat = (v: number) => Array(MODE_COUNT).fill(v);

test("only stems that exist get a body, in a fixed order", () => {
  const f = features({ bodyBands: { vocals: rows(120, flat(0.2)), bass: rows(120, flat(0.2)), drums: rows(120, flat(0.2)) } });
  const m = compileBodies(f, FPS, 120);
  assert.deepEqual(m.bodies.map(b => b.stem), ["bass", "drums", "vocals"]);
  assert.equal(m.mixOnly, false);
});

test("a mix-only clip is labelled as the full mix, never as a separated stem", () => {
  const m = compileBodies(features({ bodyBands: { mix: rows(120, flat(0.3)) } }), FPS, 120);
  assert.equal(m.mixOnly, true);
  assert.match(m.bodies[0].label, /FULL MIX/);
});

test("no spectra at all means no bodies", () => {
  assert.equal(compileBodies(features(), FPS, 120).bodies.length, 0);
});

test("a muted stem removes exactly its own body", () => {
  const all = { bass: rows(120, flat(0.2)), drums: rows(120, flat(0.2)), vocals: rows(120, flat(0.2)), other: rows(120, flat(0.2)) };
  const { drums, ...rest } = all;
  assert.deepEqual(compileBodies(features({ bodyBands: rest }), FPS, 120).bodies.map(b => b.stem), ["bass", "vocals", "other"]);
});

test("a drum hit strikes the skin at the hit frame, never before, and rings down at its decay", () => {
  const f = features({ bodyBands: { drums: rows(120, flat(0)) }, onsets: [{ frame: 40, strength: 1, kind: "kick" }] });
  const drums = compileBodies(f, FPS, 120).bodies[0];
  assert.equal(drums.strike[39], 0);
  assert.ok(drums.strike[40] >= 0.99);
  assert.ok(drums.strike[55] < drums.strike[41]);
  assert.ok(modeAmplitudes(drums, 40)[0] > 0.5);
  assert.equal(modeAmplitudes(drums, 39)[0], 0);
});

test("a bass note plucks the string at its start frame; vocals are never plucked", () => {
  const f = features({ bodyBands: { bass: rows(120, flat(0)), vocals: rows(120, flat(0)) },
    notes: [{ startFrame: 20, endFrame: 60, pitchHz: 55, stem: "bass", confidence: 0.8 }] });
  const m = compileBodies(f, FPS, 120);
  const bass = m.bodies.find(b => b.stem === "bass")!, vocals = m.bodies.find(b => b.stem === "vocals")!;
  assert.equal(bass.strike[19], 0);
  assert.ok(bass.strike[20] > 0.7);
  assert.ok(Math.max(...vocals.strike) === 0);
});

test("bright, distorted spectra bend the string into a rougher shape than a clean low one", () => {
  const clean = flat(0).map((_, k) => (k === 0 ? 0.9 : 0.02)), harsh = flat(0.7);
  const rough = (bands: number[]) => {
    const body = compileBodies(features({ bodyBands: { other: rows(120, bands) } }), FPS, 120).bodies[0];
    const amps = modeAmplitudes(body, 60);
    let total = 0, prev = stringDisplacement(amps, 0, 1);
    for (let i = 1; i <= 200; i++) { const y = stringDisplacement(amps, i / 200, 1); total += Math.abs(y - prev); prev = y; }
    return total;
  };
  assert.ok(rough(harsh) > 2 * rough(clean));
});

test("displacement is a pure function of frame and time", () => {
  const body = compileBodies(features({ bodyBands: { other: rows(120, flat(0.4)) } }), FPS, 120).bodies[0];
  const a = stringDisplacement(modeAmplitudes(body, 50), 0.37, 1.7), b = stringDisplacement(modeAmplitudes(body, 50), 0.37, 1.7);
  assert.equal(a, b);
});
