import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { type Option, type Reply, type SharedMeta, getConfig, newSenderId, sendMessage, sendVoiceNote } from "../lib/api";
import type { Language, SpokenLanguage } from "../lib/choices";
import { speak, speechText, stopSpeaking } from "../lib/speech";
import type { Cues } from "../lib/voice";

export interface Bubble { id: number; who: "bot" | "kid"; text: string; at: number; call?: boolean; kind?: "text" | "choice"; audioUrl?: string }

interface Session {
  senderId: string;
  helpline: string;
  voiceReady: boolean;
  age: string | null;
  setAge(value: string): void;
  language: Language;
  setLanguage(code: Language): void;
  bubbles: Bubble[];
  options: Option[];
  waiting: boolean;
  started: boolean;
  caseCode: string | null;
  category: string | null;
  danger: boolean;
  /** The child came through the welcome, age and language screens, so the chat starts by itself. */
  entered: boolean;
  markEntered(): void;
  aloud: boolean;
  setAloud(on: boolean): void;
  /** Send a message. `shown` is what appears in the child's bubble; null shows none. */
  send(value: string, shown?: string | null, kind?: "text" | "choice"): Promise<void>;
  /** Send a recorded voice note. It stays a voice note; the bot still answers it. */
  sendVoice(wav: Blob, spoken: SpokenLanguage, cues: Cues): Promise<void>;
  setShared(meta: SharedMeta): void;
  /** Forget the whole conversation. */
  reset(): void;
}

const Ctx = createContext<Session | null>(null);

export function useSession(): Session {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession must be used inside SessionProvider");
  return s;
}

/**
 * Everything about the conversation lives here, in memory only. Closing or
 * refreshing the page forgets it. Nothing is written to the device.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [senderId, setSenderId] = useState(newSenderId);
  const [helpline, setHelpline] = useState("116");
  const [voiceReady, setVoiceReady] = useState(false);
  const [age, setAgeState] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>("en");
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [options, setOptions] = useState<Option[]>([]);
  const [waiting, setWaiting] = useState(false);
  const [started, setStarted] = useState(false);
  const [caseCode, setCaseCode] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [danger, setDanger] = useState(false);
  const [entered, setEntered] = useState(false);
  const [aloud, setAloudState] = useState(false);

  const nextId = useRef(0);
  const audioUrls = useRef<string[]>([]);
  const shared = useRef<SharedMeta>({});
  const ageRef = useRef<string | null>(null);
  const languageRef = useRef<Language>("en");
  const lastState = useRef("START");
  const aloudRef = useRef(false);
  languageRef.current = language;
  aloudRef.current = aloud;

  useEffect(() => {
    void getConfig().then((c) => { setHelpline(c.helpline); setVoiceReady(c.voice); });
  }, []);

  const add = useCallback((who: Bubble["who"], text: string, extra: Partial<Bubble> = {}) => {
    setBubbles((b) => [...b, { id: nextId.current++, who, text, at: Date.now(), ...extra }]);
  }, []);

  /** Ask the server, then show its reply. Both typed messages and voice notes go through here. */
  const exchange = useCallback(async (ask: (meta: SharedMeta) => Promise<Reply>) => {
    setWaiting(true);
    let reply: Reply;
    try {
      const meta: SharedMeta = { ...shared.current };
      if (ageRef.current && ageRef.current !== "none") meta.age_bracket = ageRef.current;
      reply = await ask(meta);
    } catch {
      setWaiting(false);
      add("bot", `We could not connect. If you are in danger, call ${helpline}. It is free.`);
      return;
    }
    setWaiting(false);
    lastState.current = reply.state;
    const call = reply.reply_text.startsWith("Call ");
    if (call) setDanger(true);
    if (reply.case_code) setCaseCode(reply.case_code);
    // A reply with blank lines in it is shown as several short bubbles.
    const parts = reply.reply_text.split(/\n{2,}/).map((t) => t.trim()).filter(Boolean);
    parts.forEach((part, i) => add("bot", part, { call: call && i === 0 }));
    setOptions(reply.options || []);
    if (aloudRef.current) speak(speechText(reply.reply_text, reply.options || []));
  }, [add, helpline]);

  const send = useCallback(async (value: string, shown?: string | null, kind: "text" | "choice" = "text") => {
    setStarted(true);
    const wasMenu = lastState.current === "PICK_HARM";
    setOptions([]);
    if (shown !== null) add("kid", shown || value, { kind });
    if (kind === "choice" && wasMenu && shown) setCategory((c) => c ?? shown);
    await exchange((meta) => sendMessage(senderId, value, meta, languageRef.current));
  }, [add, exchange, senderId]);

  const sendVoice = useCallback(async (wav: Blob, spoken: SpokenLanguage, cues: Cues) => {
    setStarted(true);
    setOptions([]);
    const audioUrl = URL.createObjectURL(wav);
    audioUrls.current.push(audioUrl);
    add("kid", "Voice note", { audioUrl });
    await exchange((meta) => sendVoiceNote(senderId, wav, spoken, cues, meta, languageRef.current));
  }, [add, exchange, senderId]);

  const reset = useCallback(() => {
    stopSpeaking();
    audioUrls.current.forEach((u) => URL.revokeObjectURL(u));
    audioUrls.current = [];
    setSenderId(newSenderId());
    setBubbles([]); setOptions([]); setWaiting(false); setStarted(false);
    setCaseCode(null); setCategory(null); setDanger(false); setEntered(false); setAgeState(null);
    lastState.current = "START";
    shared.current = {};
  }, []);

  const value = useMemo<Session>(() => ({
    senderId, helpline, voiceReady, age,
    setAge: (v) => { ageRef.current = v; setAgeState(v); },
    language, setLanguage,
    bubbles, options, waiting, started, caseCode, category, danger,
    entered, markEntered: () => setEntered(true),
    aloud, setAloud: (on) => { setAloudState(on); if (!on) stopSpeaking(); },
    send, sendVoice, setShared: (m) => { shared.current = m; },
    reset,
  }), [senderId, helpline, voiceReady, age, language, bubbles, options, waiting, started, caseCode, category, danger, entered, aloud, send, sendVoice, reset]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
