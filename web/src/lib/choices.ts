export type SpokenLanguage = "en" | "lg";
export type Language = "en" | "lg" | "sw" | "rn";

export interface AgeChoice { value: string; label: string; hint: string }

/** `value` is what the server keeps as a flag; "none" means the child skipped the question. */
export const AGES: AgeChoice[] = [
  { value: "under_10", label: "Under 10", hint: "We'll use simple, friendly words." },
  { value: "10_12", label: "10–12", hint: "We'll keep things clear and easy." },
  { value: "13_15", label: "13–15", hint: "We'll give you full information." },
  { value: "16_17", label: "16–17", hint: "We'll treat you as a young adult." },
  { value: "none", label: "Prefer not to say", hint: "That's completely fine." },
];

export interface LanguageChoice { code: Language; name: string; note: string; full: boolean }

export const LANGUAGES: LanguageChoice[] = [
  { code: "en", name: "English", note: "Fully supported", full: true },
  { code: "lg", name: "Luganda", note: "Write or speak. Replies are in English for now", full: false },
  { code: "sw", name: "Swahili", note: "Write. Replies are in English for now", full: false },
  { code: "rn", name: "Runyankore", note: "Write. Replies are in English for now", full: false },
];

export function languageName(code: Language): string {
  return LANGUAGES.find((l) => l.code === code)?.name ?? code;
}

export function ageLabel(value: string | null): string | null {
  const found = AGES.find((a) => a.value === value);
  return found && found.value !== "none" ? found.label : null;
}

/** Voice input is offered for English and Luganda only. */
export function spokenLanguageFor(language: Language): SpokenLanguage {
  return language === "lg" ? "lg" : "en";
}
