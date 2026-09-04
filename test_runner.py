import sys
sys.path.insert(0, '/root/workspace')

from bot.services.director import direct_scenes_with_llm, fallback_procedural_director
from bot.services.audit import WorkflowAudit

test_text = "مهسا حافظی هستم، یه پونزه، شونزه سالی هستش که دارم توی حوزه دیجیتال مارکتینگ و مارکتینگ کار می‌کنم."

words = [
    {"word": "مهسا", "start": 0.0, "end": 0.5},
    {"word": "حافظی", "start": 0.5, "end": 1.1},
    {"word": "هستم،", "start": 1.1, "end": 1.6},
    {"word": "یه", "start": 1.7, "end": 1.9},
    {"word": "پونزه،", "start": 1.9, "end": 2.4},
    {"word": "شونزه", "start": 2.4, "end": 2.9},
    {"word": "سالی", "start": 2.9, "end": 3.3},
    {"word": "هستش", "start": 3.3, "end": 3.8},
    {"word": "که", "start": 3.8, "end": 4.0},
    {"word": "دارم", "start": 4.0, "end": 4.3},
    {"word": "توی", "start": 4.3, "end": 4.5},
    {"word": "حوزه", "start": 4.5, "end": 4.8},
    {"word": "دیجیتال", "start": 4.8, "end": 5.3},
    {"word": "مارکتینگ", "start": 5.3, "end": 6.0},
    {"word": "و", "start": 6.0, "end": 6.2},
    {"word": "مارکتینگ", "start": 6.2, "end": 6.8},
    {"word": "کار", "start": 6.8, "end": 7.2},
    {"word": "می‌کنم.", "start": 7.2, "end": 7.8}
]

audit = WorkflowAudit()
audit.record_asr("test.ogg", 7.8, test_text, len(words))
scenes = direct_scenes_with_llm(words, test_text, 7.8, 30, audit)

print("Total scenes:", len(scenes))
for i, s in enumerate(scenes):
    dur = (s["endFrame"] - s["startFrame"]) / 30
    print(f"Scene {i+1}: {s['type']} | frames {s['startFrame']}->{s['endFrame']} ({dur:.2f}s) | Lines: {s['lines']} | Badge: {s.get('badgeLabel')}")

log_files = audit.save()
print("Audit saved:", log_files)

# Also test fallback_procedural_director directly:
fb_scenes = fallback_procedural_director(words, 30, int(7.8 * 30))
print("\n--- Fallback Procedural Director Test ---")
print("Total fallback scenes:", len(fb_scenes))
for i, s in enumerate(fb_scenes):
    dur = (s["endFrame"] - s["startFrame"]) / 30
    print(f"Fallback Scene {i+1}: {s['type']} | frames {s['startFrame']}->{s['endFrame']} ({dur:.2f}s) | Lines: {s['lines']} | Badge: {s.get('badgeLabel')}")
