# Implementation Plan: Audio Visualizer Agent (Audioviz)

A 100% isolated music visualizer engine with synchronized kinetic lyrics, forked from Voitomo and orchestrated with `hermes-audio-engineer` and `hermes-music-dna`.

---

## 1. Executive Summary & Goals

Transform Voitomo's proven kinetic typography pipeline into a dedicated **Stem-Aware Audio Visualizer Agent** that:
1. Ingests songs/audio files via Telegram.
2. Extracts acoustic intelligence (dry vocals, isolated kick/bass, BPM, downbeats, section drops) via `hermes-audio-engineer` (port 5001) and `hermes-music-dna` (port 5002).
3. Renders audio-reactive visuals (Radial Vinyl, Swiss Oscilloscope, 3D Particle Tunnel) with synchronized snug, alternating black/white tape-strip lyrics.
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

### Task 3: Remotion Visualizer Runtimes (`renderer/src/runtime/visualizers/`)
1. **`RadialVinylVisualizer.tsx`**:
   - Center circular album art / vinyl spinning with kick-reactive scale pulse.
   - 64 radial spectrum bars driven by bass & mid frequencies.
   - Snug Persian lyric tape strips centered below the hub.
2. **`SwissOscilloscopeVisualizer.tsx`**:
   - Clean vector Lissajous curves and real-time audio phase scopes.
   - Minimalist Swiss grid tickers, BPM counter, and timestamp scrubbers.
3. **`ReactiveParticleTunnel.tsx`**:
   - High-energy 3D particle tunnel reacting to drop markers and bass booms.
   - Giant 84px punchline tape strips slamming down at musical downbeats.

### Task 4: Telegram Bot UI & Router
- **Interactive Preset Selector**:
  - ✦ Radial Vinyl (Podcast / Track Preview)
  - ⚡ Swiss Oscilloscope (Minimal / Lo-Fi)
  - 🎬 Particle Tunnel (EDM / Trap / Beat)
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
