import os
from nicegui import ui
from components.header import create_header


def show() -> None:
    """Welcome / landing screen."""
    create_header(show_exit=True)

    with ui.column().style(
        "max-width: 480px; margin: 0 auto; padding: 24px 16px; align-items: center; width: 100%;"
    ):
        # Logo centered
        logo_path = (
            "assets/habari-logo.png"
            if os.path.exists("assets/habari-logo.png")
            else "assets/habari-logo.svg"
        )
        ui.image(logo_path).style("height: 120px; width: auto; margin: 16px 0;")

        ui.label("Hello! Welcome to Habari. Your voice matters, and we're here to listen.").style(
            "font-size: 1.3rem; font-weight: 700; color: #006463; text-align: center; "
            "margin-bottom: 12px;"
        )

        ui.label(
            "You can talk about something worrying you online, ask questions, or request help. "
            "You do not have to share your name to begin."
        ).style(
            "font-size: 1rem; color: #333; text-align: center; margin-bottom: 24px; "
            "line-height: 1.5;"
        )

        # Buttons — full-width on mobile
        with ui.column().style("width: 100%; gap: 12px;"):
            ui.button(
                "Start Chat",
                on_click=lambda: ui.navigate.to("/age"),
            ).style(
                "background-color: #006463; color: white; border-radius: 8px; "
                "font-weight: 700; font-size: 1rem; width: 100%; padding: 12px;"
            )

            ui.button(
                "Get Help Now",
                on_click=lambda: ui.navigate.to("/help"),
            ).style(
                "background-color: #FFC619; color: #003F40; border-radius: 8px; "
                "font-weight: 700; font-size: 1rem; width: 100%; padding: 12px;"
            )

            ui.button(
                "Quick Exit",
                on_click=lambda: ui.run_javascript(
                    "window.location.href='https://www.bbc.co.uk/cbbc'"
                ),
            ).style(
                "background-color: #c0392b; color: white; border-radius: 8px; "
                "font-weight: 700; font-size: 1rem; width: 100%; padding: 12px;"
            )

        ui.label(
            "We keep your information private. You can use Habari without sharing your name."
        ).style(
            "font-size: 0.8rem; color: #666; font-style: italic; "
            "text-align: center; margin-top: 20px;"
        )
