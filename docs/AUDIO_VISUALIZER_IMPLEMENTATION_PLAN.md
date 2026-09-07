# Implementation Plan: Audio Visualizer Agent (Audioviz)

A 100% isolated music visualizer engine with synchronized kinetic lyrics, forked from Voitomo and orchestrated with `hermes-audio-engineer` and `hermes-music-dna`.

---

## 1. Executive Summary & Goals

Transform Voitomo's proven kinetic typography pipeline into a dedicated **Stem-Aware Audio Visualizer Agent** that:
1. Ingests songs/audio files via Telegram.
2. Extracts acoustic intelligence (dry vocals, isolated kick/bass, BPM, downbeats, section drops) via `hermes-audio-engineer` (port 5001) and `hermes-music-dna` (port 5002).
3. Renders high-end 3D audio-reactive WebGL visualizers (Particle Sphere, Quantum Iris, Neural Synapse, Monolith Field) with synchronized snug, alternating black/white tape-strip lyrics.
4. Operates in 100% isolation from Voitomo and existing production services on Server 1 and Server 2.

---

## 2. Guardrails

### Storage Isolation & 15 GB Vault Lock
- All heavy video renders, audio conversions, and feature caches write strictly to `/opt/hermes-vault/viz/` on Server 1.
- `/opt/hermes-vault/` is mounted via `sshfs` to an isolated ext4 loopback filesystem on Server 2 (`78.46.210.232:/srv/hermes-vault`), physically hard-locked at **15 GB**.
- Server 1 local disk never stores permanent render files; local `/tmp` scratch is purged post-delivery.

### Compute & Concurrency Guardrails
- Remotion render concurrency is set to `2` on Server 1 (leaving remaining cores free for Voitomo and background workloads).
- Hot rendering occurs on Server 1's local SSD for **0.00ms response time degradation**, followed by asynchronous background vault mirroring.

### Microservice Resilience
- All calls to `hermes-audio-engineer:5001` and `hermes-music-dna:5002` are wrapped with local DSP fallbacks (Librosa/Aubio and FFmpeg bandpass filters) to ensure 100% uptime even if a microservice is busy.

### Typographic Invariants
- Preserves Voitomo's strict 2-size typography system (58px body, 84px emphasis) and per-line snug tape strips for lyric overlays.

---

## 3. Architecture & Data Flow

```
                           [User sends MP3/Audio to Telegram]
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │      Audioviz Telegram Bot (4001)     │
                      └───────────────────┬───────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
      hermes-audio-engineer:5001                   hermes-music-dna:5002
      (Mel-Band RoFormer)                          (Musicological DSP)
      ├── Isolated Dry Vocals                      ├── Accurate BPM & Beat Grid
      └── Isolated Bass/Kick Stem                  └── Section Drops & Energy Curve
                    │                                           │
                    └─────────────────────┬─────────────────────┘
                                          ▼
                      ┌───────────────────────────────────────┐
                      │       Visualizer Concept Router       │
                      │  (Maps beats + bass to 30 FPS arrays) │
                      └───────────────────┬───────────────────┘
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │       Remotion Visualizer Engine      │
                      │  ├── Audio-Reactive Canvas / WebGL    │
                      │  └── Snug Alternating Tape Lyrics     │
                      └───────────────────┬───────────────────┘
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │        Async Vault Archival           │
                      │  (/opt/hermes-vault/viz/ - 15GB pool) │
                      └───────────────────┬───────────────────┘
                                          │
                                          ▼
                           [MP4 Delivered to Telegram]
```

---

## 4. Component Tasks

### Task 1: Repository & Environment Scaffolding
- Fork/clone codebase to `/opt/hermes-data/audioviz/`.
- Configure `PORT = 4001` in `renderer/server.ts` and python routers.
- Set up independent `.env` containing `TELEGRAM_BOT_TOKEN`, `MUSIC_DNA_URL`, `AUDIO_ENGINEER_URL`, and `RENDER_URL`.

### Task 2: Audio Analysis Pipeline (`audio_features.py`)
- Integrate `AudioIntelligenceAdapter` for stem extraction:
  - Dry vocals stem $\rightarrow$ Whisper lyric alignment.
  - Kick/bass stem $\rightarrow$ 30 FPS sub-bass energy array (`sub_bass[frame]`).
  - Music-DNA beat grid $\rightarrow$ downbeat and drop frame markers.
- Pass normalized numerical arrays directly into Remotion input props (zero client-side audio decoding latency).

### Task 3: 3D Audio-Reactive WebGL Runtimes (`renderer/src/runtime/visualizers/`)
1. **`ParticleSphereVisualizer.tsx` (Particle Sphere)**:
   - **Geometry**: `IcosahedronGeometry` or dense UV sphere with 15,000–30,000 point particles rendered as circular glowing dots.
   - **Shaders**: 3D Simplex/Perlin noise vertex displacement along particle normals modulated by frequency bands; fragment shader with warm golden-yellow emissive gradient (`#FFD700` to `#FFA500`), additive blending, and soft glow falloff.
   - **Audio Reactivity**: Low/bass frequencies drive scale pulsation and primary wave displacement; mids/highs drive surface ripple speed and micro-jitters; continuous slow dual-axis rotation.
   - **Post-Processing**: `UnrealBloomPass` for soft vibrant ambient glow.

2. **`QuantumIrisVisualizer.tsx` (Torus Knot / Quantum Iris)**:
   - **Geometry**: Instanced ribbon/wireframe `TorusKnotGeometry` (~20,000 sub-segments).
   - **Shaders**: Dynamic vertex displacement twisting geometry inside-out along its primary spline; neon cyan (`#00F0FF`) to deep violet (`#7B2CBF`) gradient.
   - **Audio Reactivity**: Bass expands inner radius and triggers shockwave pulses; high frequencies modulate ribbon twist speed and spawn trailing particle sparks.
   - **Post-Processing**: Additive blending, custom depth-fade, and chromatic aberration bloom.

3. **`NeuralSynapseVisualizer.tsx` (Neural Synapse / Topological Web)**:
   - **Geometry**: 1,500 interconnected floating nodes in a bounding sphere with dynamic distance-threshold line segments (Plexus effect).
   - **Shaders/Points**: Glowing node points in pure white (`#FFFFFF`); connecting lines pulsing in emerald-teal (`#00FFA3`).
   - **Audio Reactivity**: Audio transients fire electrical impulse waves traveling outward from the center across line branches; bass expands overall cluster volume.
   - **Motion**: Gentle Brownian node motion with rotational orbit and heavy camera depth of field (bokeh).

4. **`MonolithFieldVisualizer.tsx` (Monolith Field / Kinetic Wave Matrix)**:
   - **Geometry**: $32 \times 32$ planar grid (1,024 instances) of `InstancedMesh` hexagonal prisms/cuboids floating over a dark void.
   - **Shaders/Material**: High-roughness dark obsidian reflective sides with emissive neon acid-lime (`#D4FF00`) top caps.
   - **Audio Reactivity**: Spatial center-outward FFT mapping; bass drives central height displacement, mids/highs generate cascading fluid ripple waves across the array.
   - **Lighting/Effects**: Screen-space reflections, subtle floor fog, and an `UnrealBloomPass` targeting top emissive caps.

- **Unified Lyric Engine**: All 4 visualizers integrate Voitomo's proven kinetic typography overlay with 3-line max FIFO clamping and 160px safe margin containment.

### Task 4: Telegram Bot UI & Router
- **Interactive Preset Selector**:
  - 🌟 Particle Sphere (Golden Glow / Ethereal)
  - 🌀 Quantum Iris (Neon Cyan-Violet Torus Knot)
  - ⚡ Neural Synapse (Emerald Web / Topological)
  - 🏛️ Monolith Field (Acid-Lime Kinetic Wave Matrix)
- **Lyric Toggle**: Option to render pure visualizer or visualizer + synchronized tape lyrics.

### Task 5: DevOps, Container & Watchdog
- Launch container `hermes-audioviz-sandbox` using the existing `hermes-sandbox:latest` image (0 MB download).
- Bind-mount `/opt/hermes-vault/viz:/tmp/motion-renders`.
- Setup dedicated watchdog at `/opt/hermes-data/audioviz/watchdog.sh`.

---

## 5. Verification & Test Harness

### Automated Tests
1. **DSP Feature Extraction Unit Tests**:
   - `python3 -m unittest tests/test_audio_features.py`: Verify 30 FPS array generation, duration matching, and normalized 0.0–1.0 values.
2. **Microservice Contract Tests**:
   - `python3 -m unittest tests/test_audio_adapter.py`: Verify stem extraction fallback when microservices are simulated offline.
3. **Remotion Render Smoke Test**:
   - Execute test render of a 15-second visualizer on port `4001` via `server.ts`.
   - Check video output format, 1080x1080 resolution, and audio multiplexing.

### Manual Verification
1. **Telegram End-to-End Test**:
   - Send an MP3 file to the new Telegram bot.
   - Verify style selection keyboard prompt.
   - Confirm video delivery with reactive visuals and synchronized lyrics.
2. **Resource & Isolation Verification**:
   - Check `docker stats` during render to ensure CPU remains within 2 cores (`concurrency: 2`).
   - Check `df -h /opt/hermes-vault` to verify outputs write to the 15 GB Server 2 vault.
