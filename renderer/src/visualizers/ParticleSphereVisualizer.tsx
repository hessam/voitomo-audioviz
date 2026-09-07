import React, { useMemo, useRef, useEffect } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
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

const particleVertexShader = `
uniform float uTime;
uniform float uBass;
uniform float uMids;
uniform float uTreble;
varying float vNoise;
varying vec3 vPos;

${simplexNoiseGLSL}

void main() {
  vPos = position;
  vec3 normalVec = normalize(position);

  // Analytical 3D simplex displacement driven by audio bands
  float bassDisp = snoise(position * 0.4 + vec3(uTime * 0.8)) * (uBass * 1.8);
  float trebleDisp = snoise(position * 1.5 + vec3(uTime * 1.6)) * (uTreble * 0.7);
  float totalDisp = bassDisp + trebleDisp;
  vNoise = totalDisp;

  vec3 newPosition = position + normalVec * totalDisp;
  vec4 mvPosition = modelViewMatrix * vec4(newPosition, 1.0);

  // Dynamic point size modulated by bass pulse and camera distance
  gl_PointSize = (18.0 + uBass * 16.0) * (300.0 / -mvPosition.z);
  gl_Position = projectionMatrix * mvPosition;
}
`;

const particleFragmentShader = `
uniform float uBass;
varying float vNoise;
varying vec3 vPos;

void main() {
  // Soft circular glowing disc SDF
  vec2 coord = gl_PointCoord - vec2(0.5);
  float dist = length(coord);
  if (dist > 0.5) discard;

  float alpha = smoothstep(0.5, 0.08, dist);

  // Golden-amber emissive ramp: #FFD700 (Gold) -> #FFA500 (Amber Orange)
  vec3 goldColor = vec3(1.0, 0.843, 0.0);
  vec3 amberColor = vec3(1.0, 0.647, 0.0);
  vec3 warmColor = mix(goldColor, amberColor, dist * 2.0);

  // Emissive flare during high bass energy
  vec3 finalColor = warmColor * (1.1 + uBass * 0.9 + vNoise * 0.3);

  gl_FragColor = vec4(finalColor, alpha);
}
`;

interface ParticleSphereVisualizerProps {
  features: AudioMultibandFeatures;
  color?: string;
  intensity?: number;
}

export const ParticleSphereVisualizer: React.FC<ParticleSphereVisualizerProps> = ({
  features,
  intensity = 1.0,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const containerRef = useRef<HTMLDivElement>(null);

  // Three.js scene instances held in refs for Remotion deterministic reuse
  const threeRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    points: THREE.Points;
    material: THREE.ShaderMaterial;
  } | null>(null);

  // Initial setup of Three.js context (allocated once)
  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#050508");

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 11.5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1); // Explicit 1.0 pixel ratio for deterministic offscreen rendering

    // Icosahedron with detail 6 creates ~20,480 points
    const geometry = new THREE.IcosahedronGeometry(3.2, 6);

    const material = new THREE.ShaderMaterial({
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

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    containerRef.current.innerHTML = "";
    containerRef.current.appendChild(renderer.domElement);

    threeRef.current = { renderer, scene, camera, points, material };

    return () => {
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, [width, height]);

  // Deterministic frame evaluation: timeSeconds = frame / fps
  const timeSeconds = frame / fps;
  const bass = (features?.bass?.[frame] ?? 0.0) * intensity;
  const mids = (features?.mids?.[frame] ?? 0.0) * intensity;
  const treble = (features?.treble?.[frame] ?? 0.0) * intensity;

  // Update uniforms and render frame
  if (threeRef.current) {
    const { renderer, scene, camera, points, material } = threeRef.current;

    material.uniforms.uTime.value = timeSeconds;
    material.uniforms.uBass.value = bass;
    material.uniforms.uMids.value = mids;
    material.uniforms.uTreble.value = treble;

    // Continuous slow orbit rotations
    points.rotation.y = timeSeconds * 0.18;
    points.rotation.x = timeSeconds * 0.10 + bass * 0.08;

    // Scale breathing
    const scale = 1.0 + bass * 0.22;
    points.scale.set(scale, scale, scale);

    renderer.render(scene, camera);
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        position: "absolute",
        top: 0,
        left: 0,
        overflow: "hidden",
      }}
    />
  );
};
