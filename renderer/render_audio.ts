import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { RenderInputError } from "./render_contract";

const run = promisify(execFile);

export async function prepareAudio(source: unknown, directory: string, port: number) {
  if (source === undefined || source === null || source === "") return { uri: "", cleanup: async () => {} };
  if (typeof source !== "string") throw new RenderInputError("audioSrc must be a string");
  if (/^https?:\/\//.test(source)) return { uri: source, cleanup: async () => {} };
  const input = path.resolve(source);
  const stat = await fs.stat(input).catch(() => null);
  if (!stat?.isFile()) throw new RenderInputError("Audio input is missing or is not a file");
  const name = `audio-${randomUUID()}.wav`;
  const output = path.join(directory, name);
  const cleanup = async () => { await fs.rm(output, { force: true }); };
  try {
    await run("ffmpeg", ["-nostdin", "-v", "error", "-y", "-i", input, "-ar", "44100", "-ac", "2", output],
      { timeout: 120000, maxBuffer: 1024 * 1024 });
  } catch (error) {
    await cleanup();
    throw new Error(`Audio conversion failed: ${error instanceof Error ? error.message : String(error)}`);
  }
  return { uri: `http://127.0.0.1:${port}/audio/${name}`, cleanup };
}
