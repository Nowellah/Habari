import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { ageLabel, languageName } from "../lib/choices";
import { useSession } from "../state/session";

export default function Report() {
  const s = useSession();
  const navigate = useNavigate();
  const [more, setMore] = useState("");
  const [note, setNote] = useState<string | null>(null);

  if (!s.caseCode) {
    return (
      <Page>
        <h2 className="title">Your report</h2>
        <div className="emergency-banner">Your report starts once you tell us what happened in the chat.</div>
        <button type="button" className="btn-primary" onClick={() => navigate("/chat")}>Back to chat →</button>
      </Page>
    );
  }

  const said = s.bubbles.filter((b) => b.who === "kid" && b.kind !== "choice").map((b) => b.text);

  async function addMore(e: FormEvent) {
    e.preventDefault();
    const value = more.trim();
    if (!value) { setNote("Please write something to add."); return; }
    setMore("");
    setNote("Added to your report. A person will see it.");
    await s.send(value, value);
  }

  return (
    <Page>
      <h2 className="title">Review your report</h2>
      <p className="lead">This is what we have so far. You can add more details below.</p>
      <div className="info-card">
        <dl>
          <dt>What it is about</dt><dd>{s.category ?? "Not chosen"}</dd>
          <dt>Language</dt><dd>{languageName(s.language)}</dd>
          {ageLabel(s.age) && (<><dt>Age group</dt><dd>{ageLabel(s.age)}</dd></>)}
          <dt>Case code</dt><dd><strong>{s.caseCode}</strong></dd>
        </dl>
      </div>
      <p className="label">What you told us</p>
      <div className="info-card plain">
        {said.length ? said.map((t, i) => <p key={i} className="said">{t}</p>) : <p className="muted">Nothing written yet.</p>}
      </div>
      <form onSubmit={addMore}>
        <label className="label" htmlFor="more">Add more details (optional)</label>
        <textarea id="more" className="textarea" rows={3} value={more} onChange={(e) => setMore(e.target.value)} />
        {note && <p className="hint" role="status">{note}</p>}
        <button type="submit" className="btn-secondary">Add to my report</button>
      </form>
      <button type="button" className="btn-primary" onClick={() => navigate("/confirmation")}>Looks right</button>
      <hr className="section-divider" />
      <button type="button" className="btn-secondary" onClick={() => navigate("/chat")}>← Back to chat</button>
    </Page>
  );
}
