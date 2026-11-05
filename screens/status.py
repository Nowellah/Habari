import os
from nicegui import ui, app
from components.header import create_header
from services.session import session_manager
from services.api_client import api_client


# ── Status definitions ────────────────────────────────────────────────────────

_STATUSES = {
    "RECEIVED": {
        "label": "Received",
        "css": "status-received",
        "icon": "📥",
        "description": (
            "We have received your report. A safeguarding officer will review it "
            "and decide on the next steps."
        ),
    },
    "TRIAGED": {
        "label": "Triaged",
        "css": "status-triaged",
        "icon": "🔍",
        "description": (
            "Your report has been reviewed and categorised. An officer will be "
            "assigned to your case shortly."
        ),
    },
    "ASSIGNED": {
        "label": "Assigned",
        "css": "status-assigned",
        "icon": "👤",
        "description": (
            "A trained safeguarding officer has been assigned to your case "
            "and will be in touch."
        ),
    },
    "REFERRED": {
        "label": "Referred",
        "css": "status-inprogress",
        "icon": "📨",
        "description": (
            "Your case has been referred to the appropriate support organization "
            "for further action."
        ),
    },
    "IN_PROGRESS": {
        "label": "In Progress",
        "css": "status-inprogress",
        "icon": "⚙️",
        "description": (
            "Your case is being actively worked on by a safeguarding officer."
        ),
    },
    "RESOLVED": {
        "label": "Resolved",
        "css": "status-resolved",
        "icon": "✅",
        "description": (
            "Your case has been resolved. Please contact your safeguarding officer "
            "if you need more information."
        ),
    },
    "CLOSED": {
        "label": "Closed",
        "css": "status-closed",
        "icon": "🔒",
        "description": (
            "This case has been closed. If you have new information or concerns, "
            "you can open a new report."
        ),
    },
}

_DEMO_STATUSES = ["RECEIVED", "TRIAGED", "ASSIGNED", "IN_PROGRESS", "RESOLVED"]


def show() -> None:
    """Case status look-up screen."""
    create_header(show_exit=True)

    session_id = app.storage.user.get("session_id")
    session = session_manager.get_session(session_id) if session_id else None
    prefill = session.case_code if session and session.case_code else ""
    demo_mode = bool(os.getenv("DEMO_MODE", "").strip())

    with ui.column().classes("page-wrap"):
        ui.html(
            '<h2 style="font-size: 1.3rem; font-weight: 800; color: #006463; '
            'margin: 0 0 6px;">Check Your Report Status</h2>'
        )
        ui.html(
            '<p style="font-size: 0.9rem; color: #4a5568; margin: 0 0 20px;">'
            'Enter the case code you received when you submitted your report.</p>'
        )

        if demo_mode:
            ui.html(
                '<div class="emergency-banner" style="margin-bottom: 14px;">'
                '⚠️ <strong>DEMO MODE</strong> — Status results are simulated.'
                '</div>'
            )

        code_input = (
            ui.input(label="Case code", value=prefill, placeholder="e.g. AB-7F3Q9X")
            .style("width: 100%; margin-bottom: 12px;")
            .props("outlined")
        )

        result_area = ui.column().style("width: 100%;")

        async def look_up():
            code = (code_input.value or "").strip().upper()
            result_area.clear()

            if not code:
                with result_area:
                    ui.html(
                        '<p style="color: #c0392b; font-size: 0.9rem;">'
                        '⚠️ Please enter a case code.</p>'
                    )
                return

            with result_area:
                ui.html(
                    '<div style="display:flex; align-items:center; gap:8px; '
                    'color:#006463; padding: 8px 0;">'
                    '<span>Looking up status…</span></div>'
                )

            response = api_client.get_case_status(code)
            result_area.clear()

            with result_area:
                if response.get("demo"):
                    _render_demo_status(code)
                else:
                    _render_live_status(response)

        ui.button("🔍  Look Up", on_click=look_up).classes("btn-primary").props(
            "no-caps"
        ).style("margin-bottom: 16px;")

        ui.html('<hr class="section-divider">')

        ui.button(
            "← Back to Chat",
            on_click=lambda: ui.navigate.to("/chat"),
        ).classes("btn-secondary").props("no-caps")


def _render_demo_status(code: str) -> None:
    """Render a simulated status for demo mode."""
    import random
    status_key = random.choice(_DEMO_STATUSES)
    info = _STATUSES[status_key]
    ui.html(
        f'<div class="info-card" style="margin-bottom: 12px;">'
        f'  <div style="display:flex; align-items:center; gap:10px; margin-bottom: 10px;">'
        f'    <span style="font-size: 1.4rem;">{info["icon"]}</span>'
        f'    <div>'
        f'      <p style="margin:0; font-size:0.78rem; color:#718096;">Case Code</p>'
        f'      <p style="margin:0; font-weight:800; color:#006463; '
        f'         font-size:1.1rem; letter-spacing:1px;">{code}</p>'
        f'    </div>'
        f'    <span class="status-pill {info["css"]}" style="margin-left:auto;">'
        f'      {info["label"]}</span>'
        f'  </div>'
        f'  <p style="margin:0; color:#4a5568; font-size:0.9rem; line-height:1.5;">'
        f'    {info["description"]}</p>'
        f'  <p style="margin: 10px 0 0; font-size:0.75rem; color:#a0aec0; '
        f'     font-style:italic;">This is a simulated status for demo purposes.</p>'
        f'</div>'
    )


def _render_live_status(response: dict) -> None:
    """Render a real status response from the backend."""
    status_key = (response.get("status") or "").upper()
    info = _STATUSES.get(status_key)
    code = response.get("case_code", "—")

    if info:
        ui.html(
            f'<div class="info-card" style="margin-bottom: 12px;">'
            f'  <div style="display:flex; align-items:center; gap:10px; margin-bottom: 10px;">'
            f'    <span style="font-size: 1.4rem;">{info["icon"]}</span>'
            f'    <div>'
            f'      <p style="margin:0; font-size:0.78rem; color:#718096;">Case Code</p>'
            f'      <p style="margin:0; font-weight:800; color:#006463; '
            f'         font-size:1.1rem; letter-spacing:1px;">{code}</p>'
            f'    </div>'
            f'    <span class="status-pill {info["css"]}" style="margin-left:auto;">'
            f'      {info["label"]}</span>'
            f'  </div>'
            f'  <p style="margin:0; color:#4a5568; font-size:0.9rem; line-height:1.5;">'
            f'    {info["description"]}</p>'
            f'</div>'
        )
    else:
        ui.html(
            f'<div class="info-card">'
            f'<p style="color:#4a5568;">Status: <strong>{status_key or "Unknown"}</strong></p>'
            f'<p style="color:#718096; font-size:0.85rem;">Case code: {code}</p>'
            f'</div>'
        )
