import uuid
from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


_AGE_BRACKETS = [
    "Under 10",
    "10–12",
    "13–15",
    "16–17",
    "Prefer not to say",
]


def show() -> None:
    """Age selection screen."""
    create_header(show_exit=True)

    # Create a new session for this visit
    session_id = str(uuid.uuid4())
    app.storage.user["session_id"] = session_id
    session_manager.create_session(session_id)

    with ui.column().style(
        "max-width: 480px; margin: 0 auto; padding: 24px 16px; width: 100%;"
    ):
        ui.label("Which age group are you in?").style(
            "font-size: 1.3rem; font-weight: 700; color: #006463; margin-bottom: 8px;"
        )
        ui.label("This helps us use words that are right for you. You can skip this step.").style(
            "font-size: 0.9rem; color: #555; margin-bottom: 20px;"
        )

        for bracket in _AGE_BRACKETS:
            _age_card(bracket, session_id)

        ui.separator().style("margin: 20px 0;")

        ui.button(
            "Skip this step",
            on_click=lambda: ui.navigate.to("/language"),
        ).props("flat").style("color: #006463; font-size: 0.9rem;")


def _age_card(bracket: str, session_id: str) -> None:
    def select():
        session_manager.update_session(session_id, age_bracket=bracket)
        ui.navigate.to("/language")

    with ui.card().style(
        "width: 100%; cursor: pointer; margin-bottom: 10px; "
        "border: 2px solid #006463; border-radius: 10px; padding: 16px; "
        "transition: background 0.2s;"
    ).on("click", select):
        ui.label(bracket).style(
            "font-size: 1.1rem; font-weight: 600; color: #006463;"
        )
