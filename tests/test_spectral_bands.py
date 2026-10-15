"""Per-stem spectral bands: right band, causal, honest about missing stems."""
import os
import shutil
import tempfile
import unittest
import wave

import numpy as np

from bot.services import spectral_bands as sb

SR = sb.ANALYSIS_SR
FPS = 30


def tone(hz, seconds, start=0.0, total=3.0, amp=0.5):
    t = np.arange(int(total * SR)) / SR
    x = np.sin(2 * np.pi * hz * t) * amp
    x[(t < start) | (t >= start + seconds)] = 0
    return x


class BandTests(unittest.TestCase):
    def test_a_tone_lights_its_own_band(self):
        edges = sb.band_edges_hz()
        for hz in (60.0, 440.0, 3000.0):
            bands = np.array(sb.stem_bands(tone(hz, 3.0), FPS, 90))[40]
            expected = int(np.searchsorted(edges, hz, side="right") - 1)
            self.assertEqual(int(bands.argmax()), expected, hz)
            self.assertGreater(bands[expected], 0.9)
            self.assertLess(np.delete(bands, [expected, max(0, expected - 1), min(11, expected + 1)]).max(), 0.6)

    def test_no_band_moves_before_its_sound(self):
        bands = np.array(sb.stem_bands(tone(440.0, 1.5, start=1.0), FPS, 90))
        self.assertLess(bands[30].max(), 0.05, "frame 30 ends at 1.0 s: the tone has not started")
        self.assertGreater(bands[33].max(), 0.5)

    def test_silence_stays_zero(self):
        self.assertEqual(np.array(sb.stem_bands(np.zeros(SR * 2), FPS, 60)).max(), 0.0)

    def test_output_shape_and_range(self):
        bands = np.array(sb.stem_bands(tone(200.0, 2.0), FPS, 75))
        self.assertEqual(bands.shape, (75, sb.BAND_COUNT))
        self.assertTrue(((bands >= 0) & (bands <= 1)).all())


class StemNamingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = os.path.join(self.dir, "a.wav")
        with wave.open(self.path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((tone(220.0, 2.0, total=2.0) * 32000).astype("<i2").tobytes())

    def test_only_existing_stems_get_a_body(self):
        out = sb.body_bands({"bass": self.path, "drums": None, "vocals": None, "other": self.path}, self.path, FPS, 60)
        self.assertEqual(sorted(out), ["bass", "other"])

    def test_no_stems_falls_back_to_a_clearly_named_mix(self):
        out = sb.body_bands({"bass": None, "drums": None}, self.path, FPS, 60)
        self.assertEqual(list(out), ["mix"])


if __name__ == "__main__":
    unittest.main()
