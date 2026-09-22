import unittest
import os
import json
import tempfile
import asyncio
import wave
import struct
import math

from contracts.manifest import RenderManifest
from bot.services.audio_features import AudioFeatureExtractor


class TestEndToEndManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        sample_rate = 44100
        duration = 2.0
        num_samples = int(sample_rate * duration)

        with wave.open(cls.audio_path, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            raw_data = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                s = math.sin(2 * math.pi * 120 * t) * 0.8
                sample_val = int(s * 10000)
                raw_data.extend(struct.pack("<h", sample_val))

            wav_file.writeframes(raw_data)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.audio_path):
            os.remove(cls.audio_path)

    def test_all_four_presets_compile(self):
        presets = ["sphere", "iris", "neural", "monolith"]
        words = [
            {"word": "صدای", "start": 0.1, "end": 0.4},
            {"word": "سکوت", "start": 0.4, "end": 0.8},
            {"word": "در", "start": 0.8, "end": 1.0},
            {"word": "کهکشان", "start": 1.0, "end": 1.6},
        ]

        for p in presets:
            manifest = asyncio.run(
                AudioFeatureExtractor.extract_and_compile_manifest(
                    job_id=f"test-{p}",
                    audio_path=self.audio_path,
                    preset_id=p,  # type: ignore
                    words=words,
                )
            )
            self.assertEqual(manifest.preset.id, p)
            self.assertIn(manifest.video.width, (1080, 1920))
            self.assertEqual(manifest.video.height, 1080)
            self.assertEqual(manifest.video.frameCount, 60)
            self.assertEqual(len(manifest.audio.features.bass), 60)
            self.assertEqual(len(manifest.audio.features.mids), 60)
            self.assertEqual(len(manifest.audio.features.treble), 60)
            self.assertTrue(len(manifest.lyrics.lines) > 0)

            # Check JSON serialization
            serialized = json.dumps(manifest.to_dict(), ensure_ascii=False)
            self.assertIn(f"test-{p}", serialized)

    def test_show_lyrics_false_yields_zero_lyrics(self):
        words = [
            {"word": "صدای", "start": 0.1, "end": 0.4},
            {"word": "سکوت", "start": 0.4, "end": 0.8},
        ]
        manifest = asyncio.run(
            AudioFeatureExtractor.extract_and_compile_manifest(
                job_id="test-no-lyrics",
                audio_path=self.audio_path,
                preset_id="sphere",
                words=words,
                show_lyrics=False,
            )
        )
        self.assertEqual(len(manifest.lyrics.lines), 0)


if __name__ == "__main__":
    unittest.main()
