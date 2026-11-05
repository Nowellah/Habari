import os
from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


def show() -> None:
    """Report confirmation screen."""
    create_header(show_exit=True)

    session_id = app.storage.user.get("session_id")
    session = session_manager.get_session(session_id) if session_id else None
    case_code = session.case_code if session else None
    demo_mode = bool(os.getenv("DEMO_MODE", "").strip())

    with ui.column().style(
        "max-width: 560px; margin: 0 auto; padding: 24px 16px; align-items: center; width: 100%;"
    ):
        # Success icon area
        ui.html(
            '<div style="font-size: 3rem; margin-bottom: 8px;">✅</div>'
        )

        ui.label("Your report has been received.").style(
            "font-size: 1.4rem; font-weight: 700; color: #006463; "
            "text-align: center; margin-bottom: 12px;"
        )

        if demo_mode:
            ui.html(
                '<div class="emergency-banner" style="text-align:center; margin-bottom:12px;">'
                "DEMO MODE — This is a simulated report. No real officer has been notified."
                "</div>"
            )

        if case_code:
            with ui.card().style(
                "background: #FFF9F0; border: 2px solid #006463; border-radius: 10px; "
                "padding: 16px; margin-bottom: 16px; text-align: center; width: 100%;"
            ):
                ui.label("Your Case Code").style(
                    "font-size: 0.9rem; color: #555; margin-bottom: 4px;"
                )
                ui.label(case_code).style(
                    "font-size: 1.8rem; font-weight: 700; color: #006463; letter-spacing: 2px;"
                )

            ui.label(
                "Your case code is your reference number. Keep it safe — you can use it "
                "to check the status of your report."
            ).style(
                "font-size: 0.9rem; color: #555; text-align: center; margin-bottom: 20px;"
            )

            ui.button(
                "Copy Case Code",
                on_click=lambda: ui.run_javascript(
                    f"navigator.clipboard.writeText('{case_code}')"
                ),
            ).style(
                "background-color: #FFC619; color: #003F40; border-radius: 8px; "
                "font-weight: 700; width: 100%; padding: 10px; margin-bottom: 8px;"
            )
        else:
            ui.label("Your report has been submitted.").style("color: #555; margin-bottom: 16px;")

        with ui.column().style("width: 100%; gap: 8px;"):
            ui.button(
                "Check Status",
                on_click=lambda: ui.navigate.to("/status"),
            ).style(
                "background-color: #006463; color: white; border-radius: 8px; "
                "font-weight: 700; width: 100%; padding: 10px;"
            )
            ui.button(
                "Continue Chatting",
                on_click=lambda: ui.navigate.to("/chat"),
            ).style(
                "background-color: #006463; color: white; border-radius: 8px; "
                "font-weight: 700; width: 100%; padding: 10px;"
            )
            ui.button(
                "Get Human Help",
                on_click=lambda: ui.navigate.to("/help"),
            ).style(
                "background-color: #FFC619; color: #003F40; border-radius: 8px; "
                "font-weight: 700; width: 100%; padding: 10px;"
            )
