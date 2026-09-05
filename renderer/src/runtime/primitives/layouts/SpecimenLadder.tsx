import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { GlitchDecode } from "../reveals/GlitchDecode";
import { BlockWipe } from "../reveals/BlockWipe";

export interface SpecimenLadderProps {
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

export const SpecimenLadder: React.FC<SpecimenLadderProps> = ({
  content,
  reveal,
  designSystem,
  startFrame,
  endFrame,
}) => {
  const frame = useCurrentFrame();
  const sceneFrame = Math.max(0, frame - startFrame);

  const fontFamily = designSystem.type_scale.family || "Vazirmatn, sans-serif";
  const defaultWeights = designSystem.type_scale.weights || ["300", "500", "700", "900"];
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const mutedColor = designSystem.palette.muted;
  const margin = designSystem.grid.margin || 80;
  const alignment = designSystem.grid.alignment || "left";

  // Build rows dynamically
  let rows: Array<{ text: string; weight: string; isHero: boolean }> = [];
  if (content.length > 1) {
    rows = content.map((c, i) => ({
      text: c.text,
      weight: c.weight || defaultWeights[i % defaultWeights.length],
      isHero: !!c.is_hero,
    }));
  } else if (content.length === 1) {
    // Single emphasis keyword repeated across escalating weights
    const text = content[0].text;
    rows = defaultWeights.map((w, i) => ({
      text,
      weight: w,
      isHero: i === defaultWeights.length - 1,
    }));
  }

  const stagger = reveal.stagger_frames ?? 6;
  const rowDuration = 14;
  const isRtl = rows.some((r) => /[\u0600-\u06FF]/.test(r.text));

  // Determine font size to fit vertical ladder comfortably
  const rowCount = Math.max(1, rows.length);
  const fontSize = rowCount >= 5 ? 54 : rowCount >= 4 ? 64 : 76;

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
        gap: `${Math.max(8, 28 - rowCount * 3)}px`,
      }}
    >
      {rows.map((row, idx) => {
        const rowStart = idx * stagger;
        const progress = interpolate(sceneFrame, [rowStart, rowStart + rowDuration], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        const rowColor = row.isHero ? fgColor : idx === 0 ? mutedColor : fgColor;

        return (
          <div key={idx} style={{ width: "100%" }}>
            {reveal.primitive === "block_wipe" ? (
              <BlockWipe
                text={row.text}
                progress={progress}
                color={rowColor}
                accentColor={accentColor}
                fontFamily={fontFamily}
                fontWeight={row.weight}
                fontSize={fontSize}
              />
            ) : (
              <GlitchDecode
                text={row.text}
                progress={progress}
                channelOffsetPx={reveal.channel_offset_px ?? 5}
                color={rowColor}
                accentColor={accentColor}
                fontFamily={fontFamily}
                fontWeight={row.weight}
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
