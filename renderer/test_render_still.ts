import path from "path";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

async function main() {
  const entryPoint = path.resolve(__dirname, "src/index.ts");
  console.log("Bundling...");
  const serveUrl = await bundle({
    entryPoint,
    webpackOverride: (config) => config,
  });

  const composition = await selectComposition({
    serveUrl,
    id: "ParticleSphereViz",
    inputProps: {
      features: {
        bass:        new Array(100).fill(0.55),
        mids:        new Array(100).fill(0.40),
        treble:      new Array(100).fill(0.30),
        vocalEnergy: new Array(100).fill(0.65),
        transients:  [],
        beatFrames:  [0, 15, 30, 45, 60],
      },
    },
  });

  const outPath = path.resolve(__dirname, "rendered_particle_sphere.png");
  console.log("Rendering still to", outPath);
  await renderStill({
    composition,
    serveUrl,
    output: outPath,
    frame: 30,
    chromiumOptions: {
      headless: true,
      gl: "angle",
    },
    onBrowserLog: (log) => console.log("[Browser]", log.type, log.text),
  });
  console.log("✅ Still rendered!");
}

main().catch(console.error);
