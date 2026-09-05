import unittest
from contracts.creative_spec import (
    CreativeSpec, DesignSystem, Palette, TypeScale, Grid, MotionSignature, RevealConfig, Scene, SceneContent
)
from bot.services.normalizer import enforce_wcag_contrast, contrast_ratio, sanitize_anti_slop
from bot.services.director import fallback_procedural_creative_spec

class TestCreativeSpecContract(unittest.TestCase):

    def test_spec_serialization_roundtrip(self):
        ds = DesignSystem(
            concept="Ascending Weight Gravity",
            palette=Palette(bg="#0B0C10", fg="#FFFFFF", accent="#E11D48", muted="#64748B"),
            type_scale=TypeScale(family="Vazirmatn", weights=["300", "500", "700", "900"], ratio=1.333),
            grid=Grid(alignment="left", margin=80, columns=12),
            motion_signature=MotionSignature(chunking="phrase", stagger_frames=5, reveal_direction="in_place")
        )
        scenes = [
            Scene(
                id="s1",
                layout="hero_focus",
                frame_range=[0, 150],
                reveal=RevealConfig(primitive="glitch_decode", channel_offset_px=5),
                content=[SceneContent(text="تست موشن", weight="900", is_hero=True)]
            )
        ]
        spec = CreativeSpec(meta={"duration": 5.0, "fps": 30, "total_frames": 150}, design_system=ds, scenes=scenes)
        
        # Test serialization
        d = spec.to_dict()
        self.assertIn("design_system", d)
        self.assertIn("timeline", d)
        self.assertEqual(len(d["timeline"]["scenes"]), 1)
        self.assertEqual(d["timeline"]["scenes"][0]["content"][0]["text"], "تست موشن")

        # Test deserialization
        restored = CreativeSpec.from_dict(d)
        self.assertEqual(restored.design_system.concept, "Ascending Weight Gravity")
        self.assertEqual(restored.scenes[0].content[0].text, "تست موشن")
        self.assertEqual(restored.scenes[0].reveal.primitive, "glitch_decode")

    def test_wcag_contrast_enforcement(self):
        # Very low contrast: dark grey on black
        bg_dark = "#111111"
        fg_dark = "#222222"
        ratio_before = contrast_ratio(bg_dark, fg_dark)
        self.assertLess(ratio_before, 4.5)

        # Enforced
        clean_bg, clean_fg = enforce_wcag_contrast(bg_dark, fg_dark, min_ratio=4.5)
        ratio_after = contrast_ratio(clean_bg, clean_fg)
        self.assertGreaterEqual(ratio_after, 4.5)

    def test_anti_slop_sanitization(self):
        slop_text = "This design stands as a testament to delve into a new realm of branding."
        cleaned = sanitize_anti_slop(slop_text)
        self.assertNotIn("testament", cleaned.lower())
        self.assertNotIn("delve", cleaned.lower())
        self.assertNotIn("realm", cleaned.lower())

    def test_procedural_spec_generation_zero_hardcoding(self):
        sample_words = [
            {"word": "من", "start": 0.0, "end": 0.5},
            {"word": "و", "start": 0.5, "end": 0.8},
            {"word": "موج", "start": 0.8, "end": 1.4},
            {"word": "سودا", "start": 1.4, "end": 2.2}
        ]
        spec = fallback_procedural_creative_spec(sample_words, fps=30, total_frames=90, total_sec=3.0)
        
        # Must have valid design system and scenes
        self.assertIsNotNone(spec.design_system)
        self.assertGreater(len(spec.scenes), 0)
        # Verify frame continuity
        self.assertEqual(spec.scenes[0].frame_range[0], 0)
        self.assertEqual(spec.scenes[-1].frame_range[1], 90)
        # Verify content contains input words
        all_texts = " ".join(c.text for s in spec.scenes for c in s.content)
        self.assertIn("موج", all_texts)

if __name__ == "__main__":
    unittest.main()
