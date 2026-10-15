import { LyricLine, LyricMode } from "../types/manifest";

/** Show a line this many frames before its first word so it can be read (about 400 ms at 30 FPS). Starting value to tune. */
export const LEAD_IN_FRAMES = 12;
/** Keep a finished line this long while it fades. */
export const HOLD_FRAMES = 10;
const FADE_IN_FRAMES = 6;
/** Words aligned with less confidence than this are highlighted at line level, not with a fake sweep. */
export const MIN_PRECISE_SCORE = 0.35;
const PERSIAN = /[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/;

export interface WordState {
  text: string;
  /** 0..1 fill of the word */
  progress: number;
  /** True when the word's own timing is trusted enough to sweep */
  precise: boolean;
  /** Fill direction: Persian words fill right to left, Latin words left to right */
  rtl: boolean;
}

export interface VisibleLine {
  key: string;
  words: WordState[];
  opacity: number;
  current: boolean;
  isHero: boolean;
}

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export function isPersian(text: string): boolean {
  return PERSIAN.test(text);
}

/**
 * Lines to draw at `frame`, oldest first (at most two). `subtitles` highlights whole lines;
 * `video` sweeps each word with its own timing where that timing is trusted.
 */
export function visibleLines(lines: LyricLine[], frame: number, mode: LyricMode): VisibleLine[] {
  if (mode === "off" || !lines.length) return [];
  const alive = lines
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => frame >= line.startFrame - LEAD_IN_FRAMES && frame <= line.endFrame + HOLD_FRAMES)
    .slice(-2);
  return alive.map(({ line, index }, position) => {
    const current = position === alive.length - 1;
    const fadeIn = clamp01((frame - (line.startFrame - LEAD_IN_FRAMES)) / FADE_IN_FRAMES);
    const fadeOut = frame <= line.endFrame ? 1 : clamp01(1 - (frame - line.endFrame) / HOLD_FRAMES);
    const opacity = current ? fadeIn * fadeOut : Math.min(0.5, 0.5 * fadeOut);
    const timed = (line.words ?? []).filter(w => w.word.trim().length > 0);
    const words: WordState[] = timed.length
      ? timed.map(w => {
          const precise = mode === "video" && !w.isInterpolated && (w.score ?? 1) >= MIN_PRECISE_SCORE;
          const progress = precise
            ? clamp01((frame - w.startFrame) / Math.max(1, w.endFrame - w.startFrame))
            : frame >= (mode === "video" ? w.startFrame : line.startFrame) ? 1 : 0;
          return { text: w.word.trim(), progress, precise, rtl: isPersian(w.word) };
        })
      : line.text.trim().split(/\s+/).map(text => ({
          text, progress: frame >= line.startFrame ? 1 : 0, precise: false, rtl: isPersian(text),
        }));
    return { key: `${index}-${line.startFrame}`, words, opacity, current, isHero: Boolean(line.isHero) };
  });
}
