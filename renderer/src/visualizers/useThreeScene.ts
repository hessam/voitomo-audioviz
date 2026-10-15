import { DependencyList, RefObject, useLayoutEffect, useRef, useState } from "react";
import { cancelRender, continueRender, delayRender, useCurrentFrame, useVideoConfig } from "remotion";

export interface SceneContext {
  canvas: HTMLCanvasElement;
  width: number;
  height: number;
  fps: number;
  frameCount: number;
}

export interface SceneHandle {
  /** Update uniforms for `frame` and draw. Must be a pure function of the frame (seek-safe). */
  draw(frame: number): void;
  /** Release every GPU resource. */
  dispose(): void;
}

/**
 * Shared WebGL scene lifecycle for styles built on three.js:
 * allocate the canvas at an explicit size, build seeded geometry, draw the requested frame, and only
 * then release the render blocker. Per-frame draws happen in a layout effect so the captured frame
 * always contains them. A shader or context failure cancels the render with its message instead of
 * producing a silently blank video. Disposes on every exit.
 */
export function useThreeScene(build: (ctx: SceneContext) => SceneHandle, deps: DependencyList): RefObject<HTMLCanvasElement> {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<SceneHandle | null>(null);
  const frame = useCurrentFrame();
  const { width, height, fps, durationInFrames } = useVideoConfig();
  const [blocker] = useState(() => delayRender("Build WebGL scene"));

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      handleRef.current = build({ canvas, width, height, fps, frameCount: durationInFrames });
      handleRef.current.draw(frame);
      continueRender(blocker);
    } catch (error) {
      cancelRender(error);
    }
    return () => {
      handleRef.current?.dispose();
      handleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height, fps, durationInFrames, ...deps]);

  useLayoutEffect(() => {
    handleRef.current?.draw(frame);
  }, [frame]);

  return canvasRef;
}
