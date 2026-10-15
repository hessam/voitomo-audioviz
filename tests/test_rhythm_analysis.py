"""Hit timing/labels, meter and riff-cycle estimates on synthetic audio (numpy only)."""
import unittest

import numpy as np

from bot.services import rhythm_analysis as ra

SR = ra.ANALYSIS_SR


def burst(kind: str, rng) -> np.ndarray:
    n = int(0.5 * SR)
    i = np.arange(n) / SR
    env = np.exp(-i / 0.04)
    if kind == "kick":
        return np.sin(2 * np.pi * 60 * i) * np.exp(-i / 0.08)
    noise = rng.standard_normal(n)
    spec = np.fft.rfft(noise)
    f = np.fft.rfftfreq(n, 1 / SR)
    keep = (f > 1000) & (f < 4000) if kind == "snare" else f > 7000
    spec[~keep] = 0
    return np.fft.irfft(spec, n) * env * 6


def render(hits, duration, kind="kick", seed=1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.zeros(int(SR * duration))
    for t in hits:
        w = burst(kind, rng)
        s = int(t * SR)
        x[s:s + len(w)] += w[:len(x) - s]
    return x


class OnsetTests(unittest.TestCase):
    def test_each_hit_found_once_and_never_early(self):
        hits = [1.0 + 0.5 * k + 0.013 * (k % 3) for k in range(8)]
        for kind in ("kick", "snare", "cymbal"):
            a = ra.detect_onsets(render(hits, 6, kind))
            self.assertEqual(len(a.times), len(hits), kind)
            for found, true in zip(a.times, hits):
                self.assertGreaterEqual(found, true - 0.0005, f"{kind} anticipated the hit")
                self.assertLess(found - true, 0.03, f"{kind} too late")

    def test_hits_are_labelled_by_where_their_energy_is(self):
        hits = [1.0, 1.5, 2.0, 2.5]
        for kind in ("kick", "snare", "cymbal"):
            self.assertEqual(set(ra.detect_onsets(render(hits, 4, kind)).kinds), {kind})

    def test_event_frame_is_never_before_and_at_most_one_frame_after_the_hit(self):
        a = ra.detect_onsets(render([1.0, 2.0], 3, "kick"))
        frames = [e.frame for e in a.events(30, 90)]
        for frame, hit_frame in zip(frames, [30, 60]):
            self.assertIn(frame, (hit_frame, hit_frame + 1))

    def test_silence_has_no_onsets(self):
        self.assertEqual(ra.detect_onsets(np.zeros(SR * 2)).times, [])


def beat_grid(count, spacing=0.4):
    return [round(1.0 + k * spacing, 4) for k in range(count)]


class MeterTests(unittest.TestCase):
    def accent_onsets(self, beats, period, strong=1.0, weak=0.3):
        times = list(beats)
        strengths = [strong if k % period == 0 else weak for k in range(len(beats))]
        return times, strengths

    def test_seven_beat_bar_is_found(self):
        beats = beat_grid(84)
        t, s = self.accent_onsets(beats, 7)
        m = ra.estimate_meter(beats, t, s)
        self.assertIsNotNone(m)
        self.assertEqual(m.beats_per_bar, 7)
        self.assertEqual(m.downbeat_phase, 0)

    def test_four_beat_bar_is_preferred_over_eight(self):
        beats = beat_grid(96)
        t, s = self.accent_onsets(beats, 4)
        self.assertEqual(ra.estimate_meter(beats, t, s).beats_per_bar, 4)

    def test_phase_follows_the_accent(self):
        beats = beat_grid(84)
        t = list(beats)
        s = [1.0 if (k - 3) % 5 == 0 else 0.3 for k in range(len(beats))]
        m = ra.estimate_meter(beats, t, s)
        self.assertEqual((m.beats_per_bar, m.downbeat_phase), (5, 3))

    def test_flat_accents_give_no_meter(self):
        beats = beat_grid(80)
        self.assertIsNone(ra.estimate_meter(beats, beats, [0.5] * 80))

    def test_too_little_evidence_gives_no_meter(self):
        beats = beat_grid(6)
        self.assertIsNone(ra.estimate_meter(beats, beats, [1.0] * 6))


class RiffCycleTests(unittest.TestCase):
    def pattern_onsets(self, length, repeats, beat_spacing=0.4, seed=3):
        rng = np.random.default_rng(seed)
        pattern = (rng.random(length) < 0.45).astype(float) * rng.uniform(0.5, 1.0, length)
        pattern[0] = 1.0
        beats = beat_grid(int(length * repeats / 4) + 8, beat_spacing)
        step = beat_spacing / 4
        times, strengths = [], []
        for n in range(length * repeats):
            if pattern[n % length] > 0:
                times.append(1.0 + n * step)
                strengths.append(float(pattern[n % length]))
        return beats, times, strengths

    def test_23_step_cycle_is_found(self):
        beats, t, s = self.pattern_onsets(23, 8)
        riff = ra.estimate_riff_cycle(beats, t, s, fps=30)
        self.assertIsNotNone(riff)
        self.assertEqual(riff.lengthSteps, 23)
        self.assertAlmostEqual(riff.stepFrames, 0.4 * 30 / 4, places=3)

    def test_16_step_cycle_is_found(self):
        beats, t, s = self.pattern_onsets(16, 10)
        self.assertEqual(ra.estimate_riff_cycle(beats, t, s, fps=30).lengthSteps, 16)

    def test_random_hits_give_no_cycle(self):
        rng = np.random.default_rng(9)
        beats = beat_grid(120)
        t = sorted(rng.uniform(1.0, 1.0 + 119 * 0.4, 200))
        self.assertIsNone(ra.estimate_riff_cycle(beats, t, list(rng.uniform(0.3, 1, 200)), fps=30))


if __name__ == "__main__":
    unittest.main()
