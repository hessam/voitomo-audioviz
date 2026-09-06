"""
Causal Metaphor Compiler Asset Engine
Part of Astra's Visual Concept Compiler.

Architectural Principles:
1. Make the unit of invention a causal visual system, not an asset name.
2. Reject nouns and clipart. Map speech relations (pressure, friction, attraction, resonance)
   into declarative VectorIRAssembly specifications.
3. Declarative Vector IR: Primitives ('path', 'circle', 'line', 'polygon', 'arc_strip')
   with behavior operators ('attract', 'align', 'twist', 'trim', 'extrude', 'shatter').
"""

from __future__ import annotations
import os
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    ""
)
LLM_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-5.6-luna")


@dataclass
class VectorEntity:
    id: str
    primitive: str  # "path" | "circle" | "line" | "polygon" | "arc_strip"
    geometry_props: Dict[str, Any]
    style: Dict[str, Any]
    behavior: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VectorIRAssembly:
    metaphor_name: str
    canvas_role: str  # "hero_anchor" | "spatial_counterpoint" | "framing_aperture"
    entities: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AssetSpec:
    vector_ir: Dict[str, Any]
    primary_color: str
    accent_color: str
    label: Optional[str] = None
    entity_id: str = "causal_entity_01"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector_ir": self.vector_ir,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "label": self.label,
            "entity_id": self.entity_id,
            "metaphor_name": self.vector_ir.get("metaphor_name", "CausalMetaphor"),
            # Backwards-compatibility helper for any legacy inspection
            "asset_type": self.vector_ir.get("metaphor_name", "vector_ir"),
            "geometry": "vector_ir"
        }


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 15) -> dict:
    try:
        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"HTTP POST failed: {e}")
        raise


class AssetEngine:
    """
    Causal Metaphor Compiler:
    Extracts causal relations and compiles them into declarative VectorIRAssembly objects.
    """

    @classmethod
    def get_procedural_causal_models(cls) -> List[Dict[str, Any]]:
        """
        Five foundational relational causal models expressing physical dynamics:
        1. Alignment under pressure (collimated flux lines focusing on target)
        2. Friction reduction / expanding aperture (bottleneck dilation)
        3. Magnetic attraction (scattered orbits attracted to core)
        4. Topological network (relational nodes drawing vector edges)
        5. Recursive compounding resonance (expanding radiating contours)
        """
        return [
            {
                "metaphor_name": "alignment_under_pressure",
                "canvas_role": "hero_anchor",
                "entities": [
                    {
                        "id": "flux_arc_top",
                        "primitive": "path",
                        "geometry_props": {"d": "M 120 110 Q 280 180 400 225"},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 3},
                        "behavior": {"operator": "align", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 160}}
                    },
                    {
                        "id": "flux_arc_bottom",
                        "primitive": "path",
                        "geometry_props": {"d": "M 120 340 Q 280 270 400 225"},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 3},
                        "behavior": {"operator": "align", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 160}}
                    },
                    {
                        "id": "collimator_axis",
                        "primitive": "line",
                        "geometry_props": {"x1": 400, "y1": 130, "x2": 400, "y2": 320},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 2},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 14, "mass": 0.6, "stiffness": 180}}
                    },
                    {
                        "id": "focal_node",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 22},
                        "style": {"fill": "accent", "stroke": "fg", "strokeWidth": 3},
                        "behavior": {"operator": "attract", "target_pos": [400, 225], "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 170}}
                    },
                    {
                        "id": "focal_core",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 8},
                        "style": {"fill": "black", "stroke": "none", "strokeWidth": 0},
                        "behavior": {"operator": "twist", "spring_physics": {"damping": 8, "mass": 0.4, "stiffness": 200}}
                    }
                ]
            },
            {
                "metaphor_name": "friction_reduction",
                "canvas_role": "framing_aperture",
                "entities": [
                    {
                        "id": "retaining_slab_top",
                        "primitive": "line",
                        "geometry_props": {"x1": 140, "y1": 150, "x2": 660, "y2": 150},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 3},
                        "behavior": {"operator": "extrude", "spring_physics": {"damping": 14, "mass": 0.7, "stiffness": 150}}
                    },
                    {
                        "id": "retaining_slab_bottom",
                        "primitive": "line",
                        "geometry_props": {"x1": 140, "y1": 300, "x2": 660, "y2": 300},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 3},
                        "behavior": {"operator": "extrude", "spring_physics": {"damping": 14, "mass": 0.7, "stiffness": 150}}
                    },
                    {
                        "id": "streamline_primary",
                        "primitive": "path",
                        "geometry_props": {"d": "M 80 225 Q 350 180 720 225"},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 4},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    },
                    {
                        "id": "streamline_secondary",
                        "primitive": "path",
                        "geometry_props": {"d": "M 80 225 Q 350 270 720 225"},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 2},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 12, "mass": 0.6, "stiffness": 160}}
                    },
                    {
                        "id": "aperture_gate",
                        "primitive": "polygon",
                        "geometry_props": {"points": "370,180 430,180 430,270 370,270"},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 2},
                        "behavior": {"operator": "align", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 170}}
                    }
                ]
            },
            {
                "metaphor_name": "magnetic_attraction",
                "canvas_role": "hero_anchor",
                "entities": [
                    {
                        "id": "attractor_core",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 28},
                        "style": {"fill": "accent", "stroke": "fg", "strokeWidth": 3},
                        "behavior": {"operator": "extrude", "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    },
                    {
                        "id": "flux_orbital_ring",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 90},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 1.5},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 14, "mass": 0.6, "stiffness": 140}}
                    },
                    {
                        "id": "attracted_particle_01",
                        "primitive": "circle",
                        "geometry_props": {"cx": 220, "cy": 130, "r": 7},
                        "style": {"fill": "accent", "stroke": "none", "strokeWidth": 0},
                        "behavior": {"operator": "attract", "target_pos": [400, 225], "spring_physics": {"damping": 9, "mass": 0.4, "stiffness": 190}}
                    },
                    {
                        "id": "attracted_particle_02",
                        "primitive": "circle",
                        "geometry_props": {"cx": 580, "cy": 160, "r": 9},
                        "style": {"fill": "fg", "stroke": "none", "strokeWidth": 0},
                        "behavior": {"operator": "attract", "target_pos": [400, 225], "spring_physics": {"damping": 11, "mass": 0.5, "stiffness": 170}}
                    },
                    {
                        "id": "attracted_particle_03",
                        "primitive": "circle",
                        "geometry_props": {"cx": 310, "cy": 330, "r": 8},
                        "style": {"fill": "fg", "stroke": "none", "strokeWidth": 0},
                        "behavior": {"operator": "attract", "target_pos": [400, 225], "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    },
                    {
                        "id": "attracted_particle_04",
                        "primitive": "circle",
                        "geometry_props": {"cx": 520, "cy": 320, "r": 6},
                        "style": {"fill": "accent", "stroke": "none", "strokeWidth": 0},
                        "behavior": {"operator": "attract", "target_pos": [400, 225], "spring_physics": {"damping": 8, "mass": 0.4, "stiffness": 200}}
                    },
                    {
                        "id": "magnetic_field_axis",
                        "primitive": "line",
                        "geometry_props": {"x1": 100, "y1": 225, "x2": 700, "y2": 225},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 1.5},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 160}}
                    }
                ]
            },
            {
                "metaphor_name": "topological_network",
                "canvas_role": "spatial_counterpoint",
                "entities": [
                    {
                        "id": "edge_northwest",
                        "primitive": "line",
                        "geometry_props": {"x1": 240, "y1": 150, "x2": 400, "y2": 225},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 2},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 170}}
                    },
                    {
                        "id": "edge_northeast",
                        "primitive": "line",
                        "geometry_props": {"x1": 560, "y1": 150, "x2": 400, "y2": 225},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 2.5},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    },
                    {
                        "id": "edge_southwest",
                        "primitive": "line",
                        "geometry_props": {"x1": 280, "y1": 310, "x2": 400, "y2": 225},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 2},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 13, "mass": 0.6, "stiffness": 160}}
                    },
                    {
                        "id": "edge_southeast",
                        "primitive": "line",
                        "geometry_props": {"x1": 520, "y1": 310, "x2": 400, "y2": 225},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 2.5},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 11, "mass": 0.5, "stiffness": 175}}
                    },
                    {
                        "id": "peripheral_node_01",
                        "primitive": "circle",
                        "geometry_props": {"cx": 240, "cy": 150, "r": 14},
                        "style": {"fill": "black", "stroke": "fg", "strokeWidth": 2.5},
                        "behavior": {"operator": "align", "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    },
                    {
                        "id": "peripheral_node_02",
                        "primitive": "circle",
                        "geometry_props": {"cx": 560, "cy": 150, "r": 14},
                        "style": {"fill": "black", "stroke": "accent", "strokeWidth": 2.5},
                        "behavior": {"operator": "align", "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    },
                    {
                        "id": "central_hub_vertex",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 24},
                        "style": {"fill": "accent", "stroke": "fg", "strokeWidth": 3},
                        "behavior": {"operator": "extrude", "spring_physics": {"damping": 10, "mass": 0.5, "stiffness": 180}}
                    }
                ]
            },
            {
                "metaphor_name": "recursive_growth_resonance",
                "canvas_role": "hero_anchor",
                "entities": [
                    {
                        "id": "inner_resonance_ring",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 45},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 3},
                        "behavior": {"operator": "twist", "spring_physics": {"damping": 10, "mass": 0.4, "stiffness": 190}}
                    },
                    {
                        "id": "middle_resonance_ring",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 95},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 2},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 170}}
                    },
                    {
                        "id": "outer_resonance_ring",
                        "primitive": "circle",
                        "geometry_props": {"cx": 400, "cy": 225, "r": 150},
                        "style": {"fill": "none", "stroke": "accent", "strokeWidth": 2},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 14, "mass": 0.6, "stiffness": 150}}
                    },
                    {
                        "id": "resonance_horizon",
                        "primitive": "line",
                        "geometry_props": {"x1": 80, "y1": 225, "x2": 720, "y2": 225},
                        "style": {"fill": "none", "stroke": "fg", "strokeWidth": 1.5},
                        "behavior": {"operator": "trim", "spring_physics": {"damping": 12, "mass": 0.5, "stiffness": 160}}
                    },
                    {
                        "id": "growth_crest_polygon",
                        "primitive": "polygon",
                        "geometry_props": {"points": "400,165 435,225 365,225"},
                        "style": {"fill": "accent", "stroke": "black", "strokeWidth": 2},
                        "behavior": {"operator": "extrude", "spring_physics": {"damping": 9, "mass": 0.4, "stiffness": 200}}
                    }
                ]
            }
        ]

    @classmethod
    def query_llm_causal_metaphors(
        cls,
        phrases: List[str],
        creative_dna: Any
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Invokes OpenRouter LLM to extract speech semantic relations and output pure VectorIRAssembly JSON.
        """
        if not OPENROUTER_API_KEY or not phrases:
            return None

        import sys
        if "unittest" in sys.modules or os.environ.get("VOITOMO_TEST_MODE"):
            return None

        system_prompt = (
            "You are an Elite Causal Metaphor Motion Designer (Ordinary Folk / Buck / Cavalry).\n"
            "DO NOT pick clipart, nouns, or icons (no desks, search bars, laptops, or candlesticks).\n"
            "Extract the CAUSAL RELATION of the speech (e.g. alignment under pressure, friction reduction, recursive growth, magnetic attraction).\n"
            "Invent a geometric composition in an 800x450 coordinate space using 3 to 7 primitive elements.\n\n"
            "Primitives: 'path', 'circle', 'line', 'polygon', 'arc_strip'\n"
            "Operators: 'attract', 'align', 'twist', 'trim', 'extrude', 'shatter'\n"
            "Colors: 'accent', 'fg', 'bg', 'black', 'none'\n\n"
            "Output ONLY a JSON array of objects conforming to:\n"
            "[\n"
            "  {\n"
            "    \"scene_idx\": 0,\n"
            "    \"metaphor_name\": \"causal_relation_name\",\n"
            "    \"canvas_role\": \"hero_anchor\" | \"spatial_counterpoint\" | \"framing_aperture\",\n"
            "    \"entities\": [\n"
            "      {\n"
            "        \"id\": \"entity_id\",\n"
            "        \"primitive\": \"circle\" | \"line\" | \"path\" | \"polygon\",\n"
            "        \"geometry_props\": {\"cx\": 400, \"cy\": 225, \"r\": 20} or {\"x1\": 100, \"y1\": 225, \"x2\": 700, \"y2\": 225} or {\"d\": \"M 100 225 Q 400 150 700 225\"} or {\"points\": \"380,180 420,180 420,270 380,270\"},\n"
            "        \"style\": {\"fill\": \"accent\" | \"fg\" | \"black\" | \"none\", \"stroke\": \"accent\" | \"fg\" | \"black\" | \"none\", \"strokeWidth\": 2},\n"
            "        \"behavior\": {\"operator\": \"attract\" | \"align\" | \"twist\" | \"trim\" | \"extrude\" | \"shatter\", \"target_pos\": [400, 225], \"spring_physics\": {\"damping\": 12, \"mass\": 0.5, \"stiffness\": 170}}\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "]"
        )

        user_content = json.dumps({
            "metaphor_system": getattr(creative_dna, "metaphor_system", ""),
            "thesis": getattr(creative_dna, "thesis", ""),
            "phrases": [{"idx": i, "text": p} for i, p in enumerate(phrases)]
        }, ensure_ascii=False)

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.35,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"}
        }

        try:
            t0 = time.time()
            data = _http_post_json(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                payload=payload,
                timeout=20
            )
            raw = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(raw)
            assemblies = parsed if isinstance(parsed, list) else parsed.get("assemblies", parsed.get("scenes", []))
            if isinstance(assemblies, list) and len(assemblies) > 0:
                logger.info(f"✅ Causal Metaphor LLM compiled {len(assemblies)} assemblies in {time.time()-t0:.2f}s")
                return assemblies
        except Exception as e:
            logger.warning(f"Causal Metaphor LLM query skipped/fallback: {e}")

        return None

    @classmethod
    def propose(
        cls,
        phrase_text: str,
        palette: Any,
        scene_idx: int = 0,
        total_scenes: int = 1,
        creative_dna: Optional[Any] = None,
        compiled_assemblies: Optional[List[Dict[str, Any]]] = None
    ) -> AssetSpec:
        """
        Synthesize causal metaphor VectorIRAssembly for the scene.
        """
        primary = getattr(palette, "fg", "#FFFFFF")
        accent = getattr(palette, "accent", "#FF5500")

        # Check if batch-compiled LLM assembly is available
        if compiled_assemblies and scene_idx < len(compiled_assemblies):
            asm_data = compiled_assemblies[scene_idx]
            if asm_data.get("entities"):
                return AssetSpec(
                    vector_ir=asm_data,
                    primary_color=primary,
                    accent_color=accent,
                    label=asm_data.get("metaphor_name", "CAUSAL_SYSTEM").upper().replace("_", " "),
                    entity_id=f"causal_entity_{scene_idx // 3:02d}"
                )

        # Procedural Relational Metaphor Selection (Zero Nouns, 100% Causal Dynamics)
        models = cls.get_procedural_causal_models()
        model_idx = scene_idx % len(models)
        selected_model = models[model_idx]

        return AssetSpec(
            vector_ir=selected_model,
            primary_color=primary,
            accent_color=accent,
            label=selected_model["metaphor_name"].upper().replace("_", " "),
            entity_id=f"causal_entity_{scene_idx // 3:02d}"
        )
