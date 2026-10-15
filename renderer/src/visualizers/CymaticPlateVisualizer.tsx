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
const GRAINS_PER_SIDE = 260;
const PLATE_SIZE = 6.0;
const SEED = 20241016;

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

const grainVertex = `
${modeGLSL}
uniform float uAgit;
uniform float uPatterned;
uniform float uScale;
attribute vec2 aRest;
attribute vec3 aSeed;
varying float vLift;
varying float vCalm;

void main() {
  vec2 p = aRest;
  float settled = 1.0;
  if (uPatterned > 0.0) {
    for (int i = 0; i < 16; i++) {
      vec3 f = plate(p);
      vec2 g = f.yz;
      vec2 step = -f.x * g / (dot(g, g) + 0.06);
      float len = length(step);
      if (len > 0.07) step *= 0.07 / len;
      p = clamp(p + 0.85 * step, 0.0, 1.0);
    }
    settled = 1.0 - smoothstep(0.0, 0.5, abs(plate(p).x));
  }
  // Hit agitation: grains are thrown up and sideways, then fall back as it decays.
  p += (aSeed.xy - 0.5) * (0.003 + 0.30 * uAgit * aSeed.z);
  p = clamp(p, 0.0, 1.0);
  float lift = uAgit * (0.15 + 1.5 * aSeed.z * aSeed.z) * 0.55;
  vec3 world = vec3((p.x - 0.5) * ${PLATE_SIZE.toFixed(2)}, (p.y - 0.5) * ${PLATE_SIZE.toFixed(2)}, 0.03 + lift);
  vec4 mv = modelViewMatrix * vec4(world, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = clamp((2.1 + 1.2 * min(uAgit, 1.0) + 1.4 * aSeed.z) * uScale / -mv.z, 1.6, 7.0);
  vLift = lift;
  vCalm = settled;
}
`;

const grainFragment = `
varying float vLift;
varying float vCalm;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.12, d);
  vec3 sand = mix(vec3(0.55, 0.46, 0.30), vec3(1.0, 0.86, 0.55), clamp(vCalm * 0.7 + vLift * 1.4, 0.0, 1.0));
  gl_FragColor = vec4(sand, soft * (0.16 + 0.16 * vCalm + 0.3 * min(vLift, 1.0)));
}
`;

const plateVertex = `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;

const plateFragment = `
${modeGLSL}
uniform float uPatterned;
varying vec2 vUv;
void main() {
  vec3 base = mix(vec3(0.075, 0.080, 0.098), vec3(0.030, 0.033, 0.042), distance(vUv, vec2(0.5)) * 1.5);
  // Anti-nodes (where the plate moves most) glow faintly cool; nodal lines stay dark.
  float amp = uPatterned > 0.0 ? clamp(abs(plate(vUv).x) * 0.6, 0.0, 1.0) : 0.0;
  vec3 col = base + vec3(0.03, 0.065, 0.12) * amp;
  float edge = min(min(vUv.x, 1.0 - vUv.x), min(vUv.y, 1.0 - vUv.y));
  col += vec3(0.16, 0.19, 0.26) * (1.0 - smoothstep(0.0, 0.008, edge));
  gl_FragColor = vec4(col, 1.0);
}
`;

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const noteName = (hz: number) => {
  const midi = Math.round(69 + 12 * Math.log2(hz / 440));
  return `${NOTE_NAMES[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`;
};

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

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
    const shared = { uModes: { value: modeUniform }, uPatterned: { value: 0 } };

    const plate = new THREE.Mesh(
      new THREE.PlaneGeometry(PLATE_SIZE, PLATE_SIZE),
      new THREE.ShaderMaterial({ vertexShader: plateVertex, fragmentShader: plateFragment, uniforms: shared }),
    );
    scene.add(plate);

    const rand = mulberry32(SEED);
    const count = GRAINS_PER_SIDE * GRAINS_PER_SIDE;
    const rest = new Float32Array(count * 2), seed = new Float32Array(count * 3), position = new Float32Array(count * 3);
    for (let i = 0; i < GRAINS_PER_SIDE; i++) for (let j = 0; j < GRAINS_PER_SIDE; j++) {
      const k = i * GRAINS_PER_SIDE + j;
      rest[k * 2] = (i + rand()) / GRAINS_PER_SIDE;
      rest[k * 2 + 1] = (j + rand()) / GRAINS_PER_SIDE;
      seed[k * 3] = rand(); seed[k * 3 + 1] = rand(); seed[k * 3 + 2] = rand();
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
    geometry.setAttribute("aRest", new THREE.BufferAttribute(rest, 2));
    geometry.setAttribute("aSeed", new THREE.BufferAttribute(seed, 3));
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 20);
    const grainMaterial = new THREE.ShaderMaterial({
      vertexShader: grainVertex, fragmentShader: grainFragment,
      uniforms: { ...shared, uAgit: { value: 0 }, uScale: { value: height * 0.55 } },
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
    scene.add(new THREE.Points(geometry, grainMaterial));

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
        grainMaterial.uniforms.uAgit.value = timeline.agitation[index] * drive;
        renderer.render(scene, camera);
      },
      dispose() {
        geometry.dispose();
        grainMaterial.dispose();
        (plate.material as THREE.Material).dispose();
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
