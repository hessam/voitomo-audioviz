import React, { useMemo } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { AudioMultibandFeatures } from "../types/manifest";
import { Body, compileBodies, modeAmplitudes, skinDisplacement, stringDisplacement } from "./bodiesModel";
import { useThreeScene } from "./useThreeScene";

/**
 * Resonant Bodies, physically based: each stem is a real-looking object lit by an environment map.
 *  - bass: heavy metal string with saddles; other/guitar: lighter steel string
 *  - drums: lacquered shell, a head that deforms in the drum's own modes, chrome hoops
 *  - vocals: a glass-like air column whose width follows the loudness of the voice
 * Each body vibrates with its own stem's spectrum. A missing stem is not drawn. This is a physically
 * based approximation, not a photograph: true photorealism needs licensed 3D models or generated imagery.
 */
const STRING_POINTS = 160;
const SKIN_SEGMENTS = 128;
const SHELL_SEGMENTS = 96;
const COLORS: Record<string, number> = {
  bass: 0xc96a2b, drums: 0x7a1f1a, vocals: 0x9fe7ff, guitar: 0xd6b25a, other: 0xb9a6ff, instrumental: 0xd6b25a, mix: 0xe6e1d3,
};
const limit = (value: number, max: number) => max * Math.tanh(value / max);

const slotPositions = (count: number): Array<[number, number]> => {
  if (count <= 1) return [[0, 0]];
  if (count === 2) return [[-2.6, 0.1], [2.6, 0.1]];
  return [[-2.6, 1.35], [2.6, 1.35], [-2.6, -1.35], [2.6, -1.35]];
};

interface Rig { group: THREE.Group; update(frame: number, seconds: number, drive: number): void; dispose(): void }

function stringRig(body: Body, x: number, y: number, heavy: boolean): Rig {
  const group = new THREE.Group();
  group.position.set(x, y, 0);
  const length = 4.2, half = length / 2;
  const material = new THREE.MeshPhysicalMaterial({
    color: COLORS[body.stem] ?? 0xe6e1d3, metalness: 1, roughness: heavy ? 0.34 : 0.18, clearcoat: 0.5, clearcoatRoughness: 0.12,
  });
  const string = new THREE.Mesh(new THREE.BufferGeometry(), material);
  string.castShadow = true;
  group.add(string);
  const saddleMaterial = new THREE.MeshStandardMaterial({ color: 0x1b1d22, metalness: 0.9, roughness: 0.35 });
  const saddles = [-half, half].map(sx => {
    const block = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.6, 0.22), saddleMaterial);
    block.position.set(sx, 0, 0);
    block.castShadow = true;
    group.add(block);
    return block;
  });
  return {
    group,
    update(frame, seconds, drive) {
      const amps = modeAmplitudes(body, frame).map(a => a * drive);
      const points = Array.from({ length: STRING_POINTS + 1 }, (_, i) => {
        const u = i / STRING_POINTS;
        return new THREE.Vector3(-half + u * length, limit(stringDisplacement(amps, u, seconds) * 0.5, 0.85), 0);
      });
      string.geometry.dispose();
      string.geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), STRING_POINTS, heavy ? 0.045 : 0.026, 14, false);
    },
    dispose() {
      string.geometry.dispose();
      material.dispose();
      saddles.forEach(b => b.geometry.dispose());
      saddleMaterial.dispose();
    },
  };
}

function drumRig(body: Body, x: number, y: number): Rig {
  const group = new THREE.Group();
  group.position.set(x, y, 0);
  group.rotation.x = -0.5;  // tilt so the head reads as a drum head, not a disc
  const shellMaterial = new THREE.MeshPhysicalMaterial({ color: 0x2a1410, roughness: 0.42, clearcoat: 0.9, clearcoatRoughness: 0.15, side: THREE.DoubleSide });
  const shell = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.0, 0.7, SHELL_SEGMENTS, 1, true), shellMaterial);
  shell.rotation.x = Math.PI / 2;
  shell.castShadow = true;
  group.add(shell);
  const headMaterial = new THREE.MeshPhysicalMaterial({ color: 0xb9ab8e, roughness: 0.55, sheen: 0.5, sheenRoughness: 0.4, side: THREE.DoubleSide });
  const headGeometry = new THREE.CircleGeometry(0.98, SKIN_SEGMENTS);
  const head = new THREE.Mesh(headGeometry, headMaterial);
  head.position.z = 0.36;
  head.castShadow = true;
  group.add(head);
  const hoopMaterial = new THREE.MeshPhysicalMaterial({ color: 0xc9ccd3, metalness: 1, roughness: 0.22, clearcoat: 1 });
  const hoops = [0.36, -0.36].map(z => {
    const hoop = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.045, 18, 160), hoopMaterial);
    hoop.position.z = z;
    hoop.castShadow = true;
    group.add(hoop);
    return hoop;
  });
  const position = headGeometry.attributes.position as THREE.BufferAttribute;
  return {
    group,
    update(frame, seconds, drive) {
      const amps = modeAmplitudes(body, frame).map(a => a * drive);
      for (let i = 0; i < position.count; i++) {
        const px = position.getX(i), py = position.getY(i);
        const r = Math.hypot(px, py);
        const theta = Math.atan2(py, px);
        const displacement = r > 1e-6 ? limit(skinDisplacement(amps, theta, seconds) * 0.28 * r, 0.32) : 0;
        position.setZ(i, displacement);
      }
      position.needsUpdate = true;
      headGeometry.computeVertexNormals();
    },
    dispose() {
      shell.geometry.dispose();
      shellMaterial.dispose();
      headGeometry.dispose();
      headMaterial.dispose();
      hoops.forEach(h => h.geometry.dispose());
      hoopMaterial.dispose();
    },
  };
}

function airRig(body: Body, x: number, y: number): Rig {
  const group = new THREE.Group();
  group.position.set(x, y, 0);
  const material = new THREE.MeshPhysicalMaterial({
    color: COLORS.vocals, roughness: 0.12, metalness: 0, transmission: 0.85, thickness: 0.9, ior: 1.35,
    transparent: true, opacity: 0.9, clearcoat: 1, clearcoatRoughness: 0.05,
  });
  const column = new THREE.Mesh(new THREE.BufferGeometry(), material);
  group.add(column);
  return {
    group,
    update(frame, seconds, drive) {
      const amps = modeAmplitudes(body, frame).map(a => a * drive);
      const loud = amps.reduce((s, a) => s + a, 0) / amps.length;
      const profile = Array.from({ length: 49 }, (_, i) => {
        const t = i / 48;
        const r = 0.05 + (0.08 + 0.2 * Math.min(1, loud)) * Math.sin(Math.PI * t) ** 0.7 * (1 + 0.3 * Math.abs(stringDisplacement(amps, t, seconds)));
        return new THREE.Vector2(Math.max(0.02, Math.min(0.4, r)), -1.0 + t * 2.0);
      });
      column.geometry.dispose();
      column.geometry = new THREE.LatheGeometry(profile, 72);
    },
    dispose() {
      column.geometry.dispose();
      material.dispose();
    },
  };
}

function buildRigs(scene: THREE.Scene, model: ReturnType<typeof compileBodies>): Rig[] {
  const slots = slotPositions(model.bodies.length);
  return model.bodies.map((body, i) => {
    const [x, y] = slots[i];
    const rig = body.kind === "skin" ? drumRig(body, x, y)
      : body.kind === "column" ? airRig(body, x, y)
      : stringRig(body, x, y, body.kind === "heavyString");
    scene.add(rig.group);
    return rig;
  });
}

interface Props { features: AudioMultibandFeatures; intensity?: number }

export const ResonantBodiesVisualizer: React.FC<Props> = ({ features, intensity = 1 }) => {
  const drive = Number.isFinite(intensity) ? Math.max(0, Math.min(2, intensity)) : 1;
  const model = useMemo(() => compileBodies(features, 30, Math.max(features.bass.length, 1)), [features]);

  const canvasRef = useThreeScene(({ canvas, width, height }) => {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050609);
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    scene.environmentIntensity = 0.6;

    const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 100);
    camera.position.set(0, 0.6, 10.2);
    camera.lookAt(0, -0.1, 0);

    const key = new THREE.DirectionalLight(0xfff1dc, 2.2);
    key.position.set(3.5, 6, 7);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = -6; key.shadow.camera.right = 6; key.shadow.camera.top = 4; key.shadow.camera.bottom = -4;
    key.shadow.bias = -0.0004;
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x9fd8ff, 1.6);
    rim.position.set(-5, 3, -4);
    scene.add(rim);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.ShadowMaterial({ opacity: 0.4 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -2.6;
    floor.receiveShadow = true;
    scene.add(floor);

    const rigs = buildRigs(scene, model);
    return {
      draw(f: number) {
        const seconds = f / 30;
        rigs.forEach(rig => rig.update(f, seconds, drive));
        renderer.render(scene, camera);
      },
      dispose() {
        rigs.forEach(rig => { scene.remove(rig.group); rig.dispose(); });
        floor.geometry.dispose();
        (floor.material as THREE.Material).dispose();
        renderer.dispose();
      },
    };
  }, [model, drive]);

  const caption = model.bodies.length === 0 ? "NO SPECTRAL DATA" : model.mixOnly ? "NO STEMS · SHOWING THE FULL MIX" : "";
  const labels = model.bodies.map(b => b.label);
  return (
    <div style={{ position: "absolute", inset: 0, background: "#050609" }}>
      <canvas ref={canvasRef} width={1920} height={1080} style={{ width: "100%", height: "100%", display: "block" }} />
      <div style={{ position: "absolute", left: 64, top: 52, color: "#7c869a", fontFamily: "Inter, Helvetica, Arial, sans-serif", letterSpacing: 4, fontSize: 18 }}>
        <div>RESONANT BODIES</div>
        {caption && <div style={{ marginTop: 10, color: "#d9c692", fontSize: 22, letterSpacing: 3 }}>{caption}</div>}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 28, display: "flex", justifyContent: "center", gap: 90,
        color: "#7c869a", fontFamily: "Inter, Helvetica, Arial, sans-serif", letterSpacing: 4, fontSize: 17 }}>
        {labels.map(label => <div key={label}>{label}</div>)}
      </div>
    </div>
  );
};
