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
}

export const ParagraphStack: React.FC<ParagraphStackProps> = ({
  content,
  reveal,
  designSystem,
  startFrame,
  endFrame,
}) => {
  const frame = useCurrentFrame();
  const sceneFrame = Math.max(0, frame - startFrame);

  const fontFamily = designSystem.type_scale.family || "Vazirmatn, sans-serif";
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const margin = designSystem.grid.margin || 80;
  const alignment = designSystem.grid.alignment || "left";

  const isRtl = content.some((c) => /[\u0600-\u06FF]/.test(c.text));
  const stagger = reveal.stagger_frames ?? 6;
  const lineDuration = 16;

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
        gap: "24px",
      }}
    >
      {content.map((item, idx) => {
        const lineStart = idx * stagger;
        const progress = interpolate(sceneFrame, [lineStart, lineStart + lineDuration], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        const fontWeight = item.weight || (item.is_hero ? "900" : "500");
        const fontSize = item.is_hero ? 64 : 48;

        return (
          <div key={idx} style={{ maxWidth: "85%" }}>
            {reveal.primitive === "block_wipe" ? (
              <BlockWipe
                text={item.text}
                progress={progress}
                color={fgColor}
                accentColor={accentColor}
                fontFamily={fontFamily}
                fontWeight={fontWeight}
                fontSize={fontSize}
              />
            ) : (
              <GlitchDecode
                text={item.text}
                progress={progress}
                channelOffsetPx={reveal.channel_offset_px ?? 4}
                color={fgColor}
                accentColor={accentColor}
                fontFamily={fontFamily}
                fontWeight={fontWeight}
                fontSize={fontSize}
                direction={reveal.direction}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
