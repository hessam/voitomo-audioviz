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

// Vertex shader with organic corrugated wave folds maintaining spherical boundary
const particleVertexShader = `
uniform float uTime;
uniform float uBass;
uniform float uMids;
uniform float uTreble;
varying float vFresnel;
varying float vDisp;
varying float vFacing;
varying float vRidge;
varying vec3 vNormal;

${simplexNoiseGLSL}

void main() {
  vec3 n = normalize(position);

  vec3 p = position * 0.90;
  
  // 1. Broad rolling organic folds
  float n1 = snoise(p * 0.85 + vec3(uTime * 0.16, uTime * 0.08, 0.0));
  float n2 = snoise(p * 1.70 - vec3(0.0, uTime * 0.22, uTime * 0.10));
  
  // 2. Corrugated ripple ridges matching reference fingerprint texture
  float ridgeNoise = snoise(p * 1.50 + vec3(uTime * 0.12));
  float ridges = sin(position.y * 12.0 + ridgeNoise * 3.4 + uTime * 0.28) * 0.18;
  vRidge = ridges;

  // Calibrated displacement keeps overall spherical form round and cohesive
  float disp = (n1 * 0.36 + n2 * 0.18 + ridges * 0.46) * (0.48 + uBass * 0.35);
  vDisp = disp;

  vec3 displacedPosition = position + n * disp;
  vec4 mvPosition = modelViewMatrix * vec4(displacedPosition, 1.0);

  // View-space normal for rim halo and frontal lighting
  vec3 viewNormal = normalize(normalMatrix * (n + vec3(n2 * 0.10, ridges * 0.20, 0.0)));
  vNormal = viewNormal;
  vec3 viewDir = normalize(-mvPosition.xyz);
  vFresnel = clamp(1.0 - max(dot(viewNormal, viewDir), 0.0), 0.0, 1.0);

  // Soft front-facing factor: allows smooth wrap without back-hemisphere blowout
  vFacing = smoothstep(-0.35, 0.20, dot(viewNormal, viewDir));

  // Fine pinpoint dot sizing
  float pSize = (2.3 + uBass * 0.8) * (260.0 / -mvPosition.z);
  gl_PointSize = clamp(pSize, 1.5, 5.0);
  gl_Position = projectionMatrix * mvPosition;
}
`;

// Fragment shader: Radiant golden-amber palette matching reference image 1:1
const particleFragmentShader = `
varying float vFresnel;
varying float vDisp;
varying float vFacing;
varying float vRidge;
varying vec3 vNormal;
uniform float uBass;

void main() {
  if (vFacing < 0.02) discard;

  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;

  float alphaMask = smoothstep(0.5, 0.16, dist);

  // 1:1 Reference Golden Color Ramp:
  // Pure vibrant golden spectrum - low blue ensures pure blazing yellow-gold, never cold white
  vec3 deepAmber = vec3(0.96, 0.42, 0.01);
  vec3 richGold = vec3(1.0, 0.78, 0.03);
  vec3 crestYellow = vec3(1.0, 0.92, 0.14);
  vec3 rimGold = vec3(1.0, 0.96, 0.24);
  vec3 hotGold = vec3(1.0, 0.99, 0.42);

  float dispFactor = clamp(vDisp * 2.2 + 0.50, 0.0, 1.0);
  vec3 col = mix(deepAmber, richGold, dispFactor);
  
  // Highlight the corrugated ridges across the front surface
  float ridgeFactor = smoothstep(-0.05, 0.12, vRidge);
  col = mix(col, crestYellow, ridgeFactor * 0.85);

  // Front lighting to illuminate the center ridges
  vec3 lightDir = normalize(vec3(0.0, 0.2, 1.0));
  float frontLight = max(dot(vNormal, lightDir), 0.0);
  col += richGold * pow(frontLight, 1.4) * 0.45;

  // Luminous core warmth
  float coreGlow = smoothstep(0.85, 0.0, vFresnel);
  col += deepAmber * coreGlow * 0.35;

  // Concentrated golden rim halo
  float rim = pow(vFresnel, 2.0);
  col = mix(col, rimGold, rim * 0.88);
  col += hotGold * pow(vFresnel, 3.8) * 1.30;

  // Alpha curve preserves dot definition while making the whole orb luminous
  float alpha = alphaMask * vFacing * mix(0.85, 1.0, rim);
  gl_FragColor = vec4(col * (1.15 + uBass * 0.25), alpha);
}
`;

// Industrial concrete studio floor shader
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
varying vec3 vWorldPos;
varying vec2 vUv;

${simplexNoiseGLSL}

void main() {
  // Industrial dark polished concrete floor tone
  vec3 floorBase = vec3(0.010, 0.013, 0.018);

  // Stretched golden specular puddle reflection directly under the orb
  float dx = vWorldPos.x - uOrbPos.x;
  float dz = vWorldPos.z - uOrbPos.z;
  
  float reflShape = exp(-(dx * dx / 3.0 + dz * dz / 14.0));
  
  // Concrete surface micro-grain & wet streaks
  float floorGrain = snoise(vec3(vWorldPos.x * 2.2, vWorldPos.z * 5.5, 0.0)) * 0.15;
  float totalRefl = clamp(reflShape * (0.95 + floorGrain), 0.0, 1.0);

  vec3 goldReflection = vec3(1.0, 0.72, 0.10) * (1.35 + uBass * 0.40);
  vec3 finalColor = floorBase + goldReflection * totalRefl;

  // Subtle overhead spotlight specular streaks
  float spot1 = exp(-(pow(vWorldPos.x + 3.8, 2.0) / 0.8 + pow(vWorldPos.z + 1.8, 2.0) / 6.0)) * 0.06;
  float spot2 = exp(-(pow(vWorldPos.x - 3.8, 2.0) / 0.8 + pow(vWorldPos.z + 1.8, 2.0) / 6.0)) * 0.06;
  finalColor += vec3(0.7, 0.85, 1.0) * (spot1 + spot2);

  // Vignette
  float vignette = smoothstep(26.0, 4.0, length(vWorldPos.xz));
  gl_FragColor = vec4(finalColor * vignette, 1.0);
}
`;

// Spotlight lens flare shaders
const spotLensVertexShader = `
void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = 10.0 * (260.0 / -mvPosition.z);
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
        uTreble: { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const orbPoints = new THREE.Points(orbGeometry, orbMaterial);
    orbPoints.position.set(0, 0.35, 0);
    scene.add(orbPoints);

    // Lateral floating sparks / embers (concentrated in horizontal fans on left and right)
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
      // Concentrated lateral spray on left and right flanks
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
        void main() {
          vec3 p = position;
          p.y += sin(uTime * 0.4 + position.x * 1.5) * 0.10;
          p.x += cos(uTime * 0.3 + position.y * 1.5) * 0.08;
          vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
          gl_PointSize = clamp(2.4 * (280.0 / -mvPosition.z), 1.0, 5.0);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        void main() {
          vec2 coord = gl_PointCoord - vec2(0.5);
          float dist = length(coord);
          if (dist > 0.5) discard;
          float alpha = smoothstep(0.5, 0.12, dist) * 0.90;
          gl_FragColor = vec4(vec3(1.0, 0.82, 0.15), alpha);
        }
      `,
      uniforms: { uTime: { value: 0.0 } },
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

    // Studio Spotlights (spaced to left and right wings matching reference image)
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
  const mids = (features?.mids?.[frame] ?? 0.0) * intensity;
  const treble = (features?.treble?.[frame] ?? 0.0) * intensity;

  if (threeRef.current) {
    const { renderer, scene, camera, orbPoints, orbMaterial, sparkMaterial, floorMaterial } =
      threeRef.current;

    orbMaterial.uniforms.uTime.value = timeSeconds;
    orbMaterial.uniforms.uBass.value = bass;
    orbMaterial.uniforms.uMids.value = mids;
    orbMaterial.uniforms.uTreble.value = treble;

    sparkMaterial.uniforms.uTime.value = timeSeconds;
    floorMaterial.uniforms.uBass.value = bass;

    // Slow organic Y-axis rotation
    orbPoints.rotation.y = timeSeconds * 0.15;
    orbPoints.rotation.x = Math.sin(timeSeconds * 0.08) * 0.05;

    // Bass-driven pulsation
    const scale = 1.0 + bass * 0.10;
    orbPoints.scale.set(scale, scale, scale);

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
