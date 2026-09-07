# Implementation Plan: Stem-Aware 3D Audio Visualizer Agent (Audioviz)

**Architectural Review**: Evaluated and conditionally approved by Astra (Principal Graphics Architect & Lead Creative Technologist).  
**Specification**: Deterministic 3D WebGL / Three.js Audio Visualizers with Golden-Frame Fidelity & Clamped Kinetic Typography.  
**Target Deployment**: Isolated Agent runtime on Server 1 (`62.238.29.81:4001`) with storage vaulting on Server 2 (`78.46.210.232:/srv/hermes-vault`).

---

## 1. Executive Summary & Goals

Transform Voitomo's proven kinetic typography pipeline into an enterprise-grade, dedicated **Stem-Aware 3D Audio Visualizer Agent ("Audioviz")** that:
1. Ingests songs/audio files via a dedicated Telegram bot interface (`@audioviz_bot`).
2. Extracts acoustic intelligence (dry vocals, isolated kick/bass, BPM, beat grid, multiband FFT, downbeats, section drops) via `hermes-audio-engineer` (port 5001) and `hermes-music-dna` (port 5002).
3. Compiles an **Immutable Pre-Render Bundle** containing all time-series feature arrays and aligned Whisper lyrics prior to rendering.
4. Renders one of 4 high-end 3D WebGL styles (**Particle Sphere**, **Quantum Iris**, **Neural Synapse**, **Monolith Field**) inside Remotion using strict deterministic frame evaluation.
5. Overlays synchronized Persian kinetic lyrics utilizing Voitomo's verified 3-line max FIFO clamp and 160px safe padding box.
6. Operates in 100% isolation from Voitomo and other production workloads.

---

## 2. Astra Architectural Approval Gate & Required Amendments

Astra evaluated the architectural blueprint and issued **CONDITIONAL APPROVAL** subject to the following engineering amendments:

| Architecture Domain | Baseline Limitation / Issue | Astra Mandated Amendment |
|---|---|---|
| **Visual Fidelity** | Subjective "1:1 exact" prose claims cannot guarantee pixel replication across GPUs. | Adopt a `VisualReferenceContract` with pinned camera, explicit framing bounds, and approved golden-frame image-difference tolerance ($\text{SSIM} \ge 0.92$). |
| **Render Determinism** | Standard Three.js `requestAnimationFrame` / `performance.now()` causes frame jitter and drift in headless video. | Enforce mathematical frame evaluation: $\text{timeSeconds} = \text{frame} \times \text{fpsDenominator} / \text{fpsNumerator}$. Zero variable-delta loops. |
| **Audio Intelligence** | A single 30 FPS scalar volume array lacks frequency separation and drop dynamics. | Generate timestamped multiband arrays (`bass`, `mids`, `treble` normalized $[0.0, 1.0]$) and transient drop event arrays before render starts. |
| **Pipeline Purity** | In-render API calls cause Chromium frame timeout and WebGL context loss. | **Immutable Pre-Render Bundle**: 100% of stems, DSP FFTs, Whisper alignment, and fonts must be bundled locally before launching Chromium. |
| **Topological Compute** | Dynamic $O(N^2)$ CPU distance checks for 1,500 Plexus nodes causes severe frame drops. | Precompute static $k$-NN index buffer ($k \le 6$) at seed initialization. GPU shader evaluates wave pulses along existing edges. |
| **Post-Processing & Color** | Ad-hoc bloom washes out dark backgrounds and introduces banding. | Pinned pipeline: Linear-sRGB color management, half-float (`RGBA16F`) render targets, ACESFilmic tone mapping, and separate unlit emissive materials for selective bloom. |
| **Storage & Performance** | Direct remote FS writes over network throttle encoder throughput. | **Hot Staging**: Render to local NVMe SSD (`/tmp/staging-<jobId>.mp4`), verify SHA-256 checksum, then async mirror to 15 GB Server 2 ext4 vault. Purge `/tmp` immediately. |
| **GPU Execution Path** | Headless Linux containers can silently fail WebGL fallback. | Qualify Chromium flags: `--enable-unsafe-webgl`, `--use-gl=angle`, `--use-angle=vulkan` with SwiftShader CPU fallback validation. |
| **Scheduling & SLOs** | Unbounded worker allocation risks OOM; vague "100% uptime" claims. | Hard-lock concurrency to **2 Chromium workers** (1 page, 1 WebGL context per worker). Target SLO: $\le 2.0\times$ real-time render latency, 99.5% completion rate. |

---

## 3. Core Architectural Contracts

### A. Visual Reference & Golden Frame Contract
```ts
interface VisualReferenceContract {
  presetId: "sphere" | "iris" | "neural" | "monolith";
  presetVersion: "1.0.0";
  camera: {
    projection: "perspective";
    fov: number;
    position: [number, number, number];
    target: [number, number, number];
  };
  composition: {
    width: 1080;
    height: 1080;
    fps: 30;
    colorSpace: "linear-srgb";
    toneMapping: "ACESFilmic";
    safePaddingPx: 160;
  };
  goldenFrames: {
    calmTimestamp: number;   // Low energy benchmark frame
    dropTimestamp: number;   // High energy peak drop benchmark frame
    ssimTolerance: 0.92;     // Automated visual regression threshold
  };
}
```

### B. Immutable Pre-Render Manifest Contract
```ts
interface RenderManifest {
  schemaVersion: 1;
  jobId: string;
  seed: number;
  preset: {
    id: "sphere" | "iris" | "neural" | "monolith";
    version: "1.0.0";
    parameters: Record<string, number | string | boolean>;
  };
  video: {
    width: 1080;
    height: 1080;
    fpsNumerator: 30;
    fpsDenominator: 1;
    frameCount: number;
  };
  audio: {
    masterUri: string;
    vocalStemUri: string;
    bassStemUri: string;
    sha256: string;
    sampleRate: 44100;
    features: {
      bass: number[];       // 30 FPS normalized [0.0, 1.0]
      mids: number[];       // 30 FPS normalized [0.0, 1.0]
      treble: number[];     // 30 FPS normalized [0.0, 1.0]
      transients: number[]; // Frame indices of drops / kicks
    };
  };
  lyrics: {
    lines: Array<{
      text: string;
      startFrame: number;
      endFrame: number;
      isHero: boolean;
    }>;
  };
  environment: {
    containerDigest: string;
    threeVersion: string;
    remotionVersion: string;
  };
}
```

### C. Deterministic Frame Evaluation
Inside Remotion components:
```ts
const frame = useCurrentFrame();
const timeSeconds = (frame * manifest.video.fpsDenominator) / manifest.video.fpsNumerator;

// Pure time-sampled uniform values (zero performance.now() or requestAnimationFrame):
const bass = manifest.audio.features.bass[frame] ?? 0.0;
const mids = manifest.audio.features.mids[frame] ?? 0.0;
const treble = manifest.audio.features.treble[frame] ?? 0.0;
```

---

## 4. The 4 Audio-Reactive 3D WebGL Styles (Astra Shader Specifications)

### Style 1: Particle Sphere (`ParticleSphereVisualizer.tsx`)
- **Visual Family**: Luminous celestial particle orb pulsating in dark space.
- **Geometry**: `THREE.IcosahedronGeometry(radius=3.2, detail=6)` (~20,480 vertices rendered with `THREE.Points`).
- **GLSL Vertex Shader**:
  - Analytical 3D Simplex noise displacement along vertex normal vector:
    $$P' = P + \mathbf{N} \cdot \left( \text{uBass} \cdot \text{snoise}(P \cdot 0.8 + t \cdot 1.2) \cdot 1.8 + \text{uTreble} \cdot \text{snoise}(P \cdot 2.5 + t \cdot 2.0) \cdot 0.6 \right)$$
- **GLSL Fragment Shader**:
  - Distance-to-center particle disc SDF with warm golden emissive ramp:
    ```glsl
    float dist = length(gl_PointCoord - vec2(0.5));
    if (dist > 0.5) discard;
    float alpha = smoothstep(0.5, 0.08, dist);
    // Emissive ramp: #FFD700 (Gold) -> #FFA500 (Amber Orange)
    vec3 color = mix(vec3(1.0, 0.843, 0.0), vec3(1.0, 0.647, 0.0), dist * 2.0);
    gl_FragColor = vec4(color * (1.0 + uBass * 0.8), alpha);
    ```
- **Motion Dynamics**:
  - Low/Bass: Global scale breathing $[0.92, 1.25]$ + primary surface expansion.
  - High/Mids: High-frequency ripple velocity and particle micro-jitters.
  - Slow continuous orbital rotation: $\omega_y = 0.12\,\text{rad/s}, \omega_x = 0.06\,\text{rad/s}$.
- **Post-Processing**: `EffectComposer` with `UnrealBloomPass` (`strength: 1.35`, `radius: 0.65`, `threshold: 0.22`) on `RGBA16F` half-float buffer.

---

### Style 2: Quantum Iris (`QuantumIrisVisualizer.tsx`)
- **Visual Family**: Cybernetic hyper-torus ribbon folding inside-out with trailing energy sparks.
- **Geometry**: Ribbon strip built from `THREE.TorusKnotGeometry(p=2, q=3, tubularSegments=1024, radialSegments=24)`.
- **GLSL Vertex Shader**:
  - Dynamic spline twist and bass-induced radial aperture opening:
    $$\theta(u) = u \cdot 6.0\pi + t \cdot 0.8 + \text{uMids} \cdot 1.5$$
    $$R(u) = R_0 \cdot \left(1.0 + 0.35 \cdot \text{uBass} \cdot \sin(\theta(u))\right)$$
- **GLSL Fragment Shader**:
  - Neon Cyan (`#00F0FF`) to Deep Electric Violet (`#7B2CBF`) gradient mapped along spline parameter $u$:
    ```glsl
    vec3 colCyan = vec3(0.0, 0.941, 1.0);
    vec3 colViolet = vec3(0.482, 0.173, 0.749);
    vec3 baseColor = mix(colCyan, colViolet, vUv.x);
    gl_FragColor = vec4(baseColor * (1.2 + uBass * 0.5), 0.9);
    ```
- **Post-Processing**: Custom Chromatic Aberration Shader Pass ($\Delta r = +0.0035, \Delta b = -0.0035$) + `UnrealBloomPass` (`strength: 1.1`, `radius: 0.5`).

---

### Style 3: Neural Synapse (`NeuralSynapseVisualizer.tsx`)
- **Visual Family**: Dynamic topological neural network with electrical impulse wavefronts.
- **Topology Architecture (Astra $O(N)$ Optimization)**:
  - 1,500 point nodes distributed in spherical volume.
  - Precompute a static $k$-Nearest-Neighbor ($k \le 6$) line index buffer at seed initialization to completely eliminate dynamic CPU distance scans.
- **Nodes & Line Buffers**:
  - `THREE.Points`: Pure white (`#FFFFFF`) glowing nodes with soft circular alpha.
  - `THREE.LineSegments`: Emerald-teal (`#00FFA3`) synaptic connection lines.
- **Wavefront Propagation Shader**:
  - Transients and kick hits trigger expanding spherical wavefronts $r(t) = v \cdot (t - t_{\text{drop}})$.
  - Line vertex shader calculates distance from origin to highlight active electrical paths:
    ```glsl
    float dist = length(vPosition);
    float waveDist = abs(dist - uWavefrontRadius);
    float impulse = exp(-waveDist * waveDist / 0.4);
    vec3 color = mix(vec3(0.2, 0.3, 0.35), vec3(0.0, 1.0, 0.639), impulse); // Muted -> Emerald #00FFA3
    gl_FragColor = vec4(color, mix(0.15, 0.95, impulse));
    ```
- **Camera & Atmosphere**: Subtle Brownian motion drift + Depth-of-Field / Bokeh focus plane centered on the primary neural cluster.

---

### Style 4: Monolith Field (`MonolithFieldVisualizer.tsx`)
- **Visual Family**: Kinetic field of reflective obsidian pillars pulsating with neon top caps over a dark void.
- **Geometry**: Single `THREE.InstancedMesh` with 1,024 instances arranged in a $32 \times 32$ planar grid.
- **Dual-Material Division (Selective Bloom)**:
  - Prism body sides: Rough Obsidian Black PBR (`roughness: 0.82`, `metalness: 0.25`, color `#0C0D10`).
  - Top caps: Unlit high-intensity Neon Acid-Lime (`#D4FF00`).
- **Center-Outward FFT Height Wave**:
  - Distance from matrix center $r_{i,j} = \sqrt{(i-15.5)^2 + (j-15.5)^2}$.
  - Column height transformation evaluated per instance:
    $$H_{i,j}(t) = 1.0 + \text{uBass} \cdot 4.0 \cdot e^{-r / 5.0} + \text{FFT}(r) \cdot \sin(r \cdot 0.8 - t \cdot 4.0)$$
- **Atmosphere**: Dark void floor fog (`THREE.FogExp2(#050508, 0.04)`) + Selective Bloom flaring only the top neon caps ($>1.0$ luminance).

---

## 5. Unified Kinetic Lyric Overlay Integration

All 4 visualizer styles integrate Voitomo's verified Persian typography stack:
- **Strict 3-Line Maximum FIFO Clamp**: Integrated via `getFlattenedLadderLines()`. Older lines roll off cleanly to eliminate vertical overflow.
- **Dynamic Auto-Scaling**:
  - 1 line: $64\text{px} - 84\text{px}$
  - 2 lines: $54\text{px} - 72\text{px}$
  - 3 lines: $46\text{px} - 62\text{px}$
- **Strict Boundary Guarantee**: 100% contained within the **160px safe padding box** ($760 \times 760\text{px}$ usable viewport).
- **Styling**: Snug tape strips with alternating black/white contrast and subtle tactile rotation jitter ($\pm 1.2^\circ$).

---

## 6. Microservice Architecture & Data Flow

```
                           [User sends MP3/Audio to Telegram]
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │      Audioviz Telegram Bot (4001)     │
                       │    (Keyboard: 4 Preset Visualizers)   │
                       └───────────────────┬───────────────────┘
                                           │
                     ┌─────────────────────┴─────────────────────┐
                     ▼                                           ▼
       hermes-audio-engineer:5001                   hermes-music-dna:5002
       (Mel-Band RoFormer)                          (Musicological DSP)
       ├── Dry Vocal Stem Extraction                ├── BPM & Downbeat Grid
       └── Bass/Kick Stem Extraction                └── 30 FPS Multiband FFT & Drops
                     │                                           │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │    Astra Immutable Pre-Render Bundle  │
                       │  ├── Normalized 30 FPS feature arrays │
                       │  ├── Precomputed static k-NN buffers  │
                       │  └── Whisper aligned lyric segments   │
                       └───────────────────┬───────────────────┘
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │   Remotion WebGL Engine (Port 4001)   │
                       │  ├── Concurrency: 2 Chromium workers  │
                       │  ├── Deterministic Frame Evaluator    │
                       │  ├── RGBA16F Half-Float Bloom Passes  │
                       │  └── 3-Line Clamped Kinetic Lyrics    │
                       └───────────────────┬───────────────────┘
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │    Local Staging & Vault Mirroring    │
                       │  1. Fast render: /tmp/staging.mp4     │
                       │  2. Verify SHA-256 checksum           │
                       │  3. Async move: /opt/hermes-vault/viz │
                       │  4. Purge /tmp staging immediately    │
                       └───────────────────┬───────────────────┘
                                           │
                                           ▼
                           [MP4 Delivered to Telegram]
```

---

## 7. Implementation Tasks & Phasing

### Phase 1: Environment & Architecture Foundations
- [ ] **Task 1.1**: Scaffold Audioviz repository structure at `/opt/hermes-data/audioviz/` (or Voitomo module `services/audioviz/`).
- [ ] **Task 1.2**: Define TypeScript data contracts (`RenderManifest`, `VisualReferenceContract`) in `types/manifest.ts`.
- [ ] **Task 1.3**: Configure Remotion render server on dedicated port `4001` with hard-coded `concurrency: 2`.
- [ ] **Task 1.4**: Configure Chromium launch flags (`--enable-unsafe-webgl`, `--use-gl=angle`, `--use-angle=vulkan`) and test WebGL context creation.

### Phase 2: Audio Pre-Render Pipeline
- [ ] **Task 2.1**: Implement `audio_features.py` to orchestrate calls to `hermes-audio-engineer` (5001) and `hermes-music-dna` (5002).
- [ ] **Task 2.2**: Compute normalized 30 FPS feature arrays (`bass`, `mids`, `treble`) from stem audio.
- [ ] **Task 2.3**: Detect musical drop frame indices and kick transients.
- [ ] **Task 2.4**: Run Whisper forced alignment for lyric timestamps and emit immutable `manifest.json`.

### Phase 3: 3D WebGL Visualizer Runtimes (Three.js)
- [ ] **Task 3.1**: Implement `ParticleSphereVisualizer.tsx` with GLSL simplex noise displacement and warm golden emissive ramp (`#FFD700` to `#FFA500`).
- [ ] **Task 3.2**: Implement `QuantumIrisVisualizer.tsx` with TorusKnot ribbon twist, cyan-to-violet gradient (`#00F0FF` to `#7B2CBF`), and chromatic aberration pass.
- [ ] **Task 3.3**: Implement `NeuralSynapseVisualizer.tsx` with static $k$-NN topology buffer, white glowing nodes, emerald (`#00FFA3`) impulse lines, and spherical transient wavefront shader.
- [ ] **Task 3.4**: Implement `MonolithFieldVisualizer.tsx` with $32 \times 32$ `InstancedMesh`, obsidian bodies, neon acid-lime (`#D4FF00`) caps, center-outward ripple formula, and selective bloom.
- [ ] **Task 3.5**: Wire shared post-processing pipeline (`EffectComposer`, `UnrealBloomPass`, `RGBA16F`, ACESFilmic tone mapping).

### Phase 4: Lyric Layer Integration & Clamping
- [ ] **Task 4.1**: Mount `TypographyLayer.tsx` above WebGL canvas with 160px safe padding box ($760 \times 760\text{px}$).
- [ ] **Task 4.2**: Verify 3-line max FIFO roll-off clamp prevents text overflow during rapid lyrical sections.
- [ ] **Task 4.3**: Integrate alternating black/white tape strips with $\pm 1.2^\circ$ rotation jitter.

### Phase 5: Bot & Vault Storage Integration
- [ ] **Task 5.1**: Build Telegram bot handler with inline keyboard selector for the 4 styles.
- [ ] **Task 5.2**: Implement Hot Staging render to `/tmp/staging-<jobId>.mp4`.
- [ ] **Task 5.3**: Implement checksum verification and async move to `/opt/hermes-vault/viz/` on Server 2 mount.
- [ ] **Task 5.4**: Implement immediate `/tmp` staging purge and storage reservation check before job admission.

### Phase 6: Automated Verification & Test Suite
- [ ] **Task 6.1**: Unit tests for audio feature normalization and manifest generation (`test_audio_features.py`).
- [ ] **Task 6.2**: Determinism verification: Ensure frame $N$ rendered independently yields identical vertex buffers as frame $N$ in sequential render.
- [ ] **Task 6.3**: Plexus benchmark: Validate 1,500-node $k$-NN index buffer build time $< 50\text{ms}$ with zero runtime GC pauses.
- [ ] **Task 6.4**: Golden frame automated regression tests ($\text{SSIM} \ge 0.92$).
- [ ] **Task 6.5**: End-to-end render smoke test for all 4 presets on port `4001`.

---

## 8. Verification & Acceptance Criteria

### Automated Tests
1. `python3 -m unittest tests/test_audio_features.py`: Multiband feature normalization $[0.0, 1.0]$, 30 FPS array alignment.
2. `npm run test:determinism`: Bit-exact frame evaluation validation.
3. `npm run test:golden-frames`: SSIM threshold validation against approved golden frames ($\ge 0.92$).

### Manual Verification
1. **Visual Smoke Test**: Render a 15-second benchmark clip for each of the 4 visualizers and verify shader aesthetics match specifications.
2. **Lyric Containment**: Verify Persian lyrics never exceed 3 stacked lines or cross the 160px safe margin.
3. **Resource Guardrails**: Verify CPU usage does not exceed 2 worker processes and outputs land in the 15 GB Server 2 vault.
