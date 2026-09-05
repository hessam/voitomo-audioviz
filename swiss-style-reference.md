# Reference Breakdown #2: "Glitch-Decode Specimen" Style
### (source: Helvetica type-specimen clip, 960×960, 30fps, 14.4s)

This is the second reference — the one that actually corresponds to what ADR-0009 was
gesturing at with `lyric_kinetic_with_reactive_geometry`. Good news: it's simpler than that
name suggests, and it shares more structural DNA with reference #1 (the Cavalry clip) than
you'd expect. Read this alongside `reference-video-creative-brief.md`.

---

## 1. TL;DR for the agent

> A hero word/phrase materializes via a **glitch-decode reveal** (pixel corruption + RGB
> channel noise clearing into clean glyphs, in place — not flying in from elsewhere), holds at
> large scale, then scales down and docks into position as the anchor row of a **stacked
> specimen ladder** (the same word repeated in ascending weights, each row glitch-decoding in
> top-to-bottom). A static caption panel holds below it. Everything then reverses — the same
> glitch corruption regrows and the whole composition disassembles — as the exit transition.
> Flat 2D throughout: no camera movement, no 3D depth, no waveform overlay.

---

## 2. Timeline (approximate)

| Time (s) | Stage | What happens |
|---|---|---|
| 0.0–1.7 | Intro decode | "HELVETICA" resolves in place from pixel-noise/RGB-channel corruption into clean bold glyphs, at near-full-frame scale (hero size) |
| 1.7–2.3 | Hold | Hero word holds, fully clean, large |
| ~2.3–3.0 | Dock | Hero word scales down and repositions to the **top row** of a left-aligned stack (the only "camera-like" motion in the whole piece — a 2D scale+reposition tween, not a 3D camera) |
| 2.3–4.7 | Ladder build | 4 more rows glitch-decode in, top to bottom, each in a heavier font weight than the last (thin → light → regular → bold → black) |
| ~5.0–10.5 | Caption hold | Static italic small-caps caption block appears beneath the ladder: "DEVELOPED IN 1957 / BY SWISS TYPEFACE DESIGNER / MAX MIEDINGER / WITH INPUT FROM / EDUARD HOFFMANN." — no motion, just a long hold |
| ~10.5–13.5 | Exit decode | Mirror of the intro: ladder + caption re-corrupt (RGB noise regrows, glyphs displace/streak) and disassemble, same visual language reversed |
| ~13.5–14.4 | Cut | Frame drops to a flat grey/black — presumably a hard cut into the next scene (out of range of this clip) |

---

## 3. The core reveal primitive: glitch-decode (not spring, not fly-in)

This is worth being precise about because "kinetic typography" gets used loosely — this is
**not** characters flying in from off-screen or springing into place. Every glyph is already at
its final X/Y position for the whole shot. What animates is *corruption clearing*:

- Each character starts as scattered pixel-noise/short horizontal streak artifacts (red, yellow,
  cyan fragments — reads like a channel-desync / bad-decode glitch, not a soft chromatic-
  aberration blur) roughly overlapping where the glyph will eventually sit.
- Over ~15–20 frames (~0.5–0.7s) at the word level, the noise density decreases and the true
  black glyph resolves out of it. Different characters within the same word resolve at very
  slightly staggered times, so it doesn't read as fully synchronized, but there's no spatial
  travel — just a corruption-to-clean fade with color-fringing that shrinks toward zero.
- The reverse (exit) transition is the same effect played with corruption *increasing* rather
  than decreasing, ending in the glyphs displacing into short colored streaks before cutting out.

Implementation-wise this is far cheaper than spring physics or particle simulation: it's a
per-glyph (or per-word) noise/threshold mask with a time-based intensity curve, plus a small
random RGB-channel offset that decays to 0. Good candidate for a shader/canvas-filter pass in
the Remotion runtime rather than anything requiring an LLM to reason about physics parameters.

---

## 4. Layout components

- **Hero word**: single word/phrase, huge scale, centered — the "cold open."
- **Specimen ladder**: same text repeated N times stacked top-to-bottom, each row a different
  font weight, left-aligned as a block. This is a content-specific choice for a
  typography-themed video — for other subjects this slot is better thought of generically as
  a **"repeated-emphasis stack"**: same key phrase shown multiple times with an escalating
  visual property (weight, size, saturation — whatever fits the subject).
- **Caption panel**: small italic centered/left caps text block, purely static, no reveal effect
  of its own beyond a simple appear — this is the "supporting facts" slot, analogous to
  reference #1's body-text scenes.

---

## 5. Cross-reference: how this relates to `reference-video-creative-brief.md`

Now that there are two concrete references, a cleaner pattern falls out — **both clips share the
same skeleton**, they just plug in a different reveal effect and layout:

| | Reference #1 (Cavalry) | Reference #2 (Helvetica) |
|---|---|---|
| Reveal effect | solid-color block wipe, left→right, phrase chunks | pixel-noise/glitch decode, in place, per glyph |
| Motion | none (static frame, hard cuts only) | one scale+reposition tween (hero → ladder row); otherwise static |
| Structure | paragraph block → emphasis line → hard cut | hero word → repeated-emphasis stack → caption hold → reverse |
| Interstitial | feature-showcase image grid | none observed |
| Outro | static logo card | (out of clip range — likely a hard cut, not shown) |

**Neither reference uses**: spring/bounce physics, 3D camera drift or z-depth, a waveform
visualizer, or beat-reactive geometry brackets. That's the biggest actionable finding across
both breakdowns — ADR-0009's example `CreativeSpec` describes machinery that isn't evidenced in
either target style you've provided. Suggest treating `visual_strategy` as a choice between
two concrete, cheap-to-render **reveal-effect primitives** (`block_wipe` and `glitch_decode`),
each combined with a **layout** (`paragraph_stack`, `specimen_ladder`, `left/center-aligned`,
etc.), rather than building toward the more elaborate audio-reactive engine unless you have a
third reference that actually needs it.

---

## 6. Proposed `CreativeSpec` addition for this style

```json
{
  "visual_strategy": "glitch_decode_specimen",
  "timeline": {
    "scenes": [
      {
        "id": "hero",
        "background": { "color": "#FFFFFF" },
        "text_block": {
          "content": "HELVETICA",
          "scale": "hero",
          "reveal": { "type": "glitch_decode", "duration_frames": 45, "channel_offset_px": 6 }
        }
      },
      {
        "id": "dock_to_ladder",
        "transition": { "type": "scale_reposition", "from": "hero_center", "to": "ladder_row_0", "duration_frames": 18 }
      },
      {
        "id": "specimen_ladder",
        "layout": "repeated_emphasis_stack",
        "rows": [
          { "content": "HELVETICA", "weight": "thin" },
          { "content": "HELVETICA", "weight": "light" },
          { "content": "HELVETICA", "weight": "regular" },
          { "content": "HELVETICA", "weight": "bold" },
          { "content": "HELVETICA", "weight": "black" }
        ],
        "reveal": { "type": "glitch_decode", "per_row_duration_frames": 20, "stagger_frames": 8 }
      },
      {
        "id": "caption_panel",
        "type": "static_caption",
        "style": "italic_small_caps",
        "lines": [
          "DEVELOPED IN 1957",
          "BY SWISS TYPEFACE DESIGNER",
          "MAX MIEDINGER",
          "WITH INPUT FROM",
          "EDUARD HOFFMANN."
        ],
        "hold_frames": 150
      },
      {
        "id": "exit",
        "reveal": { "type": "glitch_decode", "direction": "reverse", "duration_frames": 45 }
      }
    ]
  }
}
```

---

## 7. Updated open question (supersedes the one in brief #1)

With both references in hand, the real design decision isn't "replace vs. add a strategy" —
it's simpler: **does the planner need to pick a reveal-effect (`block_wipe` vs `glitch_decode`)
and a layout independently, or are they always paired 1:1 per "look"?** If the audio content
type (VO caption vs. music/title-card) reliably predicts which pairing to use, the planner's
job is just classification; if you want the LLM to mix-and-match (e.g. glitch-decode reveal with
a paragraph-stack layout), the runtime needs both axes exposed as independent parameters in the
spec rather than baked into a single `visual_strategy` enum value.



# Reference Breakdown #3: "Swiss Minimalist Single Line" Style
        source: "text-animation-design-principles.mp4",
        clip_duration_s: 12.75,
        format: { width: 960, height: 540, fps: 30 },
        content_description: "Single-line Helvetica typography, clean and architectural: 'TEXT ANIMATION: DESIGN PRINCIPLES FOR MOVING TEXT'. Mostly static, with a subtle left-to-right center line and a final hard cut. No music, no audio-reactive effects.",
        transcript_segments: [
          { text: "TEXT ANIMATION:", speaker: "primary", start_s: 0.0, end_s: 1.0 },
          { text: "DESIGN PRINCIPLES", speaker: "primary", start_s: 1.0, end_s: 2.0 },
          { text: "FOR MOVING TEXT", speaker: "primary", start_s: 2.0, end_s: 3.0 }
        ]
        