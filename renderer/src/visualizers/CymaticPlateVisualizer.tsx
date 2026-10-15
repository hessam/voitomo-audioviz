import React, { useMemo } from "react";
import * as THREE from "three";
import { useCurrentFrame } from "remotion";
import { AudioMultibandFeatures } from "../types/manifest";
import { MAX_MODES, compileCymatic, modeIndexForPitch, MODE_TABLE } from "./cymaticModel";
import { useThreeScene } from "./useThreeScene";

/**
 * Cymatic Plate: sand on a vibrating plate. Notes pick the vibration pattern, sand collects on its
 * still lines, and drum hits throw it up before it settles. Grains keep no state: each one finds the
 * nearest still line from its rest position with a fixed number of Newton steps, so any frame (seek,
 * parallel worker) draws identically. Pattern maths: see cymaticModel.ts.
 */
const PLATE_SIZE = 6.0;

const modeGLSL = `
uniform vec4 uModes[${MAX_MODES}];   // (n, m, weight, 0)
const float PI = 3.14159265359;

// Returns (z, dz/dx, dz/dy) of the weighted pattern at p in [0,1]^2.
vec3 plate(vec2 p) {
  float z = 0.0; vec2 g = vec2(0.0);
  for (int k = 0; k < ${MAX_MODES}; k++) {
    float n = uModes[k].x, m = uModes[k].y, w = uModes[k].z;
    if (w <= 0.0) continue;
    float cnx = cos(n * PI * p.x), cmy = cos(m * PI * p.y), cmx = cos(m * PI * p.x), cny = cos(n * PI * p.y);
    float snx = sin(n * PI * p.x), smy = sin(m * PI * p.y), smx = sin(m * PI * p.x), sny = sin(n * PI * p.y);
    z += w * (cnx * cmy - cmx * cny);
    g.x += w * (-n * PI * snx * cmy + m * PI * smx * cny);
    g.y += w * (-m * PI * cnx * smy + n * PI * cmx * sny);
  }
  return vec3(z, g);
}
`;

const sandVertex = `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;

/*
 * Sand is drawn per pixel, not as particles: a grain sits on a still line where the plate's
 * displacement z is zero. The line width is measured in plate units from |z| / |grad z|, so it stays
 * a crisp, anti-aliased line at any output size. Hits widen the lines and scatter a few grains.
 */
const sandFragment = `
${modeGLSL}
uniform float uPatterned;
uniform float uAgit;
uniform float uTime;
varying vec2 vUv;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void main() {
  vec2 p = vUv;
  vec3 zg = uPatterned > 0.0 ? plate(p) : vec3(0.0);
  float grad = max(length(zg.yz), 1e-4);
  // Distance to the nearest still line, in plate units (0..0.5).
  float dist = abs(zg.x) / grad;
  float width = 0.0042 + 0.006 * min(uAgit, 1.0);
  float edge = fwidth(dist) * 1.2 + 1e-4;
  float line = 1.0 - smoothstep(width - edge, width + edge, dist);
  float glow = exp(-dist / (0.02 + 0.01 * min(uAgit, 1.0))) * 0.10;

  // Sand grain texture: fine, stable per pixel (never flickers from the time value).
  float grain = 0.45 + 0.55 * hash(floor(p * vec2(960.0, 540.0)));
  // Hit scatter: a sparse set of grains thrown off the lines, kept inside the plate.
  float scatterCell = hash(floor(p * 420.0));
  float scatter = step(0.994 - 0.006 * min(uAgit, 1.0), scatterCell) * min(uAgit, 1.0) * 0.6;

  vec3 sand = vec3(1.0, 0.84, 0.50) * (line * 0.9 * grain + glow + scatter);
  vec3 plateCol = vec3(0.075, 0.080, 0.098) - vec3(0.045, 0.047, 0.056) * distance(p, vec2(0.5)) * 1.5;
  float edgeLine = 1.0 - smoothstep(0.0, 0.006, min(min(p.x, 1.0 - p.x), min(p.y, 1.0 - p.y)));
  vec3 col = plateCol + vec3(0.16, 0.19, 0.26) * edgeLine + sand;
  gl_FragColor = vec4(col, 1.0);
}
`;

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const noteName = (hz: number) => {
  const midi = Math.round(69 + 12 * Math.log2(hz / 440));
  return `${NOTE_NAMES[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`;
};

interface Props { features: AudioMultibandFeatures; intensity?: number }

export const CymaticPlateVisualizer: React.FC<Props> = ({ features, intensity = 1 }) => {
  const frame = useCurrentFrame();
  const drive = Number.isFinite(intensity) ? Math.max(0, Math.min(2, intensity)) : 1;
  const timeline = useMemo(() => compileCymatic(features, 30, Math.max(features.bass.length, 1)), [features]);

  const canvasRef = useThreeScene(({ canvas, width, height }) => {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#030407");
    const camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 100);
    camera.up.set(0, 0, 1);
    camera.position.set(0, -8.6, 7.4);
    camera.lookAt(0, -0.45, 0);

    const modeUniform = Array.from({ length: MAX_MODES }, () => new THREE.Vector4(0, 0, 0, 0));
    const shared = { uModes: { value: modeUniform }, uPatterned: { value: 0 }, uAgit: { value: 0 }, uTime: { value: 0 } };
    const sandMaterial = new THREE.ShaderMaterial({
      vertexShader: sandVertex, fragmentShader: sandFragment, uniforms: shared,
      extensions: { derivatives: true } as any,
    });
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(PLATE_SIZE, PLATE_SIZE), sandMaterial);
    scene.add(plate);

    return {
      draw(f: number) {
        const index = Math.max(0, Math.min(timeline.frameCount - 1, f));
        let strongest = 0;
        for (let k = 0; k < MAX_MODES; k++) {
          const base = (index * MAX_MODES + k) * 3;
          const w = timeline.modes[base + 2] * drive;
          modeUniform[k].set(timeline.modes[base], timeline.modes[base + 1], Math.min(1.5, w), 0);
          strongest = Math.max(strongest, w);
        }
        shared.uPatterned.value = strongest > 0.02 ? 1 : 0;
        shared.uAgit.value = timeline.agitation[index] * drive;
        shared.uTime.value = f / 30;
        renderer.render(scene, camera);
      },
      dispose() {
        sandMaterial.dispose();
        plate.geometry.dispose();
        renderer.dispose();
      },
    };
  }, [timeline, drive]);

  const index = Math.max(0, Math.min(timeline.frameCount - 1, frame));
  const hz = timeline.dominantHz[index];
  const mode = hz > 0 ? MODE_TABLE[modeIndexForPitch(hz)] : null;
  const caption = !timeline.hasNotes
    ? "NO PITCHED NOTES DETECTED · PLATE REACTS TO HITS ONLY"
    : hz > 0 ? `${noteName(hz)} · ${hz.toFixed(1)} HZ · PATTERN (${mode!.n}, ${mode!.m})` : "—";

  return (
    <div style={{ position: "absolute", inset: 0, background: "#030407" }}>
      <canvas ref={canvasRef} width={1920} height={1080} style={{ width: "100%", height: "100%", display: "block" }} />
      <div style={{ position: "absolute", left: 64, top: 52, color: "#7c869a", fontFamily: "Inter, Helvetica, Arial, sans-serif",
        letterSpacing: 4, fontSize: 18 }}>
        <div>CYMATIC PLATE</div>
        <div style={{ marginTop: 10, color: "#d9c692", fontSize: 22, letterSpacing: 3 }}>{caption}</div>
      </div>
    </div>
  );
};
