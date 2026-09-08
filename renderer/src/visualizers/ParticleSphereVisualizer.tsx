import React, { useRef, useEffect, useState } from "react";
import { useCurrentFrame, useVideoConfig, delayRender, continueRender } from "remotion";
import * as THREE from "three";
import { AudioMultibandFeatures } from "../types/manifest";

// 3D Simplex Noise in GLSL
const simplexNoiseGLSL = `
vec4 permute(vec4 x) { return mod(((x*34.0)+1.0)*x, 289.0); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);

  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);

  vec3 x1 = x0 - i1 + 1.0 * C.xxx;
  vec3 x2 = x0 - i2 + 2.0 * C.xxx;
  vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;

  i = mod(i, 289.0);
  vec4 p = permute(permute(permute(
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0))
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));

  float n_ = 0.142857142857;
  vec3  ns = n_ * D.wyz - D.xzx;

  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);

  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);

  vec4 x = x_ *ns.x + ns.yyyy;
  vec4 y = y_ *ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);

  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);

  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));

  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;

  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);

  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;

  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}
`;

// Vertex shader with audio-reactive corrugated wave folds & micro-jitters
const particleVertexShader = `
uniform float uTime;
uniform float uBass;
uniform float uMids;
uniform float uTreble;
uniform float uVocal;
uniform float uTransient;
uniform float uBeat;
varying float vFresnel;
varying float vDisp;
varying float vFacing;
varying float vRidge;
varying vec3 vNormal;
varying float vTreble;
varying float vTransient;

${simplexNoiseGLSL}

void main() {
  vTreble = uTreble;
  vTransient = uTransient;

  vec3 n = normalize(position);
  vec3 p = position;

  // 1. Organic swirling field speed-modulated by vocal and mids
  float flowTime = uTime * 0.22 + uVocal * 1.6 + uMids * 1.1;
  float n1 = snoise(p * 0.72 + vec3(flowTime * 0.18, flowTime * 0.12, 0.0));
  float n2 = snoise(p * 1.45 - vec3(0.0, flowTime * 0.20, flowTime * 0.08));

  // 2. Harmonic fingerprint ridges running across the sphere surface
  // Wave phase advances with time and vocal/mid energy
  float wavePhase = p.y * 6.5 + p.x * 2.2 + n1 * 3.2 + flowTime * 0.85;
  float ridgeRaw = sin(wavePhase);
  // Sharp crests with smooth valleys: creates the distinct lines of dots
  float ridgeCrest = smoothstep(-0.25, 0.75, ridgeRaw);
  vRidge = ridgeCrest;

  // 3. Audio-reactive surface displacement:
  // Vocals & mids directly modulate the ridge wave height!
  float ridgeAmp = 0.26 + uVocal * 0.28 + uMids * 0.16;
  float baseAmp = 0.12 + n2 * 0.08 + uBass * 0.05; // Subtle bass breathing only!
  float disp = ridgeCrest * ridgeAmp + baseAmp;
  vDisp = disp;

  // 4. Treble micro-shimmer on individual particles
  vec3 trebleJitter = n * (snoise(position * 7.0 + vec3(uTime * 4.0)) * uTreble * 0.035);

  vec3 displacedPosition = position + n * disp + trebleJitter;
  vec4 mvPosition = modelViewMatrix * vec4(displacedPosition, 1.0);

  // Normal calculation for directional lighting and rim calculation
  vec3 viewNormal = normalize(normalMatrix * (n + vec3(n2 * 0.15, ridgeCrest * 0.25, 0.0)));
  vNormal = viewNormal;
  vec3 viewDir = normalize(-mvPosition.xyz);
  vFresnel = clamp(1.0 - max(dot(viewNormal, viewDir), 0.0), 0.0, 1.0);

  // Soft front-facing factor: cull back hemisphere to prevent blowout
  vFacing = smoothstep(-0.05, 0.25, dot(viewNormal, viewDir));

  // Point size: pin-point, clean, sharp dots (no ballooning!)
  float pSize = (2.2 + uTreble * 0.5) * (270.0 / -mvPosition.z);
  gl_PointSize = clamp(pSize, 1.4, 4.5);
  gl_Position = projectionMatrix * mvPosition;
}
`;

// Fragment shader: Radiant golden-amber palette with treble shimmer & transient flash
const particleFragmentShader = `
varying float vFresnel;
varying float vDisp;
varying float vFacing;
varying float vRidge;
varying vec3 vNormal;
varying float vTreble;
varying float vTransient;
uniform float uBass;
uniform float uMids;
uniform float uVocal;
uniform float uBeat;

void main() {
  if (vFacing < 0.02) discard;

  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;

  // Soft circular anti-aliased dot mask
  float alphaMask = smoothstep(0.5, 0.18, dist);

  // Reference 1:1 Palette (Radiant Honey Gold, NO cold white)
  vec3 valleyDark  = vec3(0.50, 0.22, 0.015); // Warm glowing amber in valleys
  vec3 ridgeAmber  = vec3(0.92, 0.55, 0.030); // Rich warm gold on slopes
  vec3 brightGold  = vec3(1.00, 0.82, 0.080); // Radiant warm golden crest
  vec3 crestYellow = vec3(1.00, 0.94, 0.200); // Luminous yellow-gold crest highlight
  vec3 rimCorona   = vec3(1.00, 0.86, 0.160); // Warm golden rim corona

  // 1. Ridge shading: valleys are warm amber, crests are blazing gold
  vec3 col = mix(valleyDark, ridgeAmber, smoothstep(0.0, 0.45, vRidge));
  col = mix(col, brightGold, smoothstep(0.45, 0.90, vRidge));

  // 2. Frontal key light illuminates the facing ridges, creating rich 3D depth
  vec3 lightDir = normalize(vec3(0.20, 0.35, 0.90));
  float NdotL = max(dot(vNormal, lightDir), 0.0);
  col += crestYellow * pow(NdotL, 1.8) * vRidge * 0.45;

  // Ambient front core warmth so the center is filled with golden dots
  col += vec3(0.35, 0.18, 0.01) * (1.0 - vFresnel * 0.6);

  // 3. Incandescent golden rim halo
  float rim = pow(vFresnel, 2.2);
  col = mix(col, rimCorona, rim * 0.65);
  col += vec3(1.0, 0.90, 0.25) * pow(vFresnel, 3.8) * 0.75;

  // 4. Treble twinkle on individual points
  float sparkle = sin(coord.x * 20.0 + coord.y * 20.0 + vTreble * 12.0) * vTreble;
  col += vec3(0.25, 0.20, 0.04) * max(0.0, sparkle);

  // 5. Transient energy pulse along the crests (brightens without deforming)
  col += vec3(0.35, 0.28, 0.05) * (vTransient * vRidge);

  // Alpha preserves dot separation and allows dark valleys to show through
  float alpha = alphaMask * vFacing * (0.80 + rim * 0.20);
  gl_FragColor = vec4(col * (1.10 + uBass * 0.15), alpha);
}
`;

// Industrial concrete studio floor shader with audio-reactive specular pool
const floorVertexShader = `
varying vec3 vWorldPos;
varying vec2 vUv;
void main() {
  vUv = uv;
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPos = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

const floorFragmentShader = `
uniform vec3 uOrbPos;
uniform float uBass;
uniform float uBeat;
uniform float uTransient;
varying vec3 vWorldPos;
varying vec2 vUv;

${simplexNoiseGLSL}

void main() {
  vec3 floorBase = vec3(0.010, 0.013, 0.018);

  float dx = vWorldPos.x - uOrbPos.x;
  float dz = vWorldPos.z - uOrbPos.z;

  // Floor reflection stretches and expands with bass & beat downbeats
  float spreadX = 2.8 + uBass * 0.6 + uTransient * 1.0;
  float reflShape = exp(-(dx * dx / spreadX + dz * dz / 15.0));

  float floorGrain = snoise(vec3(vWorldPos.x * 2.2, vWorldPos.z * 5.5, 0.0)) * 0.15;
  float totalRefl = clamp(reflShape * (0.95 + floorGrain), 0.0, 1.0);

  vec3 goldReflection = vec3(1.0, 0.72, 0.10) * (1.35 + uBass * 0.45 + uBeat * 0.35 + uTransient * 0.70);
  vec3 finalColor = floorBase + goldReflection * totalRefl;

  // Ambient spotlight reflections on wet floor
  float spot1 = exp(-(pow(vWorldPos.x + 3.8, 2.0) / 0.8 + pow(vWorldPos.z + 1.8, 2.0) / 6.0)) * 0.06;
  float spot2 = exp(-(pow(vWorldPos.x - 3.8, 2.0) / 0.8 + pow(vWorldPos.z + 1.8, 2.0) / 6.0)) * 0.06;
  finalColor += vec3(0.7, 0.85, 1.0) * (spot1 + spot2);

  float vignette = smoothstep(26.0, 4.0, length(vWorldPos.xz));
  gl_FragColor = vec4(finalColor * vignette, 1.0);
}
`;

// Spotlight lens flare shaders
const spotLensVertexShader = `
void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = 4.2 * (260.0 / -mvPosition.z);
  gl_Position = projectionMatrix * mvPosition;
}
`;

const spotLensFragmentShader = `
void main() {
  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;
  float glow = pow(smoothstep(0.5, 0.0, dist), 1.8);
  vec3 lensColor = mix(vec3(0.85, 0.92, 1.0), vec3(1.0, 1.0, 1.0), glow);
  gl_FragColor = vec4(lensColor, glow * 0.92);
}
`;

interface ParticleSphereVisualizerProps {
  features: AudioMultibandFeatures;
  intensity?: number;
}

export const ParticleSphereVisualizer: React.FC<ParticleSphereVisualizerProps> = ({
  features,
  intensity = 1.0,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [handle] = useState(() => delayRender("Init ThreeJS WebGL context"));

  const threeRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    orbPoints: THREE.Points;
    orbMaterial: THREE.ShaderMaterial;
    sparkMaterial: THREE.ShaderMaterial;
    floorMaterial: THREE.ShaderMaterial;
  } | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#030406");
    scene.fog = new THREE.FogExp2(0x030406, 0.04);

    const camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 1000);
    camera.position.set(0, 0.05, 9.4);
    camera.lookAt(0, 0.25, 0);

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);

    // High density area-weighted latitude rings: 220 rings x up to 480 points = ~70,000 points
    const orbPositions: number[] = [];
    const numRings = 220;
    const sphereRadius = 2.35;

    for (let i = 0; i < numRings; i++) {
      const lat = ((i + 0.5) / numRings - 0.5) * Math.PI * 0.94;
      const rRing = Math.cos(lat) * sphereRadius;
      const yRing = Math.sin(lat) * sphereRadius;

      // Constant surface point density
      const pointsInRing = Math.max(14, Math.round(480 * Math.cos(lat)));
      for (let j = 0; j < pointsInRing; j++) {
        const lon = (j / pointsInRing) * Math.PI * 2;
        orbPositions.push(Math.cos(lon) * rRing, yRing, Math.sin(lon) * rRing);
      }
    }

    const orbGeometry = new THREE.BufferGeometry();
    orbGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(orbPositions, 3)
    );

    // Diagonal tilt matching reference camera perspective
    orbGeometry.rotateX(-0.16);
    orbGeometry.rotateY(0.26);

    const orbMaterial = new THREE.ShaderMaterial({
      vertexShader: particleVertexShader,
      fragmentShader: particleFragmentShader,
      uniforms: {
        uTime: { value: 0.0 },
        uBass: { value: 0.0 },
        uMids: { value: 0.0 },
        uVocal: { value: 0.0 },
        uTreble: { value: 0.0 },
        uTransient: { value: 0.0 },
        uBeat: { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const orbPoints = new THREE.Points(orbGeometry, orbMaterial);
    orbPoints.position.set(0, 0.35, 0);
    scene.add(orbPoints);

    // Lateral floating sparks / embers (fan spray on both sides)
    const sparkCount = 900;
    const sparkGeo = new THREE.BufferGeometry();
    const sparkPos = new Float32Array(sparkCount * 3);

    let seed = 87654;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (let i = 0; i < sparkCount; i++) {
      const side = rand() > 0.5 ? 1 : -1;
      const r = Math.pow(rand(), 1.2);
      const x = side * (2.1 + r * 5.2);
      const y = (rand() - 0.44) * 2.6 + 0.35 + (1.0 - r) * 0.35;
      const z = (rand() - 0.5) * 2.2;

      sparkPos[i * 3] = x;
      sparkPos[i * 3 + 1] = y;
      sparkPos[i * 3 + 2] = z;
    }

    sparkGeo.setAttribute("position", new THREE.BufferAttribute(sparkPos, 3));
    const sparkMaterial = new THREE.ShaderMaterial({
      vertexShader: `
        uniform float uTime;
        uniform float uBass;
        uniform float uTreble;
        uniform float uTransient;
        uniform float uBeat;
        varying float vTwinkle;

        void main() {
          vec3 p = position;
          float side = sign(position.x);

          // Smooth gentle floating drift (no violent jumping on kicks)
          p.x += side * (uBass * 0.08 + uTransient * 0.30);
          p.y += sin(uTime * 0.4 + position.x * 1.2) * 0.10 + (uTransient * 0.12);
          p.z += cos(uTime * 0.3 + position.y * 1.2) * 0.08;

          vTwinkle = sin(uTime * 12.0 + position.x * 5.0) * uTreble;

          vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
          float pSize = (2.0 + uTransient * 0.8 + uTreble * 0.6) * (260.0 / -mvPosition.z);
          gl_PointSize = clamp(pSize, 1.2, 5.0);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        varying float vTwinkle;
        uniform float uTransient;
        void main() {
          vec2 coord = gl_PointCoord - vec2(0.5);
          float dist = length(coord);
          if (dist > 0.5) discard;

          float twinkle = 0.85 + 0.35 * vTwinkle;
          float alpha = smoothstep(0.5, 0.15, dist) * 0.85 * twinkle;
          vec3 sparkCol = vec3(1.0, 0.78, 0.12);
          gl_FragColor = vec4(sparkCol * (1.0 + uTransient * 0.8), alpha);
        }
      `,
      uniforms: {
        uTime: { value: 0.0 },
        uBass: { value: 0.0 },
        uTreble: { value: 0.0 },
        uTransient: { value: 0.0 },
        uBeat: { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const sparkPoints = new THREE.Points(sparkGeo, sparkMaterial);
    scene.add(sparkPoints);

    // Reflective Polished Concrete Floor
    const floorGeo = new THREE.PlaneGeometry(50, 50);
    const floorMaterial = new THREE.ShaderMaterial({
      vertexShader: floorVertexShader,
      fragmentShader: floorFragmentShader,
      uniforms: {
        uOrbPos: { value: new THREE.Vector3(0, 0.35, 0) },
        uBass: { value: 0.0 },
        uBeat: { value: 0.0 },
        uTransient: { value: 0.0 },
      },
      depthWrite: true,
    });

    const floorMesh = new THREE.Mesh(floorGeo, floorMaterial);
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.y = -2.35;
    scene.add(floorMesh);

    // Industrial Soundstage Background Architecture
    const pillarMat = new THREE.MeshBasicMaterial({ color: 0x06080c });
    [-7.5, -4.8, 4.8, 7.5].forEach((px) => {
      const pillar = new THREE.Mesh(new THREE.BoxGeometry(0.3, 10, 0.3), pillarMat);
      pillar.position.set(px, 1.5, -5.5);
      scene.add(pillar);
    });

    const wallMat = new THREE.MeshBasicMaterial({ color: 0x040608 });
    const wallMesh = new THREE.Mesh(new THREE.PlaneGeometry(40, 15), wallMat);
    wallMesh.position.set(0, 2.5, -6.0);
    scene.add(wallMesh);

    // Overhead Industrial Truss with triangular cross-bracing
    const trussMat = new THREE.MeshBasicMaterial({ color: 0x0e1218 });
    const leftTruss = new THREE.Mesh(new THREE.BoxGeometry(9, 0.08, 0.08), trussMat);
    leftTruss.position.set(-4.5, 3.8, -4.0);
    leftTruss.rotation.z = -0.05;
    scene.add(leftTruss);

    const rightTruss = new THREE.Mesh(new THREE.BoxGeometry(9, 0.08, 0.08), trussMat);
    rightTruss.position.set(4.5, 3.8, -4.0);
    rightTruss.rotation.z = 0.05;
    scene.add(rightTruss);

    // Studio Spotlights
    const spotCoords = [
      [-5.8, 4.0, -4.2],
      [-4.0, 3.9, -4.0],
      [-2.4, 3.8, -3.8],
      [2.4, 3.8, -3.8],
      [4.0, 3.9, -4.0],
      [5.8, 4.0, -4.2],
    ];

    const spotGeo = new THREE.BufferGeometry();
    const spotPos = new Float32Array(spotCoords.length * 3);
    spotCoords.forEach(([x, y, z], idx) => {
      spotPos[idx * 3] = x;
      spotPos[idx * 3 + 1] = y;
      spotPos[idx * 3 + 2] = z;
    });
    spotGeo.setAttribute("position", new THREE.BufferAttribute(spotPos, 3));

    const spotMat = new THREE.ShaderMaterial({
      vertexShader: spotLensVertexShader,
      fragmentShader: spotLensFragmentShader,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const spotLenses = new THREE.Points(spotGeo, spotMat);
    scene.add(spotLenses);

    threeRef.current = {
      renderer,
      scene,
      camera,
      orbPoints,
      orbMaterial,
      sparkMaterial,
      floorMaterial,
    };

    renderer.render(scene, camera);
    continueRender(handle);

    return () => {
      renderer.dispose();
      orbGeometry.dispose();
      orbMaterial.dispose();
      sparkGeo.dispose();
      sparkMaterial.dispose();
      floorGeo.dispose();
      floorMaterial.dispose();
      trussMat.dispose();
      pillarMat.dispose();
      wallMat.dispose();
      spotGeo.dispose();
      spotMat.dispose();
    };
  }, [width, height, handle]);

  // Deterministic frame update
  const timeSeconds = frame / fps;
  const bass = (features?.bass?.[frame] ?? 0.0) * intensity;
  const rawMids = features?.mids?.[frame] ?? 0.0;
  const vocal = features?.vocalEnergy?.[frame] ?? 0.0;
  const mids = (rawMids * 0.6 + vocal * 0.4) * intensity;
  const treble = (features?.treble?.[frame] ?? 0.0) * intensity;

  // Calculate exponential decaying beat impulse
  let beatImpulse = 0.0;
  if (features?.beatFrames && features.beatFrames.length > 0) {
    for (let i = features.beatFrames.length - 1; i >= 0; i--) {
      const bf = features.beatFrames[i];
      if (bf <= frame) {
        const diff = frame - bf;
        if (diff < 8) {
          beatImpulse = Math.exp(-diff * 0.48);
        }
        break;
      }
    }
  }

  // Calculate exponential decaying transient shockwave
  let transientImpulse = 0.0;
  if (features?.transients && features.transients.length > 0) {
    for (let i = features.transients.length - 1; i >= 0; i--) {
      const tf = features.transients[i];
      if (tf <= frame) {
        const diff = frame - tf;
        if (diff < 10) {
          transientImpulse = Math.exp(-diff * 0.38);
        }
        break;
      }
    }
  }

  if (threeRef.current) {
    const { renderer, scene, camera, orbPoints, orbMaterial, sparkMaterial, floorMaterial } =
      threeRef.current;

    orbMaterial.uniforms.uTime.value = timeSeconds;
    orbMaterial.uniforms.uBass.value = bass;
    orbMaterial.uniforms.uMids.value = mids;
    orbMaterial.uniforms.uVocal.value = vocal;
    orbMaterial.uniforms.uTreble.value = treble;
    orbMaterial.uniforms.uTransient.value = transientImpulse;
    orbMaterial.uniforms.uBeat.value = beatImpulse;

    sparkMaterial.uniforms.uTime.value = timeSeconds;
    sparkMaterial.uniforms.uBass.value = bass;
    sparkMaterial.uniforms.uTreble.value = treble;
    sparkMaterial.uniforms.uTransient.value = transientImpulse;
    sparkMaterial.uniforms.uBeat.value = beatImpulse;

    floorMaterial.uniforms.uBass.value = bass;
    floorMaterial.uniforms.uBeat.value = beatImpulse;
    floorMaterial.uniforms.uTransient.value = transientImpulse;

    // Slow organic Y-axis rotation
    orbPoints.rotation.y = timeSeconds * 0.12;
    orbPoints.rotation.x = Math.sin(timeSeconds * 0.06) * 0.04;

    // Smooth organic bass breathing only (no violent jumping on kicks)
    const scale = 1.0 + (bass * 0.035);
    orbPoints.scale.set(scale, scale, scale);

    // Locked cinematic camera: rock solid framing, zero camera shaking
    camera.position.set(0, 0.12, 9.35);

    renderer.render(scene, camera);
  }

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        width: "100%",
        height: "100%",
        position: "absolute",
        top: 0,
        left: 0,
        display: "block",
      }}
    />
  );
};
