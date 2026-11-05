import os
from nicegui import ui, app
from components.header import create_header
from services.session import session_manager
from services.api_client import api_client


def show() -> None:
    """Report review and submission screen."""
    create_header(show_exit=True)

    session_id = app.storage.user.get("session_id")
    session = session_manager.get_session(session_id) if session_id else None

    with ui.column().style(
        "max-width: 560px; margin: 0 auto; padding: 24px 16px; width: 100%;"
    ):
        ui.label("Review Your Report").style(
            "font-size: 1.3rem; font-weight: 700; color: #006463; margin-bottom: 16px;"
        )

        if session is None or session.current_report is None:
            ui.label("No report is currently in progress.").style("color: #555;")
            ui.button(
                "Back to Chat",
                on_click=lambda: ui.navigate.to("/chat"),
            ).style(
                "background-color: #006463; color: white; border-radius: 8px; "
                "padding: 8px 20px; margin-top: 16px;"
            )
            return

        report = session.current_report

        with ui.card().style("width: 100%; margin-bottom: 16px; padding: 16px;"):
            _info_row("Category", report.harm_category)
            _info_row("Description", report.description)
            _info_row("Language", report.language)
            if report.age_bracket:
                _info_row("Age Bracket", report.age_bracket)
            _info_row("Severity", report.severity)

        # Optional file upload
        ui.label("You may add screenshots or evidence (optional)").style(
            "font-size: 0.9rem; color: #555; margin-bottom: 8px;"
        )
        ui.upload(label="Upload evidence (optional)").style("margin-bottom: 16px;")

        submit_btn = ui.button("Submit Report").style(
            "background-color: #006463; color: white; border-radius: 8px; "
            "font-weight: 700; width: 100%; padding: 12px; margin-bottom: 8px;"
        )

        status_label = ui.label("").style("color: #555; font-size: 0.9rem;")

        async def submit():
            submit_btn.disable()
            status_label.set_text("Submitting…")
            response = api_client.send_message(session_id, "__submit_report__", session.language)
            case_code = response.get("case_code", f"DEMO-{session_id[:6].upper()}")
            session_manager.update_session(
                session_id,
                case_code=case_code,
                state="REPORT_SUBMITTED",
            )
            ui.navigate.to("/confirmation")

        submit_btn.on("click", submit)

        ui.button(
            "Back to Chat",
            on_click=lambda: ui.navigate.to("/chat"),
        ).props("flat").style("color: #006463;")


def _info_row(label: str, value: str) -> None:
    with ui.row().style("margin-bottom: 8px; gap: 8px;"):
        ui.label(f"{label}:").style("font-weight: 600; color: #003F40; min-width: 100px;")
        ui.label(value).style("color: #333;")
