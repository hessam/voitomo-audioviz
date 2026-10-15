import assert from "node:assert/strict";
import test from "node:test";
import { barPosition, beatPosition, compileOrrery, markLevel, measureDecay, riffPosition, visibleMarks, STEPS_PER_BEAT } from "./src/visualizers/orreryModel";
import { AudioMultibandFeatures } from "./src/types/manifest";

const FPS = 30;
function features(over: Partial<AudioMultibandFeatures> = {}, frames = 900): AudioMultibandFeatures {
  return { bass: Array(frames).fill(0), mids: Array(frames).fill(0), treble: Array(frames).fill(0), transients: [], ...over };
}
const evenBeats = (count: number, every = 15, first = 15) => Array.from({ length: count }, (_, i) => first + i * every);

test("a measured 7-beat bar advances 1/7 per beat and wraps after seven", () => {
  const beats = evenBeats(40);
  const model = compileOrrery(features({ beatFrames: beats, downbeatFrames: [beats[0]], meterBeats: 7 }), FPS, 900);
  assert.equal(model.beatsPerBar, 7);
  assert.equal(model.barAssumed, false);
  for (const k of [0, 1, 3, 6]) assert.ok(Math.abs(barPosition(model, beats[k])! - k / 7) < 1e-9, `beat ${k}`);
  assert.ok(Math.abs(barPosition(model, beats[7])!) < 1e-9);
  assert.ok(Math.abs(barPosition(model, beats[3] + 7.5)! - 3.5 / 7) < 1e-9);
});

test("the bar starts on the downbeat, not on the first beat", () => {
  const beats = evenBeats(40);
  const model = compileOrrery(features({ beatFrames: beats, downbeatFrames: [beats[3]], meterBeats: 5 }), FPS, 900);
  assert.ok(Math.abs(barPosition(model, beats[3])!) < 1e-9);
  assert.ok(Math.abs(barPosition(model, beats[4])! - 0.2) < 1e-9);
});

test("bar position follows beats, not wall-clock time, through a tempo change", () => {
  const beats = [15, 30, 45, 60, 75, 87, 99, 111, 123, 135, 147, 159];  // speeds up
  const model = compileOrrery(features({ beatFrames: beats, downbeatFrames: [15], meterBeats: 4 }), FPS, 400);
  assert.ok(Math.abs(barPosition(model, 111)! - 0.75) < 1e-9);
  assert.ok(Math.abs(barPosition(model, 123)! - 0.0) < 1e-9);
});

test("a 5-step riff drifts against a 16-step bar and the two realign only after 80 steps", () => {
  const beats = evenBeats(60);
  const stepFrames = 15 / STEPS_PER_BEAT;
  const onsets = Array.from({ length: 40 }, (_, n) => ({ frame: Math.round(15 + n * 5 * stepFrames), strength: 1, kind: "snare" as const }));
  const model = compileOrrery(features({ beatFrames: beats, downbeatFrames: [15], meterBeats: 4, onsets,
    riffCycle: { lengthSteps: 5, stepFrames, confidence: 0.9 } }), FPS, 900);
  assert.ok(model.riff);
  const riffPositions = model.marks.map(m => m.riffPosition!);
  // Hit times are whole frames (up to half a frame, 0.03 of a cycle, off), so allow that much.
  riffPositions.forEach(p => assert.ok(Math.min(p, 1 - p) < 0.06, `riff hit at ${p} should land on the same riff step`));
  const barPositions = model.marks.slice(0, 16).map(m => Math.round(m.barPosition! * 16) % 16);
  assert.deepEqual(barPositions.slice(0, 5), [0, 5, 10, 15, 4]);  // drifts through the bar
  assert.equal(barPositions[16 - 1], (15 * 5) % 16);
  assert.equal(barPositions.filter(p => p === 0).length, 1);
});

test("no beat grid means no bar ring, no riff ring, and an honest unsynced flag", () => {
  const model = compileOrrery(features({ onsets: [{ frame: 40, strength: 1, kind: "kick" }] }), FPS, 900);
  assert.equal(model.synced, false);
  assert.equal(model.beatsPerBar, null);
  assert.equal(barPosition(model, 100), null);
  assert.equal(riffPosition(model, 100), null);
  assert.equal(model.marks[0].barPosition, null);
});

test("assumed 4/4 is marked assumed; a measured meter is not; unknown meter hides the bar ring", () => {
  const beats = evenBeats(40);
  const assumed = compileOrrery(features({ beatFrames: beats, downbeatFrames: beats.filter((_, i) => i % 4 === 0), downbeatsAssumed: true }), FPS, 900);
  assert.deepEqual([assumed.beatsPerBar, assumed.barAssumed], [4, true]);
  const unknown = compileOrrery(features({ beatFrames: beats }), FPS, 900);
  assert.equal(unknown.beatsPerBar, null);
  assert.ok(unknown.synced);
});

test("without a riff cycle there is no riff ring", () => {
  const beats = evenBeats(40);
  const model = compileOrrery(features({ beatFrames: beats, downbeatFrames: [15], meterBeats: 4, riffCycle: null }), FPS, 900);
  assert.equal(model.riff, null);
  assert.equal(riffPosition(model, 100), null);
});

test("beat position extrapolates outside the grid instead of freezing", () => {
  const beats = [30, 45, 60, 75];
  assert.ok(Math.abs(beatPosition(beats, 15) - -1) < 1e-9);
  assert.ok(Math.abs(beatPosition(beats, 90) - 4) < 1e-9);
});

test("measured decay follows the drum envelope and falls back to defaults on thin evidence", () => {
  const drums = Array(600).fill(0);
  const onsets = [60, 150, 240, 330, 420].map(frame => ({ frame, kind: "kick" as const }));
  for (const o of onsets) for (let f = o.frame; f < o.frame + 60; f++) drums[f] = Math.exp(-(f - o.frame) / (0.3 * FPS));
  assert.ok(Math.abs(measureDecay(drums, onsets, FPS).kick - 0.3) < 0.07);
  assert.equal(measureDecay(drums, onsets.slice(0, 2), FPS).kick, 0.55);
  assert.equal(measureDecay(undefined, onsets, FPS).kick, 0.55);
});

test("marks never show before their hit, decay afterwards, and leave a faint residue", () => {
  const beats = evenBeats(40);
  const model = compileOrrery(features({ beatFrames: beats, downbeatFrames: [15], meterBeats: 4,
    onsets: [{ frame: 100, strength: 1, kind: "kick" }] }), FPS, 900);
  const mark = model.marks[0];
  assert.equal(markLevel(model, mark, 99), 0);
  assert.ok(markLevel(model, mark, 100) > 0.99);
  assert.ok(markLevel(model, mark, 112) < markLevel(model, mark, 104));
  const late = markLevel(model, mark, 100 + 5 * FPS);
  assert.ok(late > 0.03 && late < 0.3, `residue ${late}`);
  assert.equal(visibleMarks(model, 99).length, 0);
  assert.equal(visibleMarks(model, 120).length, 1);
  assert.equal(visibleMarks(model, 100 + 13 * FPS).length, 0);
});
