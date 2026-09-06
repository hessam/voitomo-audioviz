import React from "react";
import { Audio, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { HeroFocus } from "./primitives/layouts/HeroFocus";
import { SpecimenLadder } from "./primitives/layouts/SpecimenLadder";
import { ParagraphStack } from "./primitives/layouts/ParagraphStack";
import { CaptionPanel } from "./primitives/layouts/CaptionPanel";
import { PersianText } from "./primitives/PersianText";
import { TapeStrip } from "./primitives/TapeStrip";
import { BentoMatrix, GraphicTile } from "./primitives/BentoMatrix";
import { EnvironmentLayer } from "./primitives/EnvironmentLayer";
import { AssetLayer } from "./primitives/AssetLayer";
import { TypographyLayer } from "./primitives/TypographyLayer";

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
    world?: "kinetic-poster" | "editorial" | "pop-bento";
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
      badge?: string;
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
      spatial?: Record<string, any>;
      environment?: any;
      asset?: any;
      vector_ir?: any;
      assetBox?: { x: number; y: number; w: number; h: number };
      type?: any;
      type_spec?: any;
      typeBox?: { x: number; y: number; w: number; h: number };
      hero_layer?: string;
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
      const ls = interpolate(progress, [0, 1], [0.15, -0.015], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scaleX}, ${scaleY})`,
        letterSpacing: `${ls}em`,
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

function clampBadge(text?: string, fallback: string = "نکته کلیدی"): string {
  if (!text || typeof text !== "string") return fallback;
  const words = text.trim().replace(/\n/g, " ").split(/\s+/);
  if (words.length === 0) return fallback;
  const clamped = words.slice(0, 3).join(" ");
  return clamped.length > 20 ? clamped.slice(0, 20).trim() : clamped;
}

export const SwissRuntime: React.FC<SwissRuntimeProps> = ({ creativeSpec, audioSrc, words = [] }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  // Design system with procedural harmonic palette
  const ds = creativeSpec?.design_system ?? {
    concept: creativeSpec?.creative_dna?.metaphor_system || "Architectural Kinetic Specimen",
    palette: creativeSpec?.creative_dna?.palette || { bg: "#5537ED", fg: "#FFFFFF", accent: "#D4FF00", muted: "#E0E7FF" },
    type_scale: { family: creativeSpec?.creative_dna?.font_family || "Dana, Vazirmatn, sans-serif", weights: ["300", "500", "700", "900"], ratio: 1.333 },
    grid: { alignment: "center", margin: 80, columns: 12 },
  };

  const fontFamily = creativeSpec?.creative_dna?.font_family || ds.type_scale.family || "Dana, Vazirmatn, sans-serif";
  const scenes = creativeSpec?.timeline?.scenes ?? [];
  const totalFrames = creativeSpec?.meta?.total_frames || 300;
  const margin = ds.grid?.margin || 80;

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

  // Accumulating Multi-Line Tape Strips
  // Stacks 1 to 3 phrases sequentially before clearing, matching Canva/Cavalry kinetic flow
  const cycleIdx = activeSceneIdx % 3; // 0, 1, 2
  const showBento = activeScene?.layout === "bento_grid";

  const stackedScenes: Array<{ scene: (typeof scenes)[0]; isCurrent: boolean }> = [];
  for (let offset = cycleIdx; offset >= 0; offset--) {
    const sIdx = activeSceneIdx - offset;
    if (sIdx >= 0 && scenes[sIdx]) {
      stackedScenes.push({ scene: scenes[sIdx], isCurrent: offset === 0 });
    }
  }

  // Polymorphic Visual Worlds Contract:
  // 1. kinetic-poster: Music / Lyric / Poetry (75-110px stacked verses, zero HUD, zero bento)
  // 2. editorial: Education / Tutorial / LinkedIn (balanced 55px typography, step cards, minimal subtitle HUD)
  // 3. pop-bento: Commercial / Ad / Promo (dynamic variable benefit tiles, CTA takeovers, punchy BentoMatrix)
  const world = creativeSpec?.creative_dna?.world || "pop-bento";

  const isNegotiatedCompilerScene = Boolean(
    activeScene?.spatial || activeScene?.environment || activeScene?.asset || activeScene?.type
  );

  // Persistent Continuous Camera Momentum (scale: 1.0 -> 1.15 across full video duration)
  const globalProgress = Math.min(1, Math.max(0, frame / (totalFrames || 1)));
  const globalCameraScale = interpolate(globalProgress, [0, 1], [1.0, 1.15]);

  return (
    <div
      style={{
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: ds.palette.bg,
        position: "relative",
        overflow: "hidden",
        fontFamily,
        transform: `scale(${globalCameraScale})`,
        transformOrigin: "center center",
      }}
    >
      {audioSrc && <Audio src={audioSrc} />}

      {/* 4-Engine Negotiated Compiler Render Tree (Astra Architectural Contract) */}
      {isNegotiatedCompilerScene ? (
        <>
          <EnvironmentLayer
            spec={activeScene?.environment}
            defaultBg={ds.palette.bg}
          />
          <AssetLayer
            spec={activeScene?.asset}
            vectorIR={activeScene?.vector_ir || activeScene?.asset?.vector_ir}
            box={activeScene?.assetBox || activeScene?.spatial?.asset_box}
            saliency={activeScene?.spatial}
            startFrame={startFrame}
            durationInFrames={sceneDuration}
            palette={ds.palette}
          />
          <TypographyLayer
            spec={activeScene?.type || activeScene?.type_spec}
            box={activeScene?.typeBox || activeScene?.spatial?.type_box}
            saliency={activeScene?.spatial}
            stackedScenes={stackedScenes}
            fontFamily={fontFamily}
          />
        </>
      ) : (
        <>
          {world === "kinetic-poster" && (
            <KineticPosterWorld
              scene={activeScene}
              stackedScenes={stackedScenes}
              fontFamily={fontFamily}
              totalFrames={totalFrames}
            />
          )}

          {world === "editorial" && (
            <EditorialWorld
              scene={activeScene}
              stackedScenes={stackedScenes}
              activeSceneIdx={activeSceneIdx}
              scenesCount={scenes.length}
              totalFrames={totalFrames}
              frame={frame}
              fontFamily={fontFamily}
              ds={ds}
              creativeSpec={creativeSpec}
            />
          )}

          {world === "pop-bento" && (
            <PopBentoWorld
              scene={activeScene}
              stackedScenes={stackedScenes}
              activeSceneIdx={activeSceneIdx}
              scenesCount={scenes.length}
              totalFrames={totalFrames}
              frame={frame}
              fontFamily={fontFamily}
              ds={ds}
              showBento={showBento}
              cameraTransform={cameraTransform}
              creativeSpec={creativeSpec}
            />
          )}
        </>
      )}
    </div>
  );
};

/**
 * Visual World 1: Kinetic Poster (Music / Lyric / Poetry)
 * Strict Bans: BANNED: Tech HUD, Bento grids, audio meters, frame ticks.
 * What is rendered: Full-canvas typography (75–110px), stacked verses, phrase-reveal motion.
 */
export const KineticPosterWorld: React.FC<{
  scene?: any;
  stackedScenes: Array<{ scene: any; isCurrent: boolean }>;
  fontFamily: string;
  totalFrames: number;
}> = ({ stackedScenes, fontFamily }) => {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "40px 24px",
        direction: "rtl",
        zIndex: 10,
      }}
    >
      {stackedScenes.map(({ scene: s, isCurrent }, idx) => {
        const sText =
          s.layers?.find((l: any) => l.is_hero || l.weight === "900")?.text ||
          s.content?.find((c: any) => c.is_hero)?.text ||
          s.content?.[0]?.text ||
          "";
        if (!sText) return null;
        const sStart = s.frame_range[0];

        // 78-106px bold hero typography commanding center canvas
        const baseSize =
          stackedScenes.length > 2 ? 78 : stackedScenes.length === 2 ? 90 : 106;
        const fontSize = sText.length > 24 ? baseSize - 12 : baseSize;
        const tiltAngle = idx % 2 === 0 ? -1.5 : 1.5;

        return (
          <TapeStrip
            key={s.id}
            text={sText}
            isBlack={!isCurrent}
            fontSize={fontSize}
            fontFamily={fontFamily}
            startFrame={sStart}
            tiltAngle={tiltAngle}
            style={{ margin: "12px 0" }}
          />
        );
      })}
    </div>
  );
};

/**
 * Visual World 2: Editorial (Education / Tutorial / LinkedIn)
 * Strict Bans: BANNED: 8-tile bento icon matrix, full-bleed poster scaling, frozen PowerPoint footers.
 * What is rendered: High-energy Persian typography commanding center 60% of screen + minimal subtitle HUD.
 */
export const EditorialWorld: React.FC<{
  scene?: any;
  stackedScenes: Array<{ scene: any; isCurrent: boolean }>;
  activeSceneIdx: number;
  scenesCount: number;
  totalFrames: number;
  frame: number;
  fontFamily: string;
  ds: any;
  creativeSpec?: CreativeSpecInput;
}> = ({
  scene,
  stackedScenes,
  activeSceneIdx,
  scenesCount,
  totalFrames,
  frame,
  fontFamily,
  ds,
}) => {
  const currentBadge = clampBadge(
    scene?.badge || scene?.layers?.find((l: any) => l.type === "kinetic_badge")?.text,
    "نکته کلیدی"
  );
  const progressRatio = Math.min(1, Math.max(0, frame / (totalFrames || 1)));

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", fontFamily }}>
      {/* Minimal Subtitle HUD Header */}
      <div
        style={{
          position: "absolute",
          top: "28px",
          left: "48px",
          right: "48px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "14px",
          fontFamily: "monospace, sans-serif",
          color: ds.palette.muted,
          opacity: 0.85,
          zIndex: 20,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: ds.palette.accent, fontWeight: 900 }}>LESSON //</span>
          <span style={{ color: ds.palette.fg, opacity: 0.9 }}>{currentBadge}</span>
        </div>
        <div style={{ fontWeight: 700, color: ds.palette.fg }}>
          STEP [{String(activeSceneIdx + 1).padStart(2, "0")}/{String(scenesCount || 1).padStart(2, "0")}]
        </div>
      </div>

      {/* Spoken Persian phrases commanding the center vertical canvas (72px - 96px) */}
      <div
        style={{
          position: "absolute",
          inset: "80px 48px 40px 48px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
          direction: "rtl",
          zIndex: 10,
        }}
      >
        {stackedScenes.map(({ scene: s, isCurrent }, idx) => {
          const sText =
            s.layers?.find((l: any) => l.is_hero || l.weight === "900")?.text ||
            s.content?.find((c: any) => c.is_hero)?.text ||
            s.content?.[0]?.text ||
            "";
          if (!sText) return null;
          const sStart = s.frame_range[0];
          // 72px - 96px bold hero typography
          const baseSize =
            stackedScenes.length > 2 ? 72 : stackedScenes.length === 2 ? 84 : 96;
          const fontSize = sText.length > 24 ? baseSize - 12 : baseSize;
          const tiltAngle = idx % 2 === 0 ? -1.5 : 1.5;

          return (
            <TapeStrip
              key={s.id}
              text={sText}
              isBlack={!isCurrent}
              fontSize={fontSize}
              fontFamily={fontFamily}
              startFrame={sStart}
              tiltAngle={tiltAngle}
              style={{ margin: "10px 0" }}
            />
          );
        })}
      </div>

      {/* Minimal Subtitle HUD Progress Bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "4px",
          backgroundColor: `${ds.palette.fg}22`,
          zIndex: 20,
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${progressRatio * 100}%`,
            backgroundColor: ds.palette.accent,
            transition: "width 0.1s linear",
          }}
        />
      </div>
    </div>
  );
};

/**
 * Visual World 3: Pop Bento (Commercial / Ad / Promo)
 * Strict Bans: BANNED: Static 4-slot wireframe, identical 8-icon grids.
 * What is rendered: Dynamic variable product/benefit tiles, price bursts, punchy CTA takeovers + BentoMatrix.
 */
export const PopBentoWorld: React.FC<{
  scene?: any;
  stackedScenes: Array<{ scene: any; isCurrent: boolean }>;
  activeSceneIdx: number;
  scenesCount: number;
  totalFrames: number;
  frame: number;
  fontFamily: string;
  ds: any;
  showBento: boolean;
  cameraTransform?: string;
  creativeSpec?: CreativeSpecInput;
}> = ({
  scene,
  stackedScenes,
  activeSceneIdx,
  scenesCount,
  fontFamily,
  ds,
  cameraTransform = "none",
}) => {
  const currentBadge = clampBadge(
    scene?.badge || scene?.layers?.find((l: any) => l.type === "kinetic_badge")?.text,
    "پیشنهاد ویژه"
  );
  const isFinalScene = activeSceneIdx === (scenesCount || 1) - 1;
  const isBento = scene?.layout === "bento_grid";

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        fontFamily,
        transform: cameraTransform,
        transition: "transform 0.05s linear",
      }}
    >
      {/* Upper 46%: Punchy Headline & Kinetic Badge */}
      <div
        style={{
          position: "absolute",
          top: isBento ? "40px" : "18%",
          left: "5%",
          right: "5%",
          height: isBento ? "46%" : "64%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
          direction: "rtl",
          zIndex: 10,
          transition: "all 0.15s ease",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 16px",
            backgroundColor: "#000000",
            color: "#FFFFFF",
            boxShadow: "4px 4px 0px 0px #000000",
            fontSize: "15px",
            fontWeight: 800,
            fontFamily,
            marginBottom: "8px",
          }}
        >
          <span>✦</span>
          <span>{currentBadge}</span>
        </div>

        {stackedScenes.map(({ scene: s, isCurrent }, idx) => {
          const sText =
            s.layers?.find((l: any) => l.is_hero || l.weight === "900")?.text ||
            s.content?.find((c: any) => c.is_hero)?.text ||
            s.content?.[0]?.text ||
            "";
          if (!sText) return null;
          const sStart = s.frame_range[0];
          // Scale font up: 72px - 92px without bento, 50px - 66px with bento
          const baseSize = isBento
            ? (stackedScenes.length > 2 ? 50 : stackedScenes.length === 2 ? 58 : 66)
            : (stackedScenes.length > 2 ? 72 : stackedScenes.length === 2 ? 82 : 92);
          const fontSize = sText.length > 25 ? baseSize - 10 : baseSize;
          const tiltAngle = idx % 2 === 0 ? -1.5 : 1.5;

          return (
            <TapeStrip
              key={s.id}
              text={sText}
              isBlack={!isCurrent}
              fontSize={fontSize}
              fontFamily={fontFamily}
              startFrame={sStart}
              tiltAngle={tiltAngle}
            />
          );
        })}
      </div>

      {/* Lower 50%: Dynamic Bento Matrix (Strictly ONLY if scene.layout === 'bento_grid') */}
      {isBento && (
        <div style={{ position: "absolute", inset: "52% 5% 6% 5%", zIndex: 5 }}>
          {isFinalScene ? (
            <div
              style={{
                width: "100%",
                height: "100%",
                backgroundColor: "#FFFFFF",
                border: "3px solid #000000",
                boxShadow: "10px 10px 0px 0px #000000",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                direction: "rtl",
                gap: "12px",
                padding: "20px",
              }}
            >
              <span
                style={{
                  backgroundColor: ds.palette.accent,
                  color: "#000000",
                  fontSize: "16px",
                  fontWeight: 900,
                  padding: "4px 14px",
                  border: "2px solid #000000",
                  boxShadow: "3px 3px 0px 0px #000000",
                }}
              >
                ✦ اقدام فوری
              </span>
              <span style={{ fontSize: "34px", fontWeight: 900, color: "#000000" }}>
                همین حالا ثبت سفارش کنید
              </span>
            </div>
          ) : (
            <BentoMatrix style={{ width: "100%", height: "100%" }} />
          )}
        </div>
      )}
    </div>
  );
};
