import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import QuickExit from "../components/QuickExit";
import {
  type Option, type SharedMeta, type SpokenLanguage,
  getConfig, newSenderId, sendLocation, sendMessage, transcribe,
} from "../lib/api";
import { canSpeak, matchOption, speak, speechText, stopSpeaking } from "../lib/speech";
import { type Listening, canRecord, listen } from "../lib/voice";

interface Bubble { id: number; who: "bot" | "kid"; text: string; call?: boolean }

const CHECK_WORDS = "Check the words. Change anything that is wrong, then press Send.";

export default function Chat() {
  // Anonymous mode: a one-time id kept only in this page's memory.
  // Closing or refreshing the page forgets it. Nothing is written to the device.
  const senderId = useMemo(newSenderId, []);
  const [params] = useSearchParams();

  const [helpline, setHelpline] = useState("116");
  const [voiceReady, setVoiceReady] = useState(false);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [options, setOptions] = useState<Option[]>([]);
  const [started, setStarted] = useState(false);
  const [text, setText] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [locNote, setLocNote] = useState("so we can find the nearest helper. Only your district is kept.");
  const [listening, setListening] = useState(false);
  const [language, setLanguage] = useState<SpokenLanguage>("en");
  const [aloud, setAloud] = useState(false);

  const nextId = useRef(0);
  const meta = useRef<SharedMeta>({});
  const voice = useRef<Listening | null>(null);
  const aloudRef = useRef(false);
  aloudRef.current = aloud;
  const recordable = useMemo(canRecord, []) && voiceReady;
  const speakable = useMemo(canSpeak, []);

  const add = (who: Bubble["who"], body: string, call = false) =>
    setBubbles((b) => [...b, { id: nextId.current++, who, text: body, call }]);

  useEffect(() => {
    void getConfig().then((c) => { setHelpline(c.helpline); setVoiceReady(c.voice); });
  }, []);

  // Opened from a share, the embeddable link or the mock feed: fill in what was shared.
  useEffect(() => {
    if (params.get("shared") === "1") {
      const shared: SharedMeta = {};
      const url = params.get("url"), src = params.get("src"), handle = params.get("handle"), title = params.get("title");
      if (url) shared.url = url;
      if (src) shared.platform = src;
      if (handle) shared.handle = handle;
      if (title) shared.title = title;
      meta.current = shared;
      setText((params.get("text") || "").replace(shared.url || " ", "").trim());
      history.replaceState(null, "", "/chat"); // the shared details leave the address bar
    }
  }, [params]);

  useEffect(() => {
    if (voiceReady && params.get("voice") === "1") setHint("Press Speak and tell us what happened.");
  }, [voiceReady, params]);

  useEffect(() => { window.scrollTo(0, document.body.scrollHeight); }, [bubbles, options]);

  async function send(value: string, shown?: string) {
    setStarted(true);
    setOptions([]);
    add("kid", shown || value);
    let reply;
    try {
      reply = await sendMessage(senderId, value, meta.current);
    } catch {
      add("bot", `We could not connect. If you are in danger, call ${helpline}. It is free.`);
      return;
    }
    add("bot", reply.reply_text, reply.reply_text.startsWith("Call "));
    setOptions(reply.options || []);
    if (aloudRef.current) speak(speechText(reply.reply_text, reply.options || []));
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setText("");
    // Typing or saying exactly the words on a button works like pressing that button.
    const button = matchOption(value, options);
    if (button) void send(button.key, button.label);
    else void send(value);
  }

  async function onSpeak() {
    if (voice.current) { voice.current.finish(); return; }
    stopSpeaking();
    try {
      voice.current = await listen({
        onEnd: () => { voice.current = null; setListening(false); },
        onSilence: () => setHint("We did not hear anything. Press Speak to try again."),
        onAudio: async (wav) => {
          setHint("Turning your voice into words…");
          const out = await transcribe(wav, language);
          if (out.ok) { setText(out.text); setHint(CHECK_WORDS); } else setHint(out.message);
        },
      });
      setListening(true);
      setHint("Listening… it stops when you pause, or press Stop.");
    } catch {
      setHint("The microphone is off. You can type instead.");
    }
  }

  function onLocation() {
    if (!navigator.geolocation) { setLocNote("This phone cannot share location. That is OK."); return; }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try { setLocNote((await sendLocation(senderId, pos.coords.latitude, pos.coords.longitude)).reply_text); }
        catch { setLocNote("We could not send it. That is OK."); }
      },
      () => setLocNote("No problem. We will not use your location."),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    );
  }

  function leave() {
    voice.current?.abort();
    stopSpeaking();
    setBubbles([]);
    setOptions([]);
  }

  return (
    <>
      <QuickExit onExit={leave} />
      <main>
        <div className="chat">
          <header>
            <h1>Habari</h1>
            <p className="muted help">
              You are not in trouble. Nothing is saved on this phone. In danger now?{" "}
              <a href={`tel:${helpline}`}>Call {helpline}</a>, it is free. <a href="/kb">Safety tips</a>
            </p>
          </header>
          <div className="log" id="log" aria-live="polite">
            {!started && (
              <button className="start" id="start" type="button" onClick={() => void send("HELP", "Talk to us")}>
                Talk to us
              </button>
            )}
            {bubbles.map((b) => (
              <div key={b.id} className={`b ${b.who}`}>
                {b.text}
                {b.call && (<><br /><a className="call" href={`tel:${helpline}`}>Call {helpline} now</a></>)}
              </div>
            ))}
            {options.length > 0 && (
              <div className="opts">
                {options.map((o) => (
                  <button key={o.key} type="button" className="opt" onClick={() => void send(o.key, o.label)}>
                    {o.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <p className="muted help">
            <button type="button" id="share-location" className="linkish" onClick={onLocation}>
              Share roughly where I am
            </button>{" "}
            <span id="loc-note">{locNote}</span>
          </p>
          {recordable && (
            <div className="voicebar muted help" id="voicebar">
              <label>
                Speak in{" "}
                <select id="voice-lang" aria-label="Language you will speak" value={language}
                  onChange={(e) => setLanguage(e.target.value as SpokenLanguage)}>
                  <option value="en">English</option>
                  <option value="lg">Luganda</option>
                </select>
              </label>
              {speakable && (
                <label>
                  <input type="checkbox" id="read-aloud" checked={aloud}
                    onChange={(e) => { setAloud(e.target.checked); if (!e.target.checked) stopSpeaking(); }} />{" "}
                  Read replies out loud
                </label>
              )}
              {aloud && <span id="aloud-note">Replies play from the phone speaker. Use earphones if other people are near.</span>}
            </div>
          )}
          {hint && <p className="muted help" id="voice-hint">{hint}</p>}
          <form className="send" id="send" autoComplete="off" onSubmit={onSubmit}>
            {recordable && (
              <button type="button" id="speak" className={`speak${listening ? " rec" : ""}`}
                aria-label="Speak instead of typing" onClick={() => void onSpeak()}>
                {listening ? "Stop" : "Speak"}
              </button>
            )}
            <input id="text" value={text} onChange={(e) => setText(e.target.value)}
              placeholder="Type here, any language" aria-label="Your message" />
            <button type="submit">Send</button>
          </form>
        </div>
      </main>
    </>
  );
}
