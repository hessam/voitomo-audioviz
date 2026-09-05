import express from "express";
import path from "path";
import fs from "fs";
import os from "os";
import { execSync } from "child_process";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

const app = express();
app.use(express.json({ limit: "50mb" }));

const PORT = 4000;
const PROFILES_DIR = "/root/workspace/video_profiles";
const OUT_DIR = "/tmp/motion-renders";
const AUDIO_DIR = "/tmp/motion-audio";

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.mkdirSync(AUDIO_DIR, { recursive: true });

// Serve converted audio files statically for Remotion / Chromium
app.use("/audio", express.static(AUDIO_DIR));

let serveUrl: string | null = null;

function loadProfile(profileKey: string) {
  const indexPath = path.join(PROFILES_DIR, "index.json");
  const index = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  const profilePath = index.paths[profileKey] || index.paths[index.default];
  return JSON.parse(fs.readFileSync(profilePath, "utf-8"));
}

async function ensureBundle() {
  if (!serveUrl) {
    console.log("📦 Bundling Remotion composition (one-time)...");
    serveUrl = await bundle({
      entryPoint: path.resolve(__dirname, "./src/index.ts"),
      webpackOverride: (config) => config,
    });
    console.log("✅ Bundle ready:", serveUrl);
  }
  return serveUrl;
}

app.get("/health", (_req, res) => {
  res.json({ status: "ok", bundled: serveUrl !== null });
});
app.post("/render", async (req, res) => {
  const { scenes, words, text, audioSrc, durationInFrames, profile: profileKey = "swiss_clean", creativeSpec } = req.body;

  if (!creativeSpec && (!words || !Array.isArray(words)) && (!scenes || !Array.isArray(scenes))) {
    return res.status(400).json({ error: "creativeSpec, words, or scenes array required" });
  }

  try {
    const url = await ensureBundle();
    const profileData = loadProfile(profileKey);

    // Resolve audioSrc to an HTTP URL accessible by Chromium
    let resolvedAudioSrc = "";
    if (audioSrc && typeof audioSrc === "string") {
      if (audioSrc.startsWith("http://") || audioSrc.startsWith("https://")) {
        resolvedAudioSrc = audioSrc;
      } else if (fs.existsSync(audioSrc)) {
        const baseName = `audio-${Date.now()}`;
        const wavPath = path.join(AUDIO_DIR, `${baseName}.wav`);
        try {
          // Convert to WAV with 44100Hz 2ch PCM for seamless Chromium audio decode
          execSync(`ffmpeg -y -i "${audioSrc}" -ar 44100 -ac 2 "${wavPath}" 2>/dev/null`);
          resolvedAudioSrc = `http://127.0.0.1:${PORT}/audio/${baseName}.wav`;
          console.log(`🎵 Audio converted to WAV: ${resolvedAudioSrc}`);
        } catch (convErr) {
          console.warn("⚠️ ffmpeg WAV conversion failed, serving original file:", convErr);
          const ext = path.extname(audioSrc) || ".ogg";
          const copyPath = path.join(AUDIO_DIR, `${baseName}${ext}`);
          fs.copyFileSync(audioSrc, copyPath);
          resolvedAudioSrc = `http://127.0.0.1:${PORT}/audio/${baseName}${ext}`;
        }
      }
    }

    const isSwissSpec = !!creativeSpec;
    const inputProps = isSwissSpec
      ? {
          creativeSpec,
          audioSrc: resolvedAudioSrc,
          durationInFrames: durationInFrames || creativeSpec.meta?.total_frames || 300,
          words: words || [],
        }
      : {
          scenes: scenes || [],
          words: words || [],
          text: text || "",
          audioSrc: resolvedAudioSrc,
          durationInFrames: durationInFrames || 300,
          profile: profileKey,
          profileData,
        };

    const targetCompositionId = isSwissSpec ? "VoitomoSwiss" : "VoiceMotion";
    const composition = await selectComposition({
      serveUrl: url,
      id: targetCompositionId,
      inputProps,
    });

    const outPath = path.join(OUT_DIR, `render-${Date.now()}.mp4`);

    await renderMedia({
      composition: { ...composition, durationInFrames: durationInFrames || composition.durationInFrames },
      serveUrl: url,
      codec: "h264",
      outputLocation: outPath,
      inputProps,
      concurrency: 3,
      chromiumOptions: {
        disableWebSecurity: true,
        ignoreCertificateErrors: true,
        headless: true,
      },
      timeoutInMilliseconds: 360000,
    });

    console.log(`✅ Rendered: ${outPath}`);
    res.json({ path: outPath });
  } catch (err: any) {
    console.error("❌ Render error:", err?.message || err);
    res.status(500).json({ error: err?.message || String(err) });
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
