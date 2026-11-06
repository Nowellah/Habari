"""
Officer Case Detail — mirrors main branch dashboard/officer_case.html exactly.
Design tokens and layout come from api/templates/base.html on the main branch.
"""
import html as _h
import os
from nicegui import ui, app
from services.case_store import case_store
from models.case import PICKS, STATUS_LABELS, CaseStatus

_CSS = """\
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{
  --bg:#f9f8f5;--bg2:#ffffff;--fg:#1a1d21;--muted:#596170;--line:#e8e5dc;
  --accent:#1e7a5c;--accent-l:#e8f5f0;--accent-d:#155f47;--warm:#fdf6ec;
  --s4:#c0251a;--s4-l:#fee2e2;--s3:#c2410c;--s3-l:#ffedd5;
  --s2:#92600a;--s2-l:#fef3c7;--s1:#4b5563;--s1-l:#f3f4f6;
  --radius:14px;--shadow:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.05);
}
@media(prefers-color-scheme:dark){
  :root{--bg:#13151a;--bg2:#1c1f26;--fg:#e8e6e1;--muted:#9ca3af;--line:#282d35;
    --accent:#3aaa80;--accent-l:#0d2e22;--accent-d:#50c998;--warm:#1e1c18;
    --s4:#f87171;--s4-l:#2d1515;--s3:#fb923c;--s3-l:#2d1a0d;
    --s2:#facc15;--s2-l:#2a230a;--s1:#9ca3af;--s1-l:#1f2128;}
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,sans-serif;}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
main{max-width:980px;margin:0 auto;padding:24px 16px 48px;}
h1{font-size:1.45rem;font-weight:700;letter-spacing:-.01em;margin-bottom:16px;}
h2{font-size:1.05rem;font-weight:600;margin-bottom:10px;}
p{margin-bottom:8px;}
.muted{color:var(--muted);font-size:.9rem;}
.small{font-size:.82rem;}
.card{background:var(--bg2);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;box-shadow:var(--shadow);}
.card+.card{margin-top:14px;}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
  gap:14px;margin-bottom:14px;}
dl{display:grid;grid-template-columns:max-content 1fr;gap:5px 14px;}
dt{color:var(--muted);font-size:.85rem;}
dd{font-size:.9rem;}
.card form{display:flex;flex-wrap:wrap;gap:6px;align-items:end;margin:8px 0;}
select,input[type=text],input[type=password],textarea{
  font:inherit;padding:7px 11px;border:1px solid var(--line);
  border-radius:8px;background:var(--bg);color:var(--fg);}
select:focus,input:focus,textarea:focus{outline:2px solid var(--accent);border-color:transparent;}
button,.btn{font:inherit;padding:7px 16px;border-radius:8px;border:none;
  background:var(--accent);color:#fff;font-weight:600;cursor:pointer;transition:background .15s;}
button:hover,.btn:hover{background:var(--accent-d);}
button.secondary{background:transparent;border:1.5px solid var(--accent);color:var(--accent);}
button.secondary:hover{background:var(--accent-l);}
button.danger{background:var(--s4);}
button.danger:hover{background:#9a1a10;}
.sev{display:inline-block;font-weight:700;font-size:.82rem;padding:2px 8px;border-radius:999px;}
.sev-4{color:var(--s4);background:var(--s4-l);}
.sev-3{color:var(--s3);background:var(--s3-l);}
.sev-2{color:var(--s2);background:var(--s2-l);}
.sev-1{color:var(--s1);background:var(--s1-l);}
.topbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 16px;
  background:var(--bg2);border-bottom:1px solid var(--line);font-size:.88rem;
  position:sticky;top:0;z-index:100;}
.topbar .brand{font-weight:800;color:var(--accent);font-size:1.05rem;letter-spacing:-.02em;}
.topbar a{color:var(--muted);}
.topbar a:hover{color:var(--accent);text-decoration:none;}
.topbar .spacer{flex:1;}
details summary{cursor:pointer;color:var(--muted);font-size:.9rem;padding:6px 0;}
details[open] summary{color:var(--accent);}
.note-item{background:var(--warm);border-radius:8px;padding:10px 12px;margin-bottom:8px;font-size:.88rem;}
.feedback{font-size:.85rem;margin:6px 0;}
</style>"""

_OPEN_STATUSES = [
    ("triaged",     "Triaged"),
    ("assigned",    "Assigned"),
    ("in_progress", "In Progress"),
    ("referred",    "Referred"),
    ("resolved",    "Resolved"),
]
_CLOSE_REASONS = [
    ("closed",             "Resolved and closed"),
    ("closed_unfounded",   "Closed: unfounded"),
    ("closed_child_stop",  "Closed: child asked to stop"),
]
_OFFICERS = ["admin", "officer", "super"]


def _require_officer() -> bool:
    if not app.storage.user.get("officer"):
        ui.navigate.to("/officer/login")
        return False
    return True


def show(code: str) -> None:
    if not _require_officer():
        return

    ui.add_head_html(_CSS)
    officer = app.storage.user.get("officer", "Admin")
    case = case_store.get_case(code)

    _topbar(officer)

    ui.html('<main>')
    ui.html('<p><a href="/officer/dashboard">← Case queue</a></p>')

    if case is None:
        ui.html(
            f'<div class="card" style="border-color:var(--s4);">'
            f'<p style="color:var(--s4);font-weight:600;">'
            f'Case <code>{_h.escape(code.upper())}</code> not found.</p>'
            f'</div>'
        )
        ui.html("</main>")
        return

    pick_info = PICKS.get(case.pick, {})
    status_label = case.status_label

    # ── Title ─────────────────────────────────────────────────────────────────
    urgent_badge = (
        '<span style="background:var(--s4-l);color:var(--s4);border-radius:6px;'
        'padding:2px 8px;font-size:.82rem;font-weight:700;">🚨 urgent</span>'
        if case.is_urgent else ""
    )
    ui.html(
        f'<h1 style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
        f'{_h.escape(case.case_code)} '
        f'<span class="sev sev-{case.severity}">severity {case.severity}</span>'
        f'{urgent_badge}'
        f'</h1>'
    )

    # ── grid2: Case details + Actions ─────────────────────────────────────────
    ui.html('<div class="grid2">')

    # Left: case details (mirrors the Django dl block)
    ui.html(f"""
    <div class="card">
      <h2>Case</h2>
      <dl>
        <dt>Status</dt>      <dd>{_h.escape(status_label)}</dd>
        <dt>Child's pick</dt><dd>{_h.escape(pick_info.get("label_en","—"))}</dd>
        <dt>Category</dt>    <dd>{_h.escape(case.harm_category)}</dd>
        <dt>Language</dt>    <dd>{_h.escape(case.language.upper())}</dd>
        <dt>Age bracket</dt> <dd>{_h.escape(case.age_display)}</dd>
        <dt>Flags</dt>       <dd>{_h.escape(", ".join(case.flags) or "—")}</dd>
        <dt>Triage source</dt><dd>{_h.escape(case.triage_source)}</dd>
        <dt>Received</dt>    <dd>{_h.escape(case.submitted_display)}</dd>
        <dt>Officer</dt>     <dd>{_h.escape(case.assigned_to or "not assigned")}</dd>
      </dl>
    </div>""")

    # Right: actions (mirrors the Django actions card)
    # We use NiceGUI widgets here so handlers are live
    with ui.element("div").classes("card"):
        ui.html("<h2>Actions</h2>")

        fb = ui.html("").classes("feedback")

        # Acknowledge
        if case.status == "received":
            ui.button(
                "Acknowledge",
                on_click=lambda: _ack(code, fb),
            )
        else:
            ui.html(f'<p class="muted">Status: {_h.escape(status_label)}</p>')

        ui.html("<br>")

        # Assign
        ui.html('<label style="font-size:.85rem;color:var(--muted);">Assign to officer</label>')
        assign_sel = ui.select(
            options=["— select —"] + _OFFICERS,
            value=case.assigned_to or "— select —",
        ).props("dense outlined").style("width:100%;margin:6px 0 4px;")
        ui.button(
            "Assign",
            on_click=lambda: _assign(code, assign_sel.value, officer, fb),
        ).style("margin-bottom:10px;")

        # Set status
        ui.html('<label style="font-size:.85rem;color:var(--muted);">Set status</label>')
        status_sel = ui.select(
            options={k: v for k, v in _OPEN_STATUSES},
            value=case.status if case.status in dict(_OPEN_STATUSES) else "triaged",
        ).props("dense outlined").style("width:100%;margin:6px 0 4px;")
        ui.button(
            "Set status",
            on_click=lambda: _set_status(code, status_sel.value, fb),
        ).style("margin-bottom:10px;")

        # Close
        if case.is_open:
            ui.html('<label style="font-size:.85rem;color:var(--muted);">Close case</label>')
            close_sel = ui.select(
                options={k: v for k, v in _CLOSE_REASONS},
                value="closed",
            ).props("dense outlined").style("width:100%;margin:6px 0 4px;")
            note_inp = ui.input(placeholder="Short note (optional)").props(
                "dense outlined"
            ).style("width:100%;margin-bottom:4px;")
            ui.button(
                "Close case",
                on_click=lambda: _close(code, close_sel.value, note_inp.value, officer, fb),
            ).classes("danger")

    ui.html("</div>")  # end grid2

    # ── Summary ───────────────────────────────────────────────────────────────
    with ui.element("div").classes("card"):
        ui.html("<h2>Summary</h2>")
        if case.summary:
            ui.html(
                f'<p style="white-space:pre-line;">{_h.escape(case.summary)}</p>'
                '<p class="muted">Built only from the child\'s own sentences.</p>'
            )
        else:
            ui.html("<p class=\"muted\">No summary yet.</p>")
        # Description
        ui.html(
            f'<blockquote style="border-left:4px solid var(--accent);margin:12px 0 0;'
            f'padding:8px 14px;background:var(--warm);border-radius:4px 10px 10px 4px;">'
            f'<p style="font-style:italic;">{_h.escape(case.description)}</p>'
            f'</blockquote>'
        )

    # ── Officer notes ─────────────────────────────────────────────────────────
    with ui.element("div").classes("card"):
        ui.html("<h2>Officer notes</h2>")

        notes_col = ui.column().style("width:100%;gap:6px;margin-bottom:10px;")
        with notes_col:
            _render_notes(case.notes)

        note_inp2 = ui.textarea(placeholder="Add a note…").props(
            "outlined dense rows=2"
        ).style("width:100%;")
        ui.button(
            "Add note",
            on_click=lambda: _add_note(code, note_inp2, notes_col, officer),
        ).style("margin-top:6px;")

    # ── Messages ──────────────────────────────────────────────────────────────
    if case.messages:
        with ui.element("div").classes("card"):
            with ui.element("details"):
                ui.html(
                    f"<summary>Messages ({len(case.messages)}). "
                    "Open only if you need to read the child's words.</summary>"
                )
                for msg in case.messages:
                    role  = msg.get("role", "bot")
                    text  = _h.escape(msg.get("text", ""))
                    label = "Child" if role == "child" else "Habari"
                    align = "right" if role == "child" else "left"
                    ui.html(
                        f'<p style="text-align:{align};margin:6px 0;">'
                        f'<strong>{label}</strong><br>'
                        f'<span style="background:{"#FFC619" if role=="child" else "var(--warm)"};'
                        f'border-radius:10px;padding:6px 12px;display:inline-block;'
                        f'max-width:80%;font-size:.9rem;">{text}</span></p>'
                    )

    ui.html("</main>")


# ── Action handlers ───────────────────────────────────────────────────────────

def _ack(code: str, fb) -> None:
    case_store.acknowledge(code)
    fb.set_content('<span style="color:var(--accent);">✓ Acknowledged — status set to Triaged.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _assign(code: str, sel: str, officer: str, fb) -> None:
    if sel == "— select —":
        fb.set_content('<span style="color:var(--s4);">⚠ Select an officer first.</span>')
        return
    case_store.assign_case(code, sel)
    case_store.add_note(code, f"Assigned to {sel}", officer)
    fb.set_content(f'<span style="color:var(--accent);">✓ Assigned to {_h.escape(sel)}.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _set_status(code: str, status: str, fb) -> None:
    case_store.update_status(code, status)
    label = STATUS_LABELS.get(status, status)
    fb.set_content(
        f'<span style="color:var(--accent);">✓ Status → {_h.escape(label)}.</span>'
    )
    ui.navigate.to(f"/officer/case/{code}")


def _close(code: str, reason: str, note: str, officer: str, fb) -> None:
    case_store.update_status(code, reason)
    note_text = f"Closed ({reason})"
    if note.strip():
        note_text += f": {note.strip()[:150]}"
    case_store.add_note(code, note_text, officer)
    fb.set_content('<span style="color:var(--accent);">✓ Case closed.</span>')
    ui.navigate.to(f"/officer/case/{code}")


def _add_note(code: str, inp, col, officer: str) -> None:
    text = (inp.value or "").strip()
    if not text:
        return
    case_store.add_note(code, text, officer)
    inp.value = ""
    fresh = case_store.get_case(code)
    col.clear()
    with col:
        _render_notes(fresh.notes if fresh else [])


def _render_notes(notes: list) -> None:
    if not notes:
        ui.html('<p class="muted">No notes yet.</p>')
        return
    for note in reversed(notes):
        ui.html(
            f'<div class="note-item">'
            f'<span class="muted small">{_h.escape(note.officer)} · '
            f'{note.timestamp.strftime("%d %b %H:%M")}</span><br>'
            f'{_h.escape(note.text)}'
            f'</div>'
        )


def _topbar(officer: str) -> None:
    ui.html(f"""
    <nav class="topbar">
      <span class="brand">🤝 Habari</span>
      <a href="/officer/dashboard">Queue</a>
      <span class="spacer"></span>
      <span class="muted small">👤 {_h.escape(officer)}</span>
      <a href="/" style="font-size:.82rem;">← Child UI</a>
      <a href="/officer/login" style="font-size:.82rem;color:var(--s4);">Sign out</a>
    </nav>""")
