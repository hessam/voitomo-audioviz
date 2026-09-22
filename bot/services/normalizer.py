import re
from typing import List, Dict, Tuple

# Standard Persian orthographic and common ASR phoneme corrections
# Strictly generic: NO hardcoded persona names, locations, numbers, or specific sentences.
GENERIC_PHONETIC_CORRECTIONS = {
    r"\bدیژیتال\b": "دیجیتال",
    r"\bلینکتین\b": "لینکدین",
    r"\bحوضه(?=\s+(?:دیجیتال|مارکتینگ|کاری|علمی|فناوری|وب|تخصصی))\b": "حوزه",
}

UNICODE_NORMALIZATIONS = [
    (re.compile(r"[\u064A\u0649]"), "ی"),  # Arabic Yeh -> Persian Yeh
    (re.compile(r"[\u0643]"), "ک"),        # Arabic Kaf -> Persian Kaf
    (re.compile(r"\u200c+"), "\u200c"),    # Normalize consecutive ZWNJ
]

def clean_persian_token(token: str) -> str:
    """Applies standard Persian character normalizations to a single token."""
    t = token
    for pat, rep in UNICODE_NORMALIZATIONS:
        t = pat.sub(rep, t)
    for pat, rep in GENERIC_PHONETIC_CORRECTIONS.items():
        t = re.sub(pat, rep, t)
    return t

def normalize_persian_asr(raw_text: str, words: List[Dict]) -> Tuple[str, List[Dict], List[Dict]]:
    """
    Normalizes raw Whisper Persian ASR text into:
    1. clean_text: Grammatically and orthographically normalized full transcript
    2. clean_words: Word tokens with normalized characters, keeping timestamps intact
    3. diff_log: List of corrections made for audit reporting
    """
    clean_text = raw_text
    diff_log = []

    # 1. Unicode character standardizations
    for pat, rep in UNICODE_NORMALIZATIONS:
        clean_text = pat.sub(rep, clean_text)

    # 2. Generic phonetic corrections
    for pattern, replacement in GENERIC_PHONETIC_CORRECTIONS.items():
        if re.search(pattern, clean_text):
            for match in re.finditer(pattern, clean_text):
                diff_log.append({"original": match.group(0), "corrected": replacement})
            clean_text = re.sub(pattern, replacement, clean_text)

    # Clean redundant spaces
    clean_text = re.sub(r"[ \t]+", " ", clean_text).strip()

    # Apply token-level corrections preserving timestamps and metadata
    clean_words = []
    for w in words:
        orig_w = w["word"]
        new_w = clean_persian_token(orig_w).strip()
        if new_w:
            clean_words.append({
                **w,
                "word": new_w,
                "start": w["start"],
                "end": w["end"]
            })

    return clean_text, clean_words, diff_log

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Parse #RRGGBB or #RGB to integer (R, G, B) tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return 0, 0, 0

def relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate WCAG 2.1 relative luminance."""
    def channel_lum(c: int) -> float:
        c_norm = c / 255.0
        return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)

def contrast_ratio(hex1: str, hex2: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors."""
    lum1 = relative_luminance(*hex_to_rgb(hex1))
    lum2 = relative_luminance(*hex_to_rgb(hex2))
    l_light = max(lum1, lum2)
    l_dark = min(lum1, lum2)
    return (l_light + 0.05) / (l_dark + 0.05)

def enforce_wcag_contrast(bg_hex: str, fg_hex: str, min_ratio: float = 4.5) -> Tuple[str, str]:
    """
    Enforces WCAG AA compliance (ratio >= 4.5:1).
    If contrast is insufficient, automatically shifts foreground towards pure white or dark slate.
    """
    cr = contrast_ratio(bg_hex, fg_hex)
    if cr >= min_ratio:
        return bg_hex, fg_hex
    
    bg_lum = relative_luminance(*hex_to_rgb(bg_hex))
    # If background is dark, push foreground to high-luminance white/off-white
    if bg_lum < 0.4:
        return bg_hex, "#F9FAFB"
    # If background is light, push foreground to dark charcoal
    return bg_hex, "#0F172A"

BANNED_SLOP_TERMS = [
    r"\bdelve\b", r"\btestament\b", r"\brealm\b", r"\bgame[- ]changer\b",
    r"\brevolutionize\b", r"\bunlock\b", r"\bleverage\b", r"\blandscape\b",
    r"\bembark\b", r"\bjourney\b", r"\bcrucial\b", r"\bpivotal\b",
    r"\bparamount\b", r"\bfostering\b", r"\btapestry\b", r"\bmosaic\b",
    r"\bharness\b", r"\bsynergize\b"
]

def sanitize_anti_slop(text: str) -> str:
    """Removes robotic AI filler terms and passive corporate jargon."""
    cleaned = text
    for term in BANNED_SLOP_TERMS:
        cleaned = re.sub(term, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned
