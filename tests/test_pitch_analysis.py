"""YIN note detection on synthetic bass lines (numpy only)."""
import math
import unittest

import numpy as np

from bot.services import pitch_analysis as pa

SR = pa.PITCH_SR
FPS = 30


def note(hz, seconds, harmonics=(1.0, 0.5, 0.3)):
    t = np.arange(int(seconds * SR)) / SR
    wave = sum(a * np.sin(2 * np.pi * hz * (k + 1) * t) for k, a in enumerate(harmonics))
    env = np.minimum(1, t / 0.01) * np.exp(-t / 1.5)
    return wave * env * 0.4


def line(notes, gap=0.12):
    out, starts, cursor = [np.zeros(int(0.3 * SR))], [], 0.3
    for hz, seconds in notes:
        starts.append(cursor)
        out.append(note(hz, seconds))
        out.append(np.zeros(int(gap * SR)))
        cursor += seconds + gap
    return np.concatenate(out), starts


class NoteTests(unittest.TestCase):
    def test_bass_line_gives_the_right_notes_at_the_right_times(self):
        plan = [(55.0, 0.5), (73.42, 0.5), (98.0, 0.5), (41.2, 0.6)]
        x, starts = line(plan)
        found = pa.detect_notes(x, FPS, int(len(x) / SR * FPS) + 5)
        self.assertEqual(len(found), len(plan), [n.pitchHz for n in found])
        for n, (hz, _), start in zip(found, plan, starts):
            self.assertLess(abs(n.pitchHz - hz) / hz, 0.02, f"{n.pitchHz} vs {hz}")
            first_frame = math.ceil(start * FPS)
            self.assertGreaterEqual(n.startFrame, first_frame, "note shown before it sounds")
            self.assertLessEqual(n.startFrame - first_frame, 5)
            self.assertGreater(n.confidence, 0.7)

    def test_a_strong_second_harmonic_does_not_cause_an_octave_error(self):
        x = np.concatenate([np.zeros(int(0.3 * SR)), note(110.0, 0.6, harmonics=(0.6, 1.0, 0.4)), np.zeros(int(0.2 * SR))])
        found = pa.detect_notes(x, FPS, 60)
        self.assertEqual(len(found), 1)
        self.assertLess(abs(found[0].pitchHz - 110.0) / 110.0, 0.02)

    def test_silence_and_noise_give_no_notes(self):
        self.assertEqual(pa.detect_notes(np.zeros(SR * 2), FPS, 60), [])
        noise = np.random.default_rng(4).standard_normal(SR * 2) * 0.3
        self.assertLessEqual(len(pa.detect_notes(noise, FPS, 60)), 1)

    def test_note_names(self):
        self.assertEqual(pa.note_name(440.0), "A4")
        self.assertEqual(pa.note_name(55.0), "A1")
        self.assertEqual(pa.note_name(41.2), "E1")


if __name__ == "__main__":
    unittest.main()
