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

    with ui.column().classes("page-wrap").style("align-items: center;"):

        # ── Success icon ──────────────────────────────────────────────────────
        ui.html(
            '<div style="width: 72px; height: 72px; background: #e8f5e9; '
            'border-radius: 50%; display: flex; align-items: center; '
            'justify-content: center; font-size: 2rem; margin-bottom: 12px;">✅</div>'
        )

        ui.html(
            '<h2 style="font-size: 1.4rem; font-weight: 800; color: #006463; '
            'text-align: center; margin: 0 0 10px;">Your report has been received.</h2>'
        )

        # ── DEMO notice ───────────────────────────────────────────────────────
        if demo_mode:
            ui.html(
                '<div class="emergency-banner" style="text-align: center; width: 100%; '
                'margin-bottom: 14px;">'
                '⚠️ <strong>DEMO MODE</strong> — This is a simulated report. '
                'No real safeguarding officer has been notified.'
                '</div>'
            )

        # ── Case code card ────────────────────────────────────────────────────
        if case_code:
            with ui.element("div").style(
                "background: #FFF9F0; border: 2px solid #006463; border-radius: 14px; "
                "padding: 20px; margin-bottom: 16px; text-align: center; width: 100%; "
                "box-shadow: 0 2px 12px rgba(0,100,99,0.12);"
            ):
                ui.html(
                    '<p style="font-size: 0.85rem; color: #718096; margin: 0 0 6px;">Your Case Code</p>'
                )
                ui.html(
                    f'<p style="font-size: 2rem; font-weight: 800; color: #006463; '
                    f'letter-spacing: 3px; margin: 0;">{case_code}</p>'
                )

            ui.html(
                '<p style="font-size: 0.88rem; color: #4a5568; text-align: center; '
                'margin: 0 0 20px; line-height: 1.6;">'
                'Keep this code safe. You can use it to check the status of your report '
                'at any time.'
                '</p>'
            )

            # Copy button
            ui.button(
                "📋  Copy Case Code",
                on_click=lambda: ui.run_javascript(
                    f"navigator.clipboard.writeText('{case_code}').then(function(){{"
                    f"  alert('Case code copied!');"
                    f"}});"
                ),
            ).classes("btn-accent").props("no-caps").style("margin-bottom: 10px;")
        else:
            ui.html(
                '<p style="color: #4a5568; text-align: center; margin-bottom: 20px;">'
                'Your report has been submitted successfully.</p>'
            )

        # ── Action buttons ────────────────────────────────────────────────────
        with ui.column().style("width: 100%; gap: 10px;"):
            ui.button(
                "🔍  Check Report Status",
                on_click=lambda: ui.navigate.to("/status"),
            ).classes("btn-primary").props("no-caps")

            ui.button(
                "💬  Continue Chatting",
                on_click=lambda: ui.navigate.to("/chat"),
            ).classes("btn-secondary").props("no-caps")

            ui.button(
                "🆘  Get Human Help",
                on_click=lambda: ui.navigate.to("/help"),
            ).classes("btn-accent").props("no-caps")

        # ── Footer note ───────────────────────────────────────────────────────
        ui.html(
            '<p style="font-size: 0.78rem; color: #718096; text-align: center; '
            'margin-top: 20px; line-height: 1.5;">'
            'A trained safeguarding officer will review your report. '
            'Nothing will be shared with a parent or guardian without your knowledge, '
            'unless there is an immediate risk to your safety.'
            '</p>'
        )
