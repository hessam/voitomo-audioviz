import React, { useRef, useEffect } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { AudioMultibandFeatures } from "../types/manifest";

const synapseVertexShader = `
uniform float uTime;
uniform float uWavefrontRadius;
uniform float uBass;
attribute vec3 aCenter;
varying float vImpulse;

void main() {
  vec4 worldPosition = modelMatrix * vec4(position, 1.0);
  float dist = length(worldPosition.xyz);

  // Impulse wave calculation from center outwards
  float waveDist = abs(dist - uWavefrontRadius);
  float impulse = exp(-waveDist * waveDist / 1.8);
  vImpulse = impulse;

  gl_Position = projectionMatrix * viewMatrix * worldPosition;
}
`;

const synapseFragmentShader = `
uniform float uBass;
varying float vImpulse;

void main() {
  // Muted steel-blue base color transitioning to bright emerald-teal (#00FFA3) on impulse
  vec3 baseColor = vec3(0.12, 0.22, 0.28);
  vec3 impulseColor = vec3(0.0, 1.0, 0.639);

  vec3 color = mix(baseColor, impulseColor, vImpulse * (1.2 + uBass * 0.8));
  float alpha = mix(0.12, 0.95, vImpulse);

  gl_FragColor = vec4(color, alpha);
}
`;

interface NeuralSynapseVisualizerProps {
  features: AudioMultibandFeatures;
  intensity?: number;
}

export const NeuralSynapseVisualizer: React.FC<NeuralSynapseVisualizerProps> = ({
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
    nodePoints: THREE.Points;
    linesMesh: THREE.LineSegments;
    lineMaterial: THREE.ShaderMaterial;
    wavefrontRadius: { current: number };
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#030507");

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    camera.position.set(0, 0, 13.0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);

    // 1. Generate 1,500 nodes in a clustered sphere distribution
    const nodeCount = 1500;
    const nodePositions = new Float32Array(nodeCount * 3);
    const nodes: THREE.Vector3[] = [];

    // Pseudo-random deterministic generator with seed
    let seed = 12345;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (let i = 0; i < nodeCount; i++) {
      const radius = 4.2 * Math.cbrt(rand());
      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(2.0 * rand() - 1.0);

      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);

      nodePositions[i * 3] = x;
      nodePositions[i * 3 + 1] = y;
      nodePositions[i * 3 + 2] = z;
      nodes.push(new THREE.Vector3(x, y, z));
    }

    const nodeGeometry = new THREE.BufferGeometry();
    nodeGeometry.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    const nodeMaterial = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.12,
      transparent: true,
      blending: THREE.AdditiveBlending,
      opacity: 0.9,
    });
    const nodePoints = new THREE.Points(nodeGeometry, nodeMaterial);
    scene.add(nodePoints);

    // 2. Precompute static k-NN topology index buffer (k <= 5) to eliminate O(N^2) CPU thrash
    const lineIndices: number[] = [];
    const maxK = 5;
    const maxDistance = 1.6;

    for (let i = 0; i < nodeCount; i++) {
      const neighbors: { index: number; dist: number }[] = [];
      for (let j = i + 1; j < nodeCount; j++) {
        const d = nodes[i].distanceTo(nodes[j]);
        if (d < maxDistance) {
          neighbors.push({ index: j, dist: d });
        }
      }
      neighbors.sort((a, b) => a.dist - b.dist);
      for (let k = 0; k < Math.min(neighbors.length, maxK); k++) {
        lineIndices.push(i, neighbors[k].index);
      }
    }

    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    lineGeometry.setIndex(lineIndices);

    const lineMaterial = new THREE.ShaderMaterial({
      vertexShader: synapseVertexShader,
      fragmentShader: synapseFragmentShader,
      uniforms: {
        uTime: { value: 0.0 },
        uWavefrontRadius: { value: 0.0 },
        uBass: { value: 0.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const linesMesh = new THREE.LineSegments(lineGeometry, lineMaterial);
    scene.add(linesMesh);

    containerRef.current.innerHTML = "";
    containerRef.current.appendChild(renderer.domElement);

    threeRef.current = {
      renderer,
      scene,
      camera,
      nodePoints,
      linesMesh,
      lineMaterial,
      wavefrontRadius: { current: 0 },
    };

    return () => {
      renderer.dispose();
      nodeGeometry.dispose();
      nodeMaterial.dispose();
      lineGeometry.dispose();
      lineMaterial.dispose();
    };
  }, [width, height]);

  const timeSeconds = frame / fps;
  const bass = (features?.bass?.[frame] ?? 0.0) * intensity;
  const transients = features?.transients || [];

  // Wavefront propagation: cycles every ~1.5 seconds or triggers on transients
  let activeWave = (timeSeconds * 4.5) % 8.0;
  if (transients.includes(frame)) {
    activeWave = 0.5;
  }

  if (threeRef.current) {
    const { renderer, scene, camera, nodePoints, linesMesh, lineMaterial } = threeRef.current;

    lineMaterial.uniforms.uTime.value = timeSeconds;
    lineMaterial.uniforms.uWavefrontRadius.value = activeWave;
    lineMaterial.uniforms.uBass.value = bass;

    const rotY = timeSeconds * 0.12;
    const rotX = Math.sin(timeSeconds * 0.15) * 0.15;
    nodePoints.rotation.y = rotY;
    nodePoints.rotation.x = rotX;
    linesMesh.rotation.y = rotY;
    linesMesh.rotation.x = rotX;

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
