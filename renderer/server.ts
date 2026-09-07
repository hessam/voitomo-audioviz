import express from "express";
import path from "path";
import fs from "fs";
import os from "os";
import { execSync } from "child_process";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

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
  const { manifest, scenes, words, text, audioSrc, durationInFrames, profile: profileKey = "swiss_clean", creativeSpec } = req.body;

  if (!manifest && !creativeSpec && (!words || !Array.isArray(words)) && (!scenes || !Array.isArray(scenes))) {
    return res.status(400).json({ error: "manifest, creativeSpec, words, or scenes array required" });
  }

  try {
    const url = await ensureBundle();

    const targetAudioSrc = manifest?.audio?.masterUri || audioSrc;
    let resolvedAudioSrc = "";
    if (targetAudioSrc && typeof targetAudioSrc === "string") {
      if (targetAudioSrc.startsWith("http://") || targetAudioSrc.startsWith("https://")) {
        resolvedAudioSrc = targetAudioSrc;
      } else if (fs.existsSync(targetAudioSrc)) {
        const baseName = `audio-${Date.now()}`;
        const wavPath = path.join(AUDIO_DIR, `${baseName}.wav`);
        try {
          execSync(`ffmpeg -y -i "${targetAudioSrc}" -ar 44100 -ac 2 "${wavPath}" 2>/dev/null`);
          resolvedAudioSrc = `http://127.0.0.1:${PORT}/audio/${baseName}.wav`;
          console.log(`🎵 Audio converted to WAV: ${resolvedAudioSrc}`);
        } catch (convErr) {
          console.warn("⚠️ ffmpeg WAV conversion failed, serving original file:", convErr);
          const ext = path.extname(targetAudioSrc) || ".ogg";
          const copyPath = path.join(AUDIO_DIR, `${baseName}${ext}`);
          fs.copyFileSync(targetAudioSrc, copyPath);
          resolvedAudioSrc = `http://127.0.0.1:${PORT}/audio/${baseName}${ext}`;
        }
      }
    }

    let inputProps: any;
    let targetCompositionId: string;
    let renderDuration = durationInFrames;

    if (manifest) {
      targetCompositionId = "AudiovizMaster";
      renderDuration = manifest.video?.frameCount || durationInFrames || 300;
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
      concurrency: 2,
      chromiumOptions: {
        disableWebSecurity: true,
        ignoreCertificateErrors: true,
        headless: true,
        gl: "angle",
      },
      timeoutInMilliseconds: 900000,
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
