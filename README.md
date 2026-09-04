# Voitomo (Voice-to-Motion) 🎬

Autonomous kinetic typography engine converting voice notes into Swiss-style, Netflix/Cavalry-grade animated MP4 videos with $0 recurring SaaS fees.

## Key Capabilities
- **Whisper Speech Intelligence**: Sub-word timestamp extraction via Whisper `large-v3-turbo`.
- **Persian Phonetic Normalizer**: Pre-director filter correcting phoneme transcription slips.
- **LLM Art Director**: OpenRouter (`gpt-5.6-luna`) narrative beat directing across 5 archetypes (`HERO_BLOCK`, `METRIC_PUNCH`, `SPLIT_VIEWPORT`, `CALLOUT_CARD`, `BENTO_GRID`).
- **Remotion Headless Renderer**: Deterministic frame-accurate Chromium rendering.
- **Explainability Audit Trail**: Full reasoning and timeline validation recorded per run.

## Architectural Decision Records
- [ADR-0007: Autonomous Voice-to-Motion Kinetic Typography Engine](docs/decisions/ADR-0007-hermes-motion-agent-kinetic-typography-engine.md)

## Version
- **Tag**: `v1.0.0` (Production baseline checkpoint)
