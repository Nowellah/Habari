/** The page background: soft waves, dots, and on wide screens a welcome panel on each side. */
export default function Backdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <svg viewBox="0 0 1440 900" preserveAspectRatio="none">
        <defs>
          <linearGradient id="wave-top" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#5f9d94" />
            <stop offset="1" stopColor="#cfe3dd" />
          </linearGradient>
          <linearGradient id="wave-low" x1="1" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="#006463" />
            <stop offset="1" stopColor="#9fc6bd" />
          </linearGradient>
        </defs>
        <path d="M0 0 H360 C300 70 190 130 0 235 Z" fill="url(#wave-top)" />
        <path d="M0 0 H220 C170 50 90 100 0 150 Z" fill="#8bb8af" opacity=".55" />
        <path d="M1160 0 H1440 V70 C1390 125 1300 120 1245 72 C1215 48 1190 24 1160 0 Z" fill="#FFC619" opacity=".9" />
        <path d="M0 690 C170 700 330 790 560 900 H0 Z" fill="#FFC619" />
        <path d="M0 795 C210 805 410 870 620 900 H0 Z" fill="#006463" />
        <path d="M520 900 C830 880 1160 800 1440 640 V900 Z" fill="url(#wave-low)" opacity=".85" />
        <path d="M720 900 C1010 892 1250 850 1440 770 V900 Z" fill="#006463" />
      </svg>
      <span className="dots dots-left" />
      <span className="dots dots-right" />
      <div className="side side-left">
        <svg viewBox="0 0 200 190" width="200" height="190">
          <path d="M28 112 A72 72 0 0 1 172 112" fill="none" stroke="#a9cdc6" strokeWidth="14" strokeLinecap="round" />
          <rect x="10" y="92" width="26" height="46" rx="12" fill="#a9cdc6" />
          <rect x="164" y="92" width="26" height="46" rx="12" fill="#a9cdc6" />
          <path d="M176 136 C176 168 150 172 118 172" fill="none" stroke="#a9cdc6" strokeWidth="9" strokeLinecap="round" />
          <rect x="98" y="164" width="24" height="16" rx="8" fill="#a9cdc6" />
          <rect x="52" y="52" width="96" height="86" rx="26" fill="#a9cdc6" />
          <path d="M70 136 L66 160 L92 138 Z" fill="#a9cdc6" />
          <text x="100" y="116" textAnchor="middle" fontSize="64" fontWeight="800" fill="#FFF9F0" fontFamily="Inter, sans-serif">h</text>
        </svg>
        <h2>Habari</h2>
        <p>Ask. Get Help. Move Forward.</p>
        <i className="swoosh" />
      </div>
      <div className="side side-right">
        <p><strong>You are not alone.</strong><br />We are here to listen and help.</p>
        <i className="swoosh" />
      </div>
    </div>
  );
}

