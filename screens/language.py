from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


_LANGUAGES = [
    ("en", "English", False),
    ("lg", "Luganda", True),
    ("sw", "Swahili", True),
    ("rn", "Runyankore", True),
]


def show() -> None:
    """Language selection screen."""
    create_header(show_exit=True)

    with ui.column().style(
        "max-width: 480px; margin: 0 auto; padding: 24px 16px; width: 100%;"
    ):
        ui.label("Which language would you like to use?").style(
            "font-size: 1.3rem; font-weight: 700; color: #006463; margin-bottom: 8px;"
        )
        ui.label("You can change this at any time during your conversation.").style(
            "font-size: 0.9rem; color: #555; margin-bottom: 20px;"
        )

        for code, name, limited in _LANGUAGES:
            _language_card(code, name, limited)

        ui.separator().style("margin: 20px 0;")

        ui.button(
            "Continue in English",
            on_click=lambda: _select_language("en"),
        ).style(
            "background-color: #006463; color: white; border-radius: 8px; "
            "font-weight: 700; width: 100%; padding: 12px;"
        )


def _select_language(code: str) -> None:
    session_id = app.storage.user.get("session_id")
    if session_id:
        session_manager.update_session(session_id, language=code)
    ui.navigate.to("/chat")


def _language_card(code: str, name: str, limited: bool) -> None:
    def select():
        _select_language(code)

    with ui.card().style(
        "width: 100%; cursor: pointer; margin-bottom: 10px; "
        "border: 2px solid #006463; border-radius: 10px; padding: 16px;"
    ).on("click", select):
        with ui.row().style("align-items: center; gap: 8px;"):
            ui.label(name).style("font-size: 1.1rem; font-weight: 600; color: #006463;")
            if limited:
                ui.label("limited support").style(
                    "background: #FFC619; color: #003F40; font-size: 0.72rem; "
                    "font-weight: 700; padding: 2px 8px; border-radius: 4px;"
                )
