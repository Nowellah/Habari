import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { type CaseTrack, type TrackStep, getCaseStatus } from "../lib/api";
import { useSession } from "../state/session";

const STATE_WORD: Record<TrackStep["state"], string> = { done: "Done", current: "Happening now", todo: "Next", skipped: "Not needed" };

function when(iso: string): string {
  return new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function Status() {
  const s = useSession();
  const navigate = useNavigate();
  const [code, setCode] = useState(s.caseCode ?? "");
  const [word, setWord] = useState("");
  const [needsWord, setNeedsWord] = useState(false);
  const [track, setTrack] = useState<CaseTrack | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoLooked = useRef(false);

  const lookUp = useCallback(async (rawCode: string, rawWord: string) => {
    const clean = rawCode.trim().toUpperCase();
    if (!clean) { setError("Please enter your case code."); return; }
    setError(null);
    setBusy(true);
    try {
      const result = await getCaseStatus(clean, rawWord.trim());
      if (result.ok) { setTrack(result.data); setNeedsWord(false); }
      else { setTrack(null); setNeedsWord(result.needsWord); setError(result.message); }
    } catch {
      setError("We could not connect. Please try again.");
    } finally {
      setBusy(false);
    }
  }, []);

  // A child who has just reported sees their case straight away.
  useEffect(() => {
    if (s.caseCode && !autoLooked.current) { autoLooked.current = true; void lookUp(s.caseCode, ""); }
  }, [s.caseCode, lookUp]);

  function onSubmit(e: FormEvent) { e.preventDefault(); void lookUp(code, word); }

  return (
    <Page>
      <h2 className="title">Track your report</h2>
      <p className="lead">See where your report is and how long it has taken. Use the case code you were given.</p>
      <form onSubmit={onSubmit}>
        <label className="label" htmlFor="code">Case code</label>
        <input id="code" className="input" value={code} placeholder="e.g. HB-ABC234" autoComplete="off" onChange={(e) => setCode(e.target.value)} />
        {(needsWord || word) && (
          <>
            <label className="label" htmlFor="word">Your secret word</label>
            <input id="word" className="input" value={word} autoComplete="off" onChange={(e) => setWord(e.target.value)} />
          </>
        )}
        {error && <p className="hint error" role="alert">{error}</p>}
        <button type="submit" className="btn-primary" disabled={busy}>{busy ? "Looking up..." : track ? "Check again" : "Look up"}</button>
      </form>

      {track && (
        <section id="status-result" aria-live="polite">
          <div className={`track-summary${track.closed ? " closed" : ""}`}>
            <p className="small muted">Case <strong className="code small-code">{track.code}</strong></p>
            <p className="track-headline">{track.headline}</p>
            <p className="track-time">{track.closed ? `Closed after ${track.took}` : `Open for ${track.took}`}</p>
            {track.goal && <p className="small muted">{track.goal}</p>}
          </div>

          <ol className="timeline">
            {track.steps.map((st) => (
              <li key={st.key} className={`tl-step ${st.state}`}>
                <span className="tl-dot" aria-hidden="true">{st.state === "done" ? "\u2713" : ""}</span>
                <div>
                  <p className="tl-title">{st.title} <span className="sr">({STATE_WORD[st.state]})</span></p>
                  <p className="tl-detail">{st.state === "skipped" ? "Not needed for your report." : st.detail}</p>
                  {st.at && <p className="tl-time">{when(st.at)}</p>}
                </div>
              </li>
            ))}
          </ol>

          {track.messages.length > 0 && (
            <div className="info-card">
              <p className="small muted">Messages for you</p>
              {track.messages.map((m) => (
                <p key={m.at + m.text}>{m.text} <span className="tl-time">{when(m.at)}</span></p>
              ))}
            </div>
          )}
          <p className="small muted">In danger now? <a href={`tel:${s.helpline}`}>Call {s.helpline}</a>, it is free.</p>
        </section>
      )}
      <hr className="section-divider" />
      <button type="button" className="btn-secondary" onClick={() => navigate(s.started ? "/chat" : "/")}>Back</button>
    </Page>
  );
}
