import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

// Exercise the production HTTP handler with only Express and Remotion replaced.
function harness(failBundle = false) {
  let handler: Function;
  let bundles = 0;
  const renders: Record<string, any>[] = [];
  const app = { use() {}, get() {}, post(_path: string, fn: Function) { handler = fn; }, listen() {} };
  const express = Object.assign(() => app, { json() {}, static() {} });
  const localRequire = createRequire(path.join(__dirname, "server.ts"));
  const source = readFileSync(process.env.SERVER_SOURCE || path.join(__dirname, "server.ts"), "utf8");
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2020,
  } }).outputText, {
    exports: {}, __dirname, console: { log() {}, warn() {}, error() {} },
    require: (id: string) => {
      if (id === "express") return express;
      if (id === "@remotion/bundler") return { bundle: async () => {
        bundles++;
        await new Promise(resolve => setTimeout(resolve, 5));
        if (failBundle) { failBundle = false; throw new Error("bundle failed"); }
        return "bundle-url";
      } };
      if (id === "@remotion/renderer") return {
        selectComposition: async () => ({ id: "AudiovizMaster", durationInFrames: 300, width: 1920, height: 1080, fps: 30 }),
        renderMedia: async (options: Record<string, any>) => { renders.push(options); },
      };
      return localRequire(id);
    },
  });
  return { renders, get bundles() { return bundles; }, request: async (body: unknown) => {
    let status = 200;
    let result: any;
    const res = { status(code: number) { status = code; return res; }, json(value: unknown) { result = value; return res; } };
    await handler({ body }, res);
    return { status, result };
  } };
}

function manifest() {
  return { schemaVersion: 1, jobId: "test", seed: 42,
    preset: { id: "sphere", version: "1.0.0", parameters: {} },
    video: { width: 1080, height: 1080, fpsNumerator: 30, fpsDenominator: 1, frameCount: 600 },
    audio: { masterUri: "https://example.invalid/audio.wav", sha256: "a".repeat(64), sampleRate: 44100,
      features: { bass: Array(600).fill(0), mids: Array(600).fill(0), treble: Array(600).fill(0), transients: [] } },
    lyrics: { lines: [{ text: "سلام", startFrame: 0, endFrame: 60 }] } };
}

test("manifest controls exact frame count, dimensions and fps", async () => {
  const h = harness();
  assert.equal((await h.request({ manifest: manifest() })).status, 200);
  assert.equal(h.renders[0].composition.durationInFrames, 600);
  assert.equal(h.renders[0].composition.width, 1080);
  assert.equal(h.renders[0].composition.fps, 30);
});

test("ten concurrent cold requests share one bundle and unique outputs", async () => {
  const h = harness();
  await Promise.all(Array.from({ length: 10 }, () => h.request({ manifest: manifest() })));
  assert.equal(h.bundles, 1);
  assert.equal(new Set(h.renders.map(r => r.outputLocation)).size, 10);
});

test("failed bundle can be retried", async () => {
  const h = harness(true);
  assert.equal((await h.request({ manifest: manifest() })).status, 500);
  assert.equal((await h.request({ manifest: manifest() })).status, 200);
  assert.equal(h.bundles, 2);
});

test("invalid manifests fail before expensive bundling", async () => {
  const mutations = [
    (m: any) => { m.video.frameCount = -1; },
    (m: any) => { m.audio.features.bass.pop(); },
    (m: any) => { m.audio.features.mids[1] = NaN; },
    (m: any) => { m.audio.features.transients = [-1]; },
    (m: any) => { m.lyrics.lines[0].endFrame = 601; },
    (m: any) => { m.preset.id = "unknown"; },
    (m: any) => { m.audio.masterUri = ""; },
    (m: any) => { m.video.fpsNumerator = 60; },
    (m: any) => { m.video.width = 100; },
    (m: any) => { m.audio.features.vocalEnergy = [0.5]; },
    (m: any) => { m.audio.features.beatFrames = [30, 10]; },
    (m: any) => { m.lyrics.lines[0].startFrame = -1; },
    (m: any) => { m.audio.sha256 = "invalid"; },
  ];
  for (const mutate of mutations) {
    const h = harness(); const m = manifest(); mutate(m);
    assert.equal((await h.request({ manifest: m })).status, 400);
    assert.equal(h.bundles, 0);
  }
});

test("conflicting duration cannot silently truncate the manifest", async () => {
  const h = harness();
  assert.equal((await h.request({ manifest: manifest(), durationInFrames: 30 })).status, 400);
  assert.equal(h.renders.length, 0);
});

test("missing local audio fails rather than producing a silent video", async () => {
  const h = harness(); const m = manifest();
  m.audio.masterUri = "/tmp/voitomo-nonexistent-audit-input.wav";
  assert.equal((await h.request({ manifest: m })).status, 400);
  assert.equal(h.renders.length, 0);
});
