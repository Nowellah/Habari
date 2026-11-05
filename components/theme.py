"""
theme.py — Brand colors and global CSS for HABARI.

Call inject_styles() at the top of every @ui.page function.
NiceGUI 2.x requires ui.add_head_html to be called inside a page function,
not at module level.
"""
from nicegui import ui

DEEP_TEAL      = "#006463"
GOLDEN_YELLOW  = "#FFC619"
WARM_WHITE     = "#FFF9F0"
DARK_TEAL      = "#003F40"
FONT_FAMILY    = "Nunito, Segoe UI, Arial, sans-serif"

_CSS = """\
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
    --deep-teal: #006463;
    --golden-yellow: #FFC619;
    --warm-white: #FFF9F0;
    --dark-teal: #003F40;
    --danger-red: #c0392b;
    --text-dark: #1a1a2e;
    --text-mid: #4a5568;
    --text-light: #718096;
    --border: #e2e8f0;
    --card-bg: #ffffff;
    --shadow: 0 2px 12px rgba(0,100,99,0.10);
    --shadow-hover: 0 6px 24px rgba(0,100,99,0.18);
}
*, *::before, *::after { box-sizing: border-box; }
html, body {
    height: 100%;
    margin: 0; padding: 0;
    background-color: var(--warm-white);
    font-family: Nunito, 'Segoe UI', Arial, sans-serif;
    color: var(--text-dark);
    -webkit-font-smoothing: antialiased;
}

/* ── Page wrapper ── */
.page-wrap {
    max-width: 520px;
    margin: 0 auto;
    padding: 20px 16px 40px;
    width: 100%;
}

/* ── Selection cards ── */
.select-card {
    width: 100%;
    background: var(--card-bg);
    border: 2px solid var(--border);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    cursor: pointer;
    transition: border-color 0.18s, box-shadow 0.18s, transform 0.12s;
    box-shadow: var(--shadow);
    display: flex;
    align-items: center;
    gap: 12px;
}
.select-card:hover {
    border-color: var(--deep-teal);
    box-shadow: var(--shadow-hover);
    transform: translateY(-2px);
}

/* ── Chat bubbles ── */
.bubble-row { display: flex; width: 100%; margin-bottom: 6px; padding: 0 4px; }
.bubble-row.child { justify-content: flex-end; }
.bubble-row.bot   { justify-content: flex-start; }

.child-bubble {
    background: var(--golden-yellow);
    color: var(--dark-teal);
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    max-width: 78%;
    word-wrap: break-word;
    font-size: 0.95rem;
    line-height: 1.5;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.bot-bubble {
    background: var(--card-bg);
    color: var(--text-dark);
    border-left: 4px solid var(--deep-teal);
    border-radius: 4px 18px 18px 18px;
    padding: 10px 16px;
    max-width: 78%;
    word-wrap: break-word;
    font-size: 0.95rem;
    line-height: 1.5;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.bubble-time {
    font-size: 0.68rem;
    color: var(--text-light);
    margin-top: 3px;
    text-align: right;
}
.bot-bubble .bubble-time { text-align: left; }

/* ── Typing indicator ── */
.typing-dot {
    display: inline-block;
    width: 8px; height: 8px;
    background: var(--deep-teal);
    border-radius: 50%;
    margin: 0 2px;
    animation: bounce 1.2s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
    40%            { transform: translateY(-6px); opacity: 1; }
}

/* ── Quick reply pills ── */
.quick-replies-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 4px 4px 8px;
}
.qr-pill {
    background: transparent;
    color: var(--deep-teal);
    border: 2px solid var(--deep-teal);
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.82rem;
    font-family: Nunito, Arial, sans-serif;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    white-space: nowrap;
}
.qr-pill:hover { background: var(--deep-teal); color: white; }

/* ── Buttons ── */
.btn-primary {
    background: var(--deep-teal) !important;
    color: white !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    width: 100%;
    padding: 13px !important;
    transition: background 0.15s;
    box-shadow: 0 2px 8px rgba(0,100,99,0.2);
}
.btn-primary:hover { background: var(--dark-teal) !important; }

.btn-secondary {
    background: white !important;
    color: var(--deep-teal) !important;
    border: 2px solid var(--deep-teal) !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    width: 100%;
    padding: 11px !important;
}
.btn-secondary:hover { background: #e8f4f4 !important; }

.btn-accent {
    background: var(--golden-yellow) !important;
    color: var(--dark-teal) !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    width: 100%;
    padding: 13px !important;
    box-shadow: 0 2px 8px rgba(255,198,25,0.3);
}
.btn-accent:hover { filter: brightness(1.05); }

.btn-danger {
    background: var(--danger-red) !important;
    color: white !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    width: 100%;
    padding: 13px !important;
}

/* ── Badges ── */
.demo-badge {
    background: var(--golden-yellow);
    color: var(--dark-teal);
    font-weight: 800;
    font-size: 0.72rem;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── Emergency banner ── */
.emergency-banner {
    background: #fff3cd;
    border: 2px solid #FFC619;
    color: #7a5c00;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 8px 0;
    font-weight: 600;
    line-height: 1.5;
}
.emergency-banner.critical {
    background: #fdecea;
    border-color: var(--danger-red);
    color: #8b1a1a;
}

/* ── Status pills ── */
.status-pill {
    display: inline-block;
    border-radius: 20px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 0.82rem;
}
.status-received   { background: #e3f2fd; color: #1565c0; }
.status-triaged    { background: #e8f5e9; color: #2e7d32; }
.status-assigned   { background: #e8f5e9; color: #2e7d32; }
.status-inprogress { background: #fff3e0; color: #e65100; }
.status-resolved   { background: #e8f5e9; color: #2e7d32; }
.status-closed     { background: #eeeeee; color: #424242; }

/* ── Info cards ── */
.info-card {
    background: var(--card-bg);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 18px 20px;
    margin-bottom: 14px;
    border-left: 5px solid var(--deep-teal);
}

/* ── Divider ── */
.section-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 20px 0;
}

/* ── Mobile ── */
@media (max-width: 600px) {
    .child-bubble, .bot-bubble { max-width: 92%; }
    .page-wrap { padding: 12px 10px 32px; }
    .select-card { padding: 14px 16px; }
}
</style>"""


def inject_styles() -> None:
    """
    Inject brand CSS into the current page.
    Must be called inside a @ui.page function, not at module level.
    """
    ui.add_head_html(_CSS)
