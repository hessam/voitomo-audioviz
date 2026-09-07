import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { GlitchDecode } from "../reveals/GlitchDecode";
import { BlockWipe } from "../reveals/BlockWipe";

export interface ParagraphStackProps {
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

export const ParagraphStack: React.FC<ParagraphStackProps> = ({
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

  const fontFamily = designSystem?.type_scale?.family || "Vazirmatn, sans-serif";
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const mutedColor = designSystem.palette.muted;
  const margin = designSystem.grid.margin || 80;
  const alignment = designSystem.grid.alignment || "left";

  const isRtl = content.some((c) => /[\u0600-\u06FF]/.test(c.text));
  const stagger = reveal.stagger_frames ?? 8;
  const lineDuration = 18;

  // Compute font size based on lines count and max line length
  const lineCount = Math.max(1, content.length);
  const maxLineLen = Math.max(...content.map((c) => c.text.length), 10);
  const fontSize = maxLineLen <= 20 && lineCount <= 3 ? 64 : maxLineLen <= 35 ? 52 : 44;

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
        gap: "28px",
      }}
    >
      {/* Editorial Marker */}
      <div
        style={{
          fontFamily,
          fontSize: 22,
          fontWeight: 700,
          color: mutedColor,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span style={{ width: "12px", height: "2px", backgroundColor: accentColor, display: "inline-block" }} />
        EDITORIAL STATEMENT // 0{lineCount}
      </div>

      {content.map((item, idx) => {
        const lineStart = idx * stagger;
        const progress = isExiting
          ? interpolate(sceneFrame, [totalSceneFrames - 15, totalSceneFrames], [1, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          : interpolate(sceneFrame, [lineStart, lineStart + lineDuration], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

        const weight = item.weight || (idx === content.length - 1 ? "900" : "500");
        const isLast = idx === content.length - 1;
        const lineColor = isLast ? fgColor : fgColor;

        return (
          <div
            key={idx}
            style={{
              width: "100%",
              position: "relative",
              paddingLeft: !isRtl ? "20px" : 0,
              paddingRight: isRtl ? "20px" : 0,
              borderLeft: !isRtl ? `3px solid ${isLast ? accentColor : `${mutedColor}44`}` : "none",
              borderRight: isRtl ? `3px solid ${isLast ? accentColor : `${mutedColor}44`}` : "none",
            }}
          >
            {reveal.primitive === "block_wipe" ? (
              <BlockWipe
                text={item.text}
                progress={progress}
                color={lineColor}
                accentColor={accentColor}
                fontFamily={fontFamily}
                fontWeight={weight}
                fontSize={fontSize}
              />
            ) : (
              <GlitchDecode
                text={item.text}
                progress={progress}
                channelOffsetPx={reveal.channel_offset_px ?? 5}
                color={lineColor}
                accentColor={accentColor}
                fontFamily={fontFamily}
                fontWeight={weight}
                fontSize={fontSize}
                direction={isExiting ? "reverse" : reveal.direction}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
