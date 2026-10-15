import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { AudioMultibandFeatures, OnsetKind } from "../types/manifest";
import {
  OrreryMark, STEPS_PER_BEAT, barPosition, beatFraction, compileOrrery, markLevel, riffPosition, visibleMarks,
} from "./orreryModel";

/**
 * Polymeter Orrery: three dials that make rhythmic structure visible.
 *  - Bar ring: one turn per bar (segments = beats of the measured meter).
 *  - Riff ring: one turn per detected repeating pattern, so it drifts against the bar.
 *  - Beat ring: one turn per beat (four sixteenth-note steps).
 * Every hit stamps a mark where it truly falls on each dial: kick = deep notch, snare = bright
 * cut, cymbal = fine scratch. A ring with no evidence is not drawn. The central disc is kept clear
 * for lyrics. SVG, not WebGL: it captures reliably and every frame is a pure function of the manifest.
 */
const CENTER = { x: 960, y: 480 };
const RINGS = { bar: 400, riff: 325, beat: 255 } as const;
const HALF_BAND = 22;
const COLORS: Record<OnsetKind, string> = { kick: "#ff5a36", snare: "#ffe8b0", cymbal: "#7fd4ff", other: "#b9c0cf" };
const WIDTH: Record<OnsetKind, number> = { kick: 13, snare: 5.5, cymbal: 2.4, other: 3.5 };
const REACH: Record<OnsetKind, number> = { kick: 1.0, snare: 1.15, cymbal: 0.6, other: 0.7 };
const GRID = "#3a4150";
const TRACK = "#0d1016";
const HAND = "#f4f6fb";

const angle = (position: number) => 2 * Math.PI * position - Math.PI / 2;
const polar = (radius: number, position: number) => ({
  x: CENTER.x + radius * Math.cos(angle(position)),
  y: CENTER.y + radius * Math.sin(angle(position)),
});

function radial(radius: number, position: number, inner: number, outer: number) {
  const a = polar(radius + inner, position), b = polar(radius + outer, position);
  return { x1: a.x, y1: a.y, x2: b.x, y2: b.y };
}

function arcPath(radius: number, from: number, to: number) {
  const a = polar(radius, from), b = polar(radius, to);
  const sweep = to - from;
  return `M ${a.x} ${a.y} A ${radius} ${radius} 0 ${sweep > 0.5 ? 1 : 0} 1 ${b.x} ${b.y}`;
}

interface Props {
  features: AudioMultibandFeatures;
  intensity?: number;
}

export const PolymeterOrreryVisualizer: React.FC<Props> = ({ features, intensity = 1 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const model = useMemo(() => compileOrrery(features, fps, durationInFrames), [features, fps, durationInFrames]);
  const drive = Number.isFinite(intensity) ? Math.max(0, Math.min(2, intensity)) : 1;

  const bar = barPosition(model, frame);
  const riff = riffPosition(model, frame);
  const beat = beatFraction(model, frame);
  const marks = visibleMarks(model, frame);

  const showBar = model.beatsPerBar !== null;
  const showRiff = model.riff !== null;
  const aligned = bar !== null && riff !== null &&
    Math.min(bar, 1 - bar) < 0.015 && Math.min(riff, 1 - riff) < 0.015;

  const ringTicks = (radius: number, count: number, long: number) =>
    Array.from({ length: count }, (_, i) => {
      const line = radial(radius, i / count, -long, long);
      return <line key={i} {...line} stroke={GRID} strokeWidth={i === 0 ? 3 : 1.5} />;
    });

  const positionOf = (mark: OrreryMark, ring: "bar" | "riff" | "beat") =>
    ring === "bar" ? mark.barPosition : ring === "riff" ? mark.riffPosition : mark.beatFraction;

  const markLines = (ring: "bar" | "riff" | "beat") => {
    const radius = RINGS[ring];
    return (["kick", "snare", "cymbal", "other"] as OnsetKind[]).map(kind => (
      <g key={kind} style={{ filter: `drop-shadow(0 0 ${kind === "cymbal" ? 3 : 7}px ${COLORS[kind]})` }}>
        {marks.filter(m => m.kind === kind).map(mark => {
          const position = positionOf(mark, ring);
          const level = markLevel(model, mark, frame) * drive;
          if (position === null || level < 0.02) return null;
          const reach = HALF_BAND * REACH[kind];
          return (
            <line key={`${mark.frame}-${ring}`} {...radial(radius, position, -reach, reach)}
              stroke={COLORS[kind]} strokeWidth={WIDTH[kind]} strokeLinecap="round"
              opacity={Math.min(1, level)} />
          );
        })}
      </g>
    ));
  };

  const hand = (ring: "bar" | "riff" | "beat", position: number | null) => {
    if (position === null) return null;
    const radius = RINGS[ring];
    return (
      <g key={`hand-${ring}`}>
        <path d={arcPath(radius, Math.max(0, position - 0.05), Math.max(position, 0.0001))}
          stroke={HAND} strokeWidth={3} fill="none" opacity={0.16} strokeLinecap="round" />
        <line {...radial(radius, position, -HALF_BAND - 6, HALF_BAND + 6)} stroke={HAND} strokeWidth={2.5}
          strokeLinecap="round" opacity={0.9} />
      </g>
    );
  };

  const label = (text: string, radius: number, assumed = false) => (
    <text x={CENTER.x} y={CENTER.y - radius - 26} textAnchor="middle" fill={assumed ? "#9a8758" : "#7c869a"}
      fontSize={18} letterSpacing={4} fontFamily="Inter, Helvetica, Arial, sans-serif">{text}</text>
  );

  return (
    <svg width="100%" height="100%" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice"
      style={{ position: "absolute", top: 0, left: 0, background: "#050609" }}
      data-canvas={`${width}x${height}`}>
      <defs>
        <radialGradient id="orrery-bg" cx="50%" cy="46%" r="62%">
          <stop offset="0%" stopColor="#0b0d13" />
          <stop offset="100%" stopColor="#040507" />
        </radialGradient>
      </defs>
      <rect width="1920" height="1080" fill="url(#orrery-bg)" />

      {/* Dials with no evidence are simply not drawn. */}
      {showBar && (
        <g>
          <circle cx={CENTER.x} cy={CENTER.y} r={RINGS.bar} fill="none" stroke={TRACK} strokeWidth={HALF_BAND * 2} />
          <circle cx={CENTER.x} cy={CENTER.y} r={RINGS.bar} fill="none" stroke={GRID} strokeWidth={1.5}
            strokeDasharray={model.barAssumed ? "6 8" : undefined} />
          {ringTicks(RINGS.bar, model.beatsPerBar!, 12)}
          {label(`BAR · ${model.beatsPerBar} BEATS${model.barAssumed ? " (ASSUMED)" : ""}`, RINGS.bar, model.barAssumed)}
          {markLines("bar")}
          {hand("bar", bar)}
        </g>
      )}
      {showRiff && (
        <g>
          <circle cx={CENTER.x} cy={CENTER.y} r={RINGS.riff} fill="none" stroke={TRACK} strokeWidth={HALF_BAND * 2} />
          <circle cx={CENTER.x} cy={CENTER.y} r={RINGS.riff} fill="none" stroke={GRID} strokeWidth={1.5} />
          {ringTicks(RINGS.riff, model.riff!.lengthSteps, 8)}
          {label(`RIFF · ${model.riff!.lengthSteps} STEPS`, RINGS.riff)}
          {markLines("riff")}
          {hand("riff", riff)}
        </g>
      )}
      <g>
        <circle cx={CENTER.x} cy={CENTER.y} r={RINGS.beat} fill="none" stroke={TRACK} strokeWidth={HALF_BAND * 2} />
        <circle cx={CENTER.x} cy={CENTER.y} r={RINGS.beat} fill="none" stroke={GRID} strokeWidth={1.5} />
        {ringTicks(RINGS.beat, STEPS_PER_BEAT, 10)}
        {label(model.synced ? "BEAT" : "NO BEAT GRID · HITS ONLY", RINGS.beat)}
        {markLines("beat")}
        {hand("beat", beat)}
      </g>

      {aligned && (
        <circle cx={polar(RINGS.bar, 0).x} cy={polar(RINGS.bar, 0).y} r={13} fill="none" stroke={HAND}
          strokeWidth={3} opacity={0.85} style={{ filter: `drop-shadow(0 0 10px ${HAND})` }} />
      )}
    </svg>
  );
};
