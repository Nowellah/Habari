from nicegui import ui

DEEP_TEAL = "#006463"
GOLDEN_YELLOW = "#FFC619"
WARM_WHITE = "#FFF9F0"
DARK_TEAL = "#003F40"
FONT_FAMILY = "Nunito, Segoe UI, Arial, sans-serif"


def apply_global_styles() -> None:
    """Inject global CSS into the application."""
    ui.add_head_html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap');

:root {
    --deep-teal: #006463;
    --golden-yellow: #FFC619;
    --warm-white: #FFF9F0;
    --dark-teal: #003F40;
}

body {
    background-color: #FFF9F0;
    font-family: Nunito, Segoe UI, Arial, sans-serif;
    margin: 0;
    padding: 0;
}

.child-bubble {
    background: #FFC619;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    max-width: 80%;
    margin-left: auto;
    word-wrap: break-word;
}

.bot-bubble {
    background: #ffffff;
    border-left: 4px solid #006463;
    border-radius: 4px 18px 18px 18px;
    padding: 10px 16px;
    max-width: 80%;
    word-wrap: break-word;
}

.quick-reply-btn {
    background: #006463;
    color: white;
    border: none;
    border-radius: 20px;
    padding: 6px 16px;
    margin: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-family: Nunito, Segoe UI, Arial, sans-serif;
}

.quick-reply-btn:hover {
    background: #003F40;
}

.demo-badge {
    background: #FFC619;
    color: #003F40;
    font-weight: 700;
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 4px;
}

.emergency-banner {
    background: #FFC619;
    color: #003F40;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-weight: 600;
}

@media (max-width: 600px) {
    .child-bubble, .bot-bubble {
        max-width: 95%;
    }
}
</style>
""")
