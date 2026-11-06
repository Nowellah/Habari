"""
Officer Dashboard — main view.

Sections:
  1. Header + officer identity + sign-out
  2. Summary metric cards (total, open, urgent, critical)
  3. Severity matrix (bar chart via HTML/CSS)
  4. Cases by category (horizontal bars)
  5. Status breakdown table
  6. Full case queue — sorted by severity desc, then age asc
     Filters: All | Open | Critical | Unassigned
"""
import os
import html as _html
from nicegui import ui, app
from services.case_store import case_store
from models.case import SEVERITY_META, STATUS_LABELS, PICKS


# ── Auth guard ────────────────────────────────────────────────────────────────

def _require_officer():
    if not app.storage.user.get("officer"):
        ui.navigate.to("/officer/login")
        return False
    return True


# ── Page ─────────────────────────────────────────────────────────────────────

def show() -> None:
    if not _require_officer():
        return

    officer = app.storage.user.get("officer", "Officer")
    is_demo = bool(os.getenv("DEMO_MODE", "").strip())

    _officer_topbar(officer, is_demo)

    with ui.column().style(
        "max-width: 1100px; margin: 0 auto; padding: 20px 16px 48px; width: 100%;"
    ):
        # Page title
        ui.html(
            '<h1 style="font-size:1.4rem;font-weight:800;color:#003F40;margin:0 0 4px;">'
            '🛡️ Officer Dashboard</h1>'
        )
        ui.html(
            f'<p style="color:#718096;font-size:0.88rem;margin:0 0 20px;">'
            f'Most urgent first. No child identities are shown. '
            f'Logged in as <strong>{_html.escape(officer)}</strong>.</p>'
        )

        if is_demo:
            ui.html(
                '<div style="background:#fff3cd;border:2px solid #FFC619;border-radius:10px;'
                'padding:10px 16px;margin-bottom:16px;font-weight:600;color:#7a5c00;'
                'font-size:0.88rem;">⚠️ DEMO MODE — All cases and data are simulated.</div>'
            )

        # Pull fresh metrics
        m = case_store.metrics()

        # ── 1. Summary cards ─────────────────────────────────────────────────
        _summary_cards(m)

        # ── 2. Severity matrix + category breakdown ───────────────────────────
        with ui.row().style("gap:16px;flex-wrap:wrap;width:100%;margin-bottom:20px;"):
            with ui.element("div").style(
                "flex:1;min-width:260px;background:white;border-radius:14px;"
                "padding:20px;box-shadow:0 2px 12px rgba(0,100,99,0.08);"
            ):
                _severity_matrix(m["by_severity"], m["total"])

            with ui.element("div").style(
                "flex:1;min-width:260px;background:white;border-radius:14px;"
                "padding:20px;box-shadow:0 2px 12px rgba(0,100,99,0.08);"
            ):
                _category_chart(m["by_pick"], m["total"])

        # ── 3. Status breakdown ───────────────────────────────────────────────
        with ui.element("div").style(
            "background:white;border-radius:14px;padding:20px;"
            "box-shadow:0 2px 12px rgba(0,100,99,0.08);margin-bottom:20px;"
        ):
            _status_breakdown(m["by_status"])

        # ── 4. Case queue ─────────────────────────────────────────────────────
        _case_queue()


# ── Summary cards ─────────────────────────────────────────────────────────────

def _summary_cards(m: dict) -> None:
    cards = [
        {"label": "Total Cases",    "value": m["total"],  "bg": "#e8f4f4", "fg": "#006463", "icon": "📋"},
        {"label": "Open",           "value": m["open"],   "bg": "#e8f4f4", "fg": "#006463", "icon": "🔓"},
        {"label": "Urgent",         "value": m["urgent"], "bg": "#fdecea", "fg": "#B3261E", "icon": "🚨"},
        {"label": "Critical (sev 4)","value": m["by_severity"].get(4, 0), "bg": "#fdecea", "fg": "#B3261E", "icon": "⚠️"},
        {"label": "High (sev 3)",    "value": m["by_severity"].get(3, 0), "bg": "#fff3e0", "fg": "#E65100", "icon": "🔶"},
        {"label": "Medium (sev 2)",  "value": m["by_severity"].get(2, 0), "bg": "#fff8e1", "fg": "#F57C00", "icon": "🔸"},
        {"label": "Low (sev 1)",     "value": m["by_severity"].get(1, 0), "bg": "#e8f5e9", "fg": "#2E7D32", "icon": "🟢"},
    ]
    with ui.row().style("gap:12px;flex-wrap:wrap;width:100%;margin-bottom:20px;"):
        for c in cards:
            ui.html(
                f'<div style="flex:1;min-width:120px;background:{c["bg"]};'
                f'border-radius:12px;padding:16px 14px;text-align:center;'
                f'box-shadow:0 1px 6px rgba(0,0,0,0.06);">'
                f'  <div style="font-size:1.6rem;">{c["icon"]}</div>'
                f'  <div style="font-size:1.8rem;font-weight:800;color:{c["fg"]};">{c["value"]}</div>'
                f'  <div style="font-size:0.75rem;color:#4a5568;font-weight:600;margin-top:2px;">{c["label"]}</div>'
                f'</div>'
            )


# ── Severity matrix ───────────────────────────────────────────────────────────

def _severity_matrix(by_severity: dict, total: int) -> None:
    ui.html('<h3 style="font-size:1rem;font-weight:700;color:#003F40;margin:0 0 14px;">Severity Matrix</h3>')
    total_safe = max(total, 1)
    rows = [
        (4, "Critical"),
        (3, "High"),
        (2, "Medium"),
        (1, "Low"),
    ]
    for sev, label in rows:
        count = by_severity.get(sev, 0)
        pct = round(count / total_safe * 100)
        meta = SEVERITY_META[sev]
        ui.html(
            f'<div style="margin-bottom:10px;">'
            f'  <div style="display:flex;justify-content:space-between;'
            f'       align-items:center;margin-bottom:4px;">'
            f'    <span style="font-size:0.82rem;font-weight:700;color:{meta["fg"]};">'
            f'      {label}</span>'
            f'    <span style="font-size:0.82rem;color:#4a5568;font-weight:600;">'
            f'      {count} cases ({pct}%)</span>'
            f'  </div>'
            f'  <div style="background:#f0f4f8;border-radius:20px;height:10px;overflow:hidden;">'
            f'    <div style="width:{pct}%;height:100%;background:{meta["fg"]};"'
            f'         transition:"width 0.4s";border-radius:20px;"></div>'
            f'  </div>'
            f'</div>'
        )


# ── Category chart ────────────────────────────────────────────────────────────

def _category_chart(by_pick: dict, total: int) -> None:
    ui.html('<h3 style="font-size:1rem;font-weight:700;color:#003F40;margin:0 0 14px;">Cases by Category</h3>')
    total_safe = max(total, 1)
    colours = ["#B3261E", "#E65100", "#E65100", "#F57C00", "#2E7D32"]
    for idx, (_, p) in enumerate(PICKS.items()):
        label = p["short_en"]
        count = by_pick.get(label, 0)
        pct = round(count / total_safe * 100)
        colour = colours[idx % len(colours)]
        ui.html(
            f'<div style="margin-bottom:10px;">'
            f'  <div style="display:flex;justify-content:space-between;margin-bottom:3px;">'
            f'    <span style="font-size:0.8rem;font-weight:600;color:#003F40;">{label}</span>'
            f'    <span style="font-size:0.8rem;color:#718096;">{count}</span>'
            f'  </div>'
            f'  <div style="background:#f0f4f8;border-radius:20px;height:8px;overflow:hidden;">'
            f'    <div style="width:{pct}%;height:100%;background:{colour};border-radius:20px;"></div>'
            f'  </div>'
            f'</div>'
        )


# ── Status breakdown ──────────────────────────────────────────────────────────

def _status_breakdown(by_status: dict) -> None:
    ui.html('<h3 style="font-size:1rem;font-weight:700;color:#003F40;margin:0 0 14px;">Status Breakdown</h3>')
    status_colours = {
        "received":    ("#e3f2fd", "#1565c0"),
        "triaged":     ("#e8f5e9", "#2E7D32"),
        "assigned":    ("#e8f5e9", "#2E7D32"),
        "referred":    ("#fff3e0", "#E65100"),
        "in_progress": ("#fff3e0", "#E65100"),
        "acknowledged":("#e8f5e9", "#2E7D32"),
        "resolved":    ("#e8f5e9", "#2E7D32"),
        "closed":      ("#f5f5f5", "#424242"),
        "closed_unfounded":  ("#f5f5f5", "#424242"),
        "closed_child_stop": ("#f5f5f5", "#424242"),
        "safety_check":      ("#fff8e1", "#F57C00"),
    }
    with ui.row().style("gap:8px;flex-wrap:wrap;"):
        for status, count in sorted(by_status.items(), key=lambda x: -x[1]):
            label = STATUS_LABELS.get(status, status.replace("_", " ").title())
            bg, fg = status_colours.get(status, ("#f0f4f8", "#4a5568"))
            ui.html(
                f'<div style="background:{bg};border-radius:10px;padding:12px 16px;'
                f'min-width:130px;text-align:center;">'
                f'  <div style="font-size:1.6rem;font-weight:800;color:{fg};">{count}</div>'
                f'  <div style="font-size:0.75rem;color:{fg};font-weight:600;">{label}</div>'
                f'</div>'
            )


# ── Case queue ────────────────────────────────────────────────────────────────

def _case_queue() -> None:
    with ui.element("div").style(
        "background:white;border-radius:14px;padding:20px;"
        "box-shadow:0 2px 12px rgba(0,100,99,0.08);"
    ):
        with ui.row().style("justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px;"):
            ui.html('<h3 style="font-size:1rem;font-weight:700;color:#003F40;margin:0;">Case Queue</h3>')
            with ui.row().style("gap:6px;flex-wrap:wrap;"):
                filter_state = {"active": "all"}
                filter_container = ui.element("div").style("display:contents;")

        cases = case_store.all_cases()
        _render_case_table(cases)


def _render_case_table(cases: list) -> None:
    if not cases:
        ui.html('<p style="color:#718096;font-style:italic;text-align:center;padding:20px 0;">No cases yet.</p>')
        return

    # Table header
    ui.html("""
    <div style="overflow-x:auto;width:100%;">
    <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
    <thead>
      <tr style="border-bottom:2px solid #e2e8f0;">
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Case</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Severity</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Category</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Status</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Officer</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Age</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Flags</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Received</th>
        <th style="text-align:left;padding:8px 10px;color:#003F40;font-weight:700;">Action</th>
      </tr>
    </thead>
    <tbody>
    """)

    for case in cases:
        meta = case.severity_meta
        status_label = case.status_label
        flags_html = " ".join(
            f'<span style="background:#fdecea;color:#B3261E;border-radius:4px;'
            f'padding:1px 6px;font-size:0.7rem;font-weight:700;">{_html.escape(f)}</span>'
            for f in case.flags
        ) if case.flags else '<span style="color:#a0aec0;">—</span>'

        row_bg = "#fff8f8" if case.severity == 4 and case.is_open else "transparent"
        safe_desc = _html.escape(case.description[:60]) + ("…" if len(case.description) > 60 else "")

        ui.html(f"""
        <tr style="border-bottom:1px solid #f0f4f8;background:{row_bg};" title="{safe_desc}">
          <td style="padding:10px 10px;">
            <a href="/officer/case/{case.case_code}"
               style="font-weight:700;color:#006463;text-decoration:none;font-family:monospace;font-size:0.9rem;">
               {case.case_code}</a>
          </td>
          <td style="padding:10px 10px;">
            <span style="background:{meta['bg']};color:{meta['fg']};border-radius:20px;
                  padding:3px 12px;font-weight:700;font-size:0.8rem;white-space:nowrap;">
              {meta['label']}
            </span>
          </td>
          <td style="padding:10px 10px;color:#4a5568;">{_html.escape(case.pick_label)}</td>
          <td style="padding:10px 10px;color:#4a5568;">{_html.escape(status_label)}</td>
          <td style="padding:10px 10px;color:#4a5568;">{_html.escape(case.assigned_to or '—')}</td>
          <td style="padding:10px 10px;color:#4a5568;">{_html.escape(case.age_display)}</td>
          <td style="padding:10px 10px;">{flags_html}</td>
          <td style="padding:10px 10px;color:#718096;white-space:nowrap;">{case.submitted_display}</td>
          <td style="padding:10px 10px;">
            <a href="/officer/case/{case.case_code}"
               style="background:#006463;color:white;border-radius:6px;padding:4px 12px;
                      font-size:0.8rem;font-weight:700;text-decoration:none;white-space:nowrap;">
              View →
            </a>
          </td>
        </tr>
        """)

    ui.html("</tbody></table></div>")


# ── Officer top bar ───────────────────────────────────────────────────────────

def _officer_topbar(officer: str, is_demo: bool) -> None:
    with ui.row().style(
        "background:#003F40;padding:10px 20px;width:100%;align-items:center;"
        "gap:12px;box-shadow:0 2px 8px rgba(0,0,0,0.3);position:sticky;top:0;z-index:100;"
        "flex-wrap:wrap;"
    ):
        ui.html(
            '<span style="color:#FFC619;font-weight:800;font-size:1.1rem;'
            'letter-spacing:2px;cursor:pointer;" onclick="location.href=\'/officer/login\'">HABARI</span>'
        )
        ui.html(
            '<span style="color:#a0d8d8;font-size:0.85rem;font-weight:600;">'
            '· Officer Portal</span>'
        )
        if is_demo:
            ui.html('<span style="background:#FFC619;color:#003F40;font-weight:800;'
                    'font-size:0.7rem;padding:2px 8px;border-radius:20px;">DEMO</span>')
        ui.element("div").style("flex:1;")
        ui.html(
            f'<span style="color:#a0d8d8;font-size:0.82rem;">👤 {_html.escape(officer)}</span>'
        )
        ui.button(
            "← Child UI",
            on_click=lambda: ui.navigate.to("/"),
        ).props("flat no-caps").style(
            "color:#FFC619;font-size:0.82rem;font-weight:700;padding:4px 10px;"
        )
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
