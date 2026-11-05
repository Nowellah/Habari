import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { useSession } from "../state/session";

export default function Help() {
  const s = useSession();
  const navigate = useNavigate();

  async function askForPerson() {
    if (s.caseCode) await s.send("I would like a person to contact me.", "I would like a person to contact me.");
    navigate("/chat");
  }

  return (
    <Page>
      <h2 className="title">Get help now</h2>
      <p className="lead">
        Habari helps you tell someone about a worry, but it is not a replacement for emergency services or a trained
        helper. If you are in <strong>immediate danger</strong>, please call for help now.
      </p>
      <div className="help-card yellow">
        <p><strong>Child Helpline Uganda</strong></p>
        <a className="big-number" href={`tel:${s.helpline}`}>{s.helpline}</a>
        <p className="small muted">Free call.</p>
      </div>
      <div className="help-card red">
        <p><strong>Emergency services</strong></p>
        <div className="row">
          <a className="emergency-number" href="tel:999">999</a>
          <a className="emergency-number" href="tel:112">112</a>
        </div>
      </div>
      <div className="info-card">
        <p><strong>A person at Habari</strong></p>
        <p className="small">
          Every report is seen by a trained person. {s.caseCode
            ? "You can ask them to contact you."
            : "Tell us what happened in the chat and a person will see it."}
        </p>
      </div>
      <div className="notice">
        <strong>Please note:</strong> Habari cannot guarantee immediate rescue, instant confidentiality, or the deletion
        of reports. Safeguarding records may be kept as required by law.
      </div>
      <button type="button" className="btn-primary" onClick={() => void askForPerson()}>
        {s.caseCode ? "Ask a person to contact me" : "Start chat"}
      </button>
      <button type="button" className="btn-secondary" onClick={() => navigate("/chat")}>← Back to chat</button>
    </Page>
  );
}
