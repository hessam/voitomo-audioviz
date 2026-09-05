import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List

LOGS_DIR = "/root/workspace/logs"
os.makedirs(LOGS_DIR, exist_ok=True)

class WorkflowAudit:
    """
    Complete explainability and audit trail for the Voice-to-Motion Agent.
    Records decisions, reasoning, prompts, timestamps, and schema validations.
    """
    def __init__(self, run_id: str = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.created_at = datetime.now().isoformat()
        self.stages: Dict[str, Any] = {
            "asr_transcription": {},
            "transcript_alignment": {},
            "art_director_decisions": {},
            "firewall_validations": {},
            "render_execution": {}
        }
        # Reload existing audit state if available
        if self.run_id:
            json_path = os.path.join(LOGS_DIR, f"audit-{self.run_id}.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        self.created_at = saved.get("created_at", self.created_at)
                        existing_stages = saved.get("stages", {})
                        for k, v in existing_stages.items():
                            if v:
                                self.stages[k] = v
                except Exception:
                    pass

    def record_asr(self, audio_path: str, duration: float, raw_text: str, words_count: int, model: str = "large-v3-turbo"):
        self.stages["asr_transcription"] = {
            "timestamp": datetime.now().isoformat(),
            "audio_path": audio_path,
            "duration_seconds": round(duration, 2),
            "model": model,
            "recognized_words_count": words_count,
            "raw_text": raw_text
        }

    def record_normalizer(self, input_words: int, corrected_count: int, diff_samples: List[Dict]):
        if "asr_transcription" in self.stages:
            self.stages["asr_transcription"]["normalization"] = {
                "total_tokens": input_words,
                "corrected_tokens_count": corrected_count,
                "sample_corrections": diff_samples[:10]
            }

    def record_user_edit(self, original_text: str, edited_text: str, realigned_tokens: int):
        self.stages["transcript_alignment"] = {
            "timestamp": datetime.now().isoformat(),
            "user_edited": True,
            "original_text": original_text,
            "edited_text": edited_text,
            "realigned_tokens_count": realigned_tokens
        }

    def record_director(
        self,
        prompt: str,
        raw_response: str,
        scenes: List[Dict],
        model: str,
        latency_seconds: float,
        was_fallback: bool = False,
        fallback_reason: str = None
    ):
        scene_explanations = []
        for idx, s in enumerate(scenes):
            st_type = s.get("type", "HERO_BLOCK")
            lines = s.get("lines", [])
            badge = s.get("badgeLabel")
            if badge == "None" or not badge:
                badge = None
            grid_items = s.get("gridItems")
            counter_to = s.get("counterTo")
            start_f = s.get("startFrame", 0)
            end_f = s.get("endFrame", 0)

            grid_titles = []
            if grid_items:
                for g in grid_items:
                    if isinstance(g, dict):
                        grid_titles.append(g.get("title") or g.get("label") or "")
                    elif isinstance(g, str):
                        grid_titles.append(g)

            # Build narrative explanation for why this scene was constructed
            reasoning = ""
            if st_type in ("HERO_BLOCK", "hero_focus"):
                reasoning = f"Hero typographic anchor: Highlights key phrase '{' / '.join(lines)}' with in-place chromatic decode."
            elif st_type == "specimen_ladder":
                reasoning = f"Repeated emphasis ladder: Core concept '{' / '.join(lines)}' escalated across ascending font weights (300 to 900)."
            elif st_type == "paragraph_stack":
                reasoning = f"Architectural editorial block: Clean multi-line statement '{' / '.join(lines)}' revealed via phrase-chunked geometric mask."
            elif st_type == "caption_panel":
                reasoning = f"Factual metadata panel: Static small-caps architectural card anchoring supporting details."
            elif st_type == "METRIC_PUNCH":
                reasoning = f"Quantitative milestone detected: Spoken number '{counter_to}' animated as live counter with badge '{badge or 'آمار کلیدی'}'."
            elif st_type == "BENTO_GRID":
                items_str = ", ".join(grid_titles)
                reasoning = f"Capability / service matrix detected: Displays distinct items [{items_str}] with ripple animation."
            elif st_type == "SPLIT_VIEWPORT":
                reasoning = f"Asymmetric continuity beat: Text pinned off-center with technical blueprint callout for '{badge or 'محور فعالیت'}'."
            elif st_type == "CALLOUT_CARD":
                reasoning = f"Entity / team highlight: Floating badge card for '{badge or 'برند / تیم'}' with overshoot bounce."
            else:
                reasoning = f"Editorial layout '{st_type}' highlighting: '{' / '.join(lines)}'."

            scene_explanations.append({
                "scene_index": idx + 1,
                "time_window": f"{round(start_f / 30, 2)}s - {round(end_f / 30, 2)}s (frames {start_f} -> {end_f})",
                "archetype": st_type,
                "theme": s.get("theme"),
                "alignment": s.get("alignment", "center"),
                "on_screen_lines": lines,
                "badge_label": badge,
                "counter_to": counter_to,
                "grid_items": grid_titles if grid_titles else None,
                "decision_rationale": reasoning
            })

        self.stages["art_director_decisions"] = {
            "timestamp": datetime.now().isoformat(),
            "engine": "LLM_DIRECTOR" if not was_fallback else "PROCEDURAL_SEMANTIC_FALLBACK",
            "model_used": model,
            "latency_seconds": round(latency_seconds, 2),
            "fallback_triggered": was_fallback,
            "fallback_reason": fallback_reason,
            "total_scenes_generated": len(scenes),
            "scenes_breakdown": scene_explanations
        }

    def record_firewall(self, passed: bool, checks: Dict[str, Any]):
        self.stages["firewall_validations"] = {
            "timestamp": datetime.now().isoformat(),
            "overall_passed": passed,
            "checks": checks
        }

    def record_render(self, video_path: str, duration_frames: int, fps: int, render_time: float, file_size_bytes: int):
        self.stages["render_execution"] = {
            "timestamp": datetime.now().isoformat(),
            "video_path": video_path,
            "duration_frames": duration_frames,
            "fps": fps,
            "duration_seconds": round(duration_frames / fps, 2),
            "render_time_seconds": round(render_time, 2),
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 2)
        }

    def save(self) -> Dict[str, str]:
        """Saves both JSON raw log and human-readable Markdown breakdown."""
        json_path = os.path.join(LOGS_DIR, f"audit-{self.run_id}.json")
        md_path = os.path.join(LOGS_DIR, f"audit-{self.run_id}.md")

        data = {
            "audit_id": self.run_id,
            "created_at": self.created_at,
            "stages": self.stages
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Generate Human-Readable Markdown Audit Report
        asr = self.stages.get("asr_transcription", {})
        dir_dec = self.stages.get("art_director_decisions", {})
        rnd = self.stages.get("render_execution", {})
        fw = self.stages.get("firewall_validations", {})

        md_content = f"""# 🎬 گزارش کامل تصمیم‌گیری و گردش‌کار ربات موشن‌گرافی
**شناسه لاگ (Audit ID):** `{self.run_id}`  
**زمان ایجاد:** `{self.created_at}`  

---

## ۱. مرحله پردازش صوت و گفتار (ASR & Speech Intelligence)
- **مدل شناسایی گفتار:** `{asr.get('model', 'large-v3-turbo')}`
- **مدت فایل صوتی:** `{asr.get('duration_seconds', 0)} ثانیه`
- **تعداد کلمات استخراج‌شده:** `{asr.get('recognized_words_count', 0)} کلمه`
- **متن نهایی پیاده‌شده:**
> "{asr.get('raw_text', '')}"

---

## ۲. مرحله کارگردانی هنری و تصمیم‌گیری هوش مصنوعی (Art Director Decisions)
- **موتور تصمیم‌گیر:** `{dir_dec.get('engine', 'LLM_DIRECTOR')}`
- **مدل هوش مصنوعی:** `{dir_dec.get('model_used', 'N/A')}` (زمان پاسخ: `{dir_dec.get('latency_seconds', 0)} ثانیه`)
- **استفاده از فال‌بک:** `{'بله (' + str(dir_dec.get('fallback_reason')) + ')' if dir_dec.get('fallback_triggered') else 'خیر (طراحی مستقیم توسط هوش مصنوعی)'}`
- **تعداد کل صحنه‌ها:** `{dir_dec.get('total_scenes_generated', 0)} پرده روایی`

### 🔍 چرایی و تحلیل تصمیمات به تفکیک صحنه‌ها:
"""
        for sc in dir_dec.get("scenes_breakdown", []):
            md_content += f"""
#### پرده {sc.get('scene_index')}: {sc.get('archetype')} ({sc.get('time_window')})
- **متن روی صفحه:** `{', '.join(sc.get('on_screen_lines', []))}`
- **تم و چیدمان:** تم `{sc.get('theme')}` | تراز `{sc.get('alignment')}`
- **برچسب (Badge):** `{sc.get('badge_label') or 'ندارد'}`
- **عناصر گرید/شمارنده:** `{sc.get('counter_to') or sc.get('grid_items') or 'ندارد'}`
- **علت انتخاب این لی‌اوت (Rationale):**  
  *{sc.get('decision_rationale')}*
"""

        if fw:
            md_content += f"""
---

## ۳. بررسی فایروال محتوا و صحت‌سنجی (Quality & Content Firewall)
- **نتیجه کلی فایروال:** `{'✅ تایید شده (Passed)' if fw.get('overall_passed') else '❌ رد شده (Failed)'}`
"""
            for check_name, check_res in fw.get("checks", {}).items():
                md_content += f"- **{check_name}:** `{check_res}`\n"

        if rnd:
            md_content += f"""
---

## ۴. مرحله رندر و فشرده‌سازی ویدیو (Remotion Engine Execution)
- **موتور رندر:** Remotion Engine (Chromium Headless)
- **مدت زمان ویدیو:** `{rnd.get('duration_seconds')} ثانیه` (`{rnd.get('duration_frames')} فریم` @ `{rnd.get('fps')} FPS`)
- **زمان رندر روی سرور:** `{rnd.get('render_time_seconds')} ثانیه`
- **حجم فایل نهایی:** `{rnd.get('file_size_mb')} مگابایت`
- **مسیر فایل خروجی:** `{rnd.get('video_path')}`
"""

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return {"json": json_path, "markdown": md_path}
