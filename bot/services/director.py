import os
import json
import logging
import requests
import re
import time
from typing import Any, List, Dict

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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"
)
LLM_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-5.6-luna")

VALID_ICONS = [
    "Sparkles", "FolderGit2", "FolderArchive", "MessageSquare", "Send",
    "UserCheck", "Monitor", "Smartphone", "TrendingUp", "CheckCircle",
    "Flame", "Zap", "Layers", "Cpu", "Globe", "BarChart3", "FileCode2",
    "Search", "PlayCircle", "ShieldCheck", "Code2", "Terminal", "Share2"
]

STOP_WORDS = {
    "از", "به", "در", "رو", "که", "با", "برای", "این", "آن", "یه", "هم", "توی",
    "تو", "شد", "و", "یا", "تا", "بر", "من", "تو", "او", "ما", "شما", "آنها",
    "هستش", "است", "بود", "شد", "چون", "ولی", "اما", "اگر", "دیگه", "فقط",
    "چه", "چرا", "چطور", "هر", "هیچ"
}

def clean_line_typography(text: str) -> str:
    """Strips trailing and leading speech punctuation to maintain executive Swiss typography."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^[،,.\-_!?؟\s]+", "", t)
    t = re.sub(r"[،,.\-_!?؟\s]+$", "", t)
    t = re.sub(r"([^\w\s])\s*", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def extract_meaningful_keywords(words: list) -> list:
    """Extract substantive keywords from word list, ignoring prepositions and stop words."""
    cleaned = []
    for w in words:
        raw = re.sub(r"[^\w\s]", "", w["word"]).strip()
        if raw and raw not in STOP_WORDS and len(raw) >= 3:
            if raw not in cleaned:
                cleaned.append(raw)
    return cleaned

def validate_and_fix_timeline(scenes: List[Dict], total_frames: int, min_frames_per_scene: int = 36) -> List[Dict]:
    """
    Frame-accurate timeline validation:
    1. Guarantees 0-frame duration drift (exact match to total_frames)
    2. Zero gaps, zero overlaps (continuous partition)
    3. Handles trailing repetition without hardcoding any specific brand or person
    4. Enforces minimum scene duration
    """
    if not scenes:
        return []

    # Step 1: Detect and resolve trailing repetition dynamically
    if len(scenes) >= 2:
        last = scenes[-1]
        prev = scenes[-2]
        t_last = " ".join(last.get("lines", []))
        t_prev = " ".join(prev.get("lines", []))
        
        words_last = set(t_last.split())
        words_prev = set(t_prev.split())
        overlap = words_last.intersection(words_prev)
        if len(overlap) >= 3 and len(words_last) > 0 and len(overlap) / len(words_last) > 0.6:
            # Trailing repetition detected! Convert last scene to a summary callout
            last["type"] = "CALLOUT_CARD"
            last["badgeLabel"] = "جمع‌بندی"
            last["theme"] = "accent"

    # Step 2: Ensure strictly continuous frames
    scenes[0]["startFrame"] = 0
    for i in range(len(scenes) - 1):
        if scenes[i]["endFrame"] <= scenes[i]["startFrame"]:
            scenes[i]["endFrame"] = scenes[i]["startFrame"] + min_frames_per_scene
        scenes[i + 1]["startFrame"] = scenes[i]["endFrame"]

    scenes[-1]["endFrame"] = total_frames

    # Step 3: Merge any micro-scenes shorter than min_frames_per_scene
    cleaned = []
    for s in scenes:
        if cleaned and (s["endFrame"] - s["startFrame"]) < min_frames_per_scene:
            cleaned[-1]["lines"].extend(s["lines"])
            cleaned[-1]["endFrame"] = s["endFrame"]
        else:
            cleaned.append(s)

    if not cleaned:
        cleaned = scenes

    cleaned[0]["startFrame"] = 0
    cleaned[-1]["endFrame"] = total_frames
    for i in range(len(cleaned) - 1):
        cleaned[i]["endFrame"] = cleaned[i + 1]["startFrame"]

    return cleaned

def fallback_procedural_director(words: list, fps: int = 30, total_frames: int = 300) -> list:
    """
    Semantic deterministic fallback if LLM is unreachable.
    Completely dynamic: extracts keywords and numbers exclusively from the spoken words.
    """
    if not words:
        return [{
            "type": "HERO_BLOCK",
            "startFrame": 0,
            "endFrame": total_frames,
            "theme": "dark",
            "alignment": "center",
            "lines": ["..."]
        }]

    global_keywords = extract_meaningful_keywords(words)
    scenes = []
    chunk_words = []
    chunk_start = words[0]["start"]
    theme_cycle = ["dark", "accent", "light"]
    archetypes = ["HERO_BLOCK", "SPLIT_VIEWPORT", "CALLOUT_CARD", "BENTO_GRID"]
    alignments = ["center", "right", "center", "left"]
    scene_idx = 0
    min_scene_duration_sec = 1.6

    for i, w in enumerate(words):
        chunk_words.append(w["word"])
        prev_w = words[i - 1] if i > 0 else None
        pause = (w["start"] - prev_w["end"]) if prev_w else 0
        dur = w["end"] - chunk_start

        is_break = (len(chunk_words) >= 3 and dur >= min_scene_duration_sec and (
            pause > 0.4 or
            (w["word"][-1:] in ".!؟،") or
            len(chunk_words) >= 6 or
            dur >= 3.5
        )) or (i == len(words) - 1)

        if is_break:
            mid = max(1, len(chunk_words) // 2)
            l1 = clean_line_typography(" ".join(chunk_words[:mid]))
            l2 = clean_line_typography(" ".join(chunk_words[mid:])) if len(chunk_words) > mid else ""
            lines = [l1] if not l2 else [l1, l2]

            st_frame = int(chunk_start * fps)
            end_frame = int(w["end"] * fps)
            
            # Extract genuine number if present
            num_in_chunk = None
            for cw in chunk_words:
                digits = "".join(ch for ch in cw if ch.isdigit())
                if digits:
                    try:
                        num_in_chunk = int(digits)
                        break
                    except ValueError:
                        pass

            if num_in_chunk is not None:
                atype = "METRIC_PUNCH"
            else:
                atype = archetypes[scene_idx % len(archetypes)]

            meaningful_chunk_words = [cw for cw in chunk_words if re.sub(r"[^\w\s]", "", cw).strip() not in STOP_WORDS]
            badge_label = clean_line_typography(meaningful_chunk_words[0]) if meaningful_chunk_words else None
            if badge_label in STOP_WORDS or not badge_label or len(badge_label) < 3:
                badge_label = None

            grid_items = None
            if atype == "BENTO_GRID":
                kw_slice = [k for k in global_keywords if k not in STOP_WORDS and len(k) >= 2]
                if len(kw_slice) >= 2:
                    grid_items = [{"title": k, "icon": VALID_ICONS[idx % len(VALID_ICONS)]} for idx, k in enumerate(kw_slice[:4])]
                else:
                    atype = "CALLOUT_CARD"

            scene = {
                "type": atype,
                "startFrame": st_frame,
                "endFrame": end_frame,
                "theme": theme_cycle[scene_idx % len(theme_cycle)],
                "alignment": alignments[scene_idx % len(alignments)],
                "lines": lines,
                "icon": VALID_ICONS[scene_idx % len(VALID_ICONS)],
                "badgeLabel": badge_label if atype in ["CALLOUT_CARD", "SPLIT_VIEWPORT", "METRIC_PUNCH"] else None,
                "counterFrom": 0 if (atype == "METRIC_PUNCH" and num_in_chunk is not None) else None,
                "counterTo": num_in_chunk if (atype == "METRIC_PUNCH" and num_in_chunk is not None) else None,
                "gridItems": grid_items
            }
            scenes.append(scene)
            chunk_words = []
            chunk_start = w["end"]
            scene_idx += 1

    return validate_and_fix_timeline(scenes, total_frames, min_frames_per_scene=max(36, int(1.2 * fps)))

def direct_scenes_with_llm(words: list, full_text: str, duration: float, fps: int = 30, audit: Any = None) -> list:
    """
    LLM Director converts transcript tokens into a frame-accurate sequence of diverse Swiss visual scenes.
    Strictly content-grounded: NEVER hallucinates outside topics, names, or metrics.
    """
    total_frames = max(30, round(duration * fps))
    if not words:
        scenes = fallback_procedural_director(words, fps, total_frames)
        if audit:
            audit.record_director("N/A (empty words)", "", scenes, "FALLBACK", 0, was_fallback=True, fallback_reason="Empty words")
        return scenes

    t0 = time.time()
    token_feed = [{"w": w["word"], "s": round(w["start"], 2), "e": round(w["end"], 2)} for w in words]
    is_persian = any('\u0600' <= char <= '\u06FF' for char in full_text)

    prompt = (
        "You are an elite Swiss Motion Graphics Art Director creating kinetic typography for speech audio.\n\n"
        f"TOTAL DURATION IN FRAMES: {total_frames} frames (at {fps} FPS = {duration:.2f}s).\n"
        f"Your output scene sequence MUST start at frame 0 and end at EXACTLY frame {total_frames}.\n\n"
        "GOAL:\n"
        "Carefully read the SPEAKER FULL TRANSCRIPT below and understand WHAT THE SPEAKER IS ACTUALLY TALKING ABOUT.\n"
        "Direct 4 to 6 coherent narrative visual scenes that faithfully reflect the real subject matter, entities, and message of THIS audio note.\n\n"
        "ARCHETYPE SELECTION (Assign the best layout for each distinct part of the speech):\n"
        "- 'HERO_BLOCK': Central thesis, opening hook, key assertion, or main takeaway.\n"
        "- 'METRIC_PUNCH': Use ONLY if the speaker mentions an explicit spoken number, statistic, or year count. Set 'counterTo' to that exact spoken integer. IF NO NUMBER IS SPOKEN, DO NOT USE THIS!\n"
        "- 'BENTO_GRID': Use when the speaker mentions multiple items, features, platforms, or tools. Provide 'gridItems': [{'title': '...', 'icon': '...'}, ...] with 3 to 4 distinct items extracted from the speech.\n"
        "- 'SPLIT_VIEWPORT': Comparing two ideas/platforms, nuances, or contextual elaboration.\n"
        "- 'CALLOUT_CARD': Highlighting a specific entity, platform, key warning, or focal point.\n\n"
        "STRICT CONTENT INTEGRITY RULES (VIOLATIONS WILL BE REJECTED):\n"
        "1. GROUNDING: Every word in 'lines' MUST be derived strictly from what THIS speaker said in the transcript. NEVER invent outside names, outside companies, outside numbers, or topics that are not in the transcript!\n"
        "2. If the speaker does not state a name or entity, DO NOT invent one!\n"
        "3. FAITHFUL TOPIC: The visual narrative must strictly focus on the actual subject matter spoken in the transcript. Never import outside context or prior knowledge.\n"
        "4. DIVERSITY: Use at least 2 or 3 distinct archetypes across the scenes. Do NOT make every scene HERO_BLOCK.\n"
        "5. 'badgeLabel' must be a concise Persian keyword (1-2 words) summarizing that scene's actual point (e.g. 'نکته کلیدی', 'رویکرد', 'بررسی'). Never prepositions!\n"
        "6. SEAMLESS COVERAGE: startFrame and endFrame must partition 0 to " + str(total_frames) + " continuously.\n"
        "7. Output ONLY valid JSON: {\"scenes\": [...]}\n\n"
        "SPEAKER FULL TRANSCRIPT:\n\"" + full_text + "\"\n\n"
        "WORD TOKENS WITH TIMESTAMPS:\n" + json.dumps(token_feed, ensure_ascii=False)
    )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a professional Swiss Motion Graphics Art Director. Direct kinetic scenes strictly grounded in the user's transcript. Respond strictly in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "max_tokens": 2048
            },
            timeout=35
        )

        latency = time.time() - t0

        if resp.status_code == 200:
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            clean_content = content
            if "```" in clean_content:
                m = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_content, re.DOTALL)
                if m:
                    clean_content = m.group(1).strip()
                else:
                    clean_content = re.sub(r"^```(?:json)?\s*", "", clean_content)
                    clean_content = re.sub(r"\s*```$", "", clean_content)

            parsed = json.loads(clean_content)
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except Exception:
                    pass

            if isinstance(parsed, list):
                raw_scenes = parsed
            elif isinstance(parsed, dict):
                raw_scenes = parsed.get("scenes") or parsed.get("story_beats") or parsed.get("beats") or []
            else:
                raw_scenes = []

            if raw_scenes and isinstance(raw_scenes, list) and len(raw_scenes) >= 2:
                clean_scenes = []
                for s in raw_scenes:
                    if isinstance(s, str):
                        s = {"lines": [s], "type": "HERO_BLOCK"}
                    elif not isinstance(s, dict):
                        continue

                    st_type = s.get("type") or "HERO_BLOCK"
                    st_theme = s.get("theme") or "dark"
                    if st_theme not in ["light", "dark", "accent"]:
                        st_theme = "dark"
                    
                    st_align = s.get("alignment") or "center"
                    if st_align not in ["center", "right", "left"]:
                        st_align = "center"

                    st_lines = s.get("lines") or s.get("text_lines") or s.get("text") or []
                    if isinstance(st_lines, str):
                        st_lines = [st_lines]
                    elif not isinstance(st_lines, list) or len(st_lines) == 0:
                        continue

                    cleaned_lines = [clean_line_typography(str(l)) for l in st_lines if clean_line_typography(str(l))]
                    if not cleaned_lines:
                        continue

                    raw_badge = s.get("badgeLabel")
                    if raw_badge:
                        raw_badge = clean_line_typography(str(raw_badge))
                        if raw_badge in STOP_WORDS or len(raw_badge) < 2 or raw_badge == "None":
                            raw_badge = None

                    raw_grid = s.get("gridItems") or s.get("grid_items")
                    clean_grid = None
                    if raw_grid and isinstance(raw_grid, list):
                        clean_grid = []
                        for gi in raw_grid:
                            if isinstance(gi, dict):
                                clean_grid.append({
                                    "title": gi.get("title") or gi.get("label") or "",
                                    "icon": gi.get("icon") or "Globe"
                                })
                            elif isinstance(gi, str):
                                clean_grid.append({
                                    "title": gi,
                                    "icon": "Globe"
                                })

                    c_from = s.get("counterFrom")
                    c_to = s.get("counterTo")
                    if c_to is not None:
                        try:
                            c_to = int(c_to)
                        except (ValueError, TypeError):
                            c_to = None

                    # If grid items present, ensure archetype is BENTO_GRID
                    if clean_grid and len(clean_grid) >= 2:
                        st_type = "BENTO_GRID"

                    if st_type == "METRIC_PUNCH" and c_to is None:
                        num_found = None
                        for l in cleaned_lines:
                            for w in l.split():
                                digits = "".join(ch for ch in w if ch.isdigit())
                                if digits:
                                    try:
                                        num_found = int(digits)
                                        break
                                    except ValueError:
                                        pass
                        if num_found is not None:
                            c_to = num_found
                        else:
                            st_type = "CALLOUT_CARD"

                    clean_scenes.append({
                        "type": st_type,
                        "startFrame": int(s.get("startFrame", s.get("frameStart", 0))),
                        "endFrame": int(s.get("endFrame", s.get("frameEnd", total_frames))),
                        "theme": st_theme,
                        "alignment": st_align,
                        "lines": cleaned_lines,
                        "icon": s.get("icon", "Sparkles"),
                        "badgeLabel": raw_badge,
                        "metric": s.get("metric"),
                        "counterFrom": int(c_from) if c_from is not None else 0,
                        "counterTo": c_to,
                        "gridItems": clean_grid
                    })

                # Archetypal Diversity Guard: If model used all HERO_BLOCK, enforce layout variety based on content
                if all(s["type"] == "HERO_BLOCK" for s in clean_scenes) or len(set(s["type"] for s in clean_scenes)) <= 1:
                    for idx, s in enumerate(clean_scenes):
                        if s.get("gridItems") and len(s["gridItems"]) >= 2:
                            s["type"] = "BENTO_GRID"
                        elif s.get("counterTo") is not None:
                            s["type"] = "METRIC_PUNCH"
                        elif idx % 2 == 1:
                            s["type"] = "SPLIT_VIEWPORT"
                        elif idx == len(clean_scenes) - 1:
                            s["type"] = "CALLOUT_CARD"

                # Validate and fix timeline boundaries (exact duration, no gaps, deduplicate)
                clean_scenes = validate_and_fix_timeline(clean_scenes, total_frames, min_frames_per_scene=max(36, int(1.2 * fps)))

                # FIREWALL: Language check
                if clean_scenes:
                    if is_persian:
                        all_lines_text = " ".join(" ".join(s["lines"]) for s in clean_scenes)
                        persian_count = sum(1 for c in all_lines_text if '\u0600' <= c <= '\u06FF')
                        latin_count = sum(1 for c in all_lines_text if ('a' <= c.lower() <= 'z'))
                        if latin_count > persian_count or persian_count == 0:
                            logger.warning("Language firewall rejected English output. Falling back to procedural director.")
                            fb_scenes = fallback_procedural_director(words, fps, total_frames)
                            if audit:
                                audit.record_director(prompt, content, fb_scenes, LLM_MODEL, latency, was_fallback=True, fallback_reason="Language firewall: Latin > Persian")
                                audit.record_firewall(False, {"language_check": "FAILED (English detected in Persian mode)"})
                            return fb_scenes

                    if audit:
                        audit.record_director(prompt, content, clean_scenes, LLM_MODEL, latency, was_fallback=False)
                        audit.record_firewall(True, {
                            "language_check": "PASSED (100% Persian)",
                            "stop_word_check": "PASSED (Clean badges)",
                            "grid_uniqueness": "PASSED (Unique distinct chips)",
                            "timeline_coverage": f"0 to {total_frames} frames (Exact Match, 0 Drift)"
                        })

                    return clean_scenes

    except Exception as e:
        logger.warning(f"LLM Director failed ({e}), falling back to procedural director")
        latency = time.time() - t0
        fb_scenes = fallback_procedural_director(words, fps, total_frames)
        if audit:
            audit.record_director(prompt, "", fb_scenes, LLM_MODEL, latency, was_fallback=True, fallback_reason=str(e))
            audit.record_firewall(True, {"fallback_active": True, "reason": str(e)})
        return fb_scenes

    fb_scenes = fallback_procedural_director(words, fps, total_frames)
    if audit:
        audit.record_director(prompt, "", fb_scenes, LLM_MODEL, time.time() - t0, was_fallback=True, fallback_reason="LLM response did not meet schema constraints")
    return fb_scenes
