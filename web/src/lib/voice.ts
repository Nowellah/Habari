export const RATE = 16000;          // samples per second sent for transcription
const QUIET_LEVEL = 0.015;          // below this the microphone counts as quiet
const QUIET_MS = 1800;              // stop after this much quiet once the child has spoken
const NO_SPEECH_MS = 8000;          // give up if nothing is said
const MAX_MS = 60000;               // longest single recording

type AudioContextCtor = typeof AudioContext;

export function canRecord(): boolean {
  return typeof navigator.mediaDevices?.getUserMedia === "function" && audioContext() !== undefined;
}

function audioContext(): AudioContextCtor | undefined {
  return window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioContextCtor }).webkitAudioContext;
}

/** Mono 16-bit WAV at 16 kHz, built from raw samples. */
export function toWav(chunks: Float32Array[], inRate: number): Blob {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const all = new Float32Array(total);
  let at = 0;
  for (const c of chunks) { all.set(c, at); at += c.length; }
  const ratio = inRate / RATE;
  const count = Math.floor(total / ratio);
  const pcm = new Int16Array(count);
  for (let i = 0; i < count; i++) {
    const from = Math.floor(i * ratio);
    const to = Math.max(from + 1, Math.min(total, Math.floor((i + 1) * ratio)));
    let sum = 0;
    for (let j = from; j < to; j++) sum += all[j];
    const v = Math.max(-1, Math.min(1, sum / (to - from)));
    pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const dv = new DataView(buf);
  const tag = (off: number, s: string) => { for (let i = 0; i < s.length; i++) dv.setUint8(off + i, s.charCodeAt(i)); };
  tag(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); tag(8, "WAVE"); tag(12, "fmt ");
  dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true);
  dv.setUint32(24, RATE, true); dv.setUint32(28, RATE * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
  tag(36, "data"); dv.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) dv.setInt16(44 + i * 2, pcm[i], true);
  return new Blob([buf], { type: "audio/wav" });
}

export interface Listening {
  /** Stop now and use what was heard. */
  finish(): void;
  /** Stop now and throw the recording away. */
  abort(): void;
}

export interface ListenHandlers {
  onAudio(wav: Blob): void;
  onSilence(): void;
  onEnd(): void;
}

/** Records until the child pauses. The audio is kept in memory only. */
export async function listen(handlers: ListenHandlers): Promise<Listening> {
  const Ctx = audioContext()!;
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const ctx = new Ctx();
  const source = ctx.createMediaStreamSource(stream);
  const node = ctx.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  let heard = false, quiet = 0, elapsed = 0, finished = false, keep = true;

  function finish() {
    if (finished) return;
    finished = true;
    node.onaudioprocess = null;
    stream.getTracks().forEach((t) => t.stop());
    try { source.disconnect(); node.disconnect(); } catch { /* already disconnected */ }
    const rate = ctx.sampleRate;
    void ctx.close().catch(() => {});
    handlers.onEnd();
    if (!keep) return;
    if (!heard) { handlers.onSilence(); return; }
    const wav = toWav(chunks, rate);
    chunks.length = 0;
    handlers.onAudio(wav);
  }

  node.onaudioprocess = (ev) => {
    const data = ev.inputBuffer.getChannelData(0);
    chunks.push(new Float32Array(data));
    const ms = (data.length / ctx.sampleRate) * 1000;
    elapsed += ms;
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    if (Math.sqrt(sum / data.length) >= QUIET_LEVEL) { heard = true; quiet = 0; } else { quiet += ms; }
    if ((heard && quiet >= QUIET_MS) || (!heard && elapsed >= NO_SPEECH_MS) || elapsed >= MAX_MS) finish();
  };
  source.connect(node);
  node.connect(ctx.destination);
  return { finish, abort() { keep = false; finish(); } };
}
