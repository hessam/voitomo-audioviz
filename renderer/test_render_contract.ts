import assert from "node:assert/strict";
import test from "node:test";
import { RenderInputError, validateManifest } from "./render_contract";

const N = 60;
const rows = () => Array.from({ length: N }, () => Array(12).fill(0.3));
function manifest(over: Record<string, unknown> = {}, features: Record<string, unknown> = {}, preset = "orrery") {
  return {
    schemaVersion: 1, jobId: "job-1", seed: 42,
    preset: { id: preset, version: "1.0.0", parameters: {} },
    video: { width: 1920, height: 1080, fpsNumerator: 30, fpsDenominator: 1, frameCount: N },
    audio: { masterUri: "/tmp/a.wav", sha256: "a".repeat(64), sampleRate: 44100, features: {
      bass: Array(N).fill(0.1), mids: Array(N).fill(0.1), treble: Array(N).fill(0.1), transients: [5],
      bpm: null, musicalKey: "", rhythmSource: "unknown", downbeatsAssumed: false, meterBeats: null,
      beatFrames: [], downbeatFrames: [], onsets: [{ frame: 5, strength: 0.8, kind: "kick" }],
      notes: [{ startFrame: 3, endFrame: 20, pitchHz: 55, stem: "bass", confidence: 0.8 }],
      riffCycle: null, bodyBands: { mix: rows() }, ...features } },
    lyrics: { lines: [], mode: "video" }, ...over,
  };
}
const rejects = (m: unknown, pattern: RegExp) => assert.throws(() => validateManifest(m), (e: Error) => e instanceof RenderInputError && pattern.test(e.message));

test("a manifest with the new evidence fields and unknown rhythm is accepted", () => {
  for (const preset of ["sphere", "orrery", "cymatic", "bodies"]) assert.doesNotThrow(() => validateManifest(manifest({}, {}, preset)));
});

test("retired styles are rejected with a clear error", () => {
  for (const preset of ["iris", "neural", "monolith"]) rejects(manifest({}, {}, preset), /Unknown preset/);
});

test("event lists must be ordered, in range, and well formed", () => {
  rejects(manifest({}, { onsets: [{ frame: 9, strength: 1, kind: "kick" }, { frame: 4, strength: 1, kind: "kick" }] }), /onsets timeline/);
  rejects(manifest({}, { onsets: [{ frame: N, strength: 1, kind: "kick" }] }), /onsets timeline/);
  rejects(manifest({}, { onsets: [{ frame: 1, strength: 2, kind: "kick" }] }), /onset strength/);
  rejects(manifest({}, { onsets: [{ frame: 1, strength: 1, kind: "gong" }] }), /onset kind/);
  rejects(manifest({}, { notes: [{ startFrame: 5, endFrame: 5, pitchHz: 55 }] }), /note interval/);
  rejects(manifest({}, { notes: [{ startFrame: 5, endFrame: 9, pitchHz: -1 }] }), /note pitch/);
});

test("per-stem spectra must match the frame count and range", () => {
  rejects(manifest({}, { bodyBands: { mix: rows().slice(1) } }), /bodyBands.mix/);
  rejects(manifest({}, { bodyBands: { mix: rows().map(r => r.slice(1)) } }), /bodyBands.mix/);
  rejects(manifest({}, { bodyBands: { mix: rows().map(r => r.map(() => 2)) } }), /bodyBands.mix/);
  rejects(manifest({}, { bodyBands: { "../etc": rows() } }), /stem name/);
});

test("meter, rhythm source, riff cycle and lyric mode are validated", () => {
  rejects(manifest({}, { meterBeats: 40 }), /meterBeats/);
  rejects(manifest({}, { rhythmSource: "guess" }), /rhythmSource/);
  rejects(manifest({}, { riffCycle: { lengthSteps: 1, stepFrames: 3, confidence: 0.5 } }), /lengthSteps/);
  rejects(manifest({ lyrics: { lines: [], mode: "karaoke" } }), /lyrics.mode/);
  assert.doesNotThrow(() => validateManifest(manifest({}, { riffCycle: { lengthSteps: 23, stepFrames: 3.75, confidence: 0.6 }, meterBeats: 7 })));
});
