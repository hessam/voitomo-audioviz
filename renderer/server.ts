import express from "express";
import path from "path";
import fs from "fs";
import { randomUUID } from "node:crypto";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { RenderInputError, validateDuration, validateManifest } from "./render_contract";
import { prepareAudio } from "./render_audio";

const app = express();
app.use(express.json({ limit: "50mb" }));

const PORT = 4001;
const PROFILES_DIR = "/root/workspace/video_profiles";
const OUT_DIR = "/tmp/audioviz-renders";
const AUDIO_DIR = "/tmp/audioviz-audio";

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.mkdirSync(AUDIO_DIR, { recursive: true });

// Serve converted audio files statically for Remotion / Chromium
app.use("/audio", express.static(AUDIO_DIR));

let serveUrl: string | null = null;
let bundlePromise: Promise<string> | null = null;

function loadProfile(profileKey: string) {
  const indexPath = path.join(PROFILES_DIR, "index.json");
  const index = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  const profilePath = index.paths[profileKey] || index.paths[index.default];
  return JSON.parse(fs.readFileSync(profilePath, "utf-8"));
}

async function ensureBundle() {
  if (!bundlePromise) {
    console.log("📦 Bundling Remotion composition (one-time)...");
    bundlePromise = bundle({
      entryPoint: path.resolve(__dirname, "./src/index.ts"),
      webpackOverride: (config) => config,
    }).then((url) => {
      serveUrl = url;
      console.log("✅ Bundle ready:", url);
      return url;
    }).catch((error) => {
      bundlePromise = null;
      throw error;
    });
  }
  return bundlePromise;
}

app.get("/health", (_req, res) => {
  res.json({ status: "ok", bundled: serveUrl !== null });
});
app.post("/render", async (req, res) => {
  const { manifest, scenes, words, text, audioSrc, durationInFrames, profile: profileKey = "swiss_clean", creativeSpec } = req.body || {};

  if (!manifest && !creativeSpec && (!words || !Array.isArray(words)) && (!scenes || !Array.isArray(scenes))) {
    return res.status(400).json({ error: "manifest, creativeSpec, words, or scenes array required" });
  }

  let cleanupAudio: (() => Promise<void>) | undefined;
  try {
    if (durationInFrames !== undefined) validateDuration(durationInFrames);
    if (manifest) {
      validateManifest(manifest);
      if (durationInFrames !== undefined && durationInFrames !== manifest.video.frameCount) {
        throw new RenderInputError("durationInFrames conflicts with manifest.video.frameCount");
      }
    }
    const prepared = await prepareAudio(manifest?.audio?.masterUri ?? audioSrc, AUDIO_DIR, PORT);
    cleanupAudio = prepared.cleanup;
    const resolvedAudioSrc = prepared.uri;
    const url = await ensureBundle();

    let inputProps: Record<string, unknown>;
    let targetCompositionId: string;
    let renderDuration = durationInFrames;

    if (manifest) {
      targetCompositionId = "AudiovizMaster";
      renderDuration = manifest.video.frameCount;
      inputProps = {
        manifest,
        audioSrc: resolvedAudioSrc,
      };
    } else if (creativeSpec) {
      targetCompositionId = "VoitomoSwiss";
      renderDuration = durationInFrames || creativeSpec.meta?.total_frames || 300;
      inputProps = {
        creativeSpec,
        audioSrc: resolvedAudioSrc,
        durationInFrames: renderDuration,
        words: words || [],
      };
    } else {
      const profileData = loadProfile(profileKey);
      targetCompositionId = "VoiceMotion";
      renderDuration = durationInFrames || 300;
      inputProps = {
        scenes: scenes || [],
        words: words || [],
        text: text || "",
        audioSrc: resolvedAudioSrc,
        durationInFrames: renderDuration,
        profile: profileKey,
        profileData,
      };
    }

    validateDuration(renderDuration);
    const composition = await selectComposition({
      serveUrl: url,
      id: targetCompositionId,
      inputProps,
    });

    const outPath = path.join(OUT_DIR, `render-${randomUUID()}.mp4`);

    await renderMedia({
      composition: {
        ...composition,
        durationInFrames: renderDuration,
        ...(manifest ? {
          width: manifest.video.width,
          height: manifest.video.height,
          fps: manifest.video.fpsNumerator / manifest.video.fpsDenominator,
        } : {}),
      },
      serveUrl: url,
      codec: "h264",
      crf: 20,
      x264Preset: "medium",
      pixelFormat: "yuv420p",
      outputLocation: outPath,
      inputProps,
      concurrency: 2,
      onProgress: ({ renderedFrames }) => {
        const total = renderDuration || composition.durationInFrames;
        const pct = Math.round((renderedFrames / total) * 100);
        if (renderedFrames % 100 === 0 || renderedFrames === total) {
          console.log(`🎬 Render Progress: ${pct}% (${renderedFrames}/${total} frames)`);
        }
      },
      chromiumOptions: {
        disableWebSecurity: true,
        ignoreCertificateErrors: true,
        headless: true,
        gl: "angle",
      },
      timeoutInMilliseconds: Math.max(7200000, renderDuration * 2500),
    });

    console.log(`✅ Rendered: ${outPath}`);
    res.json({ path: outPath });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("❌ Render error:", message);
    res.status(err instanceof RenderInputError ? 400 : 500).json({ error: message });
  } finally {
    if (cleanupAudio) await cleanupAudio().catch((error) => console.warn("Audio cleanup failed:", error));
  }
});

app.listen(PORT, "127.0.0.1", async () => {
  console.log(`🚀 Render server on port ${PORT}`);
  try {
    await ensureBundle();
  } catch (e) {
    console.warn("⚠️ Pre-warm failed:", e);
  }
});
