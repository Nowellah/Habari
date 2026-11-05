import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { sendMessage } from "../lib/api";
import { useSession } from "../state/session";

export default function Status() {
  const s = useSession();
  const navigate = useNavigate();
  const [code, setCode] = useState(s.caseCode ?? "");
  const [word, setWord] = useState("");
  const [result, setResult] = useState<{ code: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function lookUp(e: FormEvent) {
    e.preventDefault();
    const clean = code.trim().toUpperCase();
    setResult(null);
    if (!clean) { setError("Please enter a case code."); return; }
    setError(null);
    setBusy(true);
    try {
      const reply = await sendMessage(s.senderId, `STATUS ${clean}${word.trim() ? " " + word.trim() : ""}`, {});
      setResult({ code: clean, text: reply.reply_text });
    } catch {
      setError("We could not connect. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page>
      <h2 className="title">Check your report status</h2>
      <p className="lead">Enter the case code you received when you told us what happened.</p>
      <form onSubmit={lookUp}>
        <label className="label" htmlFor="code">Case code</label>
        <input id="code" className="input" value={code} placeholder="e.g. HB-ABC234" onChange={(e) => setCode(e.target.value)} />
        <label className="label" htmlFor="word">Your secret word (only if you set one)</label>
        <input id="word" className="input" value={word} onChange={(e) => setWord(e.target.value)} />
        {error && <p className="hint error" role="alert">{error}</p>}
        <button type="submit" className="btn-primary" disabled={busy}>{busy ? "Looking up…" : "Look up"}</button>
      </form>
      {result && (
        <div className="info-card" id="status-result">
          <p className="small muted">Case code</p>
          <p className="code small-code">{result.code}</p>
          <p>{result.text}</p>
        </div>
      )}
      <hr className="section-divider" />
      <button type="button" className="btn-secondary" onClick={() => navigate("/chat")}>← Back to chat</button>
    </Page>
  );
}
