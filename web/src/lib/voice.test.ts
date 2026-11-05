import { describe, expect, it } from "vitest";
import { CueMeter, RATE, toWav } from "./voice";

async function bytes(blob: Blob): Promise<DataView> {
  return new DataView(await blob.arrayBuffer());
}

describe("toWav", () => {
  it("writes a mono 16-bit 16 kHz WAV header", async () => {
    const samples = new Float32Array(48000).fill(0.5); // one second at 48 kHz
    const wav = await bytes(toWav([samples], 48000));
    const tag = (at: number) => String.fromCharCode(...[0, 1, 2, 3].map((i) => wav.getUint8(at + i)));
    expect([tag(0), tag(8), tag(12), tag(36)]).toEqual(["RIFF", "WAVE", "fmt ", "data"]);
    expect(wav.getUint16(20, true)).toBe(1);       // PCM
    expect(wav.getUint16(22, true)).toBe(1);       // mono
    expect(wav.getUint32(24, true)).toBe(RATE);
    expect(wav.getUint16(34, true)).toBe(16);
    expect(wav.getUint32(40, true)).toBe(RATE * 2); // one second of 16-bit samples
  });
  it("joins chunks and clips out-of-range samples", async () => {
    const wav = await bytes(toWav([new Float32Array([2, 2]), new Float32Array([-2, -2])], RATE));
    expect(wav.getUint32(40, true)).toBe(8);
    expect(wav.getInt16(44, true)).toBe(0x7fff);
    expect(wav.getInt16(50, true)).toBe(-0x8000);
  });
  it("handles an empty recording", async () => {
    expect((await bytes(toWav([], 48000))).getUint32(40, true)).toBe(0);
  });
});

describe("CueMeter", () => {
  it("reports length, volume and long pauses", () => {
    const m = new CueMeter();
    m.add(0.2, 500); m.add(0.2, 500);      // speaking
    m.add(0, 1500);                         // a long pause
    m.add(0.3, 500);                        // speaking again
    expect(m.result()).toEqual({ seconds: 3, level: 23, peak: 30, pauses: 1 });
  });
  it("counts nothing for silence", () => {
    const m = new CueMeter();
    m.add(0, 2000);
    expect(m.result()).toEqual({ seconds: 2, level: 0, peak: 0, pauses: 0 });
  });
});
