import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { AudioMultibandFeatures } from "../types/manifest";
import { Body, compileBodies, modeAmplitudes, skinDisplacement, stringDisplacement } from "./bodiesModel";

/**
 * Resonant Bodies: each stem is drawn as the kind of object that makes the sound (bass: heavy string,
 * drums: skin, vocals: air column, other: string). A body vibrates in modes whose strength is that stem's
 * own spectrum, so bright or distorted sound looks jagged and clean sound looks smooth; strikes ring down
 * at each instrument's decay. A missing stem is not drawn. Lyrics sit in the band below the bodies.
 */
const CELLS = [
  { x: 0, y: 70, w: 960, h: 400 }, { x: 960, y: 70, w: 960, h: 400 },
  { x: 0, y: 470, w: 960, h: 400 }, { x: 960, y: 470, w: 960, h: 400 },
];
const COLORS: Record<string, string> = {
  bass: "#ff8a3d", drums: "#ff4d4d", vocals: "#7fe3ff", guitar: "#ffd166", other: "#c8b6ff", instrumental: "#ffd166", mix: "#e8e4d8",
};
const POINTS = 220;

const path = (pts: Array<[number, number]>, close = false) =>
  pts.map(([x, y], i) => `${i ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ") + (close ? " Z" : "");

const BodyShape: React.FC<{ body: Body; cell: typeof CELLS[number]; frame: number; seconds: number; drive: number }> =
  ({ body, cell, frame, seconds, drive }) => {
    const color = COLORS[body.stem] ?? "#e8e4d8";
    const amps = modeAmplitudes(body, frame).map(a => a * drive);
    const cx = cell.x + cell.w / 2, cy = cell.y + cell.h / 2 - 12;
    const glow = { filter: `drop-shadow(0 0 9px ${color})` };
    let shape: React.ReactNode;

    if (body.kind === "string" || body.kind === "heavyString") {
      const x0 = cell.x + 110, x1 = cell.x + cell.w - 110;
      const heavy = body.kind === "heavyString";
      const pts: Array<[number, number]> = Array.from({ length: POINTS + 1 }, (_, i) => {
        const u = i / POINTS;
        return [x0 + u * (x1 - x0), cy + stringDisplacement(amps, u, seconds) * (heavy ? 150 : 130)];
      });
      shape = (
        <g style={glow}>
          <path d={path(pts)} stroke={color} strokeWidth={heavy ? 22 : 9} opacity={0.16} fill="none" strokeLinecap="round" />
          <path d={path(pts)} stroke={color} strokeWidth={heavy ? 8 : 3.2} fill="none" strokeLinecap="round" />
          {[x0, x1].map(x => <rect key={x} x={x - 6} y={cy - 26} width={12} height={52} rx={3} fill="#2b303b" />)}
        </g>
      );
    } else if (body.kind === "skin") {
      const radius = 150;
      const ring = (scale: number, opacity: number, width: number) => {
        const pts: Array<[number, number]> = Array.from({ length: POINTS }, (_, i) => {
          const theta = (i / POINTS) * 2 * Math.PI;
          const r = radius * scale + 55 * skinDisplacement(amps, theta, seconds) * (0.4 + 0.6 * scale);
          return [cx + r * Math.cos(theta), cy + r * Math.sin(theta)];
        });
        return <path d={path(pts, true)} stroke={color} strokeWidth={width} fill="none" opacity={opacity} />;
      };
      shape = (
        <g style={glow}>
          <circle cx={cx} cy={cy} r={radius + 14} fill="none" stroke="#2b303b" strokeWidth={12} />
          {ring(1, 1, 4)}{ring(0.68, 0.55, 2.5)}{ring(0.36, 0.3, 2)}
        </g>
      );
    } else {
      const top = cell.y + 40, bottom = cell.y + cell.h - 60;
      const loud = amps.reduce((a, b) => a + b, 0) / amps.length;
      const edge = (sign: number): Array<[number, number]> => Array.from({ length: POINTS + 1 }, (_, i) => {
        const u = i / POINTS;
        const half = 26 + 120 * Math.min(1, loud) + 55 * Math.abs(stringDisplacement(amps, u, seconds));
        return [cx + sign * half * Math.sin(Math.PI * u) ** 0.6, top + u * (bottom - top)];
      });
      const left = edge(-1), right = edge(1).reverse();
      shape = (
        <g style={glow}>
          <path d={path([...left, ...right], true)} fill={color} opacity={0.14} />
          <path d={path(left)} stroke={color} strokeWidth={3.2} fill="none" />
          <path d={path(right)} stroke={color} strokeWidth={3.2} fill="none" />
        </g>
      );
    }
    return (
      <g>
        {shape}
        <text x={cell.x + cell.w / 2} y={cell.y + cell.h - 14} textAnchor="middle" fill="#7c869a" fontSize={17}
          letterSpacing={4} fontFamily="Inter, Helvetica, Arial, sans-serif">{body.label}</text>
      </g>
    );
  };

interface Props { features: AudioMultibandFeatures; intensity?: number }

export const ResonantBodiesVisualizer: React.FC<Props> = ({ features, intensity = 1 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const model = useMemo(() => compileBodies(features, fps, durationInFrames), [features, fps, durationInFrames]);
  const drive = Number.isFinite(intensity) ? Math.max(0, Math.min(2, intensity)) : 1;
  const caption = model.bodies.length === 0 ? "NO SPECTRAL DATA" : model.mixOnly ? "NO STEMS · SHOWING THE FULL MIX" : "";

  return (
    <svg width="100%" height="100%" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice"
      style={{ position: "absolute", top: 0, left: 0, background: "#050609" }}>
      <defs>
        <radialGradient id="bodies-bg" cx="50%" cy="38%" r="70%">
          <stop offset="0%" stopColor="#0c0e14" /><stop offset="100%" stopColor="#040507" />
        </radialGradient>
      </defs>
      <rect width="1920" height="1080" fill="url(#bodies-bg)" />
      <text x={64} y={64} fill="#7c869a" fontSize={18} letterSpacing={4} fontFamily="Inter, Helvetica, Arial, sans-serif">RESONANT BODIES</text>
      {caption && <text x={64} y={96} fill="#d9c692" fontSize={22} letterSpacing={3} fontFamily="Inter, Helvetica, Arial, sans-serif">{caption}</text>}
      {model.bodies.map((body, i) => (
        <BodyShape key={body.stem} body={body} cell={CELLS[model.bodies.length === 1 ? 0 : i]} frame={frame}
          seconds={frame / fps} drive={drive} />
      ))}
    </svg>
  );
};
