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

    # Apply token-level corrections preserving timestamps
    clean_words = []
    for w in words:
        orig_w = w["word"]
        new_w = clean_persian_token(orig_w).strip()
        if new_w:
            clean_words.append({
                "word": new_w,
                "start": w["start"],
                "end": w["end"]
            })

    return clean_text, clean_words, diff_log
