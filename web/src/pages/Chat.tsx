import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import avatar from "../assets/habari-icon.png";
import Page from "../components/Page";
import { MAX_PROOF_BYTES, type Option, type SharedMeta, sendLocation } from "../lib/api";
import { type SpokenLanguage, spokenLanguageFor } from "../lib/choices";
import { canSpeak, matchOption, stopSpeaking } from "../lib/speech";
import { type Listening, canRecord, listen } from "../lib/voice";
import { useSession } from "../state/session";

export default function Chat() {
  const s = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [text, setText] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [locNote, setLocNote] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [areaSaved, setAreaSaved] = useState(false);
  const askedFor = useRef<string | null>(null);
  const [spoken, setSpoken] = useState<SpokenLanguage>(spokenLanguageFor(s.language));
  const voice = useRef<Listening | null>(null);
  const autoStarted = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLInputElement>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const recordable = useMemo(canRecord, []) && s.voiceReady;
  const speakable = useMemo(canSpeak, []);

  // Opened from a share, the embeddable link or the mock feed: fill in what was shared.
  useEffect(() => {
    if (params.get("shared") !== "1") return;
    const shared: SharedMeta = {};
    for (const [from, to] of [["url", "url"], ["src", "platform"], ["handle", "handle"], ["title", "title"]] as const) {
      const v = params.get(from);
      if (v) shared[to] = v;
    }
    s.setShared(shared);
    setText((params.get("text") || "").replace(shared.url || " ", "").trim());
    history.replaceState(null, "", "/chat"); // the shared details leave the address bar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (s.voiceReady && params.get("voice") === "1") setHint("Press the microphone and tell us what happened.");
  }, [s.voiceReady, params]);

  // Arriving from the welcome, age and language screens, the chat opens by itself.
  useEffect(() => {
    if (s.entered && !s.started && !autoStarted.current) {
      autoStarted.current = true;
      void s.send("MENU", null);
    }
  }, [s]);

  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [s.bubbles, s.options, s.waiting]);
  useEffect(() => () => { voice.current?.abort(); }, []);

  /** A button press. Adding screenshots opens the file picker; every other button is sent as a choice. */
  function pick(o: Option) {
    if (o.key === "PROOF_ADD") filePicker.current?.click();
    else void s.send(o.key, o.label, "choice");
  }

  function onFile(files: FileList | null) {
    const file = files?.[0];
    if (filePicker.current) filePicker.current.value = "";
    if (!file) return;
    if (file.size > MAX_PROOF_BYTES) { setHint("That file is too big. Please choose one under 8 MB."); return; }
    setHint(null);
    void s.sendProofFile(file);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setText("");
    // Typing or saying exactly the words on a button works like pressing that button.
    const button = matchOption(value, s.options);
    if (button) pick(button);
    else void s.send(value);
  }

  async function onSpeak() {
    if (voice.current) { voice.current.finish(); return; }
    stopSpeaking();
    try {
      voice.current = await listen({
        onEnd: () => { voice.current = null; setListening(false); },
        onSilence: () => setHint("We did not hear anything. Press the microphone to try again."),
        onAudio: (wav, cues) => { setHint(null); void s.sendVoice(wav, spoken, cues); },
      });
      setListening(true);
      setHint("Recording your voice note. Press Stop to send it.");
    } catch {
      setHint("The microphone is off. You can type instead.");
    }
  }

  /** Asks the phone for a rough position. Only the district is kept by the server. */
  function shareArea(automatic: boolean) {
    if (!navigator.geolocation) {
      if (!automatic) setLocNote("This phone cannot share location. That is OK.");
      return;
    }
    if (automatic) setLocNote("To find a helper near you, I am asking your phone for your area. You can say no.");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          setLocNote((await sendLocation(s.senderId, pos.coords.latitude, pos.coords.longitude)).reply_text);
          setAreaSaved(true);
        } catch { setLocNote(automatic ? null : "We could not send it. That is OK."); }
      },
      () => setLocNote(automatic ? null : "No problem. We will not use your location."),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    );
  }

  // Once a report is open, ask for the area one time so the child does not have to look for a button.
  useEffect(() => {
    if (!s.caseCode || askedFor.current === s.caseCode) return;
    askedFor.current = s.caseCode;
    shareArea(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.caseCode]);

  return (
    <Page narrow={false}>
      <div className="chat">
        <div className="chat-head">
          <img className="avatar" src={avatar} alt="" />
          <div className="who">
            <strong>Habari <i className="online" aria-hidden="true" /></strong>
            <small>{s.waiting ? "typing…" : "Online • Private. Nothing is saved on this phone."}</small>
          </div>
        </div>
        <nav className="chat-links" aria-label="More help">
          <Link to="/help">Human help</Link>
          <Link to="/language">Language</Link>
          <Link to="/report">My report</Link>
          {!areaSaved && <button type="button" id="share-location" onClick={() => shareArea(false)}>Share roughly where I am</button>}
        </nav>
        {s.danger && (
          <div className="emergency-banner critical" role="alert">
            In danger now? <a href={`tel:${s.helpline}`}>Call {s.helpline}</a>. It is free, and you are not in trouble.
          </div>
        )}
        <div className="log" id="log" aria-live="polite">
          {!s.started && (
            <div className="intro">
              <div className="bubble-row bot">
                <img className="avatar sm" src={avatar} alt="" />
                <div className="b bot-bubble bot">
                  Hi, I am Habari. You are not in trouble. In danger now? <a href={`tel:${s.helpline}`}>Call {s.helpline}</a>, it is free.
                </div>
              </div>
              <button className="qr-pill" id="start" type="button" onClick={() => void s.send("MENU", "Talk to us")}>
                Talk to us
              </button>
            </div>
          )}
          {s.bubbles.map((b, i) => (
            <div key={b.id} className={`bubble-row ${b.who}`}>
              {b.who === "bot" && (s.bubbles[i - 1]?.who !== "bot"
                ? <img className="avatar sm" src={avatar} alt="" />
                : <span className="avatar sm gap" />)}
              <div className={`b ${b.who === "kid" ? "child-bubble kid" : "bot-bubble bot"}`}>
                {b.audioUrl ? <audio controls src={b.audioUrl} aria-label="Your voice note" />
                  : b.imageUrl ? <img className="proof-thumb" src={b.imageUrl} alt="Screenshot you added" /> : b.text}
                {b.call && (<><br /><a className="call" href={`tel:${s.helpline}`}>Call {s.helpline} now</a></>)}
                <time>{clock(b.at)}</time>
              </div>
            </div>
          ))}
          {s.waiting && (
            <div className="bubble-row bot" aria-label="Habari is typing">
              <img className="avatar sm" src={avatar} alt="" />
              <div className="bot-bubble typing"><i className="typing-dot" /><i className="typing-dot" /><i className="typing-dot" /></div>
            </div>
          )}
          {s.options.length > 0 && (
            <div className="quick-replies-row">
              {s.options.map((o) => (
                <button key={o.key} type="button" className="qr-pill opt" onClick={() => pick(o)}>
                  {o.label}
                </button>
              ))}
            </div>
          )}
          <div ref={end} />
        </div>

        {s.caseCode && (
          <div className="case-bar">
            Case <strong>{s.caseCode}</strong>
            <button type="button" className="linkish" onClick={() => navigate("/report")}>Review my report</button>
            <button type="button" className="linkish" onClick={() => navigate("/confirmation")}>Save my code</button>
          </div>
        )}
        {recordable && (
          <div className="voicebar" id="voicebar">
            <label>Voice note language{" "}
              <select id="voice-lang" aria-label="Language you will speak" value={spoken}
                onChange={(e) => setSpoken(e.target.value as SpokenLanguage)}>
                <option value="en">English</option>
                <option value="lg">Luganda</option>
              </select>
            </label>
            {speakable && (
              <label>
                <input type="checkbox" id="read-aloud" checked={s.aloud} onChange={(e) => s.setAloud(e.target.checked)} />{" "}
                Read replies out loud
              </label>
            )}
            {s.aloud && <span id="aloud-note">Replies play from the speaker. Use earphones if other people are near.</span>}
          </div>
        )}
        {hint && <p className="hint" id="voice-hint">{hint}</p>}
        {locNote && <p className="hint" id="loc-note">{locNote}</p>}
        <form className="send" id="send" autoComplete="off" onSubmit={onSubmit}>
          <input id="text" ref={box} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Type a message" aria-label="Your message" />
          {s.caseCode && (
            <>
              <input ref={filePicker} type="file" hidden accept="image/jpeg,image/png,image/webp,application/pdf"
                onChange={(e) => onFile(e.target.files)} />
              <button type="button" className="round clip" aria-label="Add a screenshot" title="Add a screenshot"
                onClick={() => filePicker.current?.click()}><ClipIcon /></button>
            </>
          )}
          {recordable && !text.trim() ? (
            <button type="button" id="speak" className={`round speak${listening ? " rec" : ""}`}
              aria-label={listening ? "Stop recording" : "Record a voice note"} title={listening ? "Stop and send" : "Record a voice note"}
              onClick={() => void onSpeak()}>
              {listening ? <StopIcon /> : <MicIcon />}
            </button>
          ) : (
            <button type="submit" className="round send-btn" aria-label="Send" title="Send"><SendIcon /></button>
          )}
        </form>
      </div>
    </Page>
  );
}

function clock(at: number): string {
  return new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const icon = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "currentColor", "aria-hidden": true } as const;
const MicIcon = () => (
  <svg {...icon}><path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z" /></svg>
);
const ClipIcon = () => (
  <svg {...icon}><path d="M16.5 6.5v9.2a4.5 4.5 0 0 1-9 0V5.6a3 3 0 0 1 6 0v9.6a1.5 1.5 0 0 1-3 0V6.5H9.5v8.7a3 3 0 0 0 6 0V5.6a4.5 4.5 0 0 0-9 0v10.1a6 6 0 0 0 12 0V6.5h-2Z" /></svg>
);
const StopIcon = () => (<svg {...icon}><rect x="6" y="6" width="12" height="12" rx="2" /></svg>);
const SendIcon = () => (<svg {...icon}><path d="M3 20.5v-6.7l9-1.8-9-1.8V3.5L22 12 3 20.5Z" /></svg>);
