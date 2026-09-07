import React from "react";
import { interpolate, spring, useCurrentFrame } from "remotion";

export interface TapeStripProps {
  text: string;
  isBlack?: boolean;
  isEmphasis?: boolean;
  fontSize?: number | string | "body" | "emphasis" | "compact";
  startFrame?: number;
  durationInFrames?: number;
  stressFrame?: number;
  fontFamily?: string;
  style?: React.CSSProperties;
  className?: string;
  tiltAngle?: number;
  tapeBg?: string;
  tapeText?: string;
  singleLine?: boolean;
  maxLines?: number;
}

export function getLines(text: string, maxLines: number = 2, forceSingleLine: boolean = false): string[] {
  if (!text) return [];
  if (text.includes("\n")) {
    const split = text.split("\n").map((l) => l.trim()).filter(Boolean);
    return split.slice(0, maxLines);
  }
  if (forceSingleLine) {
    return [text.trim()];
  }
  const words = text.trim().split(/\s+/);
  // Concise punchy phrase (up to 5 words and <= 32 chars): single snug strip
  if (words.length <= 5 && text.length <= 32) {
    return [text.trim()];
  }
  // Up to 8 words: 2 balanced snug lines
  if (words.length <= 8 || maxLines <= 2) {
    const mid = Math.ceil(words.length / 2);
    return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
  }
  // 9+ words: up to maxLines
  const lines: string[] = [];
  const chunkSize = Math.ceil(words.length / maxLines);
  for (let i = 0; i < words.length && lines.length < maxLines; i += chunkSize) {
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
  tapeBg,
  tapeText,
  singleLine = false,
  maxLines = 2,
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  const lines = getLines(text, maxLines, singleLine);

  // Dynamic Type System (Compact = 46/66px, Body = 58px, Emphasis = 84px)
  const isEmphasisResolved =
    isEmphasis === true ||
    fontSize === "emphasis" ||
    fontSize === 84 ||
    (typeof fontSize === "number" && fontSize >= 75);

  let resolvedFontSize = 58;
  if (fontSize === "compact") {
    resolvedFontSize = isEmphasisResolved ? 66 : 46;
  } else if (typeof fontSize === "number") {
    resolvedFontSize = fontSize;
  } else if (isEmphasisResolved) {
    resolvedFontSize = 84;
  }

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

        const isCompact = resolvedFontSize <= 52;
        const isMedium = resolvedFontSize <= 72;
        const lineMargin = isCompact ? "2px 0" : isMedium ? "4px 0" : "6px 0";
        const shadowOffset = isCompact ? "6px 6px 0px 0px #000000" : isMedium ? "8px 8px 0px 0px #000000" : "10px 10px 0px 0px #000000";
        const textPadding = isCompact ? "8px 20px 10px" : isMedium ? "10px 24px 14px" : "14px 32px 18px";
        const bgResolved = isThisLineBlack ? "#000000" : (tapeBg || "#FFFFFF");
        const textResolved = isThisLineBlack ? "#FFFFFF" : (tapeText || "#000000");

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
              margin: lineMargin,
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
                background: bgResolved,
                boxShadow: shadowOffset,
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
                color: textResolved,
                padding: textPadding,
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


