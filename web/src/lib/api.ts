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

export interface TrackStep { key: string; title: string; detail: string; state: "done" | "current" | "todo" | "skipped"; at: string | null }
export interface CaseTrack {
  code: string; closed: boolean; headline: string; steps: TrackStep[];
  opened_at: string; closed_at: string | null; took: string; goal: string;
  messages: { text: string; at: string }[];
}
export type TrackResult = { ok: true; data: CaseTrack } | { ok: false; needsWord: boolean; message: string };

/** Where a case is. Needs the code, and the secret word if the child set one. Nothing about the report itself comes back. */
export async function getCaseStatus(code: string, word: string): Promise<TrackResult> {
  const r = await fetch(`${BASE}/api/case-status`, {
    method: "POST", headers: JSON_HEADERS, cache: "no-store", body: JSON.stringify({ code, word }),
  });
  if (r.ok) return { ok: true, data: (await r.json()) as CaseTrack };
  const body = (await r.json().catch(() => ({}))) as { message?: string; needs_word?: boolean };
  return { ok: false, needsWord: body.needs_word === true, message: body.message || "We could not look that up. Please try again." };
}

export const MAX_PROOF_BYTES = 8 * 1024 * 1024;

/** Adds a screenshot or PDF to the child's open case. A refused file comes back as a reply they can read. */
export async function sendProof(senderId: string, file: File): Promise<Reply> {
  const form = new FormData();
  form.append("sender_id", senderId);
  form.append("file", file, file.name);
  const r = await fetch(`${BASE}/api/proof`, { method: "POST", body: form, cache: "no-store" });
  if (r.ok) return (await r.json()) as Reply;
  if (r.status === 400 || r.status === 413 || r.status === 415) {
    const data = (await r.json().catch(() => ({}))) as { message?: string };
    return {
      reply_text: data.message || "I could not use that file.",
      options: [{ key: "PROOF_ADD", label: "Try another file" }], case_code: null, state: "CASE_OPEN",
    };
  }
  throw new Error(String(r.status));
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
