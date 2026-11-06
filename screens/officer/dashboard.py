"""
Officer Dashboard — mirrors main branch officer_list.html and base.html exactly.

Design tokens, topbar, severity badges, stat strip, and case table
are all ported from api/templates/base.html + dashboard/officer_list.html
on the main branch.
"""
import html as _h
import os
from nicegui import ui, app
from services.case_store import case_store
from models.case import PICKS, SEVERITY_META, STATUS_LABELS

# ── CSS — exact port of main branch base.html + officer_list styles ──────────
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
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}
table{width:100%;border-collapse:collapse;font-size:.9rem;}
th{text-align:left;padding:8px 12px;color:var(--muted);font-weight:600;font-size:.8rem;
  text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid var(--line);}
td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:var(--warm);}
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
button,.btn{font:inherit;padding:7px 16px;border-radius:8px;border:none;
  background:var(--accent);color:#fff;font-weight:600;cursor:pointer;transition:background .15s;}
button:hover,.btn:hover{background:var(--accent-d);}
button.secondary{background:transparent;border:1.5px solid var(--accent);color:var(--accent);}
button.secondary:hover{background:var(--accent-l);}
/* Officer list extras */
.page-head{display:flex;align-items:baseline;justify-content:space-between;
  flex-wrap:wrap;gap:8px;margin-bottom:20px;}
.page-head h1{margin:0;}
.stat-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;}
.stat{background:var(--bg2);border:1px solid var(--line);border-radius:10px;
  padding:12px 18px;min-width:110px;}
.stat .n{font-size:1.6rem;font-weight:800;line-height:1;}
.stat .l{font-size:.78rem;color:var(--muted);margin-top:2px;}
.stat.red .n{color:var(--s4);}
.stat.amber .n{color:var(--s2);}
.stat.green .n{color:var(--accent);}
.alert-card{background:var(--s4-l);border:1px solid var(--s4);border-radius:10px;
  padding:14px 18px;margin-bottom:16px;}
.alert-card strong{color:var(--s4);}
td.code a{font-weight:700;color:var(--accent);font-family:monospace;letter-spacing:.03em;}
td.code a:hover{text-decoration:underline;}
tr.urgent td{background:#fff9f9;}
tr.urgent:hover td{background:#fff0f0;}
/* Severity matrix bars */
.bar-row{margin-bottom:10px;}
.bar-label{display:flex;justify-content:space-between;font-size:.82rem;margin-bottom:3px;}
.bar-track{background:var(--line);border-radius:99px;height:9px;overflow:hidden;}
.bar-fill{height:100%;border-radius:99px;transition:width .4s;}
/* Category chart */
.cat-row{margin-bottom:8px;}
</style>"""


def _require_officer() -> bool:
    if not app.storage.user.get("officer"):
        ui.navigate.to("/officer/login")
        return False
    return True


def show() -> None:
    if not _require_officer():
        return

    ui.add_head_html(_CSS)
    officer = app.storage.user.get("officer", "Admin")
    is_demo = bool(os.getenv("DEMO_MODE", "").strip())

    _topbar(officer)

    ui.html(f"""
    <main>
      <div class="page-head">
        <h1>Case queue</h1>
        <span class="muted small">Most urgent first · no reporter identities shown</span>
      </div>
    """)

    if is_demo:
        ui.html(
            '<div class="alert-card" style="background:var(--s2-l);border-color:var(--s2);">'
            '<strong style="color:var(--s2);">⚠ DEMO MODE</strong> — '
            'All cases and data are simulated.'
            '</div>'
        )

    m = case_store.metrics()
    cases = case_store.all_cases()

    # ── Stat strip ────────────────────────────────────────────────────────────
    urgent_count = sum(1 for c in cases if c.severity == 4 and c.is_open)
    open_count   = sum(1 for c in cases if c.is_open)
    total        = len(cases)

    ui.html(f"""
    <div class="stat-row">
      <div class="stat {'green' if total else ''}">
        <div class="n">{total}</div><div class="l">Total cases</div>
      </div>
      <div class="stat {'green' if open_count else ''}">
        <div class="n">{open_count}</div><div class="l">Open</div>
      </div>
      <div class="stat {'red' if urgent_count else ''}">
        <div class="n">{urgent_count}</div><div class="l">Critical (sev 4)</div>
      </div>
      <div class="stat {'amber' if m['by_severity'].get(3,0) else ''}">
        <div class="n">{m['by_severity'].get(3,0)}</div><div class="l">High (sev 3)</div>
      </div>
      <div class="stat">
        <div class="n">{m['by_severity'].get(2,0)}</div><div class="l">Medium (sev 2)</div>
      </div>
      <div class="stat">
        <div class="n">{m['by_severity'].get(1,0)}</div><div class="l">Low (sev 1)</div>
      </div>
    </div>
    """)

    # ── Severity matrix + category breakdown side by side ────────────────────
    with ui.row().style("gap:14px;flex-wrap:wrap;margin-bottom:20px;"):
        # Severity matrix
        with ui.element("div").style(
            "flex:1;min-width:240px;background:var(--bg2);border:1px solid var(--line);"
            "border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);"
        ):
            ui.html('<h2>Severity matrix</h2>')
            total_s = max(total, 1)
            for sev, label, css in [
                (4, "Critical", "var(--s4)"),
                (3, "High",     "var(--s3)"),
                (2, "Medium",   "var(--s2)"),
                (1, "Low",      "var(--s1)"),
            ]:
                n   = m["by_severity"].get(sev, 0)
                pct = round(n / total_s * 100)
                ui.html(f"""
                <div class="bar-row">
                  <div class="bar-label">
                    <span class="sev sev-{sev}">{label}</span>
                    <span class="muted">{n} &nbsp;({pct}%)</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%;background:{css};"></div>
                  </div>
                </div>""")

        # Category breakdown
        with ui.element("div").style(
            "flex:1;min-width:240px;background:var(--bg2);border:1px solid var(--line);"
            "border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);"
        ):
            ui.html('<h2>Cases by category</h2>')
            colours = ["var(--s4)","var(--s3)","var(--s3)","var(--s2)","var(--s1)"]
            for idx, (pid, p) in enumerate(PICKS.items()):
                label = p["short_en"]
                n   = m["by_pick"].get(label, 0)
                pct = round(n / max(total, 1) * 100)
                ui.html(f"""
                <div class="cat-row">
                  <div class="bar-label">
                    <span style="font-size:.82rem;font-weight:600;">{_h.escape(label)}</span>
                    <span class="muted">{n}</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%;background:{colours[idx]};"></div>
                  </div>
                </div>""")

    # ── Status breakdown ──────────────────────────────────────────────────────
    with ui.element("div").style(
        "background:var(--bg2);border:1px solid var(--line);border-radius:var(--radius);"
        "padding:18px;box-shadow:var(--shadow);margin-bottom:20px;"
    ):
        ui.html('<h2>Status breakdown</h2>')
        with ui.row().style("gap:8px;flex-wrap:wrap;"):
            for status, count in sorted(m["by_status"].items(), key=lambda x: -x[1]):
                label = STATUS_LABELS.get(status, status.replace("_"," ").title())
                ui.html(f"""
                <div style="background:var(--bg);border:1px solid var(--line);border-radius:10px;
                     padding:10px 16px;min-width:120px;text-align:center;">
                  <div style="font-size:1.5rem;font-weight:800;">{count}</div>
                  <div class="small muted">{_h.escape(label)}</div>
                </div>""")

    # ── Case table ────────────────────────────────────────────────────────────
    with ui.element("div").classes("card"):
        ui.html('<h2>Cases</h2>')
        if not cases:
            ui.html('<p class="muted" style="text-align:center;padding:24px 0;">No cases yet.</p>')
        else:
            rows_html = ""
            for c in cases:
                urgent_cls = "urgent" if c.severity == 4 and c.is_open else ""
                flags = ", ".join(c.flags) if c.flags else "—"
                sev_badge = f'<span class="sev sev-{c.severity}">{c.severity}</span>'
                status_lbl = _h.escape(c.status_label)
                officer_lbl = _h.escape(c.assigned_to or "—")
                age_lbl = _h.escape(c.age_display)
                pick_lbl = _h.escape(c.pick_label)
                received = c.submitted_display
                rows_html += f"""
                <tr class="{urgent_cls}" style="cursor:pointer"
                    onclick="location.href='/officer/case/{c.case_code}'">
                  <td class="code">
                    <a href="/officer/case/{c.case_code}">{_h.escape(c.case_code)}</a>
                  </td>
                  <td>{sev_badge}</td>
                  <td>{pick_lbl}</td>
                  <td>{status_lbl}</td>
                  <td>{officer_lbl}</td>
                  <td class="muted small">{age_lbl}</td>
                  <td class="muted small">{_h.escape(flags)}</td>
                  <td class="muted small">{_h.escape(received)}</td>
                </tr>"""

            ui.html(f"""
            <div class="wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th><th>Severity</th><th>Category</th>
                  <th>Status</th><th>Officer</th><th>Age</th>
                  <th>Flags</th><th>Received</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            </div>""")

    ui.html("</main>")


def _topbar(officer: str) -> None:
    ui.html(f"""
    <nav class="topbar">
      <span class="brand">🤝 Habari</span>
      <a href="/officer/dashboard">Queue</a>
      <span class="spacer"></span>
      <span class="muted small">👤 {_h.escape(officer)}</span>
      <a href="/" style="font-size:.82rem;">← Child UI</a>
      <a href="/officer/login" onclick="event.preventDefault();
         fetch('/officer/logout',{{method:'POST'}}).finally(()=>location.href='/officer/login')"
         style="font-size:.82rem;color:var(--s4);">Sign out</a>
    </nav>""")
