import uuid
from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


_AGE_BRACKETS = [
    ("Under 10",      "🧒", "We'll use simple, friendly words."),
    ("10–12",         "👦", "We'll keep things clear and easy."),
    ("13–15",         "🧑", "We'll give you full information."),
    ("16–17",         "👤", "We'll treat you as a young adult."),
    ("Prefer not to say", "🤐", "That's completely fine."),
]


def show() -> None:
    """Age selection screen."""
    create_header(show_exit=True)

    # Create a fresh session at the start of each journey
    session_id = str(uuid.uuid4())
    app.storage.user["session_id"] = session_id
    session_manager.create_session(session_id)

    with ui.column().classes("page-wrap"):
        ui.html(
            '<h2 style="font-size: 1.3rem; font-weight: 800; color: #006463; '
            'margin: 0 0 6px;">Which age group are you in?</h2>'
        )
        ui.html(
            '<p style="font-size: 0.9rem; color: #4a5568; margin: 0 0 20px;">'
            'This helps us talk to you in the right way. You can skip this step.</p>'
        )

        for bracket, icon, hint in _AGE_BRACKETS:
            _age_card(bracket, icon, hint, session_id)

        ui.html('<hr class="section-divider">')

        ui.button(
            "Skip this step →",
            on_click=lambda: ui.navigate.to("/language"),
        ).props("flat no-caps").style(
            "color: #006463; font-size: 0.9rem; font-weight: 600; align-self: center;"
        )


def _age_card(bracket: str, icon: str, hint: str, session_id: str) -> None:
    def select():
        session_manager.update_session(session_id, age_bracket=bracket)
        ui.navigate.to("/language")

    with ui.element("div").classes("select-card").on("click", select):
        ui.html(f'<span style="font-size: 1.6rem;">{icon}</span>')
        with ui.column().style("gap: 2px;"):
            ui.html(
                f'<span style="font-size: 1.05rem; font-weight: 700; '
                f'color: #006463;">{bracket}</span>'
            )
            ui.html(
                f'<span style="font-size: 0.8rem; color: #718096;">{hint}</span>'
            )
