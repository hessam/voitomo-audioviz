#!/usr/bin/env python3
"""
Verification Harness for Voitomo Engine v2 Refactor.
Verifies semantic and visual diversity across 3 distinct test audio profiles:
1. Commercial Advertisement (punchy, modern, Dana font, high-tempo)
2. Song / Lyric (melodic, cadence-driven, metaphor-rich)
3. Educational / Technical (structured, analytical, Vazirmatn font)
"""
import sys
import math
from contracts.creative_spec import generate_harmonic_palette
from bot.services.director import fallback_procedural_creative_spec
from bot.services.audio_adapter import AudioAnchor
from bot.services.normalizer import hex_to_rgb

def rgb_to_cielab(r: int, g: int, b: int):
    def to_lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_l, g_l, b_l = to_lin(r), to_lin(g), to_lin(b)
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
    L1, a1, b1 = rgb_to_cielab(*hex_to_rgb(hex1))
    L2, a2, b2 = rgb_to_cielab(*hex_to_rgb(hex2))
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)

def run_harness():
    print("=" * 60)
    print("🚀 VOITOMO ENGINE v2 DIVERSITY VERIFICATION HARNESS")
    print("=" * 60)

    profiles = {
        "1. Commercial Advertisement": {
            "text": "فقط در ۳ ثانیه هوش مصنوعی شما را تبدیل به یک برند جهانی می‌کند",
            "words": [
                {"word": "فقط", "start": 0.0, "end": 0.3},
                {"word": "در", "start": 0.3, "end": 0.5},
                {"word": "۳", "start": 0.5, "end": 0.8},
                {"word": "ثانیه", "start": 0.8, "end": 1.2},
                {"word": "هوش", "start": 1.7, "end": 2.0},  # 500ms cadential pause
                {"word": "مصنوعی", "start": 2.0, "end": 2.5},
                {"word": "شما", "start": 2.5, "end": 2.8},
                {"word": "را", "start": 2.8, "end": 3.0},
                {"word": "جهانی", "start": 3.1, "end": 3.6},
                {"word": "می‌کند", "start": 3.6, "end": 4.0}
            ],
            "anchors": [
                AudioAnchor(frame=36, timestamp=1.2, type="cadential_pause", energy_level=0.0, associated_word="ثانیه", duration_sec=0.5),
                AudioAnchor(frame=75, timestamp=2.5, type="emphasis", energy_level=0.92, associated_word="جهانی")
            ]
        },
        "2. Melodic Lyric / Song": {
            "text": "در شب تاریک سکوت کویر ماه به رقص می‌آید میان ستاره‌ها",
            "words": [
                {"word": "در", "start": 0.0, "end": 0.3},
                {"word": "شب", "start": 0.3, "end": 0.7},
                {"word": "تاریک", "start": 0.7, "end": 1.3},
                {"word": "سکوت", "start": 1.8, "end": 2.4},  # 500ms pause
                {"word": "کویر", "start": 2.4, "end": 3.0},
                {"word": "ماه", "start": 3.5, "end": 4.1},
                {"word": "به", "start": 4.1, "end": 4.3},
                {"word": "رقص", "start": 4.3, "end": 4.8},
                {"word": "می‌آید", "start": 4.8, "end": 5.4}
            ],
            "anchors": [
                AudioAnchor(frame=39, timestamp=1.3, type="cadential_pause", energy_level=0.0, associated_word="تاریک", duration_sec=0.5),
                AudioAnchor(frame=129, timestamp=4.3, type="emphasis", energy_level=0.88, associated_word="رقص")
            ]
        },
        "3. Educational / Technical": {
            "text": "سیستم‌های غیرمتمرکز ساختار تصمیم‌گیری را از کنترل انفرادی خارج می‌کنند",
            "words": [
                {"word": "سیستم‌های", "start": 0.0, "end": 0.6},
                {"word": "غیرمتمرکز", "start": 0.6, "end": 1.4},
                {"word": "ساختار", "start": 1.9, "end": 2.5},  # 500ms pause
                {"word": "تصمیم‌گیری", "start": 2.5, "end": 3.2},
                {"word": "را", "start": 3.2, "end": 3.4},
                {"word": "از", "start": 3.4, "end": 3.6},
                {"word": "کنترل", "start": 3.6, "end": 4.1},
                {"word": "انفرادی", "start": 4.1, "end": 4.8},
                {"word": "خارج", "start": 4.8, "end": 5.3},
                {"word": "می‌کنند", "start": 5.3, "end": 6.0}
            ],
            "anchors": [
                AudioAnchor(frame=42, timestamp=1.4, type="cadential_pause", energy_level=0.0, associated_word="غیرمتمرکز", duration_sec=0.5),
                AudioAnchor(frame=144, timestamp=4.8, type="emphasis", energy_level=0.79, associated_word="خارج")
            ]
        }
    }

    results = {}
    for name, data in profiles.items():
        spec = fallback_procedural_creative_spec(
            words=data["words"],
            fps=30,
            total_frames=len(data["words"]) * 18,
            total_sec=data["words"][-1]["end"],
            audio_anchors=data["anchors"]
        )
        dna = spec.creative_dna
        graph = spec.composition_graph

        print(f"\n📂 {name}")
        print(f"   ├─ Thesis: {dna.thesis}")
        print(f"   ├─ Emotional Tension: {dna.emotional_contradiction}")
        print(f"   ├─ Metaphor System: {dna.metaphor_system}")
        print(f"   ├─ Transformation Verbs: {dna.transformation_verbs}")
        print(f"   ├─ Font: {dna.font_family}")
        print(f"   ├─ Palette: BG={dna.palette.bg} | FG={dna.palette.fg} | Accent={dna.palette.accent}")
        print(f"   └─ Scenes: {len(graph.scenes)} (Final Scene Verb: '{graph.scenes[-1].layers[0].action_verb}')")

        # Check Navy Trap
        assert dna.palette.bg.upper() not in ("#090A0F", "#0A0B0E"), f"NAVY TRAP DETECTED in {name}!"
        results[name] = dna

    # Pairwise CIELAB Delta E Check
    print("\n" + "-" * 60)
    print("🎨 PAIRWISE CIELAB ΔE PALETTE DISTANCE (Threshold: ΔE >= 15.0)")
    print("-" * 60)
    names = list(results.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            bg1 = results[n1].palette.bg
            bg2 = results[n2].palette.bg
            de = delta_e_cielab(bg1, bg2)
            status = "✅ PASS" if de >= 15.0 else "⚠️ COLLAPSE"
            print(f"   {n1[:15]} vs {n2[:15]}: ΔE = {de:.2f} ({bg1} vs {bg2}) -> {status}")
            assert de >= 15.0, f"Pairwise Delta E {de:.2f} below threshold 15.0 between {n1} and {n2}!"

    print("\n" + "=" * 60)
    print("🎉 ALL 3 AUDIO PROFILES PASSED DIVERSITY HARNESS! ZERO COLLAPSE.")
    print("=" * 60)

if __name__ == "__main__":
    run_harness()
