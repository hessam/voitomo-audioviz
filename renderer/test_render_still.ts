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
        bass: new Array(100).fill(0.6),
        mids: new Array(100).fill(0.4),
        treble: new Array(100).fill(0.3),
        transients: [],
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
