import React from "react";
import { RectBox } from "./AssetLayer";
import { TapeStrip } from "./TapeStrip";

export interface TypeSpecInput {
  text?: string;
  mode?: "impact_single" | "accumulating_stack";
  font_size?: number;
  weight?: string;
  tilt_angle?: number;
  is_hero?: boolean;
  words_count?: number;
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
}

export const TypographyLayer: React.FC<TypographyLayerProps> = ({
  spec,
  box,
  saliency,
  stackedScenes = [],
  fontFamily = '"Vazirmatn", "Dana", sans-serif',
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
        />
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {stackedScenes.map(({ scene: s, isCurrent }, idx) => {
        const sText =
          s.layers?.find((l: any) => l.is_hero || l.weight === "900")?.text ||
          s.layers?.[0]?.text ||
          s.content?.find((c: any) => c.is_hero)?.text ||
          s.content?.[0]?.text ||
          s.type?.text ||
          "";
        if (!sText) return null;
        const sStart = s.frame_range?.[0] ?? 0;
        const sEnd = s.frame_range?.[1] ?? (sStart + 45);
        const sDuration = Math.max(1, sEnd - sStart);

        // Law 1: Author only 2 font sizes: Body = 58px, Emphasis = 84px
        const isHero = s.layers?.some((l: any) => l.is_hero) || s.content?.some((c: any) => c.is_hero);
        const isEmphasis = isCurrent && isHero;
        // Inverted accent: Alternate white and black strips; emphasis punchlines get Black Tape!
        const isBlack = isHero || idx % 2 === 1;
        const fontSize = isHero ? 84 : 58;
        const tiltAngle = idx % 2 === 0 ? -1.2 : 1.2;

        return (
          <TapeStrip
            key={s.id || idx}
            text={sText}
            isBlack={isBlack}
            isEmphasis={isHero}
            fontSize={fontSize}
            fontFamily={fontFamily}
            startFrame={sStart}
            durationInFrames={sDuration}
            tiltAngle={tiltAngle}
            style={{ margin: isHero ? "10px 0" : "6px 0" }}
          />
        );

      })}
    </div>
  );
};
