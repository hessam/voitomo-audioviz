import assert from "node:assert/strict";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";

async function main() {
  const directory = process.env.SPHERE_TEST_OUTPUT || "/tmp/voitomo-sphere-check";
  mkdirSync(directory, { recursive: true });
  const serveUrl = await bundle({ entryPoint: path.resolve(__dirname, "src/index.ts") });
  const browser = await openBrowser("chrome", {
    browserExecutable: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    chromiumOptions: { gl: "angle" },
  });
  try {
    const outputs: Buffer[] = [];
    for (const stem of ["silent", "bass", "vocalEnergy", "drumsEnergy", "bass"]) {
      const features = { bass: Array(60).fill(0), mids: Array(60).fill(0), treble: Array(60).fill(0),
        vocalEnergy: Array(60).fill(0), drumsEnergy: Array(60).fill(0), transients: [] };
      if (stem !== "silent") features[stem as "bass" | "vocalEnergy" | "drumsEnergy"].fill(0.9, 24, 32);
      const inputProps = { features };
      const composition = await selectComposition({ serveUrl, id: "ParticleSphereViz", inputProps, puppeteerInstance: browser });
      const output = path.join(directory, `${outputs.length}-${stem}.png`);
      await renderStill({ serveUrl, composition, inputProps, frame: 30, output,
        scale: 0.5, puppeteerInstance: browser,
        onBrowserLog: log => { if (log.type === "error") throw new Error(log.text); },
      });
      outputs.push(readFileSync(output));
    }
    for (let i = 1; i < 4; i++) assert.ok(!outputs[0].equals(outputs[i]), `stem ${i} must change the captured frame`);
    assert.ok(outputs[1].equals(outputs[4]), "random-access repeated frame must be identical");
    console.log(`PASS: isolated bass, vocal, drums affect actual WebGL capture; repeated frame identical. ${directory}`);
  } finally { await browser.close({ silent: true }); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
