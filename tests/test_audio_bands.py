"""Band levels must keep highs, never anticipate a sound, and never invent rhythm."""
import math
import os
import shutil
import struct
import tempfile
import unittest
import wave
from unittest import mock

import numpy as np

from bot.services import audio_features as af
from bot.services.audio_adapter import AudioIntelligenceAdapter

SR = 44100
FPS = 30


def write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        data = np.clip(np.asarray(samples), -1, 1) * 32000
        w.writeframes(data.astype("<i2").tobytes())


def tone(hz, seconds, start=0.0, total=None, amp=0.6):
    total = total or seconds + start
    t = np.arange(int(SR * total)) / SR
    x = np.sin(2 * np.pi * hz * t) * amp
    x[t < start] = 0
    x[t >= start + seconds] = 0
    return x


def kicks(hits, total):
    x = np.zeros(int(SR * total))
    for h in hits:
        n = int(0.4 * SR)
        i = np.arange(n) / SR
        s = int(h * SR)
        x[s:s + n] += np.sin(2 * np.pi * 60 * i) * np.exp(-i / 0.08) * 0.8
    return x


class BandTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def levels(self, samples, band, frames=None):
        path = os.path.join(self.dir, "a.wav")
        write_wav(path, samples)
        frames = frames or int(len(samples) / SR * FPS)
        return np.array(af.decode_band_levels(path, af.BAND_FILTERS[band], FPS, frames))

    def test_highs_survive_at_every_frequency(self):
        for hz, band in [(100, "bass"), (1000, "mids"), (3000, "mids"), (6000, "treble"), (10000, "treble")]:
            lv = self.levels(tone(hz, 2.0), band)
            self.assertGreater(lv[10:].mean(), 0.1, f"{hz} Hz vanished from {band}")

    def test_bands_are_selective(self):
        # The band filters are gentle (2-pole), so a neighbour leaks a little; the right band
        # must still read clearly louder than the wrong one.
        in_mids = self.levels(tone(6000, 2.0), "mids")[10:].mean()
        in_treble = self.levels(tone(6000, 2.0), "treble")[10:].mean()
        self.assertGreater(in_treble, 2 * in_mids)
        self.assertLess(self.levels(tone(100, 2.0), "treble")[10:].mean(), 0.02)

    def test_level_never_anticipates_a_sound(self):
        lv = self.levels(kicks([1.0], 2.0), "bass")
        self.assertLess(lv[30], 1e-6)  # frame 30 = [29/30 s, 1.0 s): the kick has not happened yet
        self.assertGreater(lv[31], 0.1)  # the first frame after the hit shows it

    def test_no_smoothing_a_step_reaches_full_level_in_one_frame(self):
        lv = self.levels(tone(100, 2.0, start=1.0, total=3.0), "bass")
        steady = lv[60:80].mean()
        self.assertLess(lv[30], 1e-6)
        self.assertGreater(lv[31], 0.9 * steady)

    def test_quiet_noise_is_not_amplified_to_full_scale(self):
        rng = np.random.default_rng(0)
        path = os.path.join(self.dir, "q.wav")
        write_wav(path, rng.standard_normal(SR * 2) * 3e-4)  # about -70 dBFS
        out = af.normalize_levels(af.decode_band_levels(path, af.BAND_FILTERS["mids"], FPS, 60))
        self.assertLess(max(out), 0.15)

    def test_frame_zero_is_silent_and_length_is_exact(self):
        lv = self.levels(tone(100, 1.0), "bass", frames=45)
        self.assertEqual(len(lv), 45)
        self.assertEqual(lv[0], 0.0)


class RhythmHonestyTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = os.path.join(self.dir, "kicks.wav")
        self.hits = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        write_wav(self.path, kicks(self.hits, 4.5))
        self.frames = int(4.5 * FPS)

    def extract(self, dna=None):
        unknown = {"status": "unknown", "bpm": None, "beats_sec": [], "beat_frames": []}
        with mock.patch.object(AudioIntelligenceAdapter, "extract_rhythm_and_beats", return_value=unknown):
            return af.extract_multiband_features_ffmpeg(self.path, fps=FPS, total_frames=self.frames, dna_data=dna)

    def test_no_analyzer_means_unknown_not_120_bpm(self):
        f = self.extract()
        self.assertEqual(f.rhythmSource, "unknown")
        self.assertIsNone(f.bpm)
        self.assertEqual(f.beatFrames, [])
        self.assertEqual(f.downbeatFrames, [])
        self.assertEqual(f.musicalKey, "")

    def test_broker_beats_are_used_and_bar_starts_are_marked_assumed(self):
        beats = [0.5 + 0.5 * k for k in range(8)]
        f = self.extract({"bpm": 120.0, "beat_times": beats, "musical_key": "E Minor"})
        self.assertEqual(f.rhythmSource, "broker")
        self.assertEqual(f.bpm, 120.0)
        self.assertEqual(f.beatFrames, [round(b * FPS) for b in beats])
        self.assertTrue(f.downbeatsAssumed)
        self.assertIsNone(f.meterBeats)

    def test_kick_hits_become_classified_events_not_before_the_sound(self):
        f = self.extract()
        kick_frames = [o.frame for o in f.onsets if o.kind == "kick"]
        self.assertEqual(len(kick_frames), len(self.hits))
        for frame, hit in zip(kick_frames, self.hits):
            self.assertGreaterEqual(frame, math.ceil(hit * FPS))
            self.assertLessEqual(frame, math.ceil(hit * FPS) + 1)
        self.assertEqual(f.transients, [o.frame for o in f.onsets if o.strength >= af.MIN_ONSET_STRENGTH_FOR_TRANSIENT])

    def test_curves_match_the_frame_count(self):
        f = self.extract()
        for name in ("bass", "mids", "treble", "vocalEnergy", "drumsEnergy", "macroEnergy"):
            self.assertEqual(len(getattr(f, name)), self.frames, name)


if __name__ == "__main__":
    unittest.main()
