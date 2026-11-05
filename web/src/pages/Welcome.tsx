import { Link, useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { stopSpeaking } from "../lib/speech";
import { useSession } from "../state/session";

export default function Welcome() {
  const navigate = useNavigate();
  const session = useSession();
  return (
    <Page>
      <div className="hero">
        <h1>Your voice matters.<br />We&apos;re here to listen.</h1>
        <p>
          You can talk about something worrying you online, ask questions, or get help.
          You do <strong>not</strong> need to share your name to begin.
        </p>
        <div className="stack">
          <button className="btn-primary" type="button" onClick={() => { session.reset(); navigate("/age"); }}>Talk to us</button>
          <button className="btn-accent" type="button" onClick={() => navigate("/help")}>Get Help Now</button>
          <button className="btn-danger" type="button"
            onClick={() => { stopSpeaking(); session.reset(); location.replace("https://www.google.com"); }}>Quick Exit</button>
        </div>
        <hr className="section-divider" />
        <div className="chips">
          <span>Private &amp; anonymous</span>
          <span>Multiple languages</span>
          <span>No name needed</span>
        </div>
        <p className="footnote">
          Quick Exit takes you away from this page. Nothing from this chat is saved on your phone.
          In danger now? <a href={`tel:${session.helpline}`}>Call {session.helpline}</a>, it is free. <Link to="/help">More help</Link>
        </p>
        <p className="footnote"><a href="/kb">Safety tips</a></p>
      </div>
    </Page>
  );
}
