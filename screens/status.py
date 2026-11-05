from nicegui import ui, app
from components.header import create_header
from services.session import session_manager
from services.api_client import api_client


_STATUS_MESSAGES: dict[str, str] = {
    "RECEIVED": "We have received your report and it is being reviewed.",
    "UNDER_REVIEW": "A safeguarding officer is reviewing your case.",
    "RESOLVED": "Your case has been resolved. Please contact your support officer for details.",
    "CLOSED": "This case has been closed.",
}


def show() -> None:
    """Case status look-up screen."""
    create_header(show_exit=True)

    session_id = app.storage.user.get("session_id")
    session = session_manager.get_session(session_id) if session_id else None
    prefill = session.case_code if session and session.case_code else ""

    with ui.column().style(
        "max-width: 560px; margin: 0 auto; padding: 24px 16px; width: 100%;"
    ):
        ui.label("Check Your Report Status").style(
            "font-size: 1.3rem; font-weight: 700; color: #006463; margin-bottom: 16px;"
        )

        code_input = ui.input(
            label="Enter your case code",
            value=prefill,
        ).style("width: 100%; margin-bottom: 12px;").props("outlined")

        result_area = ui.column().style("width: 100%;")

        async def look_up():
            code = code_input.value.strip()
            result_area.clear()
            if not code:
                with result_area:
                    ui.label("Please enter a case code.").style("color: #c0392b;")
                return

            with result_area:
                spinner = ui.spinner(size="sm").style("color: #006463;")

            response = api_client.get_case_status(code)

            result_area.clear()
            with result_area:
                if response.get("demo"):
                    ui.html(
                        '<div class="emergency-banner">'
                        "Status information is not available in demo mode."
                        "</div>"
                    )
                else:
                    status_key = response.get("status", "")
                    friendly = _STATUS_MESSAGES.get(
                        status_key,
                        "We could not retrieve the status. Please try again or call 116.",
                    )
                    with ui.card().style(
                        "width: 100%; padding: 16px; border-left: 4px solid #006463;"
                    ):
                        ui.label(f"Status: {status_key}").style(
                            "font-weight: 700; color: #006463; margin-bottom: 4px;"
                        )
                        ui.label(friendly).style("color: #333;")

        ui.button("Look Up", on_click=look_up).style(
            "background-color: #006463; color: white; border-radius: 8px; "
            "font-weight: 700; padding: 10px 24px; margin-bottom: 16px;"
        )

        ui.button(
            "Back to Chat",
            on_click=lambda: ui.navigate.to("/chat"),
        ).props("flat").style("color: #006463;")
