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
    left: box?.x !== undefined ? `${box.x}px` : "60px",
    top: box?.y !== undefined ? `${box.y}px` : "140px",
    width: box?.w !== undefined ? `${box.w}px` : "960px",
    height: box?.h !== undefined ? `${box.h}px` : "800px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
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
          fontSize={spec.font_size || 84}
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
          s.content?.find((c: any) => c.is_hero)?.text ||
          s.content?.[0]?.text ||
          s.type?.text ||
          "";
        if (!sText) return null;
        const sStart = s.frame_range?.[0] ?? 0;

        // Dynamic 72px - 96px bold typography sizing
        const baseSize =
          stackedScenes.length > 2 ? 72 : stackedScenes.length === 2 ? 84 : 96;
        const fontSize = sText.length > 24 ? baseSize - 12 : baseSize;
        const tiltAngle = idx % 2 === 0 ? -1.5 : 1.5;

        return (
          <TapeStrip
            key={s.id || idx}
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
  );
};
