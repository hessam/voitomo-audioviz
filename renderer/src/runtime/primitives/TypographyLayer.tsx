import React from "react";
import { RectBox } from "./AssetLayer";
import { TapeStrip, getLines } from "./TapeStrip";

export interface TypeSpecInput {
  text?: string;
  mode?: "impact_single" | "accumulating_stack";
  font_size?: number;
  weight?: string;
  tilt_angle?: number;
  is_hero?: boolean;
  words_count?: number;
}

export interface StackedLineItem {
  id: string;
  text: string;
  isHero: boolean;
  isCurrent: boolean;
  startFrame: number;
  durationInFrames: number;
  tiltAngle: number;
}

export function getFlattenedLadderLines(
  stackedScenes: Array<{ scene: any; isCurrent: boolean }>,
  maxLadderLines: number = 3
): StackedLineItem[] {
  const allLines: StackedLineItem[] = [];

  stackedScenes.forEach(({ scene: s, isCurrent }, sIdx) => {
    const sText =
      s.layers?.find((l: any) => l.is_hero || l.weight === "900")?.text ||
      s.layers?.[0]?.text ||
      s.content?.find((c: any) => c.is_hero)?.text ||
      s.content?.[0]?.text ||
      s.type?.text ||
      "";
    if (!sText) return;

    const sStart = s.frame_range?.[0] ?? 0;
    const currentEnd = stackedScenes.find((it) => it.isCurrent)?.scene?.frame_range?.[1];
    const sEnd = currentEnd ?? s.frame_range?.[1] ?? (sStart + 45);
    const sDuration = Math.max(1, sEnd - sStart);
    const isHero = s.layers?.some((l: any) => l.is_hero) || s.content?.some((c: any) => c.is_hero);
    const baseTilt = sIdx % 2 === 0 ? -1.2 : 1.2;

    // In accumulating ladder mode with multiple scenes, keep 1 punchy line per scene.
    // When standalone (single scene), allow up to 2 snug lines.
    const phraseLines = getLines(sText, stackedScenes.length > 1 ? 1 : 2, stackedScenes.length > 1);
    phraseLines.forEach((lineStr, lIdx) => {
      allLines.push({
        id: `${s.id || sIdx}_line_${lIdx}`,
        text: lineStr,
        isHero: Boolean(isHero),
        isCurrent,
        startFrame: sStart,
        durationInFrames: sDuration,
        tiltAngle: baseTilt + (lIdx % 2 === 0 ? 0 : 0.8),
      });
    });
  });

  // Strict Global Constraint: Never exceed 3 lines simultaneously in the ladder.
  // FIFO rolling window: oldest line rolls off when 4th line arrives.
  if (allLines.length > maxLadderLines) {
    return allLines.slice(-maxLadderLines);
  }
  return allLines;
}

export interface TypographyLayerProps {
  spec?: TypeSpecInput;
  box?: RectBox;
  saliency?: {
    hero_layer?: string;
    type_opacity?: number;
    type_scale?: number;
  };
  stackedScenes?: Array<{ scene: any; isCurrent: boolean }>;
  fontFamily?: string;
  palette?: any;
}

export const TypographyLayer: React.FC<TypographyLayerProps> = ({
  spec,
  box,
  saliency,
  stackedScenes = [],
  fontFamily = '"Vazirmatn", "Dana", sans-serif',
  palette,
}) => {
  const targetOpacity = saliency?.type_opacity ?? 1.0;
  const targetScale = saliency?.type_scale ?? 1.0;

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    top: "160px",
    left: "160px",
    right: "160px",
    bottom: "160px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: "calc(100% - 320px)",
    width: "calc(100% - 320px)",
    maxHeight: "760px",
    maxWidth: "760px",
    boxSizing: "border-box",
    textAlign: "center",
    direction: "rtl",
    zIndex: 10,
    opacity: targetOpacity,
    transform: `scale(${targetScale})`,
    transformOrigin: "center center",
  };

  if (stackedScenes.length === 0 && spec?.text) {
    // Single standalone phrase fallback
    return (
      <div style={containerStyle}>
        <TapeStrip
          text={spec.text}
          isBlack={false}
          isEmphasis={true}
          fontSize={84}
          fontFamily={fontFamily}
          tiltAngle={spec.tilt_angle || -1.5}
          tapeBg={palette?.tape_bg}
          tapeText={palette?.tape_text}
        />
      </div>
    );
  }

  const visibleLines = getFlattenedLadderLines(stackedScenes, 3);
  const lineCount = visibleLines.length;

  return (
    <div style={containerStyle}>
      {visibleLines.map((item, idx) => {
        // Dynamic Font Size & Vertical Spacing based on total line count
        let resolvedFontSize = 58;
        let resolvedMargin = "6px 0";

        if (lineCount === 1) {
          resolvedFontSize = item.isHero ? 84 : 64;
          resolvedMargin = item.isHero ? "12px 0" : "8px 0";
        } else if (lineCount === 2) {
          resolvedFontSize = item.isHero ? 72 : 54;
          resolvedMargin = item.isHero ? "8px 0" : "5px 0";
        } else {
          // 3 lines in stack: compact monumental hierarchy
          resolvedFontSize = item.isHero ? 62 : 46;
          resolvedMargin = item.isHero ? "5px 0" : "3px 0";
        }

        const isBlack = item.isHero || idx % 2 === 1;

        return (
          <TapeStrip
            key={item.id}
            text={item.text}
            isBlack={isBlack}
            isEmphasis={item.isHero}
            fontSize={resolvedFontSize}
            fontFamily={fontFamily}
            startFrame={item.startFrame}
            durationInFrames={item.durationInFrames}
            tiltAngle={item.tiltAngle}
            tapeBg={palette?.tape_bg}
            tapeText={palette?.tape_text}
            singleLine={true}
            style={{ margin: resolvedMargin }}
          />
        );
      })}
    </div>
  );
};
