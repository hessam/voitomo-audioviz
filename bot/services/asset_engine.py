"""
Metaphor Asset Engine (The Visual Subject)
Part of Astra's 4-Engine Negotiated Compiler.

Generates topic-specific procedural SVGs and visual metaphors.
Rules: Never generic bento icons.
Topic Archetypes:
1. Tech / Career / System:
   - "search_console": Generative search bar with cursor & tag chips.
   - "node_graph": Interactive node network with pulsing vertices.
   - "credential_badge": Geometric credential crest with ribbon and stars.
2. Poetry / Music / Arts:
   - "fluid_waveform": Harmonic sine wave oscillation.
   - "lunar_orbit": Morphing lunar sphere with orbital trajectory.
   - "kinetic_rings": Concentric acoustic resonance rings.
3. Finance / Business / Growth:
   - "candlestick_chart": Procedural bullish candlesticks with trend vectors.
   - "metric_dial": Radial gauge dial with growth percentage badge.
   - "volumetric_bars": 3D stepped performance pillars.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import math
import hashlib


@dataclass
class AssetSpec:
    topic: str  # "tech_career" | "poetry_music" | "finance_business"
    asset_type: str
    primary_color: str
    accent_color: str
    label: Optional[str] = None
    data_points: List[float] = field(default_factory=list)
    svg_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AssetEngine:
    """
    Generates procedural topic-specific visual subjects bounded to the allocated box.
    """

    TECH_KEYWORDS = ["لینکدین", "سیستم", "شرکت", "شغل", "کار", "پروژه", "رزومه", "مصاحبه", "تخصص", "فناوری", "رشد", "برند", "توسعه", "کد", "هوش مصنوعی"]
    POETRY_KEYWORDS = ["موزیک", "ترانه", "آواز", "صدا", "شعر", "عشق", "دل", "یار", "شب", "سکوت", "باران", "کویر", "ساز", "نوا"]
    FINANCE_KEYWORDS = ["سرمایه", "فروش", "سود", "درآمد", "بازار", "مالی", "ارزش", "قیمت", "سهام", "معامله", "ارز"]

    @classmethod
    def detect_topic(cls, text: str, world: str = "editorial") -> str:
        t = text.lower()
        if world == "kinetic-poster" or any(k in t for k in cls.POETRY_KEYWORDS):
            return "poetry_music"
        if any(k in t for k in cls.FINANCE_KEYWORDS):
            return "finance_business"
        return "tech_career"

    @classmethod
    def propose(
        cls,
        phrase_text: str,
        topic: str,
        palette: Any,
        scene_idx: int = 0
    ) -> Optional[AssetSpec]:
        """
        Generate procedural SVG data and dynamic parameters for the visual focal point.
        """
        primary = getattr(palette, "fg", "#FFFFFF")
        accent = getattr(palette, "accent", "#FF5500")

        if topic == "poetry_music":
            types = ["fluid_waveform", "lunar_orbit", "kinetic_rings"]
            asset_type = types[scene_idx % len(types)]
            data_points = [
                math.sin(i * 0.4 + scene_idx) * 35 + 50
                for i in range(16)
            ]
            label = "SONIC RESONANCE // FREQ 432Hz"
            svg_data = {
                "amplitude": 38,
                "frequency": 2.4,
                "rings_count": 5,
                "orbit_tilt": 28
            }

        elif topic == "finance_business":
            types = ["candlestick_chart", "metric_dial", "volumetric_bars"]
            asset_type = types[scene_idx % len(types)]
            data_points = [30.0, 42.0, 38.0, 55.0, 72.0, 68.0, 89.0]
            label = "+42% MOMENTUM // ACTIVE GROWTH"
            svg_data = {
                "bullish": True,
                "bars": [40, 65, 55, 80, 95],
                "dial_value": 78
            }

        else:  # tech_career
            types = ["search_console", "node_graph", "credential_badge"]
            asset_type = types[scene_idx % len(types)]
            data_points = [12.0, 24.0, 48.0, 96.0]
            label = "VERIFIED PIPELINE // STATUS 200"
            svg_data = {
                "nodes": [
                    {"x": 120, "y": 80, "label": "API"},
                    {"x": 280, "y": 140, "label": "CORE"},
                    {"x": 440, "y": 80, "label": "SYNC"},
                    {"x": 280, "y": 240, "label": "HOST"}
                ],
                "connections": [[0, 1], [1, 2], [1, 3]],
                "query": "opportunity.seek(persistence=True)"
            }

        return AssetSpec(
            topic=topic,
            asset_type=asset_type,
            primary_color=primary,
            accent_color=accent,
            label=label,
            data_points=data_points,
            svg_data=svg_data
        )
