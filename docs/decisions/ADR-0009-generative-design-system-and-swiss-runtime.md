# ADR-0009: Generative Design System & Swiss Typographic Motion Runtime

## Status
Accepted (2026-09-05)

## Context
Previous iterations relied on hardcoded scene templates (`HERO_BLOCK`, `SPLIT_VIEWPORT`, etc.) or proposed complex physics/3D simulations (spring bouncing, particle clouds, 3D camera sweeps). Empirical analysis of Swiss typography references (*Cavalry* and *Helvetica Glitch-Decode Specimen*) showed that high-end motion design requires:
1. **Strict 2D Discipline**: No bouncy springs, no 3D cameras, zero ungrounded clutter.
2. **In-Place Reveals**: Text elements materialize at their final coordinates via discrete noise/mask clearing (`glitch_decode`, `block_wipe`).
3. **Per-Generation Uniqueness**: Avoiding a closed menu of combinations by letting the LLM Art Director invent a bespoke `design_system` (palette, type scale, grid rules, acoustic motion signature, and concept hook) per audio input.

## Decision
1. **Adopt 3-Tier Model**:
   $$\text{Strict 2D Grammar} \times \text{Generative Design System} \times \text{Parametric Remotion Runtime}$$
2. **Central Contract**: `CreativeSpec` encapsulates `design_system` and `timeline.scenes`.
3. **Deterministic Remotion Runtime**:
   - `GlitchDecode`: In-place SVG-displacement and chromatic aberration filter clearing over 15–20 frames.
   - `BlockWipe`: Phrase-synchronized clip-path mask wipe.
   - `SpecimenLadder`: Dynamic repeated-emphasis stack with escalating weights (`300` $\to$ `900`).
   - `ParagraphStack`: Architectural grid layouts.
4. **Hardening & Quality Firewall**:
   - WCAG AA Contrast Enforcer ($\ge 4.5:1$).
   - 100% Token Grounding (zero hallucinated text).
   - Anti-AI-Slop Copy Filter (rejects generic filler words).
   - Acoustic Timing Normalization (reveal durations dynamically bound to word acoustic durations).

## Consequences
- **Positive**: 100% deterministic, renders in $<20\text{s}$, high visual authority matching agency-grade editorial references, zero hardcoded strings.
- **Negative**: Requires strict contrast and schema validation in Python before sending to Remotion.
