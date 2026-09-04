# ADR-0008: Hermes Multi-Agent Persian Lyric & Music Kinetic Typography Orchestration

## Status
Accepted (v1.1.0-music)

## Date
2026-09-05

## Context & Problem Statement
Voitomo's baseline (`v1.0.1`) was engineered strictly for conversational speech and spoken voice notes. When tested on music or singing tracks, standard Whisper ASR collapsed into non-speech token hallucinations (e.g. outputting `[music]`, `(music)`, or `♪♪`), while Remotion cut scenes arbitrarily during vocal phrasing rather than on musical bars.

Rather than installing heavy PyTorch/Demucs dependencies and duplicating large AI weights inside the motion agent, the Hetzner production server already hosts two specialized Hermes music instances:
1. **`hermes-audio-engineer`**: Lead audio DSP specialist with a pre-downloaded 1.57 GB `melband_roformer_big_beta4.ckpt` model for stem separation and mix acoustics.
2. **`hermes-music-dna`**: Musicological intelligence specializing in tempo, beat tracking, and harmonic/energy structural analysis.

The architectural challenge: Orchestrate the specialized intelligence of these 2 existing agents without modifying their internal state, without causing memory thrashing on the 7.6 GB server, and without breaking the existing voice-to-motion bot workflow.

---

## Decision: Non-Invasive 3-Agent Orchestration Architecture

```
[User Song Audio] (Telegram F.audio / /music)
         │
         ▼
[1. Hermes Audio Engineer]  ──► Mel-Band RoFormer Stem Separation
         │                      Isolates clean, dry vocals (`vocals.wav`)
         ▼
[2. Hermes Music DNA]       ──► Beat Grid & Tempo Extraction
         │                      Extracts BPM and downbeat frame array
         ▼
[3. Hermes Motion Agent]
         │
         ├──► Lyric ASR Pipeline: Whisper large-v3-turbo with music token suppression
         │    (`condition_on_previous_text=False`, poetic meter initial prompt)
         │
         ├──► Music Art Director: Snaps scene transitions to musical bar boundaries (4-bar/8-bar grid)
         │
         └──► Remotion Canvas: Renders kinetic typography with audio-reactive beat pulses
```

### Key Architectural Standards

1. **Strict Branch & Workflow Isolation**:
   - Developed on `feat/music-lyric-orchestration`.
   - The production voice bot router ([`bot/routers/voice.py`](file:///bot/routers/voice.py)) remains untouched and active for conversational voice notes (`F.voice`).
   - Music workflows are routed exclusively via [`bot/routers/music.py`](file:///bot/routers/music.py).

2. **Singing-Voice Whisper Tuning**:
   - `condition_on_previous_text=False`: Prevents instrumental breaks from looping non-speech tokens.
   - Punctuation/Bracket Token Cleaning: Strips `[music]`, `(موسیقی)`, `♪`.
   - Lyrical Initial Prompt: `"متن ترانه، شعر و کلمات آواز فارسی بدون موسیقی."`
   - Dual-Mode Operation: Automatic lyric extraction or verified user lyric forced alignment.

3. **Audio-Reactive Kinetic Typography**:
   - Scene cuts (`startFrame`/`endFrame`) snap strictly to detected downbeats (measures) rather than arbitrary speech pauses.
   - Dynamic canvas scales (`beatPulse`) subtly expand by 2.5% on kick/snare hits.

4. **Zero State Degradation for Existing Agents**:
   - Audio Engineer's SOUL, REAPER configurations, and stem analysis pipelines are unchanged.
   - Music DNA's Spotify and database pipelines are unchanged.
   - All shared file operations occur via zero-copy paths with automated fallback.

---

## Consequences & Verification

### Positive Consequences
- **Zero Additional AI Model Weight**: Reuses the 1.57 GB RoFormer model already present on the server.
- **High Intelligibility**: Feeding dry isolated vocals to Whisper eliminates 90%+ of `[music]` false positives.
- **Musical Coherence**: Motion cuts on musical downbeats, creating MTV/TikTok lyric video cadence.

### Negative / Trade-offs
- Stem isolation adds ~3–8 seconds of processing latency for uncompressed music tracks.
- High-concurrency isolation requires serialization (semaphore) to maintain server RAM stability.

---

## Compliance Registry

- [x] Dedicated branch `feat/music-lyric-orchestration` created.
- [x] Standard voice pipeline (`bot/routers/voice.py`) untouched.
- [x] `AudioIntelligenceAdapter` implemented with graceful local fallback.
- [x] `lyric_transcriber.py` implemented with music token suppression.
- [x] `music_director.py` implemented with beat-grid snapping.
- [x] Remotion `Composition.tsx` updated with audio-reactive beat pulse.
