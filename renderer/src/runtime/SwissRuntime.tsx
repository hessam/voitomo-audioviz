import React from "react";
import { Audio, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { HeroFocus } from "./primitives/layouts/HeroFocus";
import { SpecimenLadder } from "./primitives/layouts/SpecimenLadder";
import { ParagraphStack } from "./primitives/layouts/ParagraphStack";
import { CaptionPanel } from "./primitives/layouts/CaptionPanel";
import { PersianText } from "./primitives/PersianText";

export interface LayerNodeInput {
  id: string;
  type: string; // "typography" | "vector_shape" | "kinetic_badge" | "clip_mask"
  text?: string;
  weight?: string;
  is_hero?: boolean;
  spatial_anchor?: string;
  action_verb?: string;
  style?: Record<string, any>;
}

export interface CreativeSpecInput {
  meta?: {
    duration?: number;
    fps?: number;
    width?: number;
    height?: number;
    total_frames?: number;
  };
  creative_dna?: {
    thesis?: string;
    emotional_contradiction?: string;
    metaphor_system?: string;
    transformation_verbs?: string[];
    palette?: { bg: string; fg: string; accent: string; muted: string };
    font_family?: string;
  };
  design_system: {
    concept?: string;
    palette: {
      bg: string;
      fg: string;
      accent: string;
      muted: string;
    };
    type_scale: {
      family: string;
      weights: string[];
      ratio: number;
    };
    grid: {
      alignment: string;
      margin: number;
      columns?: number;
    };
  };
  timeline: {
    scenes: Array<{
      id: string;
      layout: string;
      frame_range: [number, number];
      reveal: {
        primitive?: string;
        target?: string;
        channel_offset_px?: number;
        stagger_frames?: number;
        direction?: "forward" | "reverse";
      };
      content: Array<{
        text: string;
        weight?: string;
        is_hero?: boolean;
      }>;
      layers?: LayerNodeInput[];
      camera_dynamic?: string;
      motion?: Record<string, any>;
    }>;
  };
}

export interface SwissRuntimeProps {
  creativeSpec?: CreativeSpecInput;
  audioSrc?: string;
  words?: Array<{ word: string; start: number; end: number }>;
}

/**
 * Maps transformation verbs (compress, invert, accrete, shatter, reconcile)
 * directly to Remotion physical spring/interpolate styles.
 */
function getVerbMotionStyle(
  verb: string,
  progress: number,
  springVal: number,
  accentColor: string,
  fgColor: string
): React.CSSProperties {
  switch (verb) {
    case "compress": {
      // Elements converge under spatial pressure towards center with high spring tension
      const scaleX = interpolate(progress, [0, 0.7, 1], [1.3, 0.95, 1.0], { extrapolateRight: "clamp" });
      const scaleY = interpolate(progress, [0, 0.7, 1], [0.8, 1.05, 1.0], { extrapolateRight: "clamp" });
      const letterSpacing = interpolate(progress, [0, 1], ["0.15em", "-0.015em"], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scaleX}, ${scaleY})`,
        letterSpacing,
      };
    }
    case "invert": {
      // Dynamic contrast flip or polar tilt
      const filter = progress < 0.45 ? "contrast(1.3)" : "none";
      const rot = interpolate(progress, [0, 1], [-4, 0], { extrapolateRight: "clamp" });
      return {
        filter,
        transform: `rotate(${rot}deg)`,
      };
    }
    case "accrete": {
      // Staggered geometric accumulation of mass and typography
      const translateY = interpolate(progress, [0, 1], [40, 0], { extrapolateRight: "clamp" });
      const opacity = interpolate(progress, [0, 0.3, 1], [0, 0.85, 1.0], { extrapolateRight: "clamp" });
      return {
        transform: `translateY(${translateY}px)`,
        opacity,
      };
    }
    case "shatter": {
      // Controlled outward dispersal snapping into structural tension
      const scale = interpolate(progress, [0, 0.35, 1], [0.88, 1.06, 1.0], { extrapolateRight: "clamp" });
      const blur = interpolate(progress, [0, 1], [6, 0], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scale})`,
        filter: blur > 0.2 ? `blur(${blur}px)` : "none",
      };
    }
    case "reconcile": {
      // Harmonious synthesis of previous opposing tensions into balanced stillness
      const scale = interpolate(progress, [0, 0.8, 1], [0.95, 1.02, 1.0], { extrapolateRight: "clamp" });
      const opacity = interpolate(progress, [0, 1], [0.2, 1.0], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scale})`,
        opacity,
      };
    }
    default:
      return {};
  }
}

/**
 * Calculates camera translation and scale from camera_dynamic.
 */
function getCameraTransform(camera: string, progress: number): string {
  switch (camera) {
    case "push": {
      const scale = interpolate(progress, [0, 1], [1.0, 1.07], { extrapolateRight: "clamp" });
      return `scale(${scale})`;
    }
    case "pan_left": {
      const x = interpolate(progress, [0, 1], [30, -30], { extrapolateRight: "clamp" });
      return `translateX(${x}px)`;
    }
    case "pan_right": {
      const x = interpolate(progress, [0, 1], [-30, 30], { extrapolateRight: "clamp" });
      return `translateX(${x}px)`;
    }
    case "drift": {
      const scale = interpolate(progress, [0, 1], [1.02, 1.06], { extrapolateRight: "clamp" });
      const y = interpolate(progress, [0, 1], [12, -12], { extrapolateRight: "clamp" });
      return `scale(${scale}) translateY(${y}px)`;
    }
    case "static":
    default:
      return "none";
  }
}

export const SwissRuntime: React.FC<SwissRuntimeProps> = ({ creativeSpec, audioSrc, words = [] }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  // Design system with procedural harmonic palette
  const ds = creativeSpec?.design_system ?? {
    concept: creativeSpec?.creative_dna?.metaphor_system || "Architectural Kinetic Specimen",
    palette: creativeSpec?.creative_dna?.palette || { bg: "#1C1412", fg: "#F7F1ED", accent: "#E05638", muted: "#8C7D75" },
    type_scale: { family: creativeSpec?.creative_dna?.font_family || "Dana, Vazirmatn, sans-serif", weights: ["300", "500", "700", "900"], ratio: 1.333 },
    grid: { alignment: "center", margin: 80, columns: 12 },
  };

  const fontFamily = creativeSpec?.creative_dna?.font_family || ds.type_scale.family || "Dana, Vazirmatn, sans-serif";
  const scenes = creativeSpec?.timeline?.scenes ?? [];
  const totalFrames = creativeSpec?.meta?.total_frames || 300;

  // Active scene selection
  let activeSceneIdx = scenes.findIndex((s) => frame >= s.frame_range[0] && frame < s.frame_range[1]);
  if (activeSceneIdx === -1 && scenes.length > 0) {
    activeSceneIdx = frame < scenes[0].frame_range[0] ? 0 : scenes.length - 1;
  }
  const activeScene = scenes[activeSceneIdx];

  const startFrame = activeScene?.frame_range[0] ?? 0;
  const endFrame = activeScene?.frame_range[1] ?? totalFrames;
  const sceneDuration = Math.max(1, endFrame - startFrame);
  const relFrame = Math.max(0, frame - startFrame);
  const sceneProgress = Math.min(1, relFrame / sceneDuration);

  // Remotion spring calculation for punchy physics
  const springVal = spring({
    frame: relFrame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 120 },
  });

  const isExiting = activeScene ? (endFrame - frame) <= 12 : false;
  const currentTime = frame / fps;
  const cameraDynamic = activeScene?.camera_dynamic || "push";
  const cameraTransform = getCameraTransform(cameraDynamic, sceneProgress);

  // Render Scene-Shot-Layer Graph IR if layers exist
  const renderGraphLayers = () => {
    if (!activeScene || !activeScene.layers || activeScene.layers.length === 0) {
      return null;
    }

    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: "80px",
          boxSizing: "border-box",
          direction: "rtl",
        }}
      >
        {activeScene.layers.map((layer, lIdx) => {
          const actionVerb = layer.action_verb || creativeSpec?.creative_dna?.transformation_verbs?.[0] || "reveal";
          const verbStyle = getVerbMotionStyle(actionVerb, sceneProgress, springVal, ds.palette.accent, ds.palette.fg);
          const isHero = layer.is_hero || lIdx === 0;

          if (layer.type === "kinetic_badge") {
            return (
              <div
                key={layer.id}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "6px 18px",
                  borderRadius: "999px",
                  border: `1px solid ${ds.palette.accent}55`,
                  backgroundColor: `${ds.palette.accent}18`,
                  color: ds.palette.accent,
                  fontSize: "18px",
                  fontWeight: 700,
                  fontFamily,
                  marginBottom: "24px",
                  ...verbStyle,
                }}
              >
                <span>✦</span>
                <PersianText
                  text={layer.text || ""}
                  fontFamily={fontFamily}
                  fontSize="18px"
                  fontWeight={700}
                  color={ds.palette.accent}
                  startFrame={startFrame + (lIdx * 3)}
                  durationInFrames={16}
                />
              </div>
            );
          }

          if (layer.type === "vector_shape") {
            return (
              <div
                key={layer.id}
                style={{
                  width: "90px",
                  height: "3px",
                  backgroundColor: ds.palette.accent,
                  margin: "18px 0",
                  ...verbStyle,
                }}
              />
            );
          }

          // Typography layer
          const textLen = (layer.text || "").length;
          const fontSize = isHero
            ? textLen <= 15 ? 84 : textLen <= 30 ? 68 : textLen <= 50 ? 56 : 46
            : 32;

          return (
            <div
              key={layer.id}
              style={{
                textAlign: "center",
                margin: isHero ? "12px 0" : "8px 0",
                ...verbStyle,
              }}
            >
              <PersianText
                text={layer.text || ""}
                fontFamily={fontFamily}
                fontSize={fontSize}
                fontWeight={layer.weight || (isHero ? 900 : 500)}
                color={isHero ? ds.palette.fg : ds.palette.muted}
                startFrame={startFrame + (lIdx * 4)}
                durationInFrames={20}
              />
            </div>
          );
        })}
      </div>
    );
  };

  // Fallback layout renderer for standard scenes
  const renderLayout = () => {
    if (!activeScene) return null;

    // Prefer Graph IR layers
    if (activeScene.layers && activeScene.layers.length > 0) {
      return renderGraphLayers();
    }

    const commonProps = {
      content: activeScene.content,
      reveal: activeScene.reveal,
      designSystem: ds,
      startFrame,
      endFrame,
      currentTime,
      words,
      isExiting,
    };

    switch (activeScene.layout) {
      case "hero_focus":
        return <HeroFocus {...commonProps} />;
      case "specimen_ladder":
        return <SpecimenLadder {...commonProps} />;
      case "paragraph_stack":
        return <ParagraphStack {...commonProps} />;
      case "caption_panel":
        return <CaptionPanel {...commonProps} />;
      default:
        return <HeroFocus {...commonProps} />;
    }
  };

  return (
    <div
      style={{
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: ds.palette.bg,
        position: "relative",
        overflow: "hidden",
        fontFamily,
      }}
    >
      {audioSrc && <Audio src={audioSrc} />}

      {/* Dynamic Motion Viewport with Camera Dynamic Transforms */}
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          zIndex: 5,
          transform: cameraTransform,
          transition: "transform 0.05s linear",
        }}
      >
        {renderLayout()}
      </div>
    </div>
  );
};
