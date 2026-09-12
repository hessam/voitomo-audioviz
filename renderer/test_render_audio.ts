import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { prepareAudio } from "./render_audio";

export function wav(seconds = 1): Buffer {
  const sampleRate = 44100;
  const dataSize = sampleRate * seconds * 2;
  const data = Buffer.alloc(44 + dataSize);
  data.write("RIFF", 0); data.writeUInt32LE(36 + dataSize, 4); data.write("WAVEfmt ", 8);
  data.writeUInt32LE(16, 16); data.writeUInt16LE(1, 20); data.writeUInt16LE(1, 22);
  data.writeUInt32LE(sampleRate, 24); data.writeUInt32LE(sampleRate * 2, 28);
  data.writeUInt16LE(2, 32); data.writeUInt16LE(16, 34); data.write("data", 36); data.writeUInt32LE(dataSize, 40);
  for (let i = 0; i < dataSize / 2; i++) data.writeInt16LE(Math.round(12000 * Math.sin(2 * Math.PI * 440 * i / sampleRate)), 44 + i * 2);
  return data;
}

test("real FFmpeg preserves duration and safely handles literal shell characters", async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "voitomo-audio-test-"));
  try {
    const input = path.join(directory, 'audio "$literal`name`.wav');
    await fs.writeFile(input, wav());
    let ticks = 0;
    const timer = setInterval(() => { ticks++; }, 1);
    const prepared = await prepareAudio(input, directory, 4001).finally(() => clearInterval(timer));
    assert.ok(ticks > 0, "conversion must release the event loop");
    const output = path.join(directory, path.basename(prepared.uri));
    const converted = await fs.readFile(output);
    assert.equal(converted.toString("ascii", 0, 4), "RIFF");
    const offset = converted.indexOf(Buffer.from("data"));
    assert.equal(converted.readUInt32LE(offset + 4), 44100 * 2 * 2);
    await prepared.cleanup();
    await assert.rejects(fs.stat(output), { code: "ENOENT" });
    assert.equal((await fs.readdir(directory)).length, 1);
  } finally { await fs.rm(directory, { recursive: true, force: true }); }
});

test("corrupt audio fails explicitly and leaves no converted artifact", async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "voitomo-audio-test-"));
  try {
    const input = path.join(directory, "corrupt.wav");
    await fs.writeFile(input, "invalid audio");
    await assert.rejects(prepareAudio(input, directory, 4001), /Audio conversion failed/);
    assert.deepEqual(await fs.readdir(directory), ["corrupt.wav"]);
  } finally { await fs.rm(directory, { recursive: true, force: true }); }
});
