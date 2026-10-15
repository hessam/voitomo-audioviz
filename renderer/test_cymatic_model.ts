import assert from "node:assert/strict";
import test from "node:test";
import { MODE_TABLE, MAX_MODES, compileCymatic, modeIndexForPitch, modesAt, plateValue } from "./src/visualizers/cymaticModel";
import { AudioMultibandFeatures } from "./src/types/manifest";

const FPS = 30;
function features(over: Partial<AudioMultibandFeatures> = {}, frames = 300): AudioMultibandFeatures {
  return { bass: Array(frames).fill(0.8), mids: Array(frames).fill(0.5), treble: Array(frames).fill(0), transients: [], ...over };
}

test("higher pitch never maps to a lower-order pattern, and low notes get few large cells", () => {
  let previous = -1;
  for (const hz of [30, 41, 55, 82, 110, 220, 440, 880, 1200]) {
    const order = (i => MODE_TABLE[i].n ** 2 + MODE_TABLE[i].m ** 2)(modeIndexForPitch(hz));
    assert.ok(order >= previous, `${hz} Hz went backwards`);
    previous = order;
  }
  const low = MODE_TABLE[modeIndexForPitch(41)], high = MODE_TABLE[modeIndexForPitch(880)];
  assert.ok(low.n ** 2 + low.m ** 2 < high.n ** 2 + high.m ** 2);
});

test("a note's pattern appears when it starts, never before, and settles after it ends", () => {
  const t = compileCymatic(features({ notes: [{ startFrame: 30, endFrame: 60, pitchHz: 55, stem: "bass", confidence: 0.9 }] }), FPS, 300);
  assert.equal(modesAt(t, 29).length, 0);
  assert.ok(modesAt(t, 30)[0].w > 0);
  assert.ok(modesAt(t, 50)[0].w > modesAt(t, 30)[0].w);
  assert.ok(modesAt(t, 70)[0].w < modesAt(t, 59)[0].w);
  assert.equal(modesAt(t, 200).length, 0);
  assert.ok(Math.abs(t.dominantHz[45] - 55) < 1e-3);
  assert.equal(t.dominantHz[10], 0);
});

test("a chord superposes patterns and the strongest note leads", () => {
  const t = compileCymatic(features({ notes: [
    { startFrame: 10, endFrame: 100, pitchHz: 55, stem: "bass", confidence: 0.9 },
    { startFrame: 10, endFrame: 100, pitchHz: 220, stem: "other", confidence: 0.5 },
  ] }), FPS, 300);
  const modes = modesAt(t, 60);
  assert.equal(modes.length, 2);
  assert.ok(modes[0].w >= modes[1].w);
  assert.ok(modes.length <= MAX_MODES);
});

test("nodal lines: sand positions where the plate is still stay still for one mode", () => {
  const mode = [{ n: 2, m: 3, w: 1 }];
  assert.ok(Math.abs(plateValue(mode, 0.2, 0.2 + 0)) >= 0);
  // The diagonal x = y is always nodal for these patterns.
  for (const x of [0.1, 0.37, 0.8]) assert.ok(Math.abs(plateValue(mode, x, x)) < 1e-9);
  assert.ok(Math.abs(plateValue(mode, 0.13, 0.71)) > 0.05);
});

test("no pitched notes: no patterns, honest flag, plate reacts to hits only", () => {
  const t = compileCymatic(features({ onsets: [{ frame: 40, strength: 1, kind: "kick" }] }), FPS, 300);
  assert.equal(t.hasNotes, false);
  assert.equal(modesAt(t, 100).length, 0);
  assert.equal(t.agitation[39], 0);
  assert.ok(t.agitation[40] >= 0.99);
  assert.ok(t.agitation[55] < t.agitation[41]);
});

test("cymbals agitate less than kicks and agitation is capped", () => {
  const kick = compileCymatic(features({ onsets: [{ frame: 20, strength: 1, kind: "kick" }] }), FPS, 100);
  const cymbal = compileCymatic(features({ onsets: [{ frame: 20, strength: 1, kind: "cymbal" }] }), FPS, 100);
  assert.ok(cymbal.agitation[20] < kick.agitation[20]);
  const many = compileCymatic(features({ onsets: Array.from({ length: 20 }, (_, i) => ({ frame: 20 + i, strength: 1, kind: "kick" as const })) }), FPS, 100);
  assert.ok(Math.max(...many.agitation) <= 1.5 + 1e-6);
});

test("compiling twice gives identical timelines", () => {
  const f = features({ notes: [{ startFrame: 5, endFrame: 80, pitchHz: 73, stem: "bass", confidence: 0.8 }] });
  const a = compileCymatic(f, FPS, 200), b = compileCymatic(f, FPS, 200);
  assert.deepEqual(Array.from(a.modes), Array.from(b.modes));
});
