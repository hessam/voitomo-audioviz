import unittest
from bot.services.spatial_director import SpatialDirectorEngine, SpatialAllocation, Rect
from bot.services.environment_engine import EnvironmentEngine, EnvironmentSpec
from bot.services.asset_engine import AssetEngine, AssetSpec
from bot.services.type_engine import KineticTypeEngine, TypeSpec
from bot.services.director import build_kinetic_phrase_scenes, fallback_procedural_creative_spec
from contracts.creative_spec import CreativeDNA, Palette, SAFE_PALETTES


class TestNegotiatedCompiler(unittest.TestCase):

    def setUp(self):
        self.palette = SAFE_PALETTES["electric_cobalt"]
        self.dna = CreativeDNA(
            thesis="سیستم‌های ابری و مقیاس‌پذیری پایدار",
            emotional_contradiction="پیچیدگی در برابر سادگی",
            metaphor_system="تراکم ساختار شبکه‌ای",
            transformation_verbs=["compress", "accrete", "reconcile"],
            palette=self.palette,
            font_family="Dana",
            world="editorial"
        )

    def test_spatial_director_dual_box_contract_bans_zero_opacity(self):
        """Verify Spatial Director strictly enforces dual-box layout and bans zero opacity."""
        type_prop = {"text": "فرصت‌های شغلی برتر", "is_hero": True}
        asset_prop = {"geometry": "connected_graph"}

        # Scene 0: split_horizontal
        alloc_h = SpatialDirectorEngine.allocate(type_prop, asset_prop, scene_idx=0, total_scenes=5, is_music=False)
        self.assertEqual(alloc_h.archetype, "split_horizontal")
        self.assertGreater(alloc_h.asset_box.w, 0)
        self.assertGreater(alloc_h.asset_box.h, 0)
        self.assertGreater(alloc_h.type_box.w, 0)
        self.assertGreater(alloc_h.type_box.h, 0)
        self.assertGreaterEqual(alloc_h.asset_opacity, 0.70)
        self.assertEqual(alloc_h.type_box.y, 80)
        self.assertEqual(alloc_h.type_box.h, 420)
        self.assertEqual(alloc_h.asset_box.y, 540)
        self.assertEqual(alloc_h.asset_box.h, 460)

        # Scene 1: split_vertical
        alloc_v = SpatialDirectorEngine.allocate(type_prop, asset_prop, scene_idx=1, total_scenes=5, is_music=False)
        self.assertEqual(alloc_v.archetype, "split_vertical")
        self.assertGreater(alloc_v.asset_box.w, 0)
        self.assertGreater(alloc_v.asset_box.h, 0)
        self.assertGreaterEqual(alloc_v.asset_opacity, 0.70)
        self.assertEqual(alloc_v.type_box.x, 520)
        self.assertEqual(alloc_v.type_box.w, 500)
        self.assertEqual(alloc_v.asset_box.x, 60)
        self.assertEqual(alloc_v.asset_box.w, 440)

    def test_environment_engine_saliency_contrast(self):
        """Verify Environment never outputs flat solid hex and respects saliency contrast."""
        env = EnvironmentEngine.propose("تست اتمسفر", self.palette, saliency_contrast=0.18, scene_idx=0, world="editorial")
        self.assertIn(env.style, EnvironmentEngine.STYLES)
        self.assertGreaterEqual(env.contrast, 0.08)
        self.assertLessEqual(env.contrast, 0.35)
        self.assertTrue(len(env.gradient_stops) >= 3)

    def test_asset_engine_procedural_visual_grammar(self):
        """Verify Asset Engine generates procedural geometries and operators."""
        # Tech topic
        tech_asset = AssetEngine.propose("برنامه‌نویسی سیستم و سرور", "tech_career", self.palette, scene_idx=0)
        self.assertIn(tech_asset.geometry, ["connected_graph", "particle_field", "vector_ribbon"])
        self.assertIn(tech_asset.operator, ["draw", "cluster", "align", "attract", "expand"])
        self.assertIsNotNone(tech_asset.entity_id)

        # Poetry topic
        poetry_asset = AssetEngine.propose("آواز و ترانه شبانه", "poetry_music", self.palette, scene_idx=0)
        self.assertIn(poetry_asset.geometry, ["vector_ribbon", "concentric_contours", "particle_field"])
        self.assertIn(poetry_asset.operator, ["flow", "accelerate", "radiate", "attract"])

    def test_type_engine_mode_switching_and_spring_physics(self):
        """Verify Type Engine selects appropriate font size and spring config."""
        # Short punchy beat
        short_type = KineticTypeEngine.propose("رشد سریع", [{"word": "رشد"}, {"word": "سریع"}], scene_idx=0)
        self.assertEqual(short_type.mode, "impact_single")
        self.assertGreaterEqual(short_type.font_size, 96)
        self.assertEqual(short_type.spring_config["damping"], 10)
        self.assertEqual(short_type.spring_config["stiffness"], 180)

        # Multi-word narrative
        long_type = KineticTypeEngine.propose("توسعه پایدار زیرساخت‌های فناوری اطلاعات", [], scene_idx=1)
        self.assertEqual(long_type.mode, "accumulating_stack")
        self.assertLessEqual(long_type.font_size, 84)

    def test_full_pipeline_negotiated_compilation(self):
        """End-to-end verification of the 4-Engine Negotiated Compiler."""
        words = [
            {"word": "ثبات", "start": 0.0, "end": 0.6},
            {"word": "در", "start": 0.65, "end": 0.8},
            {"word": "تلاش", "start": 0.85, "end": 1.4},
            {"word": "موجب", "start": 1.7, "end": 2.1},
            {"word": "دیده‌شدن", "start": 2.15, "end": 2.8},
            {"word": "می‌شود", "start": 2.85, "end": 3.3}
        ]
        scenes = build_kinetic_phrase_scenes(words, total_frames=120, fps=30, creative_dna=self.dna)
        self.assertGreater(len(scenes), 0)

        for s in scenes:
            d = s.to_dict()
            self.assertIn("spatial", d)
            self.assertIn("environment", d)
            self.assertIn("asset", d)
            self.assertIn("type", d)
            self.assertIn("hero_layer", d)
            self.assertIn("typeBox", d)
            self.assertIn("assetBox", d)

        # Test CreativeSpec serialization roundtrip with 4-engine fields
        spec = fallback_procedural_creative_spec(words, fps=30, total_frames=120, total_sec=4.0)
        spec_dict = spec.to_dict()
        self.assertIn("timeline", spec_dict)
        first_scene = spec_dict["timeline"]["scenes"][0]
        self.assertIn("spatial", first_scene)
        self.assertIn("environment", first_scene)
        self.assertIn("type", first_scene)


if __name__ == "__main__":
    unittest.main()
