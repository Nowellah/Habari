from nicegui import ui, app
from components.header import create_header
from services.session import session_manager


def show() -> None:
    """Emergency help and human support screen."""
    create_header(show_exit=True)

    with ui.column().classes("page-wrap"):
        ui.html(
            '<h2 style="font-size: 1.4rem; font-weight: 800; color: #006463; '
            'margin: 0 0 10px;">Get Help Now</h2>'
        )
        ui.html(
            '<p style="font-size: 0.95rem; color: #4a5568; margin: 0 0 20px; '
            'line-height: 1.65;">'
            'Habari helps you report concerns, but it is not a replacement for '
            'emergency services or a trained safeguarding professional. '
            'If you are in <strong>immediate danger</strong>, please call for help now.'
            '</p>'
        )

        # ── Child Helpline ────────────────────────────────────────────────────
        with ui.element("div").style(
            "background: #FFF9F0; border: 2px solid #FFC619; border-radius: 14px; "
            "padding: 20px; margin-bottom: 14px; text-align: center; width: 100%; "
            "box-shadow: 0 2px 8px rgba(255,198,25,0.2);"
        ):
            ui.html(
                '<p style="font-size: 0.9rem; font-weight: 700; color: #003F40; margin: 0 0 4px;">'
                '📞 Child Helpline Uganda</p>'
            )
            # Clickable phone link
            ui.html(
                '<a href="tel:116" style="font-size: 3rem; font-weight: 800; '
                'color: #006463; text-decoration: none; display: block; '
                'margin: 4px 0;">116</a>'
            )
            ui.html(
                '<p style="font-size: 0.78rem; color: #718096; margin: 6px 0 0; '
                'font-style: italic;">'
                'Free call. Available 24 hours. '
                '(Verify this number before production deployment.)'
                '</p>'
            )

        # ── Emergency services ────────────────────────────────────────────────
        with ui.element("div").style(
            "background: #fdecea; border: 2px solid #c0392b; border-radius: 14px; "
            "padding: 16px 20px; margin-bottom: 14px; width: 100%;"
        ):
            ui.html(
                '<p style="font-weight: 700; color: #c0392b; margin: 0 0 8px; '
                'font-size: 1rem;">🚨 Emergency Services</p>'
            )
            with ui.row().style("gap: 12px; flex-wrap: wrap;"):
                ui.html(
                    '<a href="tel:999" style="font-size: 1.3rem; font-weight: 800; '
                    'color: #c0392b; text-decoration: none; '
                    'background: white; border-radius: 8px; padding: 6px 18px; '
                    'border: 2px solid #c0392b;">📱 999</a>'
                )
                ui.html(
                    '<a href="tel:112" style="font-size: 1.3rem; font-weight: 800; '
                    'color: #c0392b; text-decoration: none; '
                    'background: white; border-radius: 8px; padding: 6px 18px; '
                    'border: 2px solid #c0392b;">📱 112</a>'
                )

        # ── Talk to officer ───────────────────────────────────────────────────
        with ui.element("div").classes("info-card").style("margin-bottom: 14px;"):
            ui.html(
                '<p style="font-weight: 700; color: #006463; margin: 0 0 6px;">👤 Safeguarding Officer</p>'
            )
            ui.html(
                '<p style="font-size: 0.88rem; color: #4a5568; margin: 0 0 12px; line-height:1.5;">'
                'A trained safeguarding officer can review your conversation and '
                'advise you. They will not share your information with a parent or '
                'guardian without telling you first, unless there is an immediate risk to your safety.'
                '</p>'
            )
            ui.html(
                '<p style="font-size: 0.78rem; color: #a0aec0; margin: 0; font-style:italic;">'
                'Note: In demo mode, officer connection is not live.'
                '</p>'
            )

        # ── Important notice ──────────────────────────────────────────────────
        with ui.element("div").style(
            "background: #f0f4f8; border-radius: 10px; padding: 14px 16px; "
            "margin-bottom: 20px; width: 100%;"
        ):
            ui.html(
                '<p style="font-size: 0.82rem; color: #4a5568; margin: 0; line-height: 1.6;">'
                '⚠️ <strong>Please note:</strong> Habari cannot guarantee immediate '
                'rescue, instant confidentiality, or the deletion of reports. '
                'Safeguarding records may be kept as required by law.'
                '</p>'
            )

        # ── Action buttons ────────────────────────────────────────────────────
        ui.button(
            "💬  Talk to a Safeguarding Officer",
            on_click=_request_human_support,
        ).classes("btn-primary").props("no-caps").style("margin-bottom: 10px;")

        ui.button(
            "← Back to Chat",
            on_click=lambda: ui.navigate.to("/chat"),
        ).classes("btn-secondary").props("no-caps")


def _request_human_support() -> None:
    session_id = app.storage.user.get("session_id")
    if session_id:
        session_manager.update_session(session_id, state="HUMAN_SUPPORT")
    ui.navigate.to("/chat")
