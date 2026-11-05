import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { useSession } from "../state/session";

export default function Confirmation() {
  const s = useSession();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try { await navigator.clipboard.writeText(s.caseCode ?? ""); setCopied(true); }
    catch { setCopied(false); }
  }

  return (
    <Page>
      <div className="center-col">
        
        <h2 className="title center">{s.caseCode ? "Your report has been received." : "No report yet."}</h2>
        {s.caseCode ? (
          <>
            <div className="code-card">
              <p>Your case code</p>
              <p className="code" id="case-code">{s.caseCode}</p>
            </div>
            <p className="lead center">
              Keep this code safe. You can use it to check on your report at any time. Nothing is saved on this phone,
              so write it down or copy it.
            </p>
            <button type="button" className="btn-accent" onClick={() => void copy()}>
              {copied ? "Copied" : "Copy case code"}
            </button>
          </>
        ) : (
          <p className="lead center">Tell us what happened in the chat and you will get a case code here.</p>
        )}
        <button type="button" className="btn-primary" onClick={() => navigate("/status")}>Check report status</button>
        <button type="button" className="btn-secondary" onClick={() => navigate("/chat")}>Continue chatting</button>
        <button type="button" className="btn-accent" onClick={() => navigate("/help")}>Get human help</button>
        <p className="footnote">A trained person will look at your report.</p>
      </div>
    </Page>
  );
}
