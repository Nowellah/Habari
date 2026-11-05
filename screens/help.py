from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


def show() -> None:
    """Emergency help and human support screen."""
    create_header(show_exit=True)

    with ui.column().style(
        "max-width: 560px; margin: 0 auto; padding: 24px 16px; width: 100%;"
    ):
        ui.label("Get Help Now").style(
            "font-size: 1.5rem; font-weight: 700; color: #006463; margin-bottom: 12px;"
        )

        ui.label(
            "Habari helps you report concerns, but it is not a replacement for emergency services. "
            "If you are in immediate danger, please call 999 or 112 now."
        ).style(
            "font-size: 1rem; color: #333; margin-bottom: 20px; line-height: 1.6;"
        )

        # Child Helpline card
        with ui.card().style(
            "width: 100%; background: #FFF9F0; border: 2px solid #FFC619; "
            "border-radius: 10px; padding: 20px; margin-bottom: 16px; text-align: center;"
        ):
            ui.label("Child Helpline Uganda").style(
                "font-size: 1rem; font-weight: 600; color: #003F40; margin-bottom: 8px;"
            )
            ui.label("116").style(
                "font-size: 3rem; font-weight: 700; color: #006463;"
            )
            ui.label(
                "(Please verify this number before production deployment)"
            ).style("font-size: 0.75rem; color: #888; margin-top: 6px;")

        # Emergency numbers
        with ui.card().style(
            "width: 100%; border: 2px solid #c0392b; border-radius: 10px; "
            "padding: 16px; margin-bottom: 16px;"
        ):
            ui.label("Emergency Services").style(
                "font-weight: 700; color: #c0392b; margin-bottom: 8px;"
            )
            ui.label("Police: 999 / 112").style("font-size: 1.1rem; color: #333;")

        # Talk to safeguarding officer
        ui.button(
            "Talk to a Safeguarding Officer",
            on_click=_request_human_support,
        ).style(
            "background-color: #006463; color: white; border-radius: 8px; "
            "font-weight: 700; width: 100%; padding: 12px; margin-bottom: 8px;"
        )

        ui.button(
            "Back to Chat",
            on_click=lambda: ui.navigate.to("/chat"),
        ).style(
            "background-color: #FFC619; color: #003F40; border-radius: 8px; "
            "font-weight: 700; width: 100%; padding: 12px;"
        )


def _request_human_support() -> None:
    session_id = app.storage.user.get("session_id")
    if session_id:
        session_manager.update_session(session_id, state="HUMAN_SUPPORT")
    ui.navigate.to("/chat")
