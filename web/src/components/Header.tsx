import { stopSpeaking } from "../lib/speech";
import { useSession } from "../state/session";

/** Exit floats over the background waves. Exit leaves at once, forgets the chat and replaces this page. */
export default function Header() {
  const session = useSession();
  return (
    <header className="topbar">
      <button className="exit" id="quick-exit" type="button"
        onClick={() => { stopSpeaking(); session.reset(); location.replace("https://www.google.com"); }}>
        Exit
      </button>
    </header>
  );
}
