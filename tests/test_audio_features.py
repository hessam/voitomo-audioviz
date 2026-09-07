import unittest
import os
import json
import tempfile
import asyncio
import subprocess
import wave
import struct
import math

from contracts.manifest import (
    RenderManifest,
    AudioMultibandFeatures,
    LyricLine,
)
from bot.services.audio_features import (
    compute_sha256,
    get_audio_duration_seconds,
    extract_multiband_features_ffmpeg,
    AudioFeatureExtractor,
)


class TestAudioFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a synthetic 3-second 44.1kHz stereo audio file with test frequencies (100Hz kick, 1kHz mid, 8kHz treble)
        cls.test_audio_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        sample_rate = 44100
        duration = 3.0
        num_samples = int(sample_rate * duration)

        with wave.open(cls.test_audio_path, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            raw_data = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                # 100Hz bass pulse every second
                bass = math.sin(2 * math.pi * 100 * t) * (1.0 if (t % 1.0) < 0.2 else 0.1)
                # 1000Hz mid continuous
                mids = math.sin(2 * math.pi * 1000 * t) * 0.4
                # 8000Hz treble bursts
                treble = math.sin(2 * math.pi * 8000 * t) * (0.5 if (t % 0.5) < 0.1 else 0.0)

                sample_val = int((bass + mids + treble) * 10000)
                sample_val = max(-32767, min(32767, sample_val))
                raw_data.extend(struct.pack("<h", sample_val))

            wav_file.writeframes(raw_data)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_audio_path):
            os.remove(cls.test_audio_path)

    def test_sha256_computation(self):
        sha = compute_sha256(self.test_audio_path)
        self.assertIsInstance(sha, str)
        self.assertEqual(len(sha), 64)

    def test_duration_detection(self):
        dur = get_audio_duration_seconds(self.test_audio_path)
        self.assertAlmostEqual(dur, 3.0, delta=0.2)

    def test_multiband_features_extraction(self):
        features = extract_multiband_features_ffmpeg(self.test_audio_path, fps=30, total_frames=90)
        self.assertIsInstance(features, AudioMultibandFeatures)
        self.assertEqual(len(features.bass), 90)
        self.assertEqual(len(features.mids), 90)
        self.assertEqual(len(features.treble), 90)

        # Check normalization bounds [0.0, 1.0]
        for b in features.bass:
            self.assertTrue(0.0 <= b <= 1.0)
        for m in features.mids:
            self.assertTrue(0.0 <= m <= 1.0)
        for tr in features.treble:
            self.assertTrue(0.0 <= tr <= 1.0)

    def test_manifest_compilation(self):
        words = [
            {"word": "سلام", "start": 0.2, "end": 0.5},
            {"word": "به", "start": 0.5, "end": 0.7},
            {"word": "جهان", "start": 0.7, "end": 1.1},
            {"word": "زیبای", "start": 1.1, "end": 1.5},
            {"word": "موسیقی", "start": 1.5, "end": 2.0},
        ]

        async def run_compile():
            return await AudioFeatureExtractor.extract_and_compile_manifest(
                job_id="test-job-001",
                audio_path=self.test_audio_path,
                preset_id="sphere",
                words=words,
                seed=1234,
            )

        manifest = asyncio.run(run_compile())
        self.assertIsInstance(manifest, RenderManifest)
        self.assertEqual(manifest.jobId, "test-job-001")
        self.assertEqual(manifest.preset.id, "sphere")
        self.assertEqual(manifest.video.frameCount, 90)
        self.assertTrue(len(manifest.lyrics.lines) > 0)
        self.assertEqual(manifest.environment["concurrency"], 2)

        # Test dictionary serialization
        manifest_dict = manifest.to_dict()
        manifest_json = json.dumps(manifest_dict, ensure_ascii=False)
        self.assertIn("test-job-001", manifest_json)
        self.assertIn("sphere", manifest_json)


if __name__ == "__main__":
    unittest.main()
