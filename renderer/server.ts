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
const OUT_DIR = fs.existsSync("/opt/hermes-vault/motion/renders")
  ? "/opt/hermes-vault/motion/renders"
  : "/tmp/audioviz-renders";
const AUDIO_DIR = fs.existsSync("/opt/hermes-vault/motion/audio")
  ? "/opt/hermes-vault/motion/audio"
  : "/tmp/audioviz-audio";

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.mkdirSync(AUDIO_DIR, { recursive: true });

// Serve converted audio files statically for Remotion / Chromium
app.use("/audio", express.static(AUDIO_DIR));

function cleanOldFiles() {
  try {
    const now = Date.now();
    for (const dir of [OUT_DIR, AUDIO_DIR]) {
      if (!fs.existsSync(dir)) continue;
      for (const f of fs.readdirSync(dir)) {
        const p = path.join(dir, f);
        try {
          const stat = fs.statSync(p);
          if (now - stat.mtimeMs > 30 * 60 * 1000) {
            fs.unlinkSync(p);
            console.log(`🧹 Pruned old file: ${p}`);
          }
        } catch {}
      }
    }
  } catch (err) {
    console.warn("Prune error:", err);
  }
}
setInterval(cleanOldFiles, 10 * 60 * 1000);
cleanOldFiles();

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

interface JobState {
  id: string;
  status: "queued" | "rendering" | "done" | "error";
  renderedFrames: number;
  totalFrames: number;
  percent: number;
  startedAt: number;
  etaSeconds: number;
  path?: string;
  error?: string;
}

const jobs = new Map<string, JobState>();

if (typeof setInterval !== "undefined") {
  setInterval(() => {
    const cutoff = Date.now() - 24 * 60 * 60 * 1000;
    for (const [id, job] of jobs.entries()) {
      if (job.startedAt < cutoff) jobs.delete(id);
    }
  }, 60 * 60 * 1000);
}

app.get("/health", (_req, res) => {
  res.json({ status: "ok", bundled: serveUrl !== null });
});

app.get("/render/jobs/:id", (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: "Job not found" });
  res.json(job);
});

async function runRenderJob(jobId: string, body: any): Promise<string> {
  const { manifest, scenes, words, text, audioSrc, durationInFrames, profile: profileKey = "swiss_clean", creativeSpec } = body || {};

  if (!manifest && !creativeSpec && (!words || !Array.isArray(words)) && (!scenes || !Array.isArray(scenes))) {
    throw new RenderInputError("manifest, creativeSpec, words, or scenes array required");
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
    const totalFrames = renderDuration || composition.durationInFrames;

    const job = jobs.get(jobId);
    if (job) {
      job.status = "rendering";
      job.totalFrames = totalFrames;
      job.startedAt = Date.now();
    }

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
      imageFormat: "jpeg",
      jpegQuality: 80,
      crf: 20,
      x264Preset: "medium",
      pixelFormat: "yuv420p",
      outputLocation: outPath,
      inputProps,
      concurrency: 2,
      onProgress: ({ renderedFrames }) => {
        const pct = Math.min(100, Math.round((renderedFrames / totalFrames) * 100));
        const currentJob = jobs.get(jobId);
        if (currentJob) {
          const elapsedSec = (Date.now() - currentJob.startedAt) / 1000;
          const fps = renderedFrames / Math.max(0.1, elapsedSec);
          const remainingFrames = Math.max(0, totalFrames - renderedFrames);
          const etaSeconds = Math.round(remainingFrames / Math.max(0.1, fps));
          currentJob.renderedFrames = renderedFrames;
          currentJob.percent = pct;
          currentJob.etaSeconds = etaSeconds;
        }
        if (renderedFrames % 100 === 0 || renderedFrames === totalFrames) {
          console.log(`🎬 Render Progress [${jobId}]: ${pct}% (${renderedFrames}/${totalFrames} frames)`);
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

    console.log(`✅ Rendered [${jobId}]: ${outPath}`);
    if (job) {
      job.status = "done";
      job.percent = 100;
      job.path = outPath;
      job.etaSeconds = 0;
    }
    return outPath;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`❌ Render error [${jobId}]:`, message);
    const job = jobs.get(jobId);
    if (job) {
      job.status = "error";
      job.error = message;
    }
    throw err;
  } finally {
    if (cleanupAudio) await cleanupAudio().catch((error) => console.warn("Audio cleanup failed:", error));
  }
}

app.post("/render", async (req, res) => {
  const isAsync = req.body?.async === true;
  const jobId = req.body?.jobId || randomUUID();

  jobs.set(jobId, {
    id: jobId,
    status: "queued",
    renderedFrames: 0,
    totalFrames: req.body?.manifest?.video?.frameCount || req.body?.durationInFrames || 300,
    percent: 0,
    startedAt: Date.now(),
    etaSeconds: 0,
  });

  if (isAsync) {
    // Return job identifier immediately for progress polling
    runRenderJob(jobId, req.body).catch(() => {});
    return res.json({ jobId, status: "queued" });
  }

  try {
    const outPath = await runRenderJob(jobId, req.body);
    res.json({ path: outPath, jobId });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    res.status(err instanceof RenderInputError ? 400 : 500).json({ error: message });
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
