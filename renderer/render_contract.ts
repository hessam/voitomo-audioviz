import { RenderManifest } from "./src/types/manifest";

export class RenderInputError extends Error {}

function requireValue(valid: boolean, message: string): asserts valid {
  if (!valid) throw new RenderInputError(message);
}

function record(value: unknown, name: string): Record<string, unknown> {
  requireValue(typeof value === "object" && value !== null && !Array.isArray(value), `${name} must be an object`);
  return value as Record<string, unknown>;
}

function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

export function validateDuration(value: unknown): asserts value is number {
  requireValue(positiveInteger(value), "durationInFrames must be a positive integer");
}

export function validateManifest(value: unknown): asserts value is RenderManifest {
  const m = record(value, "manifest");
  requireValue(m.schemaVersion === 1, "Unsupported manifest schemaVersion");
  requireValue(typeof m.jobId === "string" && m.jobId.trim().length > 0, "jobId is required");
  requireValue(typeof m.seed === "number" && Number.isSafeInteger(m.seed), "seed must be an integer");
  const preset = record(m.preset, "preset");
  requireValue(["sphere", "iris", "neural", "monolith"].includes(String(preset.id)), "Unknown preset");
  requireValue(typeof preset.version === "string" && preset.version.length > 0, "preset.version is required");
  const params = record(preset.parameters, "preset.parameters");
  requireValue(Object.values(params).every(v => typeof v === "string" || typeof v === "boolean" ||
    (typeof v === "number" && Number.isFinite(v))), "Invalid preset parameter");
  const video = record(m.video, "video");
  requireValue(positiveInteger(video.frameCount), "frameCount must be a positive integer");
  // Both formats exist in the current producer and reference contracts.
  requireValue((video.width === 1080 || video.width === 1920) && video.height === 1080, "Unsupported video dimensions");
  requireValue(video.fpsNumerator === 30 && video.fpsDenominator === 1, "Features require 30 FPS");
  const count = video.frameCount;
  const audio = record(m.audio, "audio");
  requireValue(typeof audio.masterUri === "string" && audio.masterUri.trim().length > 0, "audio.masterUri is required");
  requireValue(typeof audio.sha256 === "string" && /^[a-f0-9]{64}$/i.test(audio.sha256), "Invalid audio SHA-256");
  requireValue(positiveInteger(audio.sampleRate), "Invalid sampleRate");
  for (const key of ["vocalStemUri", "bassStemUri"]) {
    requireValue(audio[key] == null || typeof audio[key] === "string", `Invalid ${key}`);
  }
  const features = record(audio.features, "audio.features");
  for (const key of ["bass", "mids", "treble", "vocalEnergy", "drumsEnergy", "macroEnergy"]) {
    const values = features[key];
    const optional = !["bass", "mids", "treble"].includes(key);
    if (optional && (values === undefined || (Array.isArray(values) && values.length === 0))) continue;
    requireValue(Array.isArray(values) && values.length === count && values.every(v =>
      typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1), `${key} must contain frameCount normalized samples`);
  }
  for (const key of ["transients", "beatFrames", "downbeatFrames"]) {
    const values = features[key];
    if (key !== "transients" && values === undefined) continue;
    requireValue(Array.isArray(values) && values.every((v, i) =>
      Number.isSafeInteger(v) && v >= 0 && v < count && (i === 0 || v >= values[i - 1])), `Invalid ${key} timeline`);
  }
  requireValue(features.bpm === undefined || (typeof features.bpm === "number" && Number.isFinite(features.bpm) && features.bpm > 0), "Invalid bpm");
  requireValue(features.musicalKey === undefined || typeof features.musicalKey === "string", "Invalid musicalKey");
  const lyrics = record(m.lyrics, "lyrics");
  requireValue(Array.isArray(lyrics.lines), "lyrics.lines must be an array");
  let previousStart = -1;
  for (const item of lyrics.lines) {
    const line = record(item, "lyric line");
    requireValue(typeof line.text === "string" && line.text.trim().length > 0, "Empty lyric text");
    requireValue(typeof line.startFrame === "number" && Number.isSafeInteger(line.startFrame) &&
      positiveInteger(line.endFrame) && line.startFrame >= previousStart && line.startFrame >= 0 &&
      line.startFrame < line.endFrame && line.endFrame <= count, "Invalid lyric interval");
    requireValue(line.isHero === undefined || typeof line.isHero === "boolean", "Invalid isHero");
    previousStart = line.startFrame;
  }
  if (m.environment !== undefined) {
    const environment = record(m.environment, "environment");
    for (const key of ["containerDigest", "threeVersion", "remotionVersion", "gpuBackend"]) {
      requireValue(environment[key] === undefined || typeof environment[key] === "string", `Invalid environment.${key}`);
    }
  }
}
