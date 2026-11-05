import { useNavigate } from "react-router-dom";
import Page from "../components/Page";
import { AGES } from "../lib/choices";
import { useSession } from "../state/session";

export default function Age() {
  const navigate = useNavigate();
  const session = useSession();
  const choose = (value: string) => { session.setAge(value); navigate("/language"); };
  return (
    <Page>
      <h2 className="title">Which age group are you in?</h2>
      <p className="lead">This helps us talk to you in the right way. You can skip this step.</p>
      {AGES.map((a) => (
        <button key={a.value} type="button" className="select-card" onClick={() => choose(a.value)}>
          
          <span><strong>{a.label}</strong><small>{a.hint}</small></span>
        </button>
      ))}
      <hr className="section-divider" />
      <button type="button" className="linkish center" onClick={() => choose("none")}>Skip this step →</button>
    </Page>
  );
}
