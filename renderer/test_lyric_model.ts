import assert from "node:assert/strict";
import test from "node:test";
import { HOLD_FRAMES, LEAD_IN_FRAMES, visibleLines, isPersian } from "./src/components/lyricModel";
import { LyricLine } from "./src/types/manifest";

const line = (over: Partial<LyricLine> = {}): LyricLine => ({
  text: "سلام دوست من", startFrame: 100, endFrame: 160, confidence: 1,
  words: [
    { word: "سلام", startFrame: 100, endFrame: 120, score: 0.9 },
    { word: "دوست", startFrame: 120, endFrame: 140, score: 0.9 },
    { word: "من", startFrame: 140, endFrame: 160, score: 0.9 },
  ], ...over,
});

test("a line appears about 400 ms early, never earlier, and is gone after the hold", () => {
  const lines = [line()];
  assert.equal(visibleLines(lines, 100 - LEAD_IN_FRAMES - 1, "video").length, 0);
  assert.equal(visibleLines(lines, 100 - LEAD_IN_FRAMES, "video").length, 1);
  assert.equal(visibleLines(lines, 160 + HOLD_FRAMES, "video").length, 1);
  assert.equal(visibleLines(lines, 160 + HOLD_FRAMES + 1, "video").length, 0);
});

test("during the lead-in the words are visible but not yet filled", () => {
  const [l] = visibleLines([line()], 95, "video");
  assert.ok(l.opacity > 0);
  assert.ok(l.words.every(w => w.progress === 0));
});

test("each word fills over its own time, in order, and Persian fills right to left", () => {
  const at = (f: number) => visibleLines([line()], f, "video")[0].words.map(w => w.progress);
  assert.deepEqual(at(100), [0, 0, 0]);
  assert.deepEqual(at(110), [0.5, 0, 0]);
  assert.deepEqual(at(130), [1, 0.5, 0]);
  assert.deepEqual(at(160), [1, 1, 1]);
  assert.ok(visibleLines([line()], 110, "video")[0].words.every(w => w.rtl));
});

test("Latin words fill left to right and Persian detection ignores digits and Latin", () => {
  assert.equal(isPersian("hello"), false);
  assert.equal(isPersian("123"), false);
  assert.equal(isPersian("سلام"), true);
  const mixed = line({ text: "سلام hello", words: [
    { word: "سلام", startFrame: 100, endFrame: 120, score: 1 }, { word: "hello", startFrame: 120, endFrame: 140, score: 1 }] });
  assert.deepEqual(visibleLines([mixed], 130, "video")[0].words.map(w => w.rtl), [true, false]);
});

test("interpolated or low-confidence words are highlighted at line level, with no fake sweep", () => {
  const rough = line({ words: [
    { word: "سلام", startFrame: 100, endFrame: 120, score: 0.9 },
    { word: "دوست", startFrame: 120, endFrame: 140, score: 0.1 },
    { word: "من", startFrame: 140, endFrame: 160, score: 0.9, isInterpolated: true },
  ] });
  const words = visibleLines([rough], 125, "video")[0].words;
  assert.deepEqual(words.map(w => w.precise), [true, false, false]);
  assert.equal(words[1].progress, 1);  // starts instantly at its own start frame
  assert.equal(words[2].progress, 0);  // not started yet
});

test("subtitle mode highlights the whole line at once", () => {
  const before = visibleLines([line()], 105, "subtitles")[0].words.map(w => w.progress);
  const at = visibleLines([line()], 100, "subtitles")[0].words.map(w => w.progress);
  assert.deepEqual(before, [1, 1, 1]);
  assert.deepEqual(at, [1, 1, 1]);
  assert.deepEqual(visibleLines([line()], 95, "subtitles")[0].words.map(w => w.progress), [0, 0, 0]);
});

test("a line without word timings falls back to whole-line highlighting", () => {
  const bare = line({ words: undefined });
  const words = visibleLines([bare], 105, "video")[0].words;
  assert.equal(words.length, 3);
  assert.ok(words.every(w => w.progress === 1 && !w.precise));
});

test("off shows nothing; at most two lines show and the newest is current", () => {
  assert.equal(visibleLines([line()], 120, "off").length, 0);
  const a = line({ startFrame: 100, endFrame: 150 }), b = line({ startFrame: 140, endFrame: 200 }), c = line({ startFrame: 145, endFrame: 210 });
  const shown = visibleLines([a, b, c], 148, "video");
  assert.equal(shown.length, 2);
  assert.equal(shown[1].current, true);
  assert.ok(shown[0].opacity <= 0.5);
});
