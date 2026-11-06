"""
Officer login screen — PIN-based demo authentication.
In production, replace with Django session auth / JWT.
"""
import os
from nicegui import ui, app
from components.theme import inject_styles

# Demo PIN — change via OFFICER_PIN env var
_DEMO_PIN = os.getenv("OFFICER_PIN", "1234")
_DEMO_OFFICERS = {
    "1234": "Officer Nakato",
    "5678": "Officer Ssemakula",
    "9999": "Supervisor Apio",
}


def show() -> None:
    inject_styles()
    _officer_header()

    with ui.column().style(
        "max-width: 420px; margin: 60px auto 0; padding: 0 16px; "
        "align-items: center; width: 100%;"
    ):
        ui.html(
            '<div style="width:64px;height:64px;background:#006463;border-radius:50%;'
            'display:flex;align-items:center;justify-content:center;'
            'font-size:1.8rem;margin-bottom:16px;">🛡️</div>'
        )
        ui.html(
            '<h2 style="color:#006463;font-size:1.4rem;font-weight:800;'
            'text-align:center;margin:0 0 6px;">Officer Portal</h2>'
        )
        ui.html(
            '<p style="color:#718096;font-size:0.9rem;text-align:center;'
            'margin:0 0 28px;">Authorised safeguarding officers only.</p>'
        )

        with ui.element("div").style(
            "background:white;border-radius:16px;padding:28px 24px;"
            "box-shadow:0 4px 20px rgba(0,100,99,0.12);width:100%;"
        ):
            name_input = (
                ui.input(label="Officer name / ID", placeholder="e.g. Officer Nakato")
                .style("width:100%;margin-bottom:14px;")
                .props("outlined")
            )
            pin_input = (
                ui.input(label="Access PIN", placeholder="••••", password=True)
                .style("width:100%;margin-bottom:6px;")
                .props("outlined")
            )

            error_label = ui.html("").style("color:#c0392b;font-size:0.85rem;margin-bottom:12px;")

            def do_login():
                pin = (pin_input.value or "").strip()
                name = (name_input.value or "").strip()
                officer_name = _DEMO_OFFICERS.get(pin)
                if officer_name is None:
                    error_label.set_content("⚠️ Invalid PIN. Demo PINs: 1234 / 5678 / 9999")
                    return
                # Store officer identity in per-browser storage
                app.storage.user["officer"] = name or officer_name
                app.storage.user["officer_pin"] = pin
                ui.navigate.to("/officer/dashboard")

            pin_input.on("keydown.enter", do_login)

            ui.button("Sign In →", on_click=do_login).style(
                "background:#006463;color:white;border-radius:10px;"
                "font-weight:700;width:100%;padding:13px;font-size:1rem;"
                "margin-top:4px;"
            ).props("no-caps")

        ui.html(
            '<p style="font-size:0.75rem;color:#a0aec0;text-align:center;'
            'margin-top:16px;font-style:italic;">'
            'DEMO MODE — PINs: 1234 · 5678 · 9999'
            '</p>'
        )

        ui.button("← Back to Habari", on_click=lambda: ui.navigate.to("/")).props(
            "flat no-caps"
        ).style("color:#006463;margin-top:12px;font-size:0.85rem;")


def _officer_header() -> None:
    with ui.row().style(
        "background:#003F40;padding:10px 20px;width:100%;"
        "align-items:center;gap:12px;box-shadow:0 2px 8px rgba(0,0,0,0.3);"
    ):
        ui.html(
            '<span style="color:#FFC619;font-weight:800;font-size:1.1rem;'
            'letter-spacing:2px;">HABARI</span>'
        )
        ui.html(
            '<span style="color:#a0d8d8;font-size:0.85rem;font-weight:600;">'
            '· Officer Portal</span>'
        )
