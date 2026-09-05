import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface CaptionPanelProps {
  content: Array<{ text: string; weight?: string; is_hero?: boolean }>;
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

export const CaptionPanel: React.FC<CaptionPanelProps> = ({
  content,
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

  // Entrance and exit opacity transitions
  const opacity = isExiting
    ? interpolate(sceneFrame, [totalSceneFrames - 15, totalSceneFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : interpolate(sceneFrame, [0, 12], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  const fontFamily = designSystem.type_scale.family || "Vazirmatn, sans-serif";
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const mutedColor = designSystem.palette.muted;
  const margin = designSystem.grid.margin || 80;
  const alignment = designSystem.grid.alignment || "left";

  const isRtl = content.some((c) => /[\u0600-\u06FF]/.test(c.text));

  const leadLine = content.length > 0 ? content[0].text : "";
  const subLines = content.length > 1 ? content.slice(1) : [];

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
        opacity,
      }}
    >
      {/* Swiss Architectural Container Box */}
      <div
        style={{
          width: "100%",
          maxWidth: "880px",
          border: `1px solid ${mutedColor}33`,
          backgroundColor: `${designSystem.palette.bg}ee`,
          padding: "36px 40px",
          boxSizing: "border-box",
          position: "relative",
          display: "flex",
          flexDirection: "column",
          gap: "20px",
        }}
      >
        {/* Accent Corner Notches */}
        <div style={{ position: "absolute", top: -1, left: -1, width: 12, height: 12, borderTop: `2px solid ${accentColor}`, borderLeft: `2px solid ${accentColor}` }} />
        <div style={{ position: "absolute", top: -1, right: -1, width: 12, height: 12, borderTop: `2px solid ${accentColor}`, borderRight: `2px solid ${accentColor}` }} />
        <div style={{ position: "absolute", bottom: -1, left: -1, width: 12, height: 12, borderBottom: `2px solid ${accentColor}`, borderLeft: `2px solid ${accentColor}` }} />
        <div style={{ position: "absolute", bottom: -1, right: -1, width: 12, height: 12, borderBottom: `2px solid ${accentColor}`, borderRight: `2px solid ${accentColor}` }} />

        {/* Header Label */}
        <div
          style={{
            fontFamily,
            fontSize: 20,
            fontWeight: 700,
            color: accentColor,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>●</span>
          FACTUAL METADATA // VERIFIED
        </div>

        {/* Lead Bold Statement */}
        <div
          style={{
            fontFamily,
            fontSize: leadLine.length <= 25 ? 58 : 46,
            fontWeight: 900,
            color: fgColor,
            lineHeight: 1.15,
          }}
        >
          {leadLine}
        </div>

        {/* Supporting Small-caps Lines */}
        {subLines.map((line, idx) => (
          <div
            key={idx}
            style={{
              fontFamily,
              fontSize: 30,
              fontWeight: 500,
              color: mutedColor,
              lineHeight: 1.4,
              borderTop: `1px solid ${mutedColor}22`,
              paddingTop: "12px",
            }}
          >
            {line.text}
          </div>
        ))}
      </div>
    </div>
  );
};
