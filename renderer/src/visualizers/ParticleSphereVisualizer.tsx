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
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}
`;

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

SIMPLEX_NOISE_GLSL

void main() {
  vTreble = uTreble;
  vTransient = uTransient;

  vec3 n = normalize(position);
  vec3 p = position;

  float flowTime = uTime * 0.18 + uVocal * 1.4 + uMids * 0.9;
  float n1 = snoise(p * 0.68 + vec3(flowTime * 0.16, flowTime * 0.10, 0.0));
  float n2 = snoise(p * 1.35 - vec3(0.0, flowTime * 0.18, flowTime * 0.07));

  float wavePhase = p.y * 20.0 + p.x * 2.5 + n1 * 1.8 + flowTime * 0.45;
  float ridgeRaw = sin(wavePhase);
  float ridgeCrest = smoothstep(-0.05, 0.65, ridgeRaw);
  vRidge = ridgeCrest;

  float breathAmp = 0.04 + n2 * 0.02 + uBass * 0.015;
  float disp = breathAmp;
  vDisp = disp;

  vec3 trebleJitter = n * (snoise(position * 8.0 + vec3(uTime * 4.5)) * uTreble * 0.028);
  vec3 displacedPosition = position + n * disp + trebleJitter;
  vec4 mvPosition = modelViewMatrix * vec4(displacedPosition, 1.0);

  vec3 viewNormal = normalize(normalMatrix * (n + vec3(n2 * 0.12, ridgeCrest * 0.22, 0.0)));
  vNormal = viewNormal;
  vec3 viewDir = normalize(-mvPosition.xyz);
  vFresnel = clamp(1.0 - max(dot(viewNormal, viewDir), 0.0), 0.0, 1.0);
  vFacing  = smoothstep(-0.05, 0.05, dot(viewNormal, viewDir));

  float pSize = (1.8 + uTreble * 0.4) * (300.0 / -mvPosition.z);
  gl_PointSize = clamp(pSize, 1.2, 3.8);
  gl_Position = projectionMatrix * mvPosition;
}
`;

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

  float alphaMask = smoothstep(0.5, 0.16, dist);

  // Valley dots glow with mid-amber — sphere is fully lit, no dark voids
  vec3 valleyDark  = vec3(0.70, 0.38, 0.015);  // mid-amber, not near-black
  vec3 slopeAmber  = vec3(0.88, 0.55, 0.025);
  vec3 crestGold   = vec3(1.00, 0.80, 0.070);
  vec3 blazeGold   = vec3(1.00, 0.92, 0.140);
  vec3 rimWarm     = vec3(1.00, 0.82, 0.140);

  vec3 col = mix(valleyDark, slopeAmber, smoothstep(0.0, 0.35, vRidge));
  col      = mix(col, crestGold,  smoothstep(0.35, 0.70, vRidge));
  col      = mix(col, blazeGold,  smoothstep(0.70, 1.00, vRidge));

  vec3 lightDir = normalize(vec3(0.15, 0.25, 1.0));
  float NdotL = max(dot(vNormal, lightDir), 0.0);
  col += blazeGold * pow(NdotL, 2.2) * vRidge * 0.35;

  col += vec3(0.45, 0.20, 0.010) * (1.0 - vFresnel * 0.5);

  float rim = pow(vFresnel, 2.5);
  col = mix(col, rimWarm, rim * 0.55);
  col += vec3(0.95, 0.72, 0.10) * pow(vFresnel, 4.0) * 0.60;

  float sparkle = sin(coord.x * 18.0 + coord.y * 18.0 + vTreble * 10.0) * vTreble;
  col += vec3(0.22, 0.16, 0.03) * max(0.0, sparkle);

  col += vec3(0.30, 0.22, 0.04) * (vTransient * vRidge);

  float alpha = alphaMask * vFacing * (0.82 + rim * 0.18);
  gl_FragColor = vec4(col * (1.08 + uBass * 0.12), alpha);
}
`;

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

SIMPLEX_NOISE_GLSL

void main() {
  vec3 floorBase = vec3(0.008, 0.010, 0.014);

  float dx = vWorldPos.x - uOrbPos.x;
  float dz = vWorldPos.z - uOrbPos.z;

  float spreadX = 1.6 + uBass * 0.4 + uTransient * 0.6;
  float reflShape = exp(-(dx * dx / spreadX + dz * dz / 8.0));

  float floorGrain = snoise(vec3(vWorldPos.x * 3.0, vWorldPos.z * 7.0, 0.0)) * 0.10;
  float totalRefl = clamp(reflShape * (0.90 + floorGrain), 0.0, 1.0);

  vec3 goldReflection = vec3(1.0, 0.58, 0.05) * (1.20 + uBass * 0.35 + uBeat * 0.25 + uTransient * 0.50);
  vec3 finalColor = floorBase + goldReflection * totalRefl;

  float vignette = smoothstep(22.0, 3.0, length(vWorldPos.xz));
  gl_FragColor = vec4(finalColor * vignette, 1.0);
}
`;

const spotLensVertexShader = `
void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = 3.2 * (220.0 / -mvPosition.z);
  gl_Position = projectionMatrix * mvPosition;
}
`;

const spotLensFragmentShader = `
void main() {
  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;
  float glow = pow(smoothstep(0.5, 0.0, dist), 2.5);
  vec3 lensColor = vec3(0.98, 0.88, 0.72) * glow;
  gl_FragColor = vec4(lensColor, glow * 0.65);
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
    scene.background = new THREE.Color("#020304");
    scene.fog = new THREE.FogExp2(0x020304, 0.032);

    // FOV 42 + z=13.5 -> sphere fills ~50% frame height
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000);
    camera.position.set(0, 0.20, 13.5);
    camera.lookAt(0, 0.30, 0);

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);

    const orbPositions: number[] = [];
    const numRings = 200;
    const sphereRadius = 2.20;

    for (let i = 0; i < numRings; i++) {
      const lat = ((i + 0.5) / numRings - 0.5) * Math.PI * 0.94;
      const rRing = Math.cos(lat) * sphereRadius;
      const yRing = Math.sin(lat) * sphereRadius;
      const pointsInRing = Math.max(12, Math.round(440 * Math.cos(lat)));
      for (let j = 0; j < pointsInRing; j++) {
        const lon = (j / pointsInRing) * Math.PI * 2;
        orbPositions.push(Math.cos(lon) * rRing, yRing, Math.sin(lon) * rRing);
      }
    }

    const orbGeometry = new THREE.BufferGeometry();
    orbGeometry.setAttribute("position", new THREE.Float32BufferAttribute(orbPositions, 3));
    orbGeometry.rotateX(-0.12);
    orbGeometry.rotateY(0.22);

    // Inject simplex noise into shaders
    const vsWithNoise = particleVertexShader.replace("SIMPLEX_NOISE_GLSL", simplexNoiseGLSL);
    const fsFloorWithNoise = floorFragmentShader.replace("SIMPLEX_NOISE_GLSL", simplexNoiseGLSL);

    const orbMaterial = new THREE.ShaderMaterial({
      vertexShader: vsWithNoise,
      fragmentShader: particleFragmentShader,
      uniforms: {
        uTime:      { value: 0.0 },
        uBass:      { value: 0.0 },
        uMids:      { value: 0.0 },
        uVocal:     { value: 0.0 },
        uTreble:    { value: 0.0 },
        uTransient: { value: 0.0 },
        uBeat:      { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const orbPoints = new THREE.Points(orbGeometry, orbMaterial);
    orbPoints.position.set(0, 0.30, 0);
    scene.add(orbPoints);

    // Embers: tight clusters at sphere sides only
    const sparkCount = 600;
    const sparkGeo = new THREE.BufferGeometry();
    const sparkPos = new Float32Array(sparkCount * 3);

    let seed = 87654;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (let i = 0; i < sparkCount; i++) {
      const side = rand() > 0.5 ? 1 : -1;
      const r = Math.pow(rand(), 0.8);
      sparkPos[i * 3]     = side * (2.3 + r * 2.8);
      sparkPos[i * 3 + 1] = (rand() - 0.42) * 2.0 + 0.30 + (1.0 - r) * 0.25;
      sparkPos[i * 3 + 2] = (rand() - 0.5) * 1.4;
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
        varying float vAlpha;

        void main() {
          vec3 p = position;
          float side = sign(position.x);
          p.x += side * (uBass * 0.06 + uTransient * 0.18);
          p.y += sin(uTime * 0.35 + position.x * 1.0) * 0.08 + uTransient * 0.08;
          p.z += cos(uTime * 0.28 + position.y * 1.0) * 0.06;
          vTwinkle = sin(uTime * 10.0 + position.x * 4.5) * uTreble;
          float proximity = 1.0 - clamp((abs(position.x) - 2.3) / 2.8, 0.0, 1.0);
          vAlpha = 0.55 + proximity * 0.35;
          vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
          float pSize = (1.6 + uTransient * 0.6 + uTreble * 0.5) * (280.0 / -mvPosition.z);
          gl_PointSize = clamp(pSize, 1.0, 3.5);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        varying float vTwinkle;
        varying float vAlpha;
        uniform float uTransient;
        void main() {
          vec2 coord = gl_PointCoord - vec2(0.5);
          float dist = length(coord);
          if (dist > 0.5) discard;
          float twinkle = 0.80 + 0.30 * vTwinkle;
          float alpha = smoothstep(0.5, 0.12, dist) * vAlpha * twinkle;
          vec3 sparkCol = vec3(1.0, 0.72, 0.08);
          gl_FragColor = vec4(sparkCol * (1.0 + uTransient * 0.6), alpha);
        }
      `,
      uniforms: {
        uTime:      { value: 0.0 },
        uBass:      { value: 0.0 },
        uTreble:    { value: 0.0 },
        uTransient: { value: 0.0 },
        uBeat:      { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const sparkPoints = new THREE.Points(sparkGeo, sparkMaterial);
    scene.add(sparkPoints);

    const floorGeo = new THREE.PlaneGeometry(50, 50);
    const floorMaterial = new THREE.ShaderMaterial({
      vertexShader: floorVertexShader,
      fragmentShader: fsFloorWithNoise,
      uniforms: {
        uOrbPos:    { value: new THREE.Vector3(0, 0.30, 0) },
        uBass:      { value: 0.0 },
        uBeat:      { value: 0.0 },
        uTransient: { value: 0.0 },
      },
      depthWrite: true,
    });

    const floorMesh = new THREE.Mesh(floorGeo, floorMaterial);
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.y = -2.30;
    scene.add(floorMesh);

    const pillarMat = new THREE.MeshBasicMaterial({ color: 0x050709 });
    [-8.0, -5.5, 5.5, 8.0].forEach((px) => {
      const pillar = new THREE.Mesh(new THREE.BoxGeometry(0.25, 12, 0.25), pillarMat);
      pillar.position.set(px, 1.5, -6.0);
      scene.add(pillar);
    });

    const wallMat = new THREE.MeshBasicMaterial({ color: 0x030507 });
    const wallMesh = new THREE.Mesh(new THREE.PlaneGeometry(45, 18), wallMat);
    wallMesh.position.set(0, 2.5, -6.5);
    scene.add(wallMesh);

    const trussMat = new THREE.MeshBasicMaterial({ color: 0x0a0f16 });
    const trussBar = new THREE.Mesh(new THREE.BoxGeometry(22, 0.06, 0.10), trussMat);
    trussBar.position.set(0, 4.8, -4.5);
    scene.add(trussBar);

    // 5 warm tungsten spots (small, not dominant)
    const spotCoords: [number, number, number][] = [
      [-5.2, 5.0, -4.5],
      [-2.8, 4.9, -4.3],
      [ 0.0, 4.8, -4.2],
      [ 2.8, 4.9, -4.3],
      [ 5.2, 5.0, -4.5],
    ];

    const spotGeo = new THREE.BufferGeometry();
    const spotPos = new Float32Array(spotCoords.length * 3);
    spotCoords.forEach(([x, y, z], idx) => {
      spotPos[idx * 3]     = x;
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
    scene.add(new THREE.Points(spotGeo, spotMat));

    threeRef.current = { renderer, scene, camera, orbPoints, orbMaterial, sparkMaterial, floorMaterial };

    renderer.render(scene, camera);
    continueRender(handle);

    return () => {
      renderer.dispose();
      orbGeometry.dispose(); orbMaterial.dispose();
      sparkGeo.dispose(); sparkMaterial.dispose();
      floorGeo.dispose(); floorMaterial.dispose();
      trussMat.dispose(); pillarMat.dispose(); wallMat.dispose();
      spotGeo.dispose(); spotMat.dispose();
    };
  }, [width, height, handle]);

  const timeSeconds = frame / fps;
  const bass  = (features?.bass?.[frame] ?? 0.0) * intensity;
  const vocal   = features?.vocalEnergy?.[frame] ?? 0.0;
  const rawMids = features?.mids?.[frame] ?? 0.0;
  const mids    = (rawMids * 0.6 + vocal * 0.4) * intensity;
  const treble  = (features?.treble?.[frame] ?? 0.0) * intensity;

  let beatImpulse = 0.0;
  if (features?.beatFrames && features.beatFrames.length > 0) {
    for (let i = features.beatFrames.length - 1; i >= 0; i--) {
      const bf = features.beatFrames[i];
      if (bf <= frame) {
        const diff = frame - bf;
        if (diff < 8) beatImpulse = Math.exp(-diff * 0.48);
        break;
      }
    }
  }

  let transientImpulse = 0.0;
  if (features?.transients && features.transients.length > 0) {
    for (let i = features.transients.length - 1; i >= 0; i--) {
      const tf = features.transients[i];
      if (tf <= frame) {
        const diff = frame - tf;
        if (diff < 10) transientImpulse = Math.exp(-diff * 0.38);
        break;
      }
    }
  }

  if (threeRef.current) {
    const { renderer, scene, camera, orbPoints, orbMaterial, sparkMaterial, floorMaterial } = threeRef.current;

    orbMaterial.uniforms.uTime.value      = timeSeconds;
    orbMaterial.uniforms.uBass.value      = bass;
    orbMaterial.uniforms.uMids.value      = mids;
    orbMaterial.uniforms.uVocal.value     = vocal;
    orbMaterial.uniforms.uTreble.value    = treble;
    orbMaterial.uniforms.uTransient.value = transientImpulse;
    orbMaterial.uniforms.uBeat.value      = beatImpulse;

    sparkMaterial.uniforms.uTime.value      = timeSeconds;
    sparkMaterial.uniforms.uBass.value      = bass;
    sparkMaterial.uniforms.uTreble.value    = treble;
    sparkMaterial.uniforms.uTransient.value = transientImpulse;
    sparkMaterial.uniforms.uBeat.value      = beatImpulse;

    floorMaterial.uniforms.uBass.value      = bass;
    floorMaterial.uniforms.uBeat.value      = beatImpulse;
    floorMaterial.uniforms.uTransient.value = transientImpulse;

    orbPoints.rotation.y = timeSeconds * 0.10;
    orbPoints.rotation.x = Math.sin(timeSeconds * 0.05) * 0.035;

    // Minimal bass breathing — no kick shaking
    const scale = 1.0 + bass * 0.028;
    orbPoints.scale.set(scale, scale, scale);

    // Static cinematic camera
    camera.position.set(0, 0.20, 13.5);

    renderer.render(scene, camera);
  }

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0, display: "block" }}
    />
  );
};
