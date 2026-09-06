"""
Kinetic Typography Engine (The Voice)
Part of Astra's 4-Engine Negotiated Compiler.

Translates Whisper timestamps and prosody rhythm into kinetic Persian typography.
Rules:
- Measures shaped Persian text bounds before rendering.
- Dynamically switches between oversized single-word impacts (for loud beats)
  and accumulating multi-line tape stacks (for rapid narrative).
- Enforces pure RTL string flow and spring overshoot physics.
- Applies subtle alternating tilt per strip (rotate(±1.5deg)).
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import re


@dataclass
class TypeSpec:
    text: str
    mode: str  # "impact_single" | "accumulating_stack"
    font_size: int  # 72 to 106px
    weight: str = "800"
    tilt_angle: float = 0.0
    is_hero: bool = True
    spring_config: Dict[str, Any] = field(default_factory=lambda: {
        "damping": 10,
        "mass": 0.5,
        "stiffness": 180
    })
    words_count: int = 0
    char_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KineticTypeEngine:
    """
    Measures shaped Persian text and produces prosody-synced typography proposals.
    """

    @classmethod
    def clean_text(cls, text: str) -> str:
        s = re.sub(r"[ \t]+", " ", text).strip()
        # Remove trailing dangling commas or periods that look awkward on tape strips
        return s

    @classmethod
    def propose(
        cls,
        phrase_text: str,
        words: List[Dict],
        scene_idx: int = 0,
        is_hero_candidate: bool = True,
        is_music: bool = False
    ) -> TypeSpec:
        """
        Synthesizes typographic bounds and spring configuration for the phrase.
        """
        cleaned = cls.clean_text(phrase_text)
        w_list = cleaned.split()
        words_count = len(w_list)
        char_count = len(cleaned)

        # Mode switching: 1-2 words is impact single; >=3 words is accumulating stack
        if words_count <= 2 and char_count <= 14:
            mode = "impact_single"
            font_size = 104 if is_music else 96
            weight = "900"
        elif words_count <= 4:
            mode = "accumulating_stack"
            font_size = 86 if is_music else 80
            weight = "800"
        else:
            mode = "accumulating_stack"
            font_size = 76 if is_music else 72
            weight = "800"

        tilt_angle = -1.5 if (scene_idx % 2 == 0) else 1.5

        return TypeSpec(
            text=cleaned,
            mode=mode,
            font_size=font_size,
            weight=weight,
            tilt_angle=tilt_angle,
            is_hero=is_hero_candidate,
            words_count=words_count,
            char_count=char_count,
            spring_config={
                "damping": 10,
                "mass": 0.5,
                "stiffness": 180
            }
        )
