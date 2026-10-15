import React, { useEffect, useState } from "react";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import { LyricLine, LyricMode } from "../types/manifest";
import { VisibleLine, WordState, visibleLines } from "./lyricModel";

/**
 * Shared Persian lyric layer for every style.
 *  - subtitles: the line sits near the bottom and lights up as a whole.
 *  - video: lyrics lead; each word fills right to left over its own aligned time (Latin words fill
 *    left to right), and the line appears about 400 ms early so it can be read.
 * Each word is ONE element (never split into letters), so Persian letters keep their joins.
 * Region "center" puts the text in the middle (for styles that keep a clear disc for it).
 */
export type LyricRegion = "bottom" | "center";

const FONT_STACK = '"Vazirmatn", "Dana", sans-serif';
const BASE = "#6b7389";
const FILL = "#ffffff";

const Word: React.FC<{ word: WordState; weight: number }> = ({ word, weight }) => {
  const reveal = 1 - word.progress;
  const clip = word.rtl ? `inset(0 0 0 ${reveal * 100}%)` : `inset(0 ${reveal * 100}% 0 0)`;
  const text = word.rtl ? word.text : <bdi dir="ltr">{word.text}</bdi>;
  return (
    <span style={{ position: "relative", display: "inline-block", unicodeBidi: "isolate", fontWeight: weight }}>
      <span style={{ color: BASE }}>{text}</span>
      <span aria-hidden style={{
        position: "absolute", inset: 0, color: FILL, clipPath: clip, WebkitClipPath: clip,
        textShadow: "0 0 22px rgba(255,255,255,0.35)",
      }}>{text}</span>
    </span>
  );
};

const Line: React.FC<{ line: VisibleLine; size: number }> = ({ line, size }) => (
  <div dir="rtl" style={{
    display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 0.32em", opacity: line.opacity,
    fontSize: line.current ? size : size * 0.72, lineHeight: 1.55, fontFamily: FONT_STACK,
    textShadow: "0 3px 22px rgba(0,0,0,0.95)",
  }}>
    {line.words.map((word, i) => <Word key={i} word={word} weight={line.isHero ? 900 : 700} />)}
  </div>
);

interface Props { lines: LyricLine[]; mode: LyricMode; region?: LyricRegion }

export const LyricLayer: React.FC<Props> = ({ lines, mode, region = "bottom" }) => {
  const frame = useCurrentFrame();
  const [fontBlocker] = useState(() => delayRender("Load Persian lyric font"));
  useEffect(() => {
    const done = () => continueRender(fontBlocker);
    if (typeof document === "undefined" || !document.fonts) { done(); return; }
    Promise.all(["500", "700", "900"].map(w => document.fonts.load(`${w} 40px Vazirmatn`))).then(done, done);
  }, [fontBlocker]);

  const shown = visibleLines(lines, frame, mode);
  if (!shown.length) return null;
  const size = region === "center" ? 38 : mode === "video" ? 54 : 36;
  const box: React.CSSProperties = region === "center"
    ? { left: 960 - 215, width: 430, top: 480 - 120, height: 240, justifyContent: "center" }
    : { left: 96, right: 96, bottom: 70, justifyContent: "flex-end" };
  return (
    <div style={{ position: "absolute", display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
      pointerEvents: "none", zIndex: 50, ...box }}>
      {shown.map(line => <Line key={line.key} line={line} size={size} />)}
    </div>
  );
};
