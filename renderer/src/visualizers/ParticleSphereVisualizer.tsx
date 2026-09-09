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
uniform float uDrums;
uniform float uTransient;
uniform float uBeat;

varying float vRidge;
varying float vFacing;
varying float vFresnel;
varying float vDepth;
varying float vDisp;
varying float vTreble;
varying float vTransient;

SIMPLEX_NOISE_GLSL

void main() {
  vTreble = uTreble;
  vTransient = uTransient;

  vec3 n = normalize(position);

  // Time & stem flow dynamics: vocal stem drives fluid speed acceleration
  float flowTime = uTime * 0.22 + uVocal * 1.60 + uMids * 0.40;

  // 1. Multi-octave 3D Simplex noise folds the surface into smooth undulating organic lobes
  // Large scale: broad, majestic rolling lobes that bulge outward and fold inward
  vec3 pLobe = n * 1.15 + vec3(flowTime * 0.16, flowTime * 0.11, flowTime * 0.08);
  float nLobe = snoise(pLobe);

  // Medium scale: secondary undulating folds
  vec3 pFold = n * 2.30 - vec3(flowTime * 0.12, 0.0, flowTime * 0.16);
  float nFold = snoise(pFold);

  // Fine scale: gentle surface waviness
  vec3 pRipple = n * 4.40 + vec3(flowTime * 0.22);
  float nRipple = snoise(pRipple);

  // Base structural organic displacement (harmonious rolling lobes)
  float baseDisp = nLobe * 0.58 + nFold * 0.22 + nRipple * 0.06;

  // Stem-isolated dynamics:
  // Bass drives macro lobe expansion exclusively
  float bassWarp = nLobe * (uBass * 1.15);
  // Mids drive secondary undulating folds
  float midsWarp = nFold * (uMids * 0.45);
  // Drums & transients drive the sharp outward propagating shockwave ring exclusively
  float shockwave = sin(length(position) * 3.4 - uTime * 5.8) * (uDrums * 0.35 + uTransient * 0.28 + uBeat * 0.16);

  float totalDisp = baseDisp + bassWarp + midsWarp + shockwave;
  vDisp = totalDisp;

  // Vertex displacement directly along normals: position + normal * noise * amplitude
  vec3 displacedPosition = position + n * totalDisp;

  // Topographical contour bands wrapping along the organic lobes
  // Higher frequency (18.0) yields fine, elegant topographic striations
  float topoElevation = displacedPosition.y * 18.0 + nLobe * 5.2 + nFold * 2.6 + flowTime * 0.42;
  float topoLine = sin(topoElevation);
  vRidge = smoothstep(-0.15, 0.62, topoLine);

  // Transform to view space
  vec4 mvPosition = modelViewMatrix * vec4(displacedPosition, 1.0);
  vDepth = -mvPosition.z;

  // View direction & normal (calculated for both front and back particles)
  vec3 viewNormal = normalize(normalMatrix * (n + vec3(nFold * 0.15, nLobe * 0.18, 0.0)));
  vec3 viewDir = normalize(-mvPosition.xyz);
  vFacing = dot(viewNormal, viewDir);
  vFresnel = clamp(1.0 - abs(vFacing), 0.0, 1.0);

  // Point size: perspective scaled, crisp fine dots
  float pSize = (3.4 + uTreble * 0.6 + vRidge * 0.8) * (360.0 / -mvPosition.z);
  gl_PointSize = clamp(pSize, 1.6, 5.2);
  gl_Position = projectionMatrix * mvPosition;
}
`;

const particleFragmentShader = `
varying float vRidge;
varying float vFacing;
varying float vFresnel;
varying float vDepth;
varying float vDisp;
varying float vTreble;
varying float vTransient;

uniform float uBass;
uniform float uMids;
uniform float uVocal;
uniform float uTransient;
uniform float uBeat;

void main() {
  // Soft circular dot shape
  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;

  float alphaMask = smoothstep(0.5, 0.10, dist);

  // Palette: rich incandescent 2200K honey-gold
  vec3 valleyAmber = vec3(0.76, 0.38, 0.015);  // Warm glowing honey amber
  vec3 slopeGold   = vec3(0.96, 0.64, 0.040);  // Rich incandescent gold
  vec3 crestBright = vec3(1.00, 0.88, 0.150);  // Intense brilliant gold crest
  vec3 blazeWhite  = vec3(1.00, 0.98, 0.550);  // Incandescent overlapping blaze

  // Topographic contour shading
  vec3 col = mix(valleyAmber, slopeGold, smoothstep(0.0, 0.38, vRidge));
  col      = mix(col, crestBright, smoothstep(0.38, 0.72, vRidge));
  col      = mix(col, blazeWhite,  smoothstep(0.72, 1.00, vRidge) * 0.75);

  // Volumetric translucency & depth cues:
  // Both front-facing and backside particles render additively
  // Back particles are slightly softer; front particles crisp
  float facingWeight = 0.60 + 0.40 * clamp(vFacing * 0.85 + 0.25, 0.0, 1.0);

  // Rim / edge accumulation glow (glowing silhouette contour)
  float rim = pow(vFresnel, 2.0);
  vec3 rimWarm = vec3(1.00, 0.85, 0.180);
  col += rimWarm * (rim * 0.50);

  // Energy flare on bass/transient drops
  col *= (1.05 + uBass * 0.30 + uTransient * 0.40);

  // Additive blending alpha:
  // Points accumulate density in the dense core and overlapping folds
  float alpha = alphaMask * facingWeight * (0.65 + rim * 0.35 + vRidge * 0.25);

  gl_FragColor = vec4(col, alpha);
}
`;

const sparkVertexShader = `
uniform float uTime;
uniform float uBass;
uniform float uTreble;
uniform float uTransient;
varying float vAlpha;

void main() {
  vec3 p = position;
  vec3 dir = normalize(position);

  // Subtle radial expansion and orbital drift
  p += dir * (sin(uTime * 0.6 + length(position) * 1.5) * 0.15 + uBass * 0.25 + uTransient * 0.35);
  p.y += sin(uTime * 0.45 + position.x) * 0.10;

  float distFromCenter = length(p);
  float fade = smoothstep(6.5, 2.8, distFromCenter);
  vAlpha = fade * (0.60 + 0.40 * sin(uTime * 5.0 + position.y * 3.0));

  vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
  float pSize = (1.8 + uTreble * 0.6 + uTransient * 0.8) * (300.0 / -mvPosition.z);
  gl_PointSize = clamp(pSize, 1.0, 3.8);
  gl_Position = projectionMatrix * mvPosition;
}
`;

const sparkFragmentShader = `
varying float vAlpha;
uniform float uTransient;

void main() {
  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;

  float mask = smoothstep(0.5, 0.10, dist);
  vec3 sparkCol = vec3(1.00, 0.78, 0.15);
  gl_FragColor = vec4(sparkCol * (1.1 + uTransient * 0.5), mask * vAlpha * 0.75);
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
  vec3 floorBase = vec3(0.005, 0.006, 0.009);

  float dx = vWorldPos.x - uOrbPos.x;
  float dz = vWorldPos.z - uOrbPos.z;

  float spreadX = 2.4 + uBass * 0.6 + uTransient * 0.8;
  float reflShape = exp(-(dx * dx / spreadX + dz * dz / 9.0));

  float floorGrain = snoise(vec3(vWorldPos.x * 2.5, vWorldPos.z * 6.0, 0.0)) * 0.08;
  float totalRefl = clamp(reflShape * (0.85 + floorGrain), 0.0, 1.0);

  vec3 goldReflection = vec3(1.0, 0.58, 0.05) * (1.15 + uBass * 0.40 + uBeat * 0.25 + uTransient * 0.50);
  vec3 finalColor = floorBase + goldReflection * totalRefl;

  float vignette = smoothstep(24.0, 4.0, length(vWorldPos.xz));
  gl_FragColor = vec4(finalColor * vignette, 1.0);
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
    scene.background = new THREE.Color("#020204");

    // 16:9 widescreen perspective camera (orb fills ~65% of vertical frame height)
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);
    camera.position.set(0, 0.25, 12.8);
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

    // Uniform spherical point distribution (Fibonacci lattice, 60,000 equidistant points)
    // Completely uniform coverage with zero poles, zero latitudinal banding, and optimal packing
    const orbPositions: number[] = [];
    const N = 60000;
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    const baseRadius = 2.40;

    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2;
      const rAtY = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = goldenAngle * i;
      orbPositions.push(
        Math.cos(theta) * rAtY * baseRadius,
        y * baseRadius,
        Math.sin(theta) * rAtY * baseRadius
      );
    }

    const orbGeometry = new THREE.BufferGeometry();
    orbGeometry.setAttribute("position", new THREE.Float32BufferAttribute(orbPositions, 3));
    orbGeometry.rotateX(-0.10);
    orbGeometry.rotateY(0.20);

    // Inject Simplex noise into shaders
    const vsWithNoise = particleVertexShader.replace("SIMPLEX_NOISE_GLSL", simplexNoiseGLSL);
    const fsFloorWithNoise = floorFragmentShader.replace("SIMPLEX_NOISE_GLSL", simplexNoiseGLSL);

    // Volumetric translucency: Additive blending with depthWrite false
    // allows backside and interior particles to blend naturally through the front
    const orbMaterial = new THREE.ShaderMaterial({
      vertexShader: vsWithNoise,
      fragmentShader: particleFragmentShader,
      uniforms: {
        uTime:      { value: 0.0 },
        uBass:      { value: 0.0 },
        uMids:      { value: 0.0 },
        uVocal:     { value: 0.0 },
        uDrums:     { value: 0.0 },
        uTreble:    { value: 0.0 },
        uTransient: { value: 0.0 },
        uBeat:      { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      depthTest: true,
    });

    const orbPoints = new THREE.Points(orbGeometry, orbMaterial);
    orbPoints.position.set(0, 0.30, 0);
    scene.add(orbPoints);

    // Subtle floating radial embers drifting outward into dark air
    const sparkCount = 450;
    const sparkGeo = new THREE.BufferGeometry();
    const sparkPos = new Float32Array(sparkCount * 3);

    let seed = 91823;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (let i = 0; i < sparkCount; i++) {
      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(2 * rand() - 1);
      const r = 2.6 + Math.pow(rand(), 1.4) * 3.4;

      sparkPos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      sparkPos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) + 0.30;
      sparkPos[i * 3 + 2] = r * Math.cos(phi);
    }

    sparkGeo.setAttribute("position", new THREE.BufferAttribute(sparkPos, 3));
    const sparkMaterial = new THREE.ShaderMaterial({
      vertexShader: sparkVertexShader,
      fragmentShader: sparkFragmentShader,
      uniforms: {
        uTime:      { value: 0.0 },
        uBass:      { value: 0.0 },
        uTreble:    { value: 0.0 },
        uTransient: { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const sparkPoints = new THREE.Points(sparkGeo, sparkMaterial);
    scene.add(sparkPoints);

    // Grounded floor with golden reflection beneath the orb
    const floorGeo = new THREE.PlaneGeometry(60, 60);
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
    floorMesh.position.y = -2.85;
    scene.add(floorMesh);

    threeRef.current = { renderer, scene, camera, orbPoints, orbMaterial, sparkMaterial, floorMaterial };

    renderer.render(scene, camera);
    continueRender(handle);

    return () => {
      renderer.dispose();
      orbGeometry.dispose(); orbMaterial.dispose();
      sparkGeo.dispose(); sparkMaterial.dispose();
      floorGeo.dispose(); floorMaterial.dispose();
    };
  }, [width, height, handle]);

  const timeSeconds = frame / fps;
  const bass  = (features?.bass?.[frame] ?? 0.0) * intensity;
  const vocal   = features?.vocalEnergy?.[frame] ?? 0.0;
  const drums   = (features?.drumsEnergy?.[frame] ?? Math.max(bass * 0.75, features?.transients?.includes(frame) ? 1.0 : 0.0)) * intensity;
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
    orbMaterial.uniforms.uDrums.value     = drums;
    orbMaterial.uniforms.uTreble.value    = treble;
    orbMaterial.uniforms.uTransient.value = transientImpulse;
    orbMaterial.uniforms.uBeat.value      = beatImpulse;

    sparkMaterial.uniforms.uTime.value      = timeSeconds;
    sparkMaterial.uniforms.uBass.value      = bass;
    sparkMaterial.uniforms.uTreble.value    = treble;
    sparkMaterial.uniforms.uTransient.value = transientImpulse;

    floorMaterial.uniforms.uBass.value      = bass;
    floorMaterial.uniforms.uBeat.value      = beatImpulse;
    floorMaterial.uniforms.uTransient.value = transientImpulse;

    // Organic continuous rotation
    orbPoints.rotation.y = timeSeconds * 0.08;
    orbPoints.rotation.x = Math.sin(timeSeconds * 0.04) * 0.03;

    // Subtle breathing on scale
    const scale = 1.0 + bass * 0.04;
    orbPoints.scale.set(scale, scale, scale);

    // Static widescreen camera
    camera.position.set(0, 0.25, 12.8);

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
