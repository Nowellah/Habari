export interface Option { key: string; label: string }
export interface Reply { reply_text: string; options: Option[]; case_code: string | null; state: string }
export type SharedMeta = Record<string, string>;

const JSON_HEADERS = { "Content-Type": "application/json" };

/**
 * In development the API may run on another port (VITE_API_BASE_URL in web/.env).
 * A production build always uses the address it is served from.
 */
const BASE: string = import.meta.env.DEV ? (import.meta.env.VITE_API_BASE_URL ?? "") : "";

async function post(body: unknown): Promise<Reply> {
  const r = await fetch(`${BASE}/api/channel/web`, {
    method: "POST", headers: JSON_HEADERS, cache: "no-store", body: JSON.stringify(body),
  });
  return (await r.json()) as Reply;
}

export function sendMessage(senderId: string, text: string, meta: SharedMeta): Promise<Reply> {
  return post({ channel: "web", sender_id: senderId, text, meta });
}

/** Only a district is kept by the server; the coordinates end there. */
export function sendLocation(senderId: string, lat: number, lon: number): Promise<Reply> {
  return post({ channel: "web", sender_id: senderId, text: "", location: { lat, lon } });
}

export interface AppConfig { helpline: string; voice: boolean }

/** Server settings. Voice is offered only when a speech-to-text engine is set up. */
export async function getConfig(): Promise<AppConfig> {
  try {
    const r = await fetch(`${BASE}/api/config`, { cache: "no-store" });
    const data = (await r.json()) as Partial<AppConfig>;
    return { helpline: data.helpline || "116", voice: data.voice === true };
  } catch {
    return { helpline: "116", voice: false };
  }
}

export type SpokenLanguage = "en" | "lg";

export type Transcript = { ok: true; text: string } | { ok: false; message: string };

export async function transcribe(wav: Blob, language: SpokenLanguage): Promise<Transcript> {
  const form = new FormData();
  form.append("audio", wav, "voice.wav");
  form.append("language", language);
  try {
    const r = await fetch(`${BASE}/api/voice/transcribe`, { method: "POST", body: form, cache: "no-store" });
    const data = await r.json();
    return r.ok ? { ok: true, text: data.text as string } : { ok: false, message: data.message as string };
  } catch {
    return { ok: false, message: "We could not connect. Please type instead." };
  }
}

export function newSenderId(): string {
  const random = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : String(Math.random()).slice(2);
  return "web-" + random;
}
