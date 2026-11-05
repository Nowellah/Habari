from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


_LANGUAGES = [
    ("en", "English",    "🇬🇧", False,  "Fully supported"),
    ("lg", "Luganda",    "🇺🇬", True,   "Limited support"),
    ("sw", "Swahili",    "🌍", True,   "Limited support"),
    ("rn", "Runyankore", "🇺🇬", True,   "Limited support"),
]


def show() -> None:
    """Language selection screen."""
    create_header(show_exit=True)

    with ui.column().classes("page-wrap"):
        ui.html(
            '<h2 style="font-size: 1.3rem; font-weight: 800; color: #006463; '
            'margin: 0 0 6px;">Which language would you like?</h2>'
        )
        ui.html(
            '<p style="font-size: 0.9rem; color: #4a5568; margin: 0 0 20px;">'
            'You can change this at any time during your conversation.</p>'
        )

        for code, name, flag, limited, support_label in _LANGUAGES:
            _language_card(code, name, flag, limited, support_label)

        ui.html('<hr class="section-divider">')

        ui.button(
            "Continue in English →",
            on_click=lambda: _select_language("en"),
        ).classes("btn-primary").props("no-caps")


def _select_language(code: str) -> None:
    session_id = app.storage.user.get("session_id")
    if session_id:
        session_manager.update_session(session_id, language=code)
    ui.navigate.to("/chat")


def _language_card(code: str, name: str, flag: str, limited: bool, support_label: str) -> None:
    def select():
        _select_language(code)

    with ui.element("div").classes("select-card").on("click", select):
        ui.html(f'<span style="font-size: 1.8rem;">{flag}</span>')
        with ui.row().style("align-items: center; gap: 10px; flex: 1;"):
            ui.html(
                f'<span style="font-size: 1.05rem; font-weight: 700; '
                f'color: #006463;">{name}</span>'
            )
        # Support badge
        badge_style = (
            "background: #e8f5e9; color: #2e7d32;"
            if not limited else
            "background: #fff3e0; color: #e65100;"
        )
        ui.html(
            f'<span style="margin-left: auto; font-size: 0.72rem; font-weight: 700; '
            f'padding: 3px 10px; border-radius: 20px; white-space: nowrap; '
            f'{badge_style}">{support_label}</span>'
        )
