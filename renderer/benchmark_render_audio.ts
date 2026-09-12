import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { prepareAudio } from "./render_audio";

async function main() {
  const mode = process.argv[2];
  if (mode !== "before" && mode !== "after") throw new Error("Specify before or after");
  const directory = mkdtempSync(path.join(os.tmpdir(), "voitomo-benchmark-"));
  const input = path.join(directory, "input.wav");
  const times: number[] = [], delays: number[] = [];
  try {
    execFileSync("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=60", input]);
    for (let i = 0; i < 8; i++) {
      const start = performance.now();
      const timer = new Promise<number>(resolve => setTimeout(() => resolve(performance.now() - start), 1));
      if (mode === "before") {
        // Same synchronous FFmpeg conversion as the original handler; avoid shell overhead.
        const output = path.join(directory, "output.wav");
        execFileSync("ffmpeg", ["-y", "-i", input, "-ar", "44100", "-ac", "2", output], { stdio: "ignore" });
        rmSync(output);
      } else {
        const audio = await prepareAudio(input, directory, 4001);
        await audio.cleanup();
      }
      const elapsed = performance.now() - start;
      const delay = await timer;
      if (i > 0) { times.push(elapsed); delays.push(delay); } // Discard warm-up.
    }
    const median = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
    console.log(JSON.stringify({ mode, samples: times.length, inputSeconds: 60,
      medianConversionMs: median(times), medianTimerDelayMs: median(delays),
      conversionsPerSecond: 1000 / median(times),
      nodePeakRssMiB: process.resourceUsage().maxRSS / 1024,
      scope: "Node process RSS excludes FFmpeg; conversion only, no video rendering" }, null, 2));
  } finally { rmSync(directory, { recursive: true, force: true }); }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
