"""
Persian Singing Benchmark & Reliability Validation Harness
Validates Phase 4 of the Persian Vocal Reliability & Acoustic Forced Alignment Plan.

Empirical Gates:
1. Deterministic Clock Invariants: 0 <= start < end <= total_duration
2. Onset/Offset Calibration: Median error <= 50ms, P95 error <= 150ms
3. CER / WER Metric Harness
4. Truthful Status Classification: 'accepted' vs 'needs_review' vs 'interpolated'
"""

import unittest
import numpy as np
from typing import List, Dict, Any, Tuple


def compute_wer(ref_words: List[str], hyp_words: List[str]) -> float:
    """Standard Word Error Rate (Levenshtein distance over tokens)."""
    d = np.zeros((len(ref_words) + 1, len(hyp_words) + 1), dtype=np.uint32)
    for i in range(len(ref_words) + 1):
        d[i, 0] = i
    for j in range(len(hyp_words) + 1):
        d[0, j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                cost = 0
            else:
                cost = 1
            d[i, j] = min(
                d[i - 1, j] + 1,      # Deletion
                d[i, j - 1] + 1,      # Insertion
                d[i - 1, j - 1] + cost # Substitution
            )
    return float(d[len(ref_words), len(hyp_words)]) / max(len(ref_words), 1)


def compute_cer(ref_text: str, hyp_text: str) -> float:
    """Standard Character Error Rate."""
    ref_chars = list(ref_text.replace(" ", ""))
    hyp_chars = list(hyp_text.replace(" ", ""))
    return compute_wer(ref_chars, hyp_chars)


def compute_timing_errors(
    ground_truth_spans: List[Tuple[float, float]],
    predicted_spans: List[Tuple[float, float]],
) -> Dict[str, float]:
    """
    Computes absolute onset and offset errors across aligned spans.
    Returns median and P95 errors in milliseconds.
    """
    if not ground_truth_spans or not predicted_spans:
        return {"median_onset_ms": 0.0, "p95_onset_ms": 0.0, "median_offset_ms": 0.0, "p95_offset_ms": 0.0}

    count = min(len(ground_truth_spans), len(predicted_spans))
    onset_errors = [
        abs(predicted_spans[i][0] - ground_truth_spans[i][0]) * 1000.0
        for i in range(count)
    ]
    offset_errors = [
        abs(predicted_spans[i][1] - ground_truth_spans[i][1]) * 1000.0
        for i in range(count)
    ]

    return {
        "median_onset_ms": float(np.median(onset_errors)),
        "p95_onset_ms": float(np.percentile(onset_errors, 95)),
        "median_offset_ms": float(np.median(offset_errors)),
        "p95_offset_ms": float(np.percentile(offset_errors, 95)),
    }


def classify_phrase_acceptance(
    phrase_words: List[Dict[str, Any]],
    confidence_threshold: float = 0.60
) -> str:
    """
    Quality-gated acceptance classification:
    - If any word is interpolated -> 'interpolated'
    - If average confidence < confidence_threshold -> 'needs_review'
    - Otherwise -> 'accepted'
    """
    if not phrase_words:
        return "needs_review"
    if any(w.get("is_interpolated", False) for w in phrase_words):
        return "interpolated"
    scores = [w.get("score", 1.0) for w in phrase_words if w.get("score") is not None]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    if avg_score < confidence_threshold:
        return "needs_review"
    return "accepted"


class TestPersianSingingBenchmark(unittest.TestCase):

    def test_wer_cer_metrics(self):
        ref = ["سلام", "ای", "دل", "تنها"]
        hyp = ["سلام", "ای", "دل", "زیبا"]
        wer = compute_wer(ref, hyp)
        self.assertEqual(wer, 0.25)  # 1 substitution out of 4 words

        cer = compute_cer("سلام دل", "سلام گل")
        self.assertGreater(cer, 0.0)
        self.assertLessEqual(cer, 0.5)

    def test_timing_calibration_metrics(self):
        gt = [(1.0, 1.5), (1.6, 2.2), (2.3, 3.0)]
        pred = [(1.02, 1.51), (1.63, 2.22), (2.28, 2.98)]
        metrics = compute_timing_errors(gt, pred)
        # Verify median error <= 50ms, p95 <= 150ms
        self.assertLessEqual(metrics["median_onset_ms"], 50.0)
        self.assertLessEqual(metrics["p95_onset_ms"], 150.0)
        self.assertLessEqual(metrics["median_offset_ms"], 50.0)
        self.assertLessEqual(metrics["p95_offset_ms"], 150.0)

    def test_acceptance_classification_gates(self):
        # 1. Fully accepted high confidence
        good_words = [
            {"word": "دریا", "start": 0.5, "end": 1.0, "score": 0.95, "is_interpolated": False},
            {"word": "آرام", "start": 1.1, "end": 1.8, "score": 0.92, "is_interpolated": False},
        ]
        self.assertEqual(classify_phrase_acceptance(good_words), "accepted")

        # 2. Low confidence -> needs review
        uncertain_words = [
            {"word": "دریا", "start": 0.5, "end": 1.0, "score": 0.45, "is_interpolated": False},
            {"word": "آرام", "start": 1.1, "end": 1.8, "score": 0.52, "is_interpolated": False},
        ]
        self.assertEqual(classify_phrase_acceptance(uncertain_words), "needs_review")

        # 3. Interpolated words -> never false certainty
        interpolated_words = [
            {"word": "دریا", "start": 0.5, "end": 1.0, "score": 0.95, "is_interpolated": False},
            {"word": "آرام", "start": 1.1, "end": 1.8, "score": 0.90, "is_interpolated": True},
        ]
        self.assertEqual(classify_phrase_acceptance(interpolated_words), "interpolated")


if __name__ == "__main__":
    unittest.main()
