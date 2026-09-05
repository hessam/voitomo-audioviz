import unittest
import math
from bot.services.normalizer import hex_to_rgb
from bot.services.director import fallback_procedural_creative_spec

def rgb_to_cielab(r: int, g: int, b: int):
    """Converts RGB to CIELAB (D65 Illuminant)."""
    # RGB to linear
    def to_lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_l, g_l, b_l = to_lin(r), to_lin(g), to_lin(b)

    # Linear RGB to XYZ
    x = (r_l * 0.4124 + g_l * 0.3576 + b_l * 0.1805) / 0.95047
    y = (r_l * 0.2126 + g_l * 0.7152 + b_l * 0.0722) / 1.00000
    z = (r_l * 0.0193 + g_l * 0.1192 + b_l * 0.9505) / 1.08883

    def f(t):
        return t ** (1/3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    L = max(0.0, (116.0 * fy) - 16.0)
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return L, a, b

def delta_e_cielab(hex1: str, hex2: str) -> float:
    """Euclidean distance in CIELAB space (CIE76). Delta E > 2.3 is visually perceptible."""
    L1, a1, b1 = rgb_to_cielab(*hex_to_rgb(hex1))
    L2, a2, b2 = rgb_to_cielab(*hex_to_rgb(hex2))
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)

class TestDiversityMetrics(unittest.TestCase):

    def test_pairwise_delta_e_and_diversity(self):
        # 5 distinct audio text inputs
        inputs = [
            [{"word": "همایون", "start": 0.0, "end": 1.0}, {"word": "شجریان", "start": 1.0, "end": 2.0}],
            [{"word": "طراحی", "start": 0.0, "end": 0.8}, {"word": "تایپوگرافی", "start": 0.8, "end": 1.8}, {"word": "سوئیسی", "start": 1.8, "end": 2.6}],
            [{"word": "هوش", "start": 0.0, "end": 0.5}, {"word": "مصنوعی", "start": 0.5, "end": 1.2}, {"word": "مولد", "start": 1.2, "end": 2.0}],
            [{"word": "شب", "start": 0.0, "end": 0.5}, {"word": "سکوت", "start": 0.5, "end": 1.2}, {"word": "کویر", "start": 1.2, "end": 2.0}],
            [{"word": "فناوری", "start": 0.0, "end": 0.8}, {"word": "بلاکچین", "start": 0.8, "end": 1.8}, {"word": "غیرمتمرکز", "start": 1.8, "end": 2.8}],
        ]

        specs = [fallback_procedural_creative_spec(words, fps=30, total_frames=90, total_sec=3.0) for words in inputs]

        # Verify concepts are all unique
        concepts = [s.design_system.concept for s in specs]
        self.assertEqual(len(set(concepts)), len(inputs), "Each input must have a unique concept hook!")

        # Verify accents have high Delta E variance across runs
        accents = [s.design_system.palette.accent for s in specs]
        unique_accents = set(accents)
        self.assertGreaterEqual(len(unique_accents), 3, "Accent palette must vary across different texts!")

        # Calculate collapse rate (pairs with Delta E < 5.0)
        collapse_count = 0
        total_pairs = 0
        for i in range(len(accents)):
            for j in range(i + 1, len(accents)):
                total_pairs += 1
                de = delta_e_cielab(accents[i], accents[j])
                if de < 5.0:
                    collapse_count += 1

        collapse_rate = collapse_count / total_pairs
        self.assertLess(collapse_rate, 0.40, f"Collapse rate {collapse_rate:.2%} exceeded threshold!")

if __name__ == "__main__":
    unittest.main()
