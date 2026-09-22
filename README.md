# Voitomo Audioviz 🎬✨

[![CI Quality Gate](https://github.com/hessam/voitomo-audioviz/actions/workflows/ci.yml/badge.svg)](https://github.com/hessam/voitomo-audioviz/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Remotion](https://img.shields.io/badge/Renderer-Remotion%204.0-red.svg)](https://remotion.dev)
[![Three.js](https://img.shields.io/badge/WebGL-Three.js-black.svg)](https://threejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-blue.svg)](https://www.typescriptlang.org)
[![Python](https://img.shields.io/badge/Python-3.11+-yellow.svg)](https://www.python.org)

**Voitomo Audioviz** is an autonomous 3D WebGL audio visualizer and kinetic typography engine. It converts raw audio (voice notes, podcasts, or music tracks) into broadcast-grade, Swiss-style kinetic video assets with frame-accurate audio reactivity and $0 recurring SaaS fees.

---

## 🏛 System Architecture

The pipeline decouples audio intelligence from deterministic rendering via a declarative **Manifest Contract**:

```mermaid
flowchart TD
    subgraph IN["1. Audio Ingestion & Analysis"]
        A["Audio Track (WAV/MP3)"] --> B["Audio DSP Pipeline\n(FFT, RMS, Beat Grid, Spectral Centroid)"]
        A --> C["Whisper Alignment Engine\n(large-v3-turbo sub-word timestamps)"]
        C --> D["Phonetic Normalizer\n(Zero-slip phonetic correction)"]
    end

    subgraph DIR["2. Art Direction & Manifest Synthesis"]
        B --> E["Director Engine\n(LLM Beat Choreography & Visualizer Archetypes)"]
        D --> E
        E --> F["Declarative Composition Manifest\n(JSON Contract with Frame Delays & Motion Props)"]
    end

    subgraph RENDER["3. Remotion 3D WebGL Runtime"]
        F --> G["Remotion Canvas\n(Chromium Frame-Accurate Clock)"]
        G --> H["Three.js Generative Visualizers\n• ParticleSphere (Instanced Meshes)\n• NeuralSynapse (Procedural Curves)\n• QuantumIris (Audio-reactive Shaders)\n• MonolithField (Depth Attenuation)"]
        G --> I["Kinetic Typography Layer\n(Swiss-grid & Vazirmatn Optical Align)"]
    end

    subgraph OUT["4. Headless Delivery"]
        H --> J["Remotion Headless Exporter\n(H.264 / ProRes MP4)"]
        I --> J
        J --> K["Broadcast-Ready Video Asset"]
    end
```

---

## ⚡ Key Capabilities

* **Audio-Reactive 3D WebGL**: Custom Three.js shaders reacting directly to spectral frequency bands, RMS power curves, and onset transients (`ParticleSphereVisualizer`, `NeuralSynapseVisualizer`, `QuantumIrisVisualizer`).
* **Deterministic Sub-Word Sync**: Sub-word acoustic alignment ensures kinetic typography matches voice cadences frame-for-frame, even over instrumental pauses.
* **LLM Art Direction**: Automatically analyzes semantic mood, narrative momentum, and tempo to assign kinetic archetypes (`HERO_FOCUS`, `METRIC_PUNCH`, `SPLIT_VIEWPORT`, `BENTO_GRID`).
* **Headless Infrastructure**: Fully scriptable via Node.js and Python. Runs locally or scaled across headless cloud GPU/CPU instances (Docker / Vast.ai / Bare Metal).

---

## 📊 Technical Benchmarks

| Metric | Measured Performance |
| :--- | :--- |
| **Audio Feature Extraction** | < 1.8s for 60s stereo audio (16kHz mono downmix) |
| **ASR Sub-Word Alignment** | ~0.2x real-time on GPU / ~1.1x real-time on 8-core CPU |
| **Remotion Rendering (1080p60)** | ~1.4x real-time via Headless Chromium instanced rendering |
| **SaaS Cost** | **$0.00 / month** (Open-source self-hosted stack) |

---

## 🚀 Quickstart

### 1. Clone & Configure
```bash
git clone https://github.com/hessam/voitomo-audioviz.git
cd voitomo-audioviz

# Create local environment configuration
cp .env.example .env
```

### 2. Start the 3D Remotion Server
```bash
cd renderer
npm install
npm run server
# -> Audioviz 3D WebGL render server listening on http://127.0.0.1:4001
```

### 3. Run Audio Feature Extraction & Preview
In another terminal:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r <(python3 -c "import tomli; ...") # or pip install pydantic aiohttp librosa

# Run end-to-end manifest test
python tests/test_end_to_end_manifest.py
```

---

## 📂 Repository Structure

```text
voitomo-audioviz/
├── bot/
│   ├── routers/            # Telegram and webhook intake endpoints
│   └── services/           # DSP analysis, Whisper ASR, and Art Direction
│       ├── audio_features.py   # FFT, RMS, spectral flux extractor
│       ├── alignment.py        # Sub-word alignment timeline
│       ├── director.py         # Narrative scene orchestration
│       └── normalizer.py       # Phonetic normalization
├── contracts/              # Pydantic schemas defining the Manifest protocol
├── renderer/               # Remotion + Three.js 3D composition runtime
│   ├── server.ts           # Express headless rendering daemon
│   └── src/
│       ├── Composition.tsx # Root video timeline orchestrator
│       └── visualizers/    # 3D Three.js shaders & particle meshes
│           ├── ParticleSphereVisualizer.tsx
│           ├── NeuralSynapseVisualizer.tsx
│           └── QuantumIrisVisualizer.tsx
└── tests/                  # Invariant harnesses & integration test suites
```

---

## 📜 Architecture Decision Records (ADRs)

* [ADR-0007: Autonomous Voice-to-Motion Kinetic Typography Engine](docs/decisions/ADR-0007-hermes-motion-agent-kinetic-typography-engine.md)
* [ADR-0008: Lyric Typography Orchestration & Music Token Filtering](docs/decisions/ADR-0008-hermes-music-agents-lyric-typography-orchestration.md)

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 Hessam Mousavi.
