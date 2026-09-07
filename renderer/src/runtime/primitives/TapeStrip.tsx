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

export function getLines(text: string): string[] {
  if (!text) return [];
  if (text.includes("\n")) {
    return text.split("\n").map((l) => l.trim()).filter(Boolean);
  }
  const words = text.trim().split(/\s+/);
  // Short punchy phrase (1-3 words and <= 18 chars): single snug strip
  if (words.length <= 3 && text.length <= 18) {
    return [text.trim()];
  }
  // If 4-5 words: 2 balanced snug lines
  if (words.length <= 5) {
    const mid = Math.ceil(words.length / 2);
    return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
  }
  // If 6+ words: 2 or 3 lines of 2-3 words each
  const lines: string[] = [];
  const chunkSize = Math.ceil(words.length / (words.length >= 7 ? 3 : 2));
  for (let i = 0; i < words.length; i += chunkSize) {
    lines.push(words.slice(i, i + chunkSize).join(" "));
  }
  return lines;
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

  const lines = getLines(text);

  // Law 1: Strict 2-Size Type System (Body = 58px, Emphasis = 84px)
  const isEmphasisResolved =
    isEmphasis === true ||
    fontSize === "emphasis" ||
    fontSize === 84 ||
    (typeof fontSize === "number" && fontSize >= 75);
  const resolvedFontSize = isEmphasisResolved ? 84 : 58;

  // Law 2: Vocal Stress Morphing
  // Smooth 1.0 -> 1.08 -> 1.0 scale pulse around vocal stress peak
  const targetStressFrame =
    stressFrame ?? (startFrame + Math.min(16, Math.max(6, Math.floor(durationInFrames * 0.4))));
  const stressScale = interpolate(
    frame,
    [targetStressFrame - 5, targetStressFrame, targetStressFrame + 5],
    [1.0, 1.08, 1.0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Law 6: Clean Scene Clears Before Color Cuts
  const framesLeft = durationInFrames > 0 ? durationInFrames - relFrame : 999;
  const exitOpacity = interpolate(framesLeft, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitZoom = interpolate(framesLeft, [0, 6], [1.06, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        opacity: exitOpacity,
        ...style,
      }}
      className={className}
    >
      {lines.map((lineText, lineIdx) => {
        // Individual line stagger: each line snaps into place with a 3-frame delay
        const lineRelFrame = Math.max(0, relFrame - lineIdx * 3);

        // Decoupled horizontal tape stretch for THIS line
        const tapeProgress = spring({
          frame: lineRelFrame,
          fps: 30,
          config: { damping: 12, mass: 0.6, stiffness: 160 },
        });
        const tapeScaleX = interpolate(tapeProgress, [0, 1], [0, 1.0]);

        // Decoupled text zoom for THIS line
        const textProgress = interpolate(lineRelFrame, [0, 8], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const textZoom = interpolate(textProgress, [0, 1], [1.15, 1.0]);

        const enterOpacity = interpolate(lineRelFrame, [0, 3], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        // Task 2: Inverted Accent Tape Strips
        // Alternate between White and Black tape strips; emphasis punchlines get Black Tape!
        const isThisLineBlack = isEmphasisResolved
          ? true
          : isBlack
          ? lineIdx % 2 === 0
          : lineIdx % 2 === 1;

        // Subtle alternating angle jitter (-0.8deg, +0.8deg) for tactile sticker look
        const lineTilt = tiltAngle + (lineIdx % 2 === 0 ? -0.8 : 0.8);

        return (
          <div
            key={`${lineIdx}_${lineText}`}
            className="tape-strip-line-wrapper"
            style={{
              position: "relative",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "fit-content",
              alignSelf: "center",
              margin: isEmphasisResolved ? "6px 0" : "4px 0",
              transform: `rotate(${lineTilt}deg)`,
              transformOrigin: "center center",
              opacity: enterOpacity,
            }}
          >
            {/* Snug hugging tape background with its OWN hard offset shadow */}
            <div
              aria-hidden="true"
              style={{
                position: "absolute",
                inset: 0,
                background: isThisLineBlack ? "#000000" : "#FFFFFF",
                boxShadow: "10px 10px 0px 0px #000000",
                transform: `scaleX(${tapeScaleX})`,
                transformOrigin: "center center",
                borderRadius: "0px",
                zIndex: 1,
              }}
            />

            {/* Tight hugging Persian text inside */}
            <span
              dir="rtl"
              lang="fa"
              className={`tape-strip ${isThisLineBlack ? "black" : ""}`}
              style={{
                position: "relative",
                zIndex: 2,
                display: "inline-block",
                transform: `scale(${textZoom * stressScale * exitZoom})`,
                transformOrigin: "center center",
                color: isThisLineBlack ? "#FFFFFF" : "#000000",
                padding: isEmphasisResolved ? "14px 32px 18px" : "10px 24px 14px",
                fontFamily,
                fontWeight: 800,
                fontSize: `${resolvedFontSize}px`,
                lineHeight: 1.35,
                direction: "rtl",
                unicodeBidi: "isolate",
                whiteSpace: "nowrap",
                wordBreak: "keep-all",
                textAlign: "center",
                letterSpacing: "normal",
                WebkitFontSmoothing: "antialiased",
              }}
            >
              {lineText}
            </span>
          </div>
        );
      })}
    </div>
  );
};


