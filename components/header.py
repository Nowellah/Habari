import os
from nicegui import ui
from .theme import DEEP_TEAL, DARK_TEAL, GOLDEN_YELLOW


def create_header(show_exit: bool = True) -> None:
    """Render the HABARI application header bar."""
    # Determine logo path
    logo_path = "assets/habari-logo.png" if os.path.exists("assets/habari-logo.png") else "assets/habari-logo.svg"
    demo_mode = bool(os.getenv("DEMO_MODE", "").strip())

    with ui.row().style(
        f"background-color: {DARK_TEAL}; padding: 8px 16px; width: 100%; "
        "align-items: center; box-sizing: border-box; gap: 12px;"
    ).classes("items-center w-full"):
        ui.image(logo_path).style("height: 40px; width: auto;")
        ui.label("HABARI").style(
            f"color: {GOLDEN_YELLOW}; font-weight: 700; font-size: 1.25rem; letter-spacing: 1px;"
        )
        ui.space()

        if demo_mode:
            ui.label("DEMO MODE").classes("demo-badge")

        if show_exit:
            ui.button(
                "Quick Exit",
                on_click=lambda: ui.run_javascript(
                    "window.location.href='https://www.bbc.co.uk/cbbc'"
                ),
            ).props("flat").style(
                "background-color: #c0392b; color: white; border-radius: 6px; "
                "padding: 4px 12px; font-size: 0.85rem;"
            )
