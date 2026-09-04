import sys
sys.path.insert(0, '/root/workspace')

from bot.services.normalizer import normalize_persian_asr
from bot.services.director import direct_scenes_with_llm
from bot.services.audit import WorkflowAudit

raw_text = "محصه حافظی هستم، یه پونزه، شونزه سالی هستش که دم توی حوضه دیژیتال مارکتینگ و مارکتینگ قبیتاً کار میکنم. شیش سالی هست که ساکن ترکیم، اینجا هم همون کار خودم رو ادامه میدم. مضافه این که به کمک دوستان یه تیمی رو جمع کردیم به اسم محتوالی که کاری مارکتینگ رو توش انجام میدیم. در واقع کار سایت SEO Google Ads و یکی از جذب تنقسمتها برای من کار لینکتین مارکتینگ هستش."
audio_duration = 32.51
fps = 30
expected_total_frames = round(audio_duration * fps) # 975

words_list = raw_text.split()
words = []
step = audio_duration / len(words_list)
for i, w in enumerate(words_list):
    words.append({
        "word": w,
        "start": round(i * step, 2),
        "end": round((i + 1) * step, 2)
    })

clean_text, clean_words, diffs = normalize_persian_asr(raw_text, words)

print("=== NORMALIZER TEST ===")
print("Clean Text:", clean_text[:120], "...")
print(f"Total Corrections: {len(diffs)}")

audit = WorkflowAudit()
audit.record_asr("test_voice.ogg", audio_duration, raw_text, len(clean_words))
audit.record_normalizer(len(clean_words), len(diffs), diffs)

scenes = direct_scenes_with_llm(clean_words, clean_text, audio_duration, fps, audit)

print("\n=== TIMELINE & DIVERSITY TEST ===")
print(f"Expected Total Frames: {expected_total_frames} (at 30 FPS = {expected_total_frames / fps:.2f}s)")
print(f"Total Scenes: {len(scenes)}")

types_used = set()
for i, s in enumerate(scenes):
    types_used.add(s["type"])
    dur_s = (s["endFrame"] - s["startFrame"]) / fps
    print(f"Scene {i+1}: {s['type']} | {s['startFrame']} -> {s['endFrame']} ({dur_s:.2f}s) | Lines: {s['lines']} | Badge: {s.get('badgeLabel')}")

assert scenes[0]["startFrame"] == 0, "Scene 1 must start at frame 0"
assert scenes[-1]["endFrame"] == expected_total_frames, f"Last scene must end at {expected_total_frames}, got {scenes[-1]['endFrame']}"
print("\n✅ Exact Frame Timing PASSED: 0 ->", scenes[-1]["endFrame"])
print(f"✅ Diverse Archetypes Used: {types_used}")

log_files = audit.save()
print("Saved audit log:", log_files["markdown"])
