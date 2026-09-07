import React, { useRef, useEffect } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { AudioMultibandFeatures } from "../types/manifest";

interface MonolithFieldVisualizerProps {
  features: AudioMultibandFeatures;
  intensity?: number;
}

export const MonolithFieldVisualizer: React.FC<MonolithFieldVisualizerProps> = ({
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
    instancedMesh: THREE.InstancedMesh;
    gridSize: number;
    dummy: THREE.Object3D;
    limeColor: THREE.Color;
    obsidianColor: THREE.Color;
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#030305");
    scene.fog = new THREE.FogExp2(0x030305, 0.035);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    // Isometric-angled elevated perspective looking down across the matrix
    camera.position.set(0, 14.0, 18.0);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);

    // 32 x 32 grid = 1,024 instances
    const gridSize = 32;
    const count = gridSize * gridSize;

    // Hexagonal prism or slender cuboid pillar geometry
    const pillarWidth = 0.55;
    const pillarHeight = 3.0;
    const geometry = new THREE.BoxGeometry(pillarWidth, pillarHeight, pillarWidth);

    // Custom material with emissive acid-lime cap
    const material = new THREE.MeshStandardMaterial({
      color: 0x0e0f12,
      roughness: 0.85,
      metalness: 0.25,
    });

    const instancedMesh = new THREE.InstancedMesh(geometry, material, count);
    instancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    // Add directional and ambient lighting for crisp obsidian bevel highlights
    const ambientLight = new THREE.AmbientLight(0x20222a, 1.2);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xd4ff00, 1.5);
    dirLight.position.set(5, 20, 10);
    scene.add(dirLight);

    const backLight = new THREE.DirectionalLight(0x00f0ff, 0.8);
    backLight.position.set(-10, 10, -10);
    scene.add(backLight);

    scene.add(instancedMesh);

    containerRef.current.innerHTML = "";
    containerRef.current.appendChild(renderer.domElement);

    const dummy = new THREE.Object3D();
    const limeColor = new THREE.Color("#D4FF00");
    const obsidianColor = new THREE.Color("#0E0F12");

    threeRef.current = {
      renderer,
      scene,
      camera,
      instancedMesh,
      gridSize,
      dummy,
      limeColor,
      obsidianColor,
    };

    return () => {
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, [width, height]);

  const timeSeconds = frame / fps;
  const bass = (features?.bass?.[frame] ?? 0.0) * intensity;
  const mids = (features?.mids?.[frame] ?? 0.0) * intensity;
  const treble = (features?.treble?.[frame] ?? 0.0) * intensity;

  if (threeRef.current) {
    const { renderer, scene, camera, instancedMesh, gridSize, dummy, limeColor, obsidianColor } =
      threeRef.current;

    const center = (gridSize - 1) / 2;
    const spacing = 0.72;

    let index = 0;
    for (let i = 0; i < gridSize; i++) {
      for (let j = 0; j < gridSize; j++) {
        const x = (i - center) * spacing;
        const z = (j - center) * spacing;
        const distFromCenter = Math.sqrt((i - center) ** 2 + (j - center) ** 2);

        // Center-outward FFT ripple waves
        const bassImpact = bass * 4.5 * Math.exp(-distFromCenter / 4.5);
        const wave = Math.sin(distFromCenter * 0.75 - timeSeconds * 3.8) * (mids * 1.8 + 0.2);
        const ripple = Math.cos(distFromCenter * 1.5 + timeSeconds * 2.0) * (treble * 0.6);

        const heightScale = Math.max(0.15, 0.4 + bassImpact + wave + ripple);

        dummy.position.set(x, (heightScale * 3.0) / 2, z);
        dummy.scale.set(1.0, heightScale, 1.0);
        dummy.updateMatrix();

        instancedMesh.setMatrixAt(index, dummy.matrix);

        // Dynamic instance coloring: glowing lime on peak heights, obsidian on rest
        if (heightScale > 1.4) {
          instancedMesh.setColorAt(index, limeColor);
        } else {
          instancedMesh.setColorAt(index, obsidianColor);
        }

        index++;
      }
    }

    instancedMesh.instanceMatrix.needsUpdate = true;
    if (instancedMesh.instanceColor) {
      instancedMesh.instanceColor.needsUpdate = true;
    }

    // Gentle camera orbit
    const camAngle = timeSeconds * 0.08;
    camera.position.x = Math.sin(camAngle) * 18.0;
    camera.position.z = Math.cos(camAngle) * 18.0;
    camera.lookAt(0, 1.0, 0);

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
