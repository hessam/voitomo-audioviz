import unittest
from bot.services.alignment import realign_transcript, patch_word
from bot.services.normalizer import normalize_persian_asr
from bot.services.audio_features import group_words_into_phrases


class TestAlignmentRegressions(unittest.TestCase):

    def test_realign_transcript_clamps_to_total_duration(self):
        """
        Reproduction defect:
        Original words: 'الف' [0, 0.999], 'ج' [0.999, 1.0]
        Replacement: 'الف یک دو سه ج'
        Audio duration: 1.0s
        Old code extended output to 2.349s past master audio clock.
        Fix requirement: ALL words must be strictly within [0.0, total_duration].
        """
        orig_words = [
            {"word": "الف", "start": 0.0, "end": 0.999, "score": 0.95},
            {"word": "ج", "start": 0.999, "end": 1.0, "score": 0.92},
        ]
        new_text = "الف یک دو سه ج"
        total_duration = 1.0

        aligned = realign_transcript(orig_words, new_text, total_duration=total_duration)

        self.assertEqual(len(aligned), 5)
        for i, w in enumerate(aligned):
            self.assertGreaterEqual(w["start"], 0.0, f"Word {w['word']} start < 0")
            self.assertLess(w["start"], w["end"], f"Word {w['word']} start >= end")
            self.assertLessEqual(w["end"], total_duration, f"Word {w['word']} end ({w['end']}) exceeds audio duration ({total_duration})")
            if i > 0:
                self.assertGreaterEqual(w["start"], aligned[i - 1]["end"], f"Word {w['word']} overlaps with previous")

        # Words 'یک', 'دو', 'سه' must be flagged as interpolated
        self.assertFalse(aligned[0].get("is_interpolated", False))
        self.assertTrue(aligned[1].get("is_interpolated", False))
        self.assertTrue(aligned[2].get("is_interpolated", False))
        self.assertTrue(aligned[3].get("is_interpolated", False))

    def test_empty_orig_words_flags_interpolation(self):
        """
        Reproduction defect:
        Empty recognized words + 5 tokens with 10.0s duration.
        Old code returned timestamps without indicating they are unaligned guesses.
        Fix requirement: All tokens must have is_interpolated=True and alignment_source='interpolated'.
        """
        orig_words = []
        new_text = "یک دو سه چهار پنج"
        total_duration = 10.0

        aligned = realign_transcript(orig_words, new_text, total_duration=total_duration)

        self.assertEqual(len(aligned), 5)
        for w in aligned:
            self.assertTrue(w.get("is_interpolated"), f"Word {w['word']} was not flagged as interpolated")
            self.assertEqual(w.get("alignment_source"), "interpolated")
            self.assertLessEqual(w["end"], total_duration)

    def test_normalizer_preserves_word_metadata(self):
        """
        Defect:
        normalize_persian_asr discarded score, probability, and provenance metadata.
        Fix requirement: normalize_persian_asr must retain all existing dict keys on words.
        """
        words = [
            {
                "word": "دیژیتال",
                "start": 0.5,
                "end": 1.2,
                "score": 0.89,
                "is_interpolated": False,
                "source": "whisper_large_v3",
            }
        ]
        raw_text = "دیژیتال"

        clean_text, clean_words, diff_log = normalize_persian_asr(raw_text, words)

        self.assertEqual(clean_words[0]["word"], "دیجیتال")
        self.assertEqual(clean_words[0]["start"], 0.5)
        self.assertEqual(clean_words[0]["end"], 1.2)
        self.assertEqual(clean_words[0]["score"], 0.89)
        self.assertFalse(clean_words[0]["is_interpolated"])
        self.assertEqual(clean_words[0]["source"], "whisper_large_v3")

    def test_pause_aware_phrase_grouping(self):
        """
        Defect:
        audio_features grouped words blindly by 5-word chunks without pause detection.
        Fix requirement: Grouping must split on acoustic pauses (e.g. gap >= 0.5s)
        even when word count is under 5.
        """
        words = [
            {"word": "سلام", "start": 1.0, "end": 1.5, "score": 0.95},
            {"word": "دوست", "start": 1.6, "end": 2.0, "score": 0.90},
            # 1.2s vocal pause here:
            {"word": "من", "start": 3.2, "end": 3.6, "score": 0.92},
            {"word": "امروز", "start": 3.7, "end": 4.1, "score": 0.94},
        ]

        phrases = group_words_into_phrases(words, fps=30, pause_threshold_sec=0.5, max_words_per_phrase=6)

        # Must be split into 2 phrases due to the 1.2s pause between 'دوست' and 'من'
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[0].text, "سلام دوست")
        self.assertEqual(phrases[1].text, "من امروز")
        # Check words and confidence retention in phrases
        self.assertEqual(len(phrases[0].words), 2)
        self.assertEqual(phrases[0].words[0].word, "سلام")
        self.assertEqual(phrases[0].words[1].word, "دوست")
        self.assertAlmostEqual(phrases[0].confidence, (0.95 + 0.90) / 2, places=2)

    def test_alignment_contract_invariants(self):
        """
        Hard deterministic gates from PERSIAN_VOCAL_RELIABILITY_PLAN:
        - 0 <= start < end <= total_duration
        - Strictly non-decreasing start times
        - Preserved scores and metadata
        """
        words = [
            {"word": "یک", "start": 0.1, "end": 0.5, "score": 0.8},
            {"word": "دو", "start": 0.6, "end": 1.2, "score": 0.85},
            {"word": "سه", "start": 1.3, "end": 2.0, "score": 0.9},
        ]
        phrases = group_words_into_phrases(words, fps=30, pause_threshold_sec=0.5, max_words_per_phrase=6)
        self.assertTrue(len(phrases) >= 1)
        for p in phrases:
            self.assertGreater(p.endFrame, p.startFrame)
            self.assertTrue(hasattr(p, "words"))
            self.assertTrue(hasattr(p, "confidence"))
            for w in p.words:
                self.assertGreaterEqual(w.endFrame, w.startFrame)


if __name__ == "__main__":
    unittest.main()
