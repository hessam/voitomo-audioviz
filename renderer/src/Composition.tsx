import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import * as Icons from "lucide-react";

export interface GridItem {
  title: string;
  icon?: string;
  bg?: string;
}

export interface SceneData {
  type:
    | "HERO_BLOCK"
    | "BENTO_GRID"
    | "METRIC_PUNCH"
    | "SPLIT_VIEWPORT"
    | "SWISS_TEXT"
    | "CALLOUT_CARD"
    | "ICON_GRID"
    | "METRIC_CALLOUT";
  startFrame: number;
  endFrame: number;
  theme: "light" | "dark" | "accent";
  lines: string[];
  alignment?: "center" | "right" | "left";
  eyebrow?: string;
  icon?: string;
  badgeLabel?: string;
  metric?: string;
  counterFrom?: number;
  counterTo?: number;
  gridItems?: { icon?: string; label?: string; title?: string; bg?: string }[];
}

export interface WordTiming {
  word: string;
  start: number;
  end: number;
}

export interface DirectorProps {
  scenes?: SceneData[];
  words?: WordTiming[];
  audioSrc?: string;
  durationInFrames: number;
  profile?: string;
  profileData?: any;
}

/**
 * Resolves a Lucide icon safely by string name, fallback to Sparkles
 */
function resolveIcon(name?: string) {
  if (name && (Icons as Record<string, any>)[name]) {
    return (Icons as Record<string, any>)[name];
  }
  return Icons.Sparkles;
}

/**
 * Procedural Technical Accents & Secondary Motion Elements
 */
export const AnimatedCounter: React.FC<{
  from?: number | null;
  to?: number | null;
  relFrame: number;
  suffix?: string;
}> = ({ from = 0, to = 0, relFrame, suffix = "" }) => {
  const safeFrom = typeof from === "number" && !isNaN(from) ? from : 0;
  const safeTo = typeof to === "number" && !isNaN(to) ? to : 0;
  const progress = interpolate(relFrame, [0, 22], [0, 1], {
    extrapolateRight: "clamp",
  });
  const val = Math.floor(interpolate(progress, [0, 1], [safeFrom, safeTo]));
  return (
    <span style={{ fontFamily: "monospace, sans-serif", fontWeight: 900 }}>
      {val}
      {suffix}
    </span>
  );
};

export const BarcodeStrip: React.FC<{ color?: string; relFrame?: number }> = ({
  color = "#000000",
  relFrame = 0,
}) => (
  <div style={{ display: "flex", gap: 3, height: 26, alignItems: "flex-end" }}>
    {[40, 85, 25, 100, 60, 30, 90, 50, 75, 20, 100, 45, 85, 30, 65, 95].map(
      (baseH, i) => {
        // Micro-wave secondary motion
        const wobble = Math.sin((relFrame + i * 4) * 0.15) * 10;
        const h = Math.min(100, Math.max(15, baseH + wobble));
        return (
          <div
            key={i}
            style={{
              width: 4,
              height: `${h}%`,
              backgroundColor: color,
              borderRadius: 1,
            }}
          />
        );
      }
    )}
  </div>
);

export const ViewportGridOverlay: React.FC<{
  sceneNum?: string | number;
  theme?: string;
  frame: number;
  fps: number;
}> = ({ sceneNum = "01", theme = "light", frame, fps }) => {
  const isDark = theme === "dark";
  const lineColor = isDark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.12)";
  const textColor = isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.45)";

  const seconds = Math.floor(frame / fps);
  const subFrame = frame % fps;
  const timecode = `00:${String(seconds).padStart(2, "0")}:${String(
    subFrame
  ).padStart(2, "0")}`;

  // Pulsing status blip
  const blipOpacity = 0.4 + 0.6 * Math.abs(Math.sin(frame * 0.18));

  return (
    <div
      style={{
        position: "absolute",
        inset: 32,
        border: `1px dashed ${lineColor}`,
        pointerEvents: "none",
        zIndex: 5,
      }}
    >
      {/* Top Left Tag + Status */}
      <div
        style={{
          position: "absolute",
          top: 8,
          left: 12,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            backgroundColor: "#22C55E",
            opacity: blipOpacity,
          }}
        />
        <span
          style={{
            fontSize: 13,
            fontFamily: "Vazirmatn, monospace",
            color: textColor,
            letterSpacing: "0.06em",
          }}
        >
          [ ۰{sceneNum} // کینتیک ]
        </span>
      </div>

      {/* Top Right Live Timecode */}
      <span
        style={{
          position: "absolute",
          top: 8,
          right: 12,
          fontSize: 13,
          fontFamily: "monospace",
          color: textColor,
          letterSpacing: "0.06em",
        }}
      >
        ⏱ {timecode}
      </span>

      {/* Bottom Right Resolution */}
      <span
        style={{
          position: "absolute",
          bottom: 8,
          right: 12,
          fontSize: 13,
          fontFamily: "monospace",
          color: textColor,
          letterSpacing: "0.06em",
        }}
      >
        + ۱۰۸۰ × ۱۹۲۰ +
      </span>

      {/* Corner crosshairs */}
      <div
        style={{
          position: "absolute",
          top: -6,
          left: -6,
          width: 14,
          height: 14,
          borderLeft: `2px solid ${lineColor}`,
          borderTop: `2px solid ${lineColor}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: -6,
          right: -6,
          width: 14,
          height: 14,
          borderRight: `2px solid ${lineColor}`,
          borderTop: `2px solid ${lineColor}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: -6,
          left: -6,
          width: 14,
          height: 14,
          borderLeft: `2px solid ${lineColor}`,
          borderBottom: `2px solid ${lineColor}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: -6,
          right: -6,
          width: 14,
          height: 14,
          borderRight: `2px solid ${lineColor}`,
          borderBottom: `2px solid ${lineColor}`,
        }}
      />
    </div>
  );
};

export const VoiceMotion: React.FC<DirectorProps> = ({
  scenes = [],
  words = [],
  audioSrc,
  durationInFrames,
  profileData,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Active scene selection
  const { activeScene, sceneIdx, nextScene } = useMemo(() => {
    if (scenes && scenes.length > 0) {
      const idx = scenes.findIndex(
        (s) => frame >= s.startFrame && frame < s.endFrame
      );
      if (idx !== -1) {
        return {
          activeScene: scenes[idx],
          sceneIdx: idx + 1,
          nextScene: idx < scenes.length - 1 ? scenes[idx + 1] : undefined,
        };
      }
      return {
        activeScene: scenes[scenes.length - 1],
        sceneIdx: scenes.length,
        nextScene: undefined,
      };
    }
    return {
      activeScene: {
        type: "HERO_BLOCK" as const,
        startFrame: 0,
        endFrame: durationInFrames,
        theme: "light" as const,
        lines:
          words.length > 0
            ? [words.slice(0, 4).map((w) => w.word).join(" ")]
            : ["..."],
      },
      sceneIdx: 1,
      nextScene: undefined,
    };
  }, [scenes, frame, durationInFrames, words]);

  // Color paletting
  const themeColors = useMemo(() => {
    const accentHex = profileData?.palette?.accent || "#4F39F6";
    const darkHex = "#111114";
    const lightHex = "#EAEAEB";

    const map = {
      light: {
        bg: lightHex,
        tagPrimary: { bg: "#000000", text: "#FFFFFF" },
        tagAlt: { bg: "#FFFFFF", text: "#000000" },
        cardBg: "#FFFFFF",
        cardText: "#111111",
        accent: accentHex,
      },
      dark: {
        bg: darkHex,
        tagPrimary: { bg: "#FFFFFF", text: "#000000" },
        tagAlt: { bg: "#222228", text: "#FFFFFF" },
        cardBg: "#1C1C22",
        cardText: "#FFFFFF",
        accent: accentHex,
      },
      accent: {
        bg: accentHex,
        tagPrimary: { bg: "#FFFFFF", text: "#000000" },
        tagAlt: { bg: "#000000", text: "#FFFFFF" },
        cardBg: "#FFFFFF",
        cardText: "#000000",
        accent: "#000000",
      },
    };

    return map[activeScene.theme] || map.light;
  }, [activeScene.theme, profileData]);

  // Next theme colors (for transformational transitions)
  const nextThemeColors = useMemo(() => {
    if (!nextScene) return null;
    const accentHex = profileData?.palette?.accent || "#4F39F6";
    const map = {
      light: "#EAEAEB",
      dark: "#111114",
      accent: accentHex,
    };
    return map[nextScene.theme] || "#111114";
  }, [nextScene, profileData]);

  // Kinetic Time Tracking
  const relFrame = Math.max(0, frame - activeScene.startFrame);
  const sceneDuration = Math.max(
    1,
    activeScene.endFrame - activeScene.startFrame
  );

  // 1. Continuous Idle Camera Drift & Parallax
  const cameraZoom = interpolate(relFrame, [0, sceneDuration], [0.97, 1.05], {
    extrapolateRight: "clamp",
  });

  // 2. Transformational Transition Physics (TRANSFORM -> BECOME)
  // Last 7 frames: Morphing Geometric Shutter Blade sweeps across
  const TRANSITION_DURATION = 7;
  const framesUntilExit = activeScene.endFrame - frame;
  const inTransition = framesUntilExit <= TRANSITION_DURATION && !!nextScene;

  const morphSpring = spring({
    frame: Math.max(0, TRANSITION_DURATION - framesUntilExit),
    fps,
    config: { damping: 12, stiffness: 360, mass: 0.5 },
  });

  // Outgoing scene compresses and shifts slightly into the incoming morph
  const sceneExitScale = inTransition
    ? interpolate(morphSpring, [0, 1], [1, 0.9])
    : 1.0;
  const sceneExitOpacity = inTransition
    ? interpolate(morphSpring, [0, 0.8, 1], [1, 0.7, 0.1])
    : 1.0;

  // Incoming morph plane expansion
  const morphWipeInset = inTransition
    ? interpolate(morphSpring, [0, 1], [100, 0])
    : 100;

  const lines = Array.isArray(activeScene.lines) ? activeScene.lines : [];
  const IconComp = resolveIcon(activeScene.icon);

  // Secondary Accents Entrance Timing
  const badgeDelay = Math.max(2, lines.length * 3 + 2);
  const badgeRelFrame = Math.max(0, relFrame - badgeDelay);
  const badgeSpring = spring({
    frame: badgeRelFrame,
    fps,
    config: { damping: 9, stiffness: 280, mass: 0.6 },
  });
  const badgeScale = interpolate(badgeSpring, [0, 1], [0.4, 1.0]);
  const badgeTranslateY = interpolate(badgeSpring, [0, 1], [28, 0]);

  // Dynamic Underline Rule Animation
  const lineRuleProgress = interpolate(
    spring({
      frame: Math.max(0, relFrame - 4),
      fps,
      config: { damping: 12, stiffness: 320 },
    }),
    [0, 1],
    [0, 100]
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: themeColors.bg,
        justifyContent: "center",
        alignItems: "center",
        direction: "rtl",
        fontFamily: "Vazirmatn, system-ui, sans-serif",
        overflow: "hidden",
      }}
    >
      {audioSrc && <Audio src={audioSrc} />}

      {/* Continuous Camera Drift Layer */}
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          transform: `scale(${cameraZoom * sceneExitScale})`,
          opacity: sceneExitOpacity,
          transformOrigin: "center center",
        }}
      >
        {/* Technical Blueprint Viewport Overlay */}
        <ViewportGridOverlay
          sceneNum={sceneIdx}
          theme={activeScene.theme}
          frame={frame}
          fps={fps}
        />

        {/* Subtle Background Watermark Number for Depth */}
        <div
          style={{
            position: "absolute",
            fontSize: "280px",
            fontWeight: 900,
            color: activeScene.theme === "dark" ? "#FFFFFF" : "#000000",
            opacity: 0.035,
            userSelect: "none",
            pointerEvents: "none",
            zIndex: 1,
            transform: `translate(${interpolate(
              relFrame,
              [0, sceneDuration],
              [-20, 20]
            )}px, 0)`,
          }}
        >
          {String(sceneIdx).padStart(2, "0")}
        </div>

        {/* Main Content Layout Canvas */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems:
              activeScene.alignment === "right"
                ? "flex-start"
                : activeScene.alignment === "left"
                ? "flex-end"
                : "center",
            justifyContent: "center",
            width: "100%",
            maxWidth: "960px",
            padding: "0 48px",
            direction: "rtl",
            zIndex: 10,
          }}
        >
          {/* =========================================================
              ARCHETYPE 1: HERO_BLOCK (Interlocking Word/Line Blocks)
              ========================================================= */}
          {(activeScene.type === "HERO_BLOCK" ||
            activeScene.type === "SWISS_TEXT" ||
            !activeScene.type) && (
            <div
              style={{
                display: "inline-flex",
                flexDirection: "column",
                alignItems: "flex-start",
                margin: 0,
                gap: 0,
              }}
            >
              {lines.map((line, idx) => {
                const isHeroLine =
                  idx === lines.length - 1 && lines.length > 1;
                const isAlt = idx % 2 === 1;
                const tagStyle = isAlt
                  ? themeColors.tagAlt
                  : themeColors.tagPrimary;

                // Cascading Line Stagger
                const lineSpring = spring({
                  frame: relFrame - idx * 3,
                  fps,
                  config: { damping: 11, stiffness: 340, mass: 0.5 },
                });
                const lineScale = interpolate(lineSpring, [0, 1], [0.72, 1.0]);
                const lineTranslateY = interpolate(lineSpring, [0, 1], [35, 0]);
                const clipInset = Math.max(
                  0,
                  interpolate(lineSpring, [0, 1], [100, 0])
                );
                const lineOpacity = interpolate(
                  lineSpring,
                  [0, 0.2, 1],
                  [0, 1, 1]
                );

                return (
                  <div
                    key={`${activeScene.startFrame}-${idx}`}
                    style={{
                      backgroundColor: tagStyle.bg,
                      color: tagStyle.text,
                      padding: isHeroLine ? "16px 42px" : "10px 28px",
                      fontSize: isHeroLine ? "66px" : "42px",
                      fontWeight: isHeroLine ? 900 : 800,
                      lineHeight: 1.12,
                      letterSpacing: "-0.02em",
                      borderRadius: "2px",
                      marginTop: idx > 0 ? "-3px" : "0px",
                      boxShadow: "0 14px 40px rgba(0,0,0,0.18)",
                      direction: "rtl",
                      whiteSpace: "nowrap",
                      transform: `translateY(${lineTranslateY}px) scale(${lineScale})`,
                      transformOrigin: "right center",
                      clipPath: `inset(0 0 0 ${clipInset}%)`,
                      opacity: lineOpacity,
                    }}
                  >
                    {line}
                  </div>
                );
              })}

              {/* Dynamic Kinetic Underline Accent */}
              <div
                style={{
                  width: `${lineRuleProgress}%`,
                  height: "5px",
                  backgroundColor: themeColors.accent,
                  marginTop: "12px",
                  borderRadius: "2px",
                }}
              />

              {/* Procedural Soundwave Barcode Accent */}
              <div
                style={{
                  marginTop: "14px",
                  transform: `scale(${badgeScale})`,
                  transformOrigin: "right center",
                }}
              >
                <BarcodeStrip
                  color={
                    activeScene.theme === "dark"
                      ? "#FFFFFF"
                      : activeScene.theme === "accent"
                      ? "#FFFFFF"
                      : "#000000"
                  }
                  relFrame={relFrame}
                />
              </div>
            </div>
          )}

          {/* =========================================================
              ARCHETYPE 2: BENTO_GRID (2x2 Matrix with Layer Overlap)
              ========================================================= */}
          {(activeScene.type === "BENTO_GRID" ||
            activeScene.type === "ICON_GRID") && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: "100%",
                gap: "18px",
              }}
            >
              {lines.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  {lines.map((l, i) => (
                    <div
                      key={i}
                      style={{
                        backgroundColor: themeColors.tagPrimary.bg,
                        color: themeColors.tagPrimary.text,
                        padding: "8px 24px",
                        fontSize: "36px",
                        fontWeight: 900,
                        borderRadius: "2px",
                        boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
                      }}
                    >
                      {l}
                    </div>
                  ))}
                </div>
              )}

              {/* 2x2 Bento Matrix */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "14px",
                  width: "100%",
                  maxWidth: "820px",
                  direction: "rtl",
                }}
              >
                {(activeScene.gridItems && activeScene.gridItems.length > 0
                  ? activeScene.gridItems
                  : [
                      { title: "سئو و بهینه‌سازی", icon: "TrendingUp" },
                      { title: "کمپین‌های گوگل", icon: "Globe" },
                      { title: "تولید محتوا", icon: "FileCode2" },
                      { title: "برندینگ دیجیتال", icon: "Sparkles" },
                    ]
                ).map((item, gIdx) => {
                  const GridIcon = resolveIcon(item.icon);
                  const itemSpring = spring({
                    frame: relFrame - (badgeDelay + gIdx * 2.5),
                    fps,
                    config: { damping: 10, stiffness: 300, mass: 0.5 },
                  });
                  const itemScale = interpolate(itemSpring, [0, 1], [0.4, 1]);
                  const itemY = interpolate(itemSpring, [0, 1], [24, 0]);

                  return (
                    <div
                      key={gIdx}
                      style={{
                        backgroundColor: themeColors.cardBg,
                        color: themeColors.cardText,
                        borderRadius: "14px",
                        padding: "18px 22px",
                        display: "flex",
                        alignItems: "center",
                        gap: "14px",
                        boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
                        border: `1px solid ${
                          activeScene.theme === "dark"
                            ? "rgba(255,255,255,0.08)"
                            : "rgba(0,0,0,0.06)"
                        }`,
                        transform: `translateY(${itemY}px) scale(${itemScale})`,
                        transformOrigin: "center center",
                      }}
                    >
                      <div
                        style={{
                          width: 44,
                          height: 44,
                          borderRadius: "10px",
                          backgroundColor: item.bg || themeColors.accent,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#FFFFFF",
                          flexShrink: 0,
                        }}
                      >
                        <GridIcon size={24} />
                      </div>
                      <span style={{ fontSize: "24px", fontWeight: 800 }}>
                        {item.title || item.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* =========================================================
              ARCHETYPE 3: METRIC_PUNCH (Animated Number + Overlap)
              ========================================================= */}
          {(activeScene.type === "METRIC_PUNCH" ||
            activeScene.type === "METRIC_CALLOUT") && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "14px",
              }}
            >
              {lines.map((l, i) => (
                <div
                  key={i}
                  style={{
                    backgroundColor: themeColors.tagPrimary.bg,
                    color: themeColors.tagPrimary.text,
                    padding: "10px 30px",
                    fontSize: "38px",
                    fontWeight: 900,
                    borderRadius: "2px",
                    boxShadow: "0 10px 28px rgba(0,0,0,0.16)",
                  }}
                >
                  {l}
                </div>
              ))}

              <div
                style={{
                  backgroundColor: themeColors.cardBg,
                  color: themeColors.cardText,
                  borderRadius: "20px",
                  padding: "24px 48px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "10px",
                  marginTop: "-10px", // Interlocking overlap
                  boxShadow: "0 18px 48px rgba(0,0,0,0.22)",
                  transform: `translateY(${badgeTranslateY}px) scale(${badgeScale})`,
                  transformOrigin: "center center",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: "14px",
                    color: themeColors.accent,
                    fontSize: "92px",
                    fontWeight: 900,
                    lineHeight: 1,
                  }}
                >
                  {typeof activeScene.counterTo === "number" && !isNaN(activeScene.counterTo) ? (
                    <AnimatedCounter
                      from={activeScene.counterFrom || 0}
                      to={activeScene.counterTo}
                      relFrame={badgeRelFrame}
                      suffix={activeScene.metric ? "" : "+"}
                    />
                  ) : (
                    <span>{activeScene.metric || (activeScene.badgeLabel ? activeScene.badgeLabel : "۱۶+")}</span>
                  )}
                  {activeScene.badgeLabel && (
                    <span
                      style={{
                        fontSize: "26px",
                        fontWeight: 800,
                        color: themeColors.cardText,
                        opacity: 0.88,
                      }}
                    >
                      {activeScene.badgeLabel}
                    </span>
                  )}
                </div>
                <BarcodeStrip
                  color={themeColors.accent}
                  relFrame={relFrame}
                />
              </div>
            </div>
          )}

          {/* =========================================================
              ARCHETYPE 4: SPLIT_VIEWPORT (Asymmetrical Layout)
              ========================================================= */}
          {activeScene.type === "SPLIT_VIEWPORT" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                width: "100%",
                gap: "20px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  gap: 0,
                }}
              >
                {lines.map((l, i) => (
                  <div
                    key={i}
                    style={{
                      backgroundColor:
                        i === 0
                          ? themeColors.tagPrimary.bg
                          : themeColors.tagAlt.bg,
                      color:
                        i === 0
                          ? themeColors.tagPrimary.text
                          : themeColors.tagAlt.text,
                      padding: i === 0 ? "10px 24px" : "14px 36px",
                      fontSize: i === 0 ? "34px" : "56px",
                      fontWeight: 900,
                      marginTop: i > 0 ? "-2px" : 0,
                      borderRadius: "2px",
                      boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
                    }}
                  >
                    {l}
                  </div>
                ))}
              </div>

              <div
                style={{
                  backgroundColor: themeColors.cardBg,
                  color: themeColors.cardText,
                  borderRadius: "16px",
                  padding: "20px 32px",
                  display: "flex",
                  alignItems: "center",
                  gap: "18px",
                  boxShadow: "0 12px 36px rgba(0,0,0,0.16)",
                  transform: `translateY(${badgeTranslateY}px) scale(${badgeScale})`,
                  transformOrigin: "right center",
                }}
              >
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: "12px",
                    backgroundColor: themeColors.accent,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#FFFFFF",
                  }}
                >
                  <IconComp size={30} />
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: "26px", fontWeight: 800 }}>
                    {(activeScene.badgeLabel && activeScene.badgeLabel !== "None") ? activeScene.badgeLabel : "استراتژی و برند"}
                  </span>
                  <span
                    style={{
                      fontSize: "13px",
                      fontFamily: "Vazirmatn, sans-serif",
                      opacity: 0.6,
                    }}
                  >
                    آژانس محتوالی // B2B
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* =========================================================
              ARCHETYPE 5: CALLOUT_CARD (Interlocking Badge)
              ========================================================= */}
          {activeScene.type === "CALLOUT_CARD" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "16px",
              }}
            >
              {lines.map((l, i) => (
                <div
                  key={i}
                  style={{
                    backgroundColor: themeColors.tagPrimary.bg,
                    color: themeColors.tagPrimary.text,
                    padding: "12px 34px",
                    fontSize: "52px",
                    fontWeight: 900,
                    borderRadius: "2px",
                    boxShadow: "0 10px 30px rgba(0,0,0,0.16)",
                  }}
                >
                  {l}
                </div>
              ))}

              <div
                style={{
                  backgroundColor: themeColors.cardBg,
                  color: themeColors.cardText,
                  borderRadius: "14px",
                  padding: "16px 32px",
                  display: "flex",
                  alignItems: "center",
                  gap: "14px",
                  marginTop: "-6px", // Overlap
                  boxShadow: "0 12px 32px rgba(0,0,0,0.15)",
                  transform: `translateY(${badgeTranslateY}px) scale(${badgeScale})`,
                  transformOrigin: "center center",
                }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: "10px",
                    backgroundColor: themeColors.accent,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#FFFFFF",
                  }}
                >
                  <IconComp size={28} />
                </div>
                {activeScene.badgeLabel && (
                  <span style={{ fontSize: "26px", fontWeight: 800 }}>
                    {activeScene.badgeLabel}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* =========================================================
          TRANSFORMATIONAL MORPHING PLANE (TRANSFORM -> BECOME)
          Sweeps across in the final frames of current scene,
          becoming the background canvas of the incoming scene!
          ========================================================= */}
      {inTransition && nextThemeColors && (
        <AbsoluteFill
          style={{
            backgroundColor: nextThemeColors,
            clipPath: `inset(0 0 0 ${morphWipeInset}%)`,
            zIndex: 30,
            pointerEvents: "none",
          }}
        />
      )}

      {/* Subtle bottom timeline progress indicator */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          height: "6px",
          backgroundColor: themeColors.accent,
          width: `${Math.min(100, (frame / durationInFrames) * 100)}%`,
          zIndex: 40,
        }}
      />
    </AbsoluteFill>
  );
};
