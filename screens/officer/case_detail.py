"""
Officer Case Detail — mirrors django dashboard/officer_case.html from the UI branch.

Sections:
  1. Case metadata (code, severity, pick, status, SLA, language, channel)
  2. Description / child's words
  3. Actions (acknowledge, assign, set status, add note, close)
  4. Notes log
  5. Flags
  6. Sanitised message thread (collapsed by default)
"""
import html as _html
from nicegui import ui, app
from services.case_store import case_store
from models.case import SEVERITY_META, STATUS_LABELS, PICKS, CaseStatus


_OFFICERS = ["Officer Nakato", "Officer Ssemakula", "Supervisor Apio"]

_OPEN_STATUSES: list[tuple[str, str]] = [
    ("triaged",     "Triaged"),
    ("assigned",    "Assigned"),
    ("in_progress", "In Progress"),
    ("referred",    "Referred"),
    ("resolved",    "Resolved"),
]
_CLOSE_REASONS: list[tuple[str, str]] = [
    ("closed",             "Resolved & closed"),
    ("closed_unfounded",   "Closed: unfounded"),
    ("closed_child_stop",  "Closed: child asked to stop"),
]


# ── Auth guard ────────────────────────────────────────────────────────────────

def _require_officer() -> bool:
    if not app.storage.user.get("officer"):
        ui.navigate.to("/officer/login")
        return False
    return True


# ── Page ─────────────────────────────────────────────────────────────────────

def show(code: str) -> None:
    if not _require_officer():
        return

    officer = app.storage.user.get("officer", "Officer")
    case = case_store.get_case(code)

    _topbar()

    with ui.column().style(
        "max-width: 1000px; margin: 0 auto; padding: 20px 16px 48px; width: 100%;"
    ):
        # Back link
        ui.html(
            '<a href="/officer/dashboard" style="color:#006463;font-size:0.88rem;'
            'font-weight:700;text-decoration:none;">← Case queue</a>'
        )

        if case is None:
            ui.html(
                f'<div style="background:#fdecea;border:2px solid #B3261E;border-radius:12px;'
                f'padding:20px;margin-top:16px;color:#B3261E;font-weight:600;">'
                f'Case <strong>{_html.escape(code.upper())}</strong> was not found.</div>'
            )
            return

        meta = case.severity_meta

        # ── Title ──────────────────────────────────────────────────────────
        ui.html(
            f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0 20px;">'
            f'  <h1 style="font-size:1.4rem;font-weight:800;color:#003F40;margin:0;'
            f'      font-family:monospace;">{_html.escape(case.case_code)}</h1>'
            f'  <span style="background:{meta["bg"]};color:{meta["fg"]};border-radius:20px;'
            f'        padding:4px 14px;font-weight:700;font-size:0.88rem;">'
            f'    Severity {case.severity} — {meta["label"]}'
            f'  </span>'
            f'  {"<span style=\"background:#fdecea;color:#B3261E;border-radius:6px;padding:3px 10px;font-size:0.78rem;font-weight:700;\">🚨 URGENT</span>" if case.is_urgent else ""}'
            f'</div>'
        )

        with ui.row().style("gap:16px;flex-wrap:wrap;width:100%;align-items:flex-start;"):

            # ── Left column: metadata + description ────────────────────────
            with ui.column().style("flex:2;min-width:280px;gap:16px;"):

                # Metadata card
                with ui.element("div").style(_card_style()):
                    ui.html('<h3 style="font-size:0.95rem;font-weight:700;color:#003F40;margin:0 0 14px;">Case Details</h3>')
                    _dl_row("Status",        case.status_label)
                    _dl_row("Pick",          f'{case.pick} — {PICKS.get(case.pick, {}).get("label_en", "—")}')
                    _dl_row("Category",      case.harm_category)
                    _dl_row("Language",      case.language.upper())
                    _dl_row("Age bracket",   case.age_display)
                    _dl_row("Assigned to",   case.assigned_to or "Not assigned")
                    _dl_row("Triage source", case.triage_source)
                    _dl_row("Received",      case.submitted_display)
                    if case.flags:
                        _dl_row("Flags", ", ".join(case.flags))

                # Description card
                with ui.element("div").style(_card_style()):
                    ui.html('<h3 style="font-size:0.95rem;font-weight:700;color:#003F40;margin:0 0 10px;">Child\'s Description</h3>')
                    ui.html(
                        f'<p style="color:#1a1a2e;line-height:1.6;font-size:0.92rem;'
                        f'white-space:pre-line;background:#FFF9F0;border-left:4px solid #006463;'
                        f'border-radius:4px 10px 10px 4px;padding:12px 14px;margin:0;">'
                        f'{_html.escape(case.description)}</p>'
                    )

                # Message thread (collapsed)
                if case.messages:
                    with ui.expansion(
                        f"💬 Message thread ({len(case.messages)} messages) — open only if needed",
                        icon="chat"
                    ).style(
                        "width:100%;border:1px solid #e2e8f0;border-radius:12px;background:white;"
                    ):
                        for msg in case.messages:
                            role = msg.get("role", "bot")
                            text = _html.escape(msg.get("text", ""))
                            align = "flex-end" if role == "child" else "flex-start"
                            bubble_bg = "#FFC619" if role == "child" else "#f0f4f8"
                            bubble_fg = "#003F40" if role == "child" else "#1a1a2e"
                            label = "Child" if role == "child" else "Habari"
                            ui.html(
                                f'<div style="display:flex;justify-content:{align};margin:4px 0;">'
                                f'  <div style="background:{bubble_bg};color:{bubble_fg};'
                                f'       border-radius:12px;padding:8px 14px;max-width:80%;'
                                f'       font-size:0.88rem;">'
                                f'    <strong>{label}</strong><br>{text}'
                                f'  </div>'
                                f'</div>'
                            )

            # ── Right column: actions + notes ──────────────────────────────
            with ui.column().style("flex:1;min-width:260px;gap:16px;"):

                # Actions card
                with ui.element("div").style(_card_style()):
                    ui.html('<h3 style="font-size:0.95rem;font-weight:700;color:#003F40;margin:0 0 14px;">Actions</h3>')

                    feedback = ui.html("").style("font-size:0.85rem;margin-bottom:8px;")

                    # Acknowledge
                    if case.status == "received":
                        ui.button(
                            "✅ Acknowledge case",
                            on_click=lambda: _ack(code, feedback),
                        ).style(
                            "background:#006463;color:white;border-radius:8px;"
                            "font-weight:700;width:100%;padding:10px;margin-bottom:8px;"
                        ).props("no-caps")

                    # Assign to officer
                    ui.html('<label style="font-size:0.82rem;font-weight:600;color:#003F40;">Assign to officer</label>')
                    assign_sel = ui.select(
                        options=["— select —"] + _OFFICERS,
                        value=case.assigned_to or "— select —",
                    ).style("width:100%;margin-bottom:6px;").props("outlined dense")
                    ui.button(
                        "Assign",
                        on_click=lambda: _assign(code, assign_sel.value, officer, feedback),
                    ).style(
                        "background:#006463;color:white;border-radius:8px;"
                        "font-weight:700;width:100%;padding:8px;margin-bottom:12px;"
                    ).props("no-caps")

                    # Set status
                    ui.html('<label style="font-size:0.82rem;font-weight:600;color:#003F40;">Update status</label>')
                    status_sel = ui.select(
                        options={k: v for k, v in _OPEN_STATUSES},
                        value=case.status if case.status in dict(_OPEN_STATUSES) else "triaged",
                    ).style("width:100%;margin-bottom:6px;").props("outlined dense")
                    ui.button(
                        "Set Status",
                        on_click=lambda: _set_status(code, status_sel.value, feedback),
                    ).style(
                        "background:#006463;color:white;border-radius:8px;"
                        "font-weight:700;width:100%;padding:8px;margin-bottom:12px;"
                    ).props("no-caps")

                    # Close case
                    if case.is_open:
                        ui.html('<label style="font-size:0.82rem;font-weight:600;color:#003F40;">Close case</label>')
                        close_sel = ui.select(
                            options={k: v for k, v in _CLOSE_REASONS},
                            value="closed",
                        ).style("width:100%;margin-bottom:6px;").props("outlined dense")
                        ui.button(
                            "Close Case",
                            on_click=lambda: _close(code, close_sel.value, officer, feedback),
                        ).style(
                            "background:#c0392b;color:white;border-radius:8px;"
                            "font-weight:700;width:100%;padding:8px;"
                        ).props("no-caps")

                # Notes card
                with ui.element("div").style(_card_style()):
                    ui.html('<h3 style="font-size:0.95rem;font-weight:700;color:#003F40;margin:0 0 12px;">Officer Notes</h3>')

                    notes_area = ui.column().style("width:100%;gap:8px;margin-bottom:10px;")
                    with notes_area:
                        _render_notes(case.notes)

                    note_input = (
                        ui.textarea(placeholder="Add a note…")
                        .style("width:100%;font-size:0.88rem;")
                        .props("outlined dense rows=2")
                    )
                    ui.button(
                        "Add Note",
                        on_click=lambda: _add_note(code, note_input, notes_area, officer),
                    ).style(
                        "background:#006463;color:white;border-radius:8px;"
                        "font-weight:700;width:100%;padding:8px;margin-top:6px;"
                    ).props("no-caps")


# ── Action handlers ───────────────────────────────────────────────────────────

def _ack(code: str, feedback) -> None:
    case_store.acknowledge(code)
    feedback.set_content('<span style="color:#2E7D32;">✅ Case acknowledged — status set to Triaged.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _assign(code: str, officer_sel: str, current_officer: str, feedback) -> None:
    if officer_sel == "— select —":
        feedback.set_content('<span style="color:#c0392b;">⚠️ Please select an officer.</span>')
        return
    case_store.assign_case(code, officer_sel)
    case_store.add_note(code, f"Assigned to {officer_sel}", current_officer)
    feedback.set_content(f'<span style="color:#2E7D32;">✅ Assigned to {_html.escape(officer_sel)}.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _set_status(code: str, status: str, feedback) -> None:
    case_store.update_status(code, status)
    label = STATUS_LABELS.get(status, status)
    feedback.set_content(f'<span style="color:#2E7D32;">✅ Status updated to {_html.escape(label)}.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _close(code: str, reason: str, officer: str, feedback) -> None:
    case_store.update_status(code, reason)
    case_store.add_note(code, f"Case closed: {reason}", officer)
    feedback.set_content(f'<span style="color:#2E7D32;">✅ Case closed.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _add_note(code: str, note_input, notes_area, officer: str) -> None:
    text = (note_input.value or "").strip()
    if not text:
        return
    case_store.add_note(code, text, officer)
    note_input.value = ""
    # Refresh the notes in-place
    notes_area.clear()
    fresh = case_store.get_case(code)
    if fresh:
        with notes_area:
            _render_notes(fresh.notes)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _render_notes(notes: list) -> None:
    if not notes:
        ui.html('<p style="color:#a0aec0;font-size:0.82rem;font-style:italic;">No notes yet.</p>')
        return
    for note in reversed(notes):
        ui.html(
            f'<div style="background:#f7fafa;border-radius:8px;padding:10px 12px;">'
            f'  <div style="font-size:0.78rem;color:#718096;margin-bottom:4px;">'
            f'    <strong>{_html.escape(note.officer)}</strong> · '
            f'    {note.timestamp.strftime("%d %b %H:%M")}'
            f'  </div>'
            f'  <div style="font-size:0.88rem;color:#1a1a2e;">{_html.escape(note.text)}</div>'
            f'</div>'
        )


def _dl_row(label: str, value: str) -> None:
    ui.html(
        f'<div style="display:flex;gap:8px;margin-bottom:8px;align-items:flex-start;">'
        f'  <span style="font-weight:600;color:#003F40;min-width:120px;flex-shrink:0;'
        f'               font-size:0.83rem;">{_html.escape(label)}</span>'
        f'  <span style="color:#1a1a2e;font-size:0.83rem;line-height:1.4;">{_html.escape(str(value))}</span>'
        f'</div>'
    )


def _card_style() -> str:
    return (
        "background:white;border-radius:14px;padding:20px;"
        "box-shadow:0 2px 12px rgba(0,100,99,0.08);width:100%;"
    )


def _topbar() -> None:
    officer = app.storage.user.get("officer", "Officer")
    with ui.row().style(
        "background:#003F40;padding:10px 20px;width:100%;align-items:center;"
        "gap:12px;box-shadow:0 2px 8px rgba(0,0,0,0.3);position:sticky;top:0;z-index:100;"
    ):
        ui.html(
            '<a href="/officer/dashboard" style="color:#FFC619;font-weight:800;'
            'font-size:1.1rem;letter-spacing:2px;text-decoration:none;">HABARI</a>'
        )
        ui.html('<span style="color:#a0d8d8;font-size:0.85rem;font-weight:600;">· Officer Portal</span>')
        ui.element("div").style("flex:1;")
        ui.html(f'<span style="color:#a0d8d8;font-size:0.82rem;">👤 {_html.escape(officer)}</span>')
        ui.button(
            "← Dashboard",
            on_click=lambda: ui.navigate.to("/officer/dashboard"),
        ).props("flat no-caps").style("color:#FFC619;font-size:0.82rem;font-weight:700;")
        ui.button(
            "Sign Out",
            on_click=_sign_out,
        ).props("flat no-caps").style(
            "color:white;background:#c0392b;border-radius:6px;"
            "font-size:0.8rem;font-weight:700;padding:4px 12px;min-height:30px;"
        )


def _sign_out() -> None:
    app.storage.user.pop("officer", None)
    app.storage.user.pop("officer_pin", None)
    ui.navigate.to("/officer/login")
