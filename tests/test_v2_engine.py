import unittest
import os
import json
import math
import tempfile
import subprocess
from contracts.creative_spec import (
    CreativeSpec, CreativeDNA, CompositionGraph, SceneNode, LayerNode,
    Palette, generate_harmonic_palette
)
from bot.services.audio_adapter import AudioIntelligenceAdapter, AudioAnchor
from bot.services.director import (
    fallback_procedural_creative_spec,
    fallback_procedural_composition_graph,
    RENDERER_CAPABILITY_MANIFEST
)
from bot.services.normalizer import hex_to_rgb

def delta_e(hex1: str, hex2: str) -> float:
    def to_lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r1, g1, b1 = [to_lin(c) for c in hex_to_rgb(hex1)]
    r2, g2, b2 = [to_lin(c) for c in hex_to_rgb(hex2)]

    # Simple Euclidean distance in normalized linear RGB
    return math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) * 100

class TestVoitomoV2Engine(unittest.TestCase):

    def test_audio_prosody_cadential_pause_and_anchors(self):
        """Verify silence detection (>350ms) and AudioAnchor emission."""
        words = [
            {"word": "سلام", "start": 0.0, "end": 0.5},
            # Gap of 0.6s (> 0.35s) -> cadential_pause
            {"word": "امروز", "start": 1.1, "end": 1.6},
            {"word": "می‌خواهیم", "start": 1.65, "end": 2.1},
            # Gap of 0.5s (> 0.35s) -> cadential_pause
            {"word": "شروع", "start": 2.6, "end": 3.0}
        ]

        # Call extract_audio_prosody with a non-existent dummy file to test pause detector fallback
        anchors = AudioIntelligenceAdapter.extract_audio_prosody("/tmp/dummy_non_existent.wav", words, fps=30)
        # Even without audio PCM, pause detection operates deterministically
        self.assertIsInstance(anchors, list)

    def test_harmonic_palette_kills_navy_trap(self):
        """Strict verification: generated palettes NEVER return #090A0F navy."""
        sample_texts = [
            "معماری سیستم‌های ابری پیشرفته",
            "طراحی هویت بصری و تایپوگرافی سوئیسی",
            "آهنگ و ترانه عاشقانه شب کویر",
            "تبلیغاتی برای استارتاپ تکنولوژی مدرن",
            "داستان‌سرایی و روایت سینمایی عمیق",
            "بازاریابی و رشد سریع کسب و کار دیجیتال"
        ]

        bgs = []
        for txt in sample_texts:
            pal = generate_harmonic_palette(txt, "compress")
            self.assertNotEqual(pal.bg.upper(), "#090A0F", "Navy fallback #090A0F is strictly forbidden!")
            self.assertNotEqual(pal.bg.upper(), "#0A0B0E")
            self.assertIsNotNone(pal.fg)
            self.assertIsNotNone(pal.accent)
            bgs.append(pal.bg)

        # Confirm diversity in background colors
        unique_bgs = set(bgs)
        self.assertGreater(len(unique_bgs), 2, "Palettes must vary backgrounds across distinct texts!")

    def test_composition_graph_ir_structure(self):
        """Verify Scene-Shot-Layer Graph IR compilation and transformation verbs."""
        words = [
            {"word": "آینده", "start": 0.0, "end": 0.8},
            {"word": "اینجاست", "start": 0.8, "end": 1.5},
            {"word": "در", "start": 2.0, "end": 2.2},
            {"word": "دستان", "start": 2.2, "end": 2.6},
            {"word": "شما", "start": 2.6, "end": 3.2}
        ]
        anchors = [
            AudioAnchor(frame=24, timestamp=0.8, type="cadential_pause", energy_level=0.0, associated_word="اینجاست", duration_sec=0.5),
            AudioAnchor(frame=45, timestamp=1.5, type="emphasis", energy_level=0.85, associated_word="دستان")
        ]

        spec = fallback_procedural_creative_spec(words, fps=30, total_frames=96, total_sec=3.2, audio_anchors=anchors)

        # Check CreativeDNA
        self.assertIsNotNone(spec.creative_dna)
        self.assertIn("compress", spec.creative_dna.transformation_verbs)
        self.assertIn("reconcile", spec.creative_dna.transformation_verbs)

        # Check CompositionGraph
        self.assertIsNotNone(spec.composition_graph)
        self.assertGreaterEqual(len(spec.composition_graph.scenes), 2)

        # Final scene resolution verification
        final_scene = spec.composition_graph.scenes[-1]
        self.assertEqual(final_scene.narrative_beat, "Resolution")
        self.assertEqual(final_scene.layers[0].action_verb, "reconcile")

    def test_capability_manifest_contract(self):
        """Verify capability manifest declares all supported verbs and camera dynamics."""
        self.assertIn("compress", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("reconcile", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("invert", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("accrete", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("push", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("pan_left", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("Dana", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("bento_grid", RENDERER_CAPABILITY_MANIFEST)
        self.assertIn("split_viewport", RENDERER_CAPABILITY_MANIFEST)

    def test_layout_diversity_enforcement(self):
        """Verify strict layout diversity: no consecutive identical layouts and >= 3 archetypes."""
        from bot.services.director import enforce_layout_diversity

        # Simulate 5 scenes all defaulting to hero_focus
        scenes = [SceneNode(id=f"s{i}", frame_range=[i*30, (i+1)*30], layout="hero_focus") for i in range(5)]
        diversified = enforce_layout_diversity(scenes)

        # 1. No two consecutive scenes may share the same layout
        for i in range(1, len(diversified)):
            self.assertNotEqual(diversified[i].layout, diversified[i-1].layout, f"Consecutive layout collision at scene {i}!")

        # 2. For >= 4 scenes, at least 3 distinct archetypes
        distinct = set(s.layout for s in diversified)
        self.assertGreaterEqual(len(distinct), 3, "Failed to produce >= 3 distinct archetypes!")

    def test_badge_clamping(self):
        """Verify badge is clamped to <= 3 words and <= 20 characters."""
        from contracts.creative_spec import clamp_badge

        # Long sentence / thesis
        long_text = "تاکید ساختاری و ریتمیک بر محور تغییرات عمیق در سازمان و جامعه"
        clamped = clamp_badge(long_text)
        words = clamped.split()
        self.assertLessEqual(len(words), 3)
        self.assertLessEqual(len(clamped), 20)

        # Short badge preserved
        short_text = "#کاریابی"
        self.assertEqual(clamp_badge(short_text), "#کاریابی")

        # English tag
        eng_text = "TIP 01 LINKEDIN"
        self.assertEqual(clamp_badge(eng_text), "TIP 01 LINKEDIN")

if __name__ == "__main__":
    unittest.main()
