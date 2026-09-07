import React from "react";
import { interpolate, spring, useCurrentFrame } from "remotion";

export interface TapeStripProps {
  text: string;
  isBlack?: boolean;
  isEmphasis?: boolean;
  fontSize?: number | string | "body" | "emphasis";
  startFrame?: number;
  durationInFrames?: number;
  stressFrame?: number;
  fontFamily?: string;
  style?: React.CSSProperties;
  className?: string;
  tiltAngle?: number;
}

export const TapeStrip: React.FC<TapeStripProps> = ({
  text,
  isBlack = false,
  isEmphasis = false,
  fontSize = 58,
  startFrame = 0,
  durationInFrames = 45,
  stressFrame,
  fontFamily = '"Vazirmatn", "Dana", sans-serif',
  style = {},
  className = "",
  tiltAngle = 0,
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  // Law 1: Strict 2-Size Type System (Body = 58px, Emphasis = 84px)
  const isEmphasisResolved =
    isEmphasis === true ||
    fontSize === "emphasis" ||
    fontSize === 84 ||
    (typeof fontSize === "number" && fontSize >= 75);
  const resolvedFontSize = isEmphasisResolved ? 84 : 58;

  // Law 2: Vocal Stress Morphing
  // Smooth 1.0 -> 1.08 -> 1.0 scale pulse around the vocal stress peak frame
  const targetStressFrame =
    stressFrame ?? (startFrame + Math.min(16, Math.max(6, Math.floor(durationInFrames * 0.4))));
  const stressScale = interpolate(
    frame,
    [targetStressFrame - 5, targetStressFrame, targetStressFrame + 5],
    [1.0, 1.08, 1.0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Law 4: Decoupled Tape-Reveal Physics
  // Rectangular tape stretches horizontally: scaleX(spring(progress, { damping: 12, stiffness: 160 }))
  const tapeProgress = spring({
    frame: relFrame,
    fps: 30,
    config: { damping: 12, mass: 0.6, stiffness: 160 },
  });
  const tapeScaleX = interpolate(tapeProgress, [0, 1], [0, 1.0]);

  // Persian text inside zooms out gently: scale(interpolate(progress, [0, 1], [1.15, 1.0]))
  const textProgress = interpolate(relFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const textZoom = interpolate(textProgress, [0, 1], [1.15, 1.0]);

  // Law 6: Zero-Edge-Bleed Motion Grammar & Clean Scene Clears Before Color Cuts
  // Outgoing text zooms-in/fades to opacity: 0 for 6 frames before scene ends
  const framesLeft = durationInFrames > 0 ? durationInFrames - relFrame : 999;
  const exitOpacity = interpolate(framesLeft, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitZoom = interpolate(framesLeft, [0, 6], [1.06, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const enterOpacity = interpolate(relFrame, [0, 4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const finalOpacity = enterOpacity * exitOpacity;

  return (
    <div
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        margin: isEmphasisResolved ? "14px 0" : "10px 0",
        transform: `rotate(${tiltAngle}deg)`,
        transformOrigin: "center center",
        opacity: finalOpacity,
        ...style,
      }}
      className={className}
    >
      {/* Decoupled Tape Background (Stretches horizontally with hard 12px shadow) */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          background: isBlack ? "#000000" : "#FFFFFF",
          boxShadow: "12px 12px 0px 0px #000000",
          transform: `scaleX(${tapeScaleX})`,
          transformOrigin: "center center",
          borderRadius: "0px",
          zIndex: 1,
        }}
      />

      {/* Decoupled Persian Text (Gentle zoom-out, vocal stress pulse, non-distorted typography) */}
      <span
        dir="rtl"
        lang="fa"
        className={`tape-strip-text ${isBlack ? "black" : ""}`}
        style={{
          position: "relative",
          zIndex: 2,
          display: "inline-block",
          transform: `scale(${textZoom * stressScale * exitZoom})`,
          transformOrigin: "center center",
          color: isBlack ? "#FFFFFF" : "#000000",
          padding: isEmphasisResolved ? "16px 36px 20px" : "12px 28px 16px",
          fontFamily,
          fontWeight: 800,
          fontSize: `${resolvedFontSize}px`,
          lineHeight: 1.45,
          direction: "rtl",
          unicodeBidi: "isolate",
          whiteSpace: "pre-wrap",
          wordBreak: "keep-all",
          maxWidth: "960px",
          textAlign: "center",
          letterSpacing: "normal",
          WebkitFontSmoothing: "antialiased",
        }}
      >
        {text}
      </span>
    </div>
  );
};

