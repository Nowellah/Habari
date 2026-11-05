interface Props { onExit?: () => void }

/** Leaves the site at once and replaces this page so Back does not return to it. */
export default function QuickExit({ onExit }: Props) {
  return (
    <button className="exit" id="quick-exit" type="button"
      onClick={() => { onExit?.(); location.replace("https://www.google.com"); }}>
      Quick exit
    </button>
  );
}
