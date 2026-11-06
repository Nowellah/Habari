import os
import random
import string
from nicegui import ui, app
from components.header import create_header
from services.session import session_manager
from services.api_client import api_client
from services.case_store import case_store
from services.safety import safety_service
from models.report import Report


def show() -> None:
    """Report review and submission screen."""
    create_header(show_exit=True)

    session_id = app.storage.user.get("session_id")
    session = session_manager.get_session(session_id) if session_id else None
    demo_mode = bool(os.getenv("DEMO_MODE", "").strip())

    with ui.column().classes("page-wrap"):
        ui.html(
            '<h2 style="font-size: 1.3rem; font-weight: 800; color: #006463; '
            'margin: 0 0 4px;">Review Your Report</h2>'
        )
        ui.html(
            '<p style="font-size: 0.88rem; color: #4a5568; margin: 0 0 16px;">'
            'Check your information before submitting. '
            'You can edit your description below.</p>'
        )

        if demo_mode:
            ui.html(
                '<div class="emergency-banner" style="margin-bottom: 14px;">'
                '⚠️ <strong>DEMO MODE</strong> — No real report will be sent to an officer.'
                '</div>'
            )

        # ── Guard: no session ─────────────────────────────────────────────────
        if session is None:
            _no_report_state("No active session found.")
            return

        # ── Auto-build a report if none exists ───────────────────────────────
        report = session.current_report
        if report is None:
            harm = session.harm_category or "General concern"
            # Collect last substantive child message
            from services.conversation import HARM_CATEGORIES, HARM_CATEGORIES_SIMPLE
            child_texts = [
                m.text for m in session.messages
                if m.role == "child"
                and m.text not in HARM_CATEGORIES
                and m.text not in HARM_CATEGORIES_SIMPLE
            ]
            desc = child_texts[-1] if child_texts else "No description provided yet."
            report = Report(
                harm_category=harm,
                description=desc,
                language=session.language,
                age_bracket=session.age_bracket,
            )
            session_manager.update_session(session_id, current_report=report)
            session = session_manager.get_session(session_id)
            report = session.current_report  # type: ignore[assignment]

        # ── Report summary ────────────────────────────────────────────────────
        with ui.element("div").classes("info-card"):
            _info_row("📂 Category", report.harm_category)
            _info_row("🌍 Language", report.language.upper())
            if report.age_bracket:
                _info_row("👤 Age group", report.age_bracket)
            sev = report.severity
            sev_colors = {
                "critical": ("#fdecea", "#c0392b"),
                "high":     ("#fff3e0", "#e65100"),
                "medium":   ("#fff8e1", "#f57c00"),
                "low":      ("#e8f5e9", "#2e7d32"),
            }
            bg, fg = sev_colors.get(sev, ("#f0f4f8", "#4a5568"))
            with ui.row().style("gap: 8px; align-items: center; margin-top: 4px;"):
                ui.html(
                    '<span style="font-weight: 600; color: #003F40; '
                    'min-width: 120px; flex-shrink: 0;">⚠️ Severity</span>'
                )
                ui.html(
                    f'<span class="status-pill" style="background:{bg}; color:{fg};">'
                    f'{sev.capitalize()}</span>'
                )

        # ── Editable description ──────────────────────────────────────────────
        ui.html(
            '<p style="font-size: 0.88rem; font-weight: 600; color: #003F40; '
            'margin: 0 0 6px;">📝 Your description</p>'
        )
        desc_input = (
            ui.textarea(value=report.description)
            .style(
                "width: 100%; font-family: Nunito, Arial, sans-serif; "
                "font-size: 0.95rem; margin-bottom: 14px;"
            )
            .props("outlined rows=4")
        )

        # ── Optional evidence upload ──────────────────────────────────────────
        with ui.expansion("📎 Add evidence (optional)", icon="attach_file").style(
            "width: 100%; margin-bottom: 14px; border: 1px solid #e2e8f0; "
            "border-radius: 10px; background: white;"
        ):
            ui.html(
                '<p style="font-size: 0.85rem; color: #718096; padding: 8px 0 4px;">'
                'Upload screenshots or files that support your report. '
                'This is entirely optional.</p>'
            )
            ui.upload(label="Choose file", auto_upload=False, max_files=3).style(
                "width: 100%;"
            )

        # ── Status label ──────────────────────────────────────────────────────
        status_html = ui.html("").style("font-size: 0.88rem; text-align: center;")

        # ── Submit button ─────────────────────────────────────────────────────
        submit_btn = (
            ui.button("📤  Submit Report")
            .classes("btn-primary")
            .props("no-caps")
            .style("margin-bottom: 10px;")
        )

        async def submit():
            desc = (desc_input.value or "").strip()
            if not desc:
                status_html.set_content(
                    '<span style="color:#c0392b;">⚠️ Please add a description before submitting.</span>'
                )
                return

            # Update report with edited description
            session_manager.update_session(
                session_id,
                current_report=Report(
                    harm_category=report.harm_category,
                    description=desc,
                    language=report.language,
                    age_bracket=report.age_bracket,
                    severity=report.severity,
                ),
            )

            submit_btn.set_enabled(False)
            status_html.set_content(
                '<span style="color:#006463;">⏳ Submitting your report…</span>'
            )

            response = api_client.send_message(
                session_id, "__submit_report__",
                session_manager.get_session(session_id).language,
            )

            # Use real case code if backend returned one; else generate demo code
            case_code = response.get("case_code") or _demo_case_code()

            # Register in the local case store so the officer dashboard sees it
            current = session_manager.get_session(session_id)
            urgency = safety_service.check_urgency(desc)
            # Map string severity → integer scale (1-4) matching Django backend
            _sev_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            sev_int = _sev_map.get(report.severity, 2)
            case_store.register_case(
                session_id=session_id,
                harm_category=report.harm_category,
                description=desc,
                severity=sev_int,
                language=report.language,
                age_bracket=report.age_bracket,
                messages=[
                    {"role": m.role, "text": m.text}
                    for m in (current.messages if current else [])
                ],
                is_urgent=urgency["urgent"],
                case_code=case_code,
            )

            session_manager.update_session(
                session_id,
                case_code=case_code,
                state="REPORT_SUBMITTED",
            )
            ui.navigate.to("/confirmation")

        submit_btn.on("click", submit)

        ui.html('<hr class="section-divider">')

        ui.button(
            "← Back to Chat",
            on_click=lambda: ui.navigate.to("/chat"),
        ).classes("btn-secondary").props("no-caps")


# ── helpers ───────────────────────────────────────────────────────────────────

def _no_report_state(msg: str) -> None:
    ui.html(
        f'<div class="emergency-banner" style="margin-bottom: 16px;">{msg}</div>'
    )
    ui.button(
        "Start a conversation →",
        on_click=lambda: ui.navigate.to("/chat"),
    ).classes("btn-primary").props("no-caps")


def _info_row(label: str, value: str) -> None:
    with ui.row().style("gap: 8px; align-items: flex-start; margin-bottom: 10px;"):
        ui.html(
            f'<span style="font-weight: 600; color: #003F40; '
            f'min-width: 120px; flex-shrink: 0;">{label}</span>'
        )
        ui.html(f'<span style="color: #1a1a2e; line-height: 1.4;">{value}</span>')


def _demo_case_code() -> str:
    chars = string.ascii_uppercase + string.digits
    prefix = "".join(random.choices(string.ascii_uppercase, k=2))
    suffix = "".join(random.choices(chars, k=6))
    return f"{prefix}-{suffix}"
