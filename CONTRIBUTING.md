# Contributing to Voitomo Audioviz

Thank you for your interest in contributing to **Voitomo Audioviz**! We welcome contributions to audio DSP pipelines, Three.js shaders, Remotion compositions, and LLM art direction.

---

## Development Workflow

### Prerequisites
- **Node.js**: `v20.x` or later
- **Python**: `3.11` or later
- **FFmpeg**: Installed and available in `$PATH`

### 1. Repository Setup
```bash
# Clone the repository
git clone https://github.com/hessam/voitomo-audioviz.git
cd voitomo-audioviz

# Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r <(python3 -c "import tomli; ...") # or pip install dependencies

# Setup Node.js Remotion renderer
cd renderer
npm install
cd ..

# Copy configuration
cp .env.example .env
```

### 2. Branching & Commit Conventions
We enforce **Conventional Commits**:
- `feat:` New features (e.g. `feat(visualizer): add fluid galaxy shader`)
- `fix:` Bug fixes (e.g. `fix(dsp): resolve beat onset drift at 120bpm`)
- `perf:` Performance improvements (e.g. `perf(renderer): optimize instanced mesh buffer`)
- `docs:` Documentation changes
- `refactor:` Code restructuring without behavior changes
- `test:` Adding or updating tests

### 3. Pull Request Checklist
Before opening a PR, ensure:
- [ ] No API keys, credentials, or `.env` files are tracked.
- [ ] TypeScript type checks pass: `cd renderer && npx tsc --noEmit`.
- [ ] Python test harness passes: `python -m pytest tests/`.
- [ ] Large binary assets (MP3s, MP4s, compiled binaries) are excluded.
