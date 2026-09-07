import React, { useRef, useEffect } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { AudioMultibandFeatures } from "../types/manifest";

const torusVertexShader = `
uniform float uTime;
uniform float uBass;
uniform float uMids;
uniform float uTreble;
varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vWorldPos;

void main() {
  vUv = uv;
  vNormal = normal;

  // Inside-out spline twist calculation
  float twistAngle = uv.x * 6.28318 * 3.0 + uTime * 0.9 + uMids * 1.8;
  float radialDisplace = sin(twistAngle) * (uBass * 0.45 + 0.05);

  vec3 displacedPosition = position + normal * radialDisplace;
  vec4 worldPosition = modelMatrix * vec4(displacedPosition, 1.0);
  vWorldPos = worldPosition.xyz;

  gl_Position = projectionMatrix * viewMatrix * worldPosition;
}
`;

const torusFragmentShader = `
uniform float uBass;
uniform float uTreble;
varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vWorldPos;

void main() {
  // Cyan (#00F0FF) to Deep Violet (#7B2CBF) gradient along spline u
  vec3 cyan = vec3(0.0, 0.941, 1.0);
  vec3 violet = vec3(0.482, 0.173, 0.749);
  vec3 magenta = vec3(1.0, 0.0, 0.5);

  float t = fract(vUv.x * 2.0);
  vec3 baseColor = mix(cyan, violet, t);

  // Rim lighting effect
  vec3 viewDir = normalize(cameraPosition - vWorldPos);
  float rim = 1.0 - max(dot(viewDir, normalize(vNormal)), 0.0);
  rim = pow(rim, 2.5);

  vec3 emissive = mix(baseColor, magenta, rim * (0.6 + uTreble * 0.8));
  emissive *= (1.2 + uBass * 0.8);

  gl_FragColor = vec4(emissive, 0.88);
}
`;

interface QuantumIrisVisualizerProps {
  features: AudioMultibandFeatures;
  intensity?: number;
}

export const QuantumIrisVisualizer: React.FC<QuantumIrisVisualizerProps> = ({
  features,
  intensity = 1.0,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const containerRef = useRef<HTMLDivElement>(null);

  const threeRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    torusMesh: THREE.Mesh;
    material: THREE.ShaderMaterial;
    sparks: THREE.Points;
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#040308");

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 10.0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);

    // TorusKnotGeometry ribbon (p=2, q=3)
    const geometry = new THREE.TorusKnotGeometry(2.5, 0.55, 600, 32, 2, 3);

    const material = new THREE.ShaderMaterial({
      vertexShader: torusVertexShader,
      fragmentShader: torusFragmentShader,
      uniforms: {
        uTime: { value: 0.0 },
        uBass: { value: 0.0 },
        uMids: { value: 0.0 },
        uTreble: { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });

    const torusMesh = new THREE.Mesh(geometry, material);
    scene.add(torusMesh);

    // Trailing spark particles around the knot
    const sparkCount = 1500;
    const sparkGeometry = new THREE.BufferGeometry();
    const sparkPositions = new Float32Array(sparkCount * 3);
    for (let i = 0; i < sparkCount; i++) {
      const u = Math.random() * Math.PI * 2;
      const v = Math.random() * Math.PI * 2;
      const r = 2.5 + (Math.random() - 0.5) * 1.8;
      sparkPositions[i * 3] = r * Math.cos(u);
      sparkPositions[i * 3 + 1] = r * Math.sin(u) * Math.cos(v);
      sparkPositions[i * 3 + 2] = (Math.random() - 0.5) * 3.0;
    }
    sparkGeometry.setAttribute("position", new THREE.BufferAttribute(sparkPositions, 3));
    const sparkMaterial = new THREE.PointsMaterial({
      color: 0x00f0ff,
      size: 0.08,
      transparent: true,
      blending: THREE.AdditiveBlending,
      opacity: 0.75,
    });
    const sparks = new THREE.Points(sparkGeometry, sparkMaterial);
    scene.add(sparks);

    containerRef.current.innerHTML = "";
    containerRef.current.appendChild(renderer.domElement);

    threeRef.current = { renderer, scene, camera, torusMesh, material, sparks };

    return () => {
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      sparkGeometry.dispose();
      sparkMaterial.dispose();
    };
  }, [width, height]);

  const timeSeconds = frame / fps;
  const bass = (features?.bass?.[frame] ?? 0.0) * intensity;
  const mids = (features?.mids?.[frame] ?? 0.0) * intensity;
  const treble = (features?.treble?.[frame] ?? 0.0) * intensity;

  if (threeRef.current) {
    const { renderer, scene, camera, torusMesh, material, sparks } = threeRef.current;

    material.uniforms.uTime.value = timeSeconds;
    material.uniforms.uBass.value = bass;
    material.uniforms.uMids.value = mids;
    material.uniforms.uTreble.value = treble;

    torusMesh.rotation.y = timeSeconds * 0.25;
    torusMesh.rotation.x = timeSeconds * 0.15;
    torusMesh.rotation.z = Math.sin(timeSeconds * 0.3) * 0.2;

    const scale = 1.0 + bass * 0.18;
    torusMesh.scale.set(scale, scale, scale);

    sparks.rotation.y = timeSeconds * 0.35;
    sparks.rotation.x = timeSeconds * -0.20;

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
