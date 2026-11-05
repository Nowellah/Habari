import os
from nicegui import ui
from .theme import GOLDEN_YELLOW, DARK_TEAL


def create_header(show_exit: bool = True) -> None:
    """Render the HABARI application header bar."""
    logo_path = (
        "assets/habari-logo.png"
        if os.path.exists("assets/habari-logo.png")
        else "assets/habari-logo.svg"
    )
    demo_mode = bool(os.getenv("DEMO_MODE", "").strip())

    with ui.row().style(
        f"background-color: {DARK_TEAL}; padding: 10px 16px; width: 100%; "
        "align-items: center; box-sizing: border-box; gap: 10px; "
        "position: sticky; top: 0; z-index: 100; "
        "box-shadow: 0 2px 8px rgba(0,0,0,0.25);"
    ):
        # Logo — clicking goes home
        ui.image(logo_path).style(
            "height: 38px; width: auto; cursor: pointer;"
        ).on("click", lambda: ui.navigate.to("/"))

        ui.label("HABARI").style(
            f"color: {GOLDEN_YELLOW}; font-weight: 800; font-size: 1.2rem; "
            "letter-spacing: 2px; cursor: pointer;"
        ).on("click", lambda: ui.navigate.to("/"))

        ui.space()

        if demo_mode:
            ui.html('<span class="demo-badge">DEMO</span>')

        if show_exit:
            ui.button(
                "✕ Exit",
                on_click=lambda: ui.run_javascript(
                    "window.location.replace('https://www.bbc.co.uk/cbbc')"
                ),
            ).props("flat no-caps").style(
                "background-color: #c0392b; color: white; border-radius: 6px; "
                "padding: 4px 14px; font-size: 0.82rem; font-weight: 700; min-height: 32px;"
            )
