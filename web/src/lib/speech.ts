import type { Option } from "./api";

/** Lower-case letters, digits and spaces only, for comparing what was said with a button label. */
export function plain(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9 ]/g, "").trim();
}

export function matchOption(text: string, options: Option[]): Option | null {
  const want = plain(text);
  if (!want) return null;
  return options.find((o) => plain(o.label) === want) ?? null;
}

/**
 * Text for reading aloud: digits are spoken one by one, and a typed list of
 * choices is replaced by the question followed by the button labels.
 */
export function speechText(text: string, options: Option[]): string {
  let t = text;
  if (options.length) {
    const list = t.search(/\s[1-9]\s+[A-Z]/);
    if (list > 0) t = t.slice(0, list).trim();
    t += " You can choose: " + options.map((o) => o.label).join(", ") + ".";
  }
  return t.replace(/\d{3,}/g, (m) => m.split("").join(" ")).replace(/\s*\n+\s*/g, ". ").replace(/\.{2,}/g, ".");
}

export const canSpeak = (): boolean => "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}

export function speak(text: string): void {
  if (!canSpeak()) return;
  stopSpeaking();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en";
  u.rate = 0.95;
  window.speechSynthesis.speak(u);
}
