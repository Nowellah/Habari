"""
Officer login — uses the main branch base.html design tokens.
Credentials:  username: admin   password: admin
              username: officer  password: officer
              username: super    password: super
In production replace with Django session auth / JWT.
"""
import os
from nicegui import ui, app

# ── CSS ported exactly from main branch base.html ────────────────────────────
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
.card{background:var(--bg2);border:1px solid var(--line);border-radius:var(--radius);
      padding:28px 24px;box-shadow:var(--shadow);}
select,input[type=text],input[type=password]{
  font:inherit;padding:8px 12px;border:1px solid var(--line);border-radius:8px;
  background:var(--bg);color:var(--fg);width:100%;margin-bottom:14px;}
select:focus,input:focus{outline:2px solid var(--accent);border-color:transparent;}
button{font:inherit;padding:9px 18px;border-radius:8px;border:none;
  background:var(--accent);color:#fff;font-weight:600;cursor:pointer;width:100%;
  transition:background .15s;}
button:hover{background:var(--accent-d);}
.err{color:var(--s4);font-size:.85rem;margin-bottom:10px;}
.brand{font-weight:800;color:var(--accent);font-size:1.2rem;letter-spacing:-.02em;}
.hint{color:var(--muted);font-size:.78rem;text-align:center;margin-top:14px;}
</style>"""

# Credentials: {username: display_name}
_USERS = {
    "admin":   "Admin",
    "officer": "Officer",
    "super":   "Supervisor",
}
_PASSWORDS = {
    "admin":   "admin",
    "officer": "officer",
    "super":   "super",
}


def show() -> None:
    ui.add_head_html(_CSS)

    with ui.column().style(
        "max-width:400px;margin:80px auto 0;padding:0 16px;width:100%;"
    ):
        # Brand
        with ui.row().style("align-items:center;gap:10px;justify-content:center;margin-bottom:24px;"):
            ui.html('<span class="brand">🤝 Habari</span>')
            ui.html('<span style="color:var(--muted);font-size:.9rem;font-weight:600;">Officer Portal</span>')

        with ui.element("div").classes("card"):
            ui.html('<h2 style="font-size:1.1rem;font-weight:700;margin-bottom:18px;">Sign in</h2>')

            username_input = ui.input(placeholder="Username").props("outlined dense").style(
                "width:100%;margin-bottom:12px;"
            )
            password_input = ui.input(placeholder="Password", password=True).props(
                "outlined dense"
            ).style("width:100%;margin-bottom:6px;")

            err = ui.html("").style("color:var(--s4);font-size:.85rem;margin-bottom:10px;")

            def do_login():
                u = (username_input.value or "").strip().lower()
                p = (password_input.value or "").strip()
                if _PASSWORDS.get(u) == p:
                    app.storage.user["officer"] = _USERS[u]
                    app.storage.user["officer_role"] = u
                    ui.navigate.to("/officer/dashboard")
                else:
                    err.set_content("⚠️ Incorrect username or password.")

            password_input.on("keydown.enter", do_login)

            ui.button("Sign in →", on_click=do_login).style("margin-top:4px;")

        ui.html(
            '<p class="hint" style="color:var(--muted);font-size:.78rem;'
            'text-align:center;margin-top:14px;">DEMO — admin/admin · officer/officer · super/super</p>'
        )

        ui.button(
            "← Back to Habari",
            on_click=lambda: ui.navigate.to("/"),
        ).style(
            "background:transparent;border:1.5px solid var(--accent);color:var(--accent);"
            "width:100%;border-radius:8px;padding:8px;margin-top:12px;font-weight:600;"
        )
