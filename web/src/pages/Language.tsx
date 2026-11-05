import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { LANGUAGES, type Language as Code } from "../lib/choices";
import { useSession } from "../state/session";

export default function Language() {
  const navigate = useNavigate();
  const session = useSession();
  const choose = (code: Code) => { session.setLanguage(code); session.markEntered(); navigate("/chat"); };
  return (
    <Page>
      <h2 className="title">Which language would you like?</h2>
      <p className="lead">You can change this at any time during your conversation.</p>
      {LANGUAGES.map((l) => (
        <button key={l.code} type="button" className="select-card" onClick={() => choose(l.code)}>
          
          <span><strong>{l.name}</strong></span>
          <span className={`badge ${l.full ? "badge-ok" : "badge-warn"}`}>{l.note}</span>
        </button>
      ))}
      <hr className="section-divider" />
      <button type="button" className="btn-primary" onClick={() => choose("en")}>Continue in English →</button>
    </Page>
  );
}
