"""
Procedural Visual Grammar Asset Engine
Part of Astra's Persistent Kinetic Motion System.

Replaces static clipart with 4 generative procedural primitives:
1. particle_field: operator="align" | "attract" (Scattered particles attract/align into focused beams)
2. connected_graph: operator="draw" | "cluster" (Isolated nodes draw dynamic vector edges)
3. vector_ribbon: operator="accelerate" | "expand" (Flowing vector ribbons through geometric bottlenecks)
4. concentric_contours: operator="pulse" | "radiate" (Acoustic and social resonance rings)

Entities maintain persistent IDs (shared_entity_id) across narrative beats for match-morph continuity.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import math


@dataclass
class AssetSpec:
    geometry: str  # "particle_field" | "connected_graph" | "vector_ribbon" | "concentric_contours"
    operator: str  # "align" | "attract" | "draw" | "accelerate" | "expand" | "pulse" | "radiate"
    primary_color: str
    accent_color: str
    params: Dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None
    entity_id: str = "persistent_entity_01"
    topic: str = "tech_career"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["asset_type"] = self.geometry
        return d


class AssetEngine:
    """
    Synthesizes procedural visual grammar entities and operators.
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
        scene_idx: int = 0,
        total_scenes: int = 1
    ) -> AssetSpec:
        """
        Synthesize procedural generative entity with continuous entity ID and active operator.
        """
        primary = getattr(palette, "fg", "#FFFFFF")
        accent = getattr(palette, "accent", "#FF5500")

        # Persistent entity across multi-phrase segments (clusters of 3-4 scenes)
        cluster_id = scene_idx // 3
        entity_id = f"entity_cluster_{cluster_id:02d}"

        # Topic & relational operator mapping
        if topic == "poetry_music":
            geometries = ["vector_ribbon", "concentric_contours", "particle_field"]
            geom = geometries[scene_idx % len(geometries)]
            if geom == "vector_ribbon":
                operator = "flow" if scene_idx % 2 == 0 else "accelerate"
                params = {"wave_freq": 2.2, "amplitude": 45, "ribbon_count": 4}
                label = "HARMONIC FLOW // OSCILLATION"
            elif geom == "concentric_contours":
                operator = "radiate"
                params = {"pulse_rate": 1.6, "ring_count": 6}
                label = "SONIC RADIANCE // 432Hz"
            else:
                operator = "attract"
                params = {"count": 32, "speed": 1.2}
                label = "PARTICLE COHESION"

        elif topic == "finance_business":
            geometries = ["connected_graph", "vector_ribbon", "concentric_contours"]
            geom = geometries[scene_idx % len(geometries)]
            if geom == "connected_graph":
                operator = "cluster" if scene_idx % 2 == 0 else "draw"
                params = {"nodes": 8, "edges": 12, "highlight_node": scene_idx % 8}
                label = "CAPITAL TOPOLOGY // LIQUIDITY"
            elif geom == "vector_ribbon":
                operator = "accelerate"
                params = {"wave_freq": 1.8, "amplitude": 50, "growth_vector": True}
                label = "COMPOUNDING TRAJECTORY"
            else:
                operator = "pulse"
                params = {"pulse_rate": 2.0, "ring_count": 5}
                label = "VALUE EXPANSION // +42%"

        else:  # tech_career
            geometries = ["connected_graph", "particle_field", "vector_ribbon"]
            geom = geometries[scene_idx % len(geometries)]
            if geom == "connected_graph":
                operator = "draw" if scene_idx % 2 == 0 else "cluster"
                params = {"nodes": 10, "edges": 15, "active_path": True}
                label = "RELATIONAL TOPOLOGY // NETWORK"
            elif geom == "particle_field":
                operator = "align" if scene_idx % 2 == 0 else "attract"
                params = {"count": 40, "beam_focus": True}
                label = "SIGNAL COHERENCE // RECOGNITION"
            else:
                operator = "expand"
                params = {"wave_freq": 2.0, "amplitude": 40}
                label = "BOTTLENECK DILATION // FLOW"

        return AssetSpec(
            geometry=geom,
            operator=operator,
            primary_color=primary,
            accent_color=accent,
            params=params,
            label=label,
            entity_id=entity_id,
            topic=topic
        )
