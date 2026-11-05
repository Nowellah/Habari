import type { SpokenLanguage } from "./choices";
import type { Cues } from "./voice";

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

export function sendMessage(senderId: string, text: string, meta: SharedMeta, language?: string): Promise<Reply> {
  return post({ channel: "web", sender_id: senderId, text, meta, ...(language ? { language } : {}) });
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

/**
 * Sends a voice note. The server keeps the recording for the person who follows up,
 * and the bot answers it like a typed message.
 */
export async function sendVoiceNote(
  senderId: string, wav: Blob, spoken: SpokenLanguage, cues: Cues, meta: SharedMeta, language?: string,
): Promise<Reply> {
  const form = new FormData();
  form.append("sender_id", senderId);
  form.append("audio", wav, "voice.wav");
  form.append("spoken", spoken);
  form.append("cues", JSON.stringify(cues));
  form.append("meta", JSON.stringify(meta));
  if (language) form.append("language", language);
  const r = await fetch(`${BASE}/api/voice-note`, { method: "POST", body: form, cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return (await r.json()) as Reply;
}

export function newSenderId(): string {
  const random = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : String(Math.random()).slice(2);
  return "web-" + random;
}
