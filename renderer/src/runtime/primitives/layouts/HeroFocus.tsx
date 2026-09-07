import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { GlitchDecode } from "../reveals/GlitchDecode";
import { BlockWipe } from "../reveals/BlockWipe";

export interface HeroFocusProps {
  content: Array<{ text: string; weight?: string; is_hero?: boolean }>;
  reveal: {
    primitive?: string;
    channel_offset_px?: number;
    stagger_frames?: number;
    direction?: "forward" | "reverse";
  };
  designSystem: {
    palette: { bg: string; fg: string; accent: string; muted: string };
    type_scale: { family: string; weights: string[]; ratio: number };
    grid: { alignment: string; margin: number };
  };
  startFrame: number;
  endFrame: number;
  currentTime?: number;
  words?: Array<{ word: string; start: number; end: number }>;
  isExiting?: boolean;
}

export const HeroFocus: React.FC<HeroFocusProps> = ({
  content,
  reveal,
  designSystem,
  startFrame,
  endFrame,
  currentTime = 0,
  words = [],
  isExiting = false,
}) => {
  const frame = useCurrentFrame();
  const sceneFrame = Math.max(0, frame - startFrame);
  const totalSceneFrames = Math.max(1, endFrame - startFrame);

  // Reveal takes first 20 frames
  const revealDuration = Math.min(20, Math.max(10, Math.round(totalSceneFrames * 0.25)));
  const progress = isExiting
    ? interpolate(sceneFrame, [totalSceneFrames - 15, totalSceneFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : interpolate(sceneFrame, [0, revealDuration], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  const fontFamily = designSystem?.type_scale?.family || "Vazirmatn, sans-serif";
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const mutedColor = designSystem.palette.muted;
  const alignment = designSystem.grid.alignment || "left";
  const margin = designSystem.grid.margin || 80;

  // Split content into Eyebrow (lead) and Hero Title (punch)
  const hasEyebrow = content.length >= 2;
  const eyebrowText = hasEyebrow ? content[0].text : "";
  const heroLines = hasEyebrow ? content.slice(1) : content;
  const heroText = heroLines.map((c) => c.text).join(" ") || " ";

  const isRtl = /[\u0600-\u06FF]/.test(heroText + eyebrowText);

  // Dynamic font size: keep it massive for true Swiss impact
  const heroLength = heroText.length;
  const heroFontSize = heroLength <= 18 ? 88 : heroLength <= 36 ? 74 : heroLength <= 60 ? 62 : 52;

  // Helper to render text with live audio word-level illumination
  const renderInteractiveWords = (fullText: string, defaultColor: string, baseWeight: string | number) => {
    const tokens = fullText.split(/\s+/).filter(Boolean);
    if (!words || words.length === 0 || tokens.length === 0) {
      return <span>{fullText}</span>;
    }

    return (
      <span>
        {tokens.map((token, i) => {
          // Clean punctuation for matching
          const cleanToken = token.replace(/[.,?!،؟]/g, "").trim();
          const match = words.find((w) => {
            const cleanW = w.word.replace(/[.,?!،؟]/g, "").trim();
            return cleanW === cleanToken && currentTime >= w.start - 0.2 && currentTime <= w.end + 0.6;
          });

          const isCurrent = match && currentTime >= match.start && currentTime <= match.end;
          const isPast = match && currentTime > match.end;

          let tokenColor = defaultColor;
          let opacity = 0.55;
          let textShadow = "none";

          if (isCurrent) {
            tokenColor = accentColor;
            opacity = 1.0;
            textShadow = `0 0 20px ${accentColor}88`;
          } else if (isPast) {
            tokenColor = defaultColor;
            opacity = 1.0;
          }

          return (
            <span
              key={i}
              style={{
                color: tokenColor,
                opacity,
                textShadow,
                transition: "color 0.15s ease, opacity 0.15s ease",
                marginRight: isRtl ? "0" : "0.25em",
                marginLeft: isRtl ? "0.25em" : "0",
                display: "inline-block",
              }}
            >
              {token}
            </span>
          );
        })}
      </span>
    );
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: alignment === "center" ? "center" : isRtl ? "flex-end" : "flex-start",
        padding: `${margin}px`,
        boxSizing: "border-box",
        direction: isRtl ? "rtl" : "ltr",
        gap: "20px",
      }}
    >
      {/* Eyebrow / Context Lead */}
      {hasEyebrow && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontFamily,
            fontSize: 32,
            fontWeight: 500,
            color: mutedColor,
            letterSpacing: "-0.01em",
            opacity: Math.min(1, progress * 1.5),
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: accentColor,
              display: "inline-block",
            }}
          />
          {eyebrowText}
        </div>
      )}

      {/* Hero Massive Punch */}
      {reveal.primitive === "block_wipe" ? (
        <BlockWipe
          text={heroText}
          progress={progress}
          color={fgColor}
          accentColor={accentColor}
          fontFamily={fontFamily}
          fontWeight={900}
          fontSize={heroFontSize}
        />
      ) : (
        <GlitchDecode
          text={heroText}
          progress={progress}
          channelOffsetPx={reveal.channel_offset_px ?? 6}
          color={fgColor}
          accentColor={accentColor}
          fontFamily={fontFamily}
          fontWeight={900}
          fontSize={heroFontSize}
          direction={isExiting ? "reverse" : reveal.direction}
        >
          {renderInteractiveWords(heroText, fgColor, 900)}
        </GlitchDecode>
      )}
    </div>
  );
};
